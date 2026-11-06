"""Run reservations, numbered rerun backups and durable acquisition logs."""
from contextlib import contextmanager
from dataclasses import dataclass
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
import uuid

import numpy as np

from . import __version__
from .config import SUBJECTS_ROOT
from .timing import block_timing_rows


def write_json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")


def write_tsv(path,rows,columns):
    with Path(path).open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,columns,delimiter="\t",extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k:("n/a" if row.get(k) is None else row[k]) for k in columns})


def result_day():
    """Experiment computer's local date, matching PTB3's YYMMDD convention."""
    return datetime.now().astimezone().strftime("%y%m%d")


def result_directory(config,root=None,day=None):
    """Default: participant/results/date/run; an explicit root keeps its API."""
    config.validate()
    leaf=f"{config.mode}_run-{config.run:02d}"
    if root is not None:
        return Path(root)/f"sub-{config.subject}"/leaf
    day=day or result_day()
    if len(day)!=6 or not day.isdigit():
        raise ValueError("Result date must be YYMMDD.")
    datetime.strptime(day,"%y%m%d")
    subjects=Path(getattr(config,"_subjects_dir",SUBJECTS_ROOT)).resolve()
    return subjects/config.subject/"results"/day/leaf


EXISTING_POLICIES=("backup","error")


def validate_existing_policy(existing):
    if existing not in EXISTING_POLICIES:
        raise ValueError("existing must be backup or error.")


class AcquisitionInProgressError(RuntimeError):
    """Another process owns the same participant/date/mode/run reservation."""


@contextmanager
def _run_lock(path):
    # Keep the lock file: unlinking a released lock can create two independent
    # lock inodes on POSIX. OS locks are released even after process termination.
    lock=path.parent/("."+path.name+".lock")
    with lock.open("a+b") as stream:
        if stream.seek(0,os.SEEK_END)==0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            raise AcquisitionInProgressError(
                f"Cannot lock acquisition {path}; another process may still be running it. "
                "Wait for that run to finish before retrying.") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name=="nt":
                msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def _backup_run(path):
    # Move only a real acquisition directory within its explicitly chosen
    # parent. Refuse symlinks/junctions, including dangling reparse points.
    info=path.lstat()
    reparse=getattr(info,"st_file_attributes",0)&getattr(stat,"FILE_ATTRIBUTE_REPARSE_POINT",0)
    parent=path.parent.resolve()
    if not stat.S_ISDIR(info.st_mode) or path.is_symlink() or reparse or path.resolve().parent!=parent:
        raise ValueError(f"Existing acquisition must be a real directory, not a file or link: {path}")
    pattern=re.compile(re.escape(path.name)+r"_old-(\d+)$")
    numbers=[int(m.group(1)) for p in path.parent.iterdir() if (m:=pattern.fullmatch(p.name))]
    number=max(numbers,default=0)+1
    backup=path.with_name(f"{path.name}_old-{number:02d}")
    while os.path.lexists(backup):
        number+=1
        backup=path.with_name(f"{path.name}_old-{number:02d}")
    if backup.parent.resolve()!=parent:
        raise ValueError("Backup must remain in the acquisition's parent directory.")
    path.rename(backup)
    return backup


@dataclass(frozen=True)
class RunReservation:
    path: Path
    backup: Path | None
    acquisition_id: str


