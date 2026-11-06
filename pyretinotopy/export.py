"""TR exposure averages using the exact same aperture fields as presentation."""
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .carriers import CarrierRenderer
from .design import Design
from .geometry import Rasterizer
from .modes import parse_mode
from .outputs import write_json


def realized_intervals(design,frames_path):
    """Frame-held apertures; dropped frames extend the preceding image."""
    with Path(frames_path).open(encoding="utf-8",newline="") as f:
        frames=list(csv.DictReader(f,delimiter="\t"))
    if len(frames)<2:
        raise ValueError("Actual export requires at least two recorded flips, including an end flip.")
    times=[float(row["flip_time"]) for row in frames]
    if any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError("Actual flip timestamps must be strictly increasing.")
    intervals=[]
    for row,a,b in zip(frames,times,times[1:]):
        index=row["segment"]
        components=() if index in ("n/a","None","") else design.segments[int(index)].components
        intervals.append((a,b,components))
    return intervals,times[-1]


def export_windows(config,path,tr_s=None,resolution=128,frames_path=None):
    config.validate()
    design=Design(config)
    raster=Rasterizer(config,resolution)
    tr_s=config.timing.tr_s if tr_s is None else tr_s
    if tr_s<=0 or not np.isfinite(tr_s):
        raise ValueError("TR must be positive and finite.")
    if frames_path:
        intervals,duration=realized_intervals(design,frames_path)
    else:
        intervals=[(s.onset,s.onset+s.duration,s.components) for s in design.segments]
        duration=design.duration
    n=int(np.ceil(duration/tr_s-1e-10))
    if n*resolution*resolution*4>1024**3:
        raise ValueError("Window export would exceed 1 GiB. Reduce resolution.")
    windows=np.zeros((n,resolution,resolution),dtype=np.float32)
    # Integrate each held aperture over the volume acquisition interval.
    for start,end,components in intervals:
        if not components:
            continue
        mask=raster.mask(components)
        for i in range(max(0,int(start//tr_s)),min(n,int(np.ceil(end/tr_s)))):
            overlap=max(0,min(end,(i+1)*tr_s)-max(start,i*tr_s))
            windows[i]+=mask*(overlap/tr_s)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    metadata={"mode":config.mode,"axis_order":"time,y,x","positive_y":"up; top array row is upper visual field",
              "tr_s":tr_s,"duration_s":duration,"field_extent_deg":raster.extent_deg,
              "resolution":resolution,"source":"recorded_flips" if frames_path else "planned",
              "meaning":"Fraction of each full TR exposed to the geometric aperture; final partial TR padded with blank.",
              "includes_fixation":False,"includes_carrier_and_disparity":False,
              "config":config.to_dict()}
    if path.suffix.lower()==".mat":
        from scipy.io import savemat
        metadata["axis_order"]="y,x,time"
        savemat(path,{"stim_windows":windows.transpose(1,2,0),"subjID":config.subject,
                      "metadata_json":json.dumps(metadata),"TR":tr_s},do_compression=True)
    elif path.suffix.lower()==".npz":
        np.savez_compressed(path,stim_windows=windows,tr_s=tr_s,
                            metadata_json=json.dumps(metadata),times_s=np.arange(n)*tr_s)
    else:
        raise ValueError("Window output must end with .npz or .mat.")
    write_json(path.with_suffix(".json"),metadata)
    return windows,metadata


def preview(config,path,time_s=None,resolution=384):
    """Side-by-side LEFT/RIGHT eye illustration; unrelated to display packing."""
    design=Design(config)
    if time_s is None:
        time_s=config.timing.initial_fixation_s+min(1,design.active_duration/2)
    if not np.isfinite(time_s) or not 0<=time_s<design.duration:
        raise ValueError("Preview time must lie within the run.")
    raster=Rasterizer(config,resolution)
    renderer=CarrierRenderer(config,raster)
    try:
        left,right=renderer.render(parse_mode(config.mode).carrier,design.at(time_s).components,time_s)
    finally:
        renderer.close()
    bg=np.asarray(config.display.background)
    def flatten(rgba):
        return np.uint8(np.clip((rgba[:,:,:3]*rgba[:,:,3:]+bg*(1-rgba[:,:,3:]))*255,0,255))
    sheet=Image.new("RGB",(resolution*2,resolution+40),(35,35,35))
    sheet.paste(Image.fromarray(flatten(left)),(0,40))
    sheet.paste(Image.fromarray(flatten(right)),(resolution,40))
    draw=ImageDraw.Draw(sheet)
    draw.text((10,10),f"{config.mode}  t={time_s:.3f}s  LEFT",fill="white")
    draw.text((resolution+10,10),"RIGHT (+y up; - disparity = near)",fill="white")
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(path)
    return path


def preview_positions(config,directory,resolution=384):
    """Offline equivalent of the original DEBUG position-image inspection."""
    directory=Path(directory)
    if directory.exists() and any(directory.iterdir()):raise FileExistsError(directory)
    directory.mkdir(parents=True,exist_ok=True)
    design=Design(config);seen=set();entries=[]
    for segment in design.segments:
        if not segment.components or segment.components in seen:continue
        seen.add(segment.components)
        time_s=segment.onset+min(.001,segment.duration/4)
        path=directory/f'position-{len(entries)+1:04d}.png'
        preview(config,path,time_s,resolution)
        entries.append({"file":path.name,"time_s":time_s,"condition":segment.condition,
                        "components":segment.components})
    write_json(directory/"manifest.json",{"config":config.to_dict(),"positions":entries,
               "meaning":"First occurrence of each unique aperture; offline left/right carrier previews, not physical display captures."})
    return directory
