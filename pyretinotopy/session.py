"""Sequential acquisitions, validated before opening the first window."""
import json
from pathlib import Path

from .config import load_config, load_subject_config
from .outputs import result_directory, validate_existing_policy


def load_session(path,output_root=None,existing="backup"):
    validate_existing_policy(existing)
    path=Path(path).resolve()
    data=json.loads(path.read_text(encoding="utf-8-sig"))
    if set(data)!={"runs"} or not isinstance(data["runs"],list) or not data["runs"]:
        raise ValueError("Session must contain a nonempty runs list.")
    configs=[]
    destinations=set()
    for entry in data["runs"]:
        if not isinstance(entry,dict) or set(entry)-{"config","mode","run","subject","subjects_dir"}:
            raise ValueError("Session entries accept config, subject, mode, run and subjects_dir.")
        if "config" in entry:
            if "subjects_dir" in entry:
                raise ValueError("subjects_dir cannot accompany an explicit config.")
            c=load_config(path.parent/entry["config"],entry.get("mode"))
        elif "subject" in entry and "mode" in entry:
            root=path.parent/entry["subjects_dir"] if "subjects_dir" in entry else None
            c=load_subject_config(entry["subject"],entry["mode"],root)
        else:
            raise ValueError("Each session entry requires config or both subject and mode.")
        for key in ("run","subject"):
            if key in entry:
                setattr(c,key,entry[key])
        c.validate(presentation=True)
        destination=result_directory(c,output_root).resolve()
        if destination in destinations:
            raise ValueError(f"Duplicate acquisition in session: {destination}; assign distinct run numbers.")
        if existing=="error" and destination.exists():
            raise ValueError(f"Existing acquisition directory; session cancelled without changes: {destination}")
        destinations.add(destination)
        configs.append(c)
    return configs


def run_session(path,output_root=None,existing="backup"):
    from .runner import run
    outputs=[]
    for config in load_session(path,output_root,existing):
        result=run(config,output_root,existing=existing)
        outputs.append(str(result.resolve()))
        summary=json.loads((result/"summary.json").read_text(encoding="utf-8"))
        if summary["status"]!="completed":
            break
    return outputs