@contextmanager
def reserve_run(root,config,existing="backup"):
    """Hold the OS lock through preparation, presentation and final log saving.

    A rerun archives the complete previous directory before opening a window.
    No existing file contents are edited. ``error`` cancels on existing results.
    """
    validate_existing_policy(existing)
    path=result_directory(config,root)
    snapshot=config.to_dict()
    for key in ("object_source","object_cache_dir"):
        value=snapshot["stimulus"][key]
        if value:
            snapshot["stimulus"][key]=str(Path(value).resolve())
    path.parent.mkdir(parents=True,exist_ok=True)
    with _run_lock(path):
        backup=None
        if os.path.lexists(path):
            if existing=="error":
                raise FileExistsError(f"Acquisition already exists; cancelled without changes: {path}")
            backup=_backup_run(path)
        try:
            path.mkdir(exist_ok=False)
        except OSError:
            # If creation fails after archiving, restore the original name when
            # free; the previous data remain intact even if restoration fails.
            if backup is not None and not os.path.lexists(path):
                backup.rename(path)
            raise
        acquisition_id=str(uuid.uuid4())
        write_json(path/"config.json",snapshot)
        write_json(path/"acquisition.json",{
            "acquisition_id":acquisition_id,"subject":config.subject,"mode":config.mode,"run":config.run,
            "created_at":datetime.now().astimezone().isoformat(),"existing_results_policy":existing,
            "previous_results_backup":str(backup.resolve()) if backup is not None else None})
        yield RunReservation(path,backup,acquisition_id)


def create_run_dir(root,config,existing="backup"):
    """Create a snapshot directory; continuous writers must use reserve_run."""
    with reserve_run(root,config,existing) as reservation:
        return reservation.path


def save_run(path,config,design,tasks,frames,events,status,error=None,metadata=None):
    path=Path(path)
    for event in events:
        if event.get("trial_type")=="target":
            target=tasks.targets[int(event["value"])]
            if target.actual_offset is not None:
                event["duration"]=target.actual_offset-target.actual_onset
    write_tsv(path/"frames.tsv",frames,["frame","planned_time","flip_time","interval", "segment",
              "condition","carrier_epoch","target","second_eye_flip_time","eye_skew_s",
              "update_cpu_s","draw_cpu_s","upload_cpu_s"])
    write_tsv(path/"events.tsv",events,["onset","duration","trial_type","value","segment",
                                     "planned_onset","onset_error_s"])
    blocks=block_timing_rows(design,frames)
    write_tsv(path/"block_timing.tsv",blocks,["series","block","planned_onset_s","scheduled_onset_s",
                                            "actual_onset_s","error_s","frame"])
    write_tsv(path/"targets.tsv",tasks.rows(),["index","onset","duration","patch","actual_onset",
              "actual_offset","response_time"])
    write_tsv(path/"responses.tsv",tasks.responses,["onset","key","classification","target","rt"])
    refresh=config.display.refresh_hz
    intervals=[r["interval"] for r in frames if r["interval"] is not None]
    report={"subject":config.subject,"mode":config.mode,"run":config.run,
            "status":status,"error":error,"version":__version__,"python":sys.version,
            "platform":platform.platform(),"saved_at":datetime.now().astimezone().isoformat(),
            "design":design.summary(),"task":tasks.summary(),
            "timing":{"recorded_flips":len(frames),
                      "long_intervals":sum(v>1.5/refresh for v in intervals),
                      "estimated_missed_frames":sum(max(0,round(v*refresh)-1) for v in intervals),
                      "max_interval_s":max(intervals,default=None)},
            "block_timing":{"observed_boundaries":sum(r["error_s"] is not None for r in blocks),
                            "max_abs_error_s":max((abs(r["error_s"]) for r in blocks if r["error_s"] is not None),default=None),
                            "clock":"all boundaries relative to the first actual run flip"},
            "metadata":metadata or {}}
    write_json(path/"summary.json",report)
    write_json(path/"events.json",{
        "onset":{"Description":"Seconds relative to the first actual run flip. Scanner triggers may be negative."},
        "trial_type":{"Description":"stimulus, blank, trigger, response, target, abort or end"},
        "value":{"Description":"Stimulus condition, key name, or target index."},
        "duration":{"Description":"Actual flip-to-flip duration when known; n/a for instantaneous events."}})
    if design.multifocal is not None:
        np.save(path/"multifocal_design.npy",design.multifocal,allow_pickle=False)
    return report
