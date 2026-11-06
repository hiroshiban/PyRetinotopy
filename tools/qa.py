"""Reproducible offline contact sheet and optional native PsychoPy smoke runs.

Run from the project directory. --live opens short-lived stimulus windows.
"""
import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image, ImageDraw

from pyretinotopy import __version__
from pyretinotopy.config import defaults, load_config
from pyretinotopy.design import Design
from pyretinotopy.export import preview, export_windows
from pyretinotopy.modes import BASES
from pyretinotopy.outputs import write_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    args=parser.parse_args()
    base=Path(__file__).resolve().parents[1]
    output=base/"docs/qa"
    output.mkdir(parents=True,exist_ok=True)
    sheet=Image.new("RGB",(4*320,4*190),(30,30,30))
    draw=ImageDraw.Draw(sheet)
    for i,mode in enumerate(BASES):
        c=defaults(mode+"f")
        path=preview(c,output/(mode+".png"),resolution=160)
        image=Image.open(path).crop((0,40,160,200)).resize((168,168))
        x=(i%4)*320
        y=(i//4)*190
        sheet.paste(image,(x,y+20))
        draw.text((x+10,y+4),mode,fill="white")
    sheet.save(output/"stimulus-gallery.png")
    object_config=load_config(base/"examples/object-images.json")
    preview(object_config,output/"objects.png",resolution=384)
    stereo=load_config(base/"examples/stereo-rds.json")
    preview(stereo,output/"rds.png",resolution=384)
    export_windows(defaults("barf"),output/"bar-windows.npz",resolution=48)
    report={"version":__version__,"offline_gallery":"stimulus-gallery.png","date":datetime.now().astimezone().isoformat(),"live":[]}
    write_json(output/"validation.json",report)
    if args.live:
        from pyretinotopy.runner import run, Scene
        from pyretinotopy.geometry import Rasterizer
        from pyretinotopy.tasks import TaskSchedule
        timestamp=datetime.now().strftime("%Y%m%d-%H%M%S")
        for name,mode,display in (("checker","ccw","mono"),("bar","barf","mono"),
                ("dual-aperture","ccwexpf","mono"),("rds","ccwdf","parallel"),
                ("interleaved","ccwdf","interleavedline"),("anaglyph","ccwf","redgreen"),
                ("objects","ccwi","parallel"),("object-anaglyph","ccwi","redgreen"),
                ("fix-cross","ccwf","mono"),("fix-concentric","ccwf","mono"),
                ("grid-gamma","hrff","parallel"),("hrf-clock","hrf","mono")):
            c=defaults(mode)
            smoke=load_config(base/"examples/smoke.json")
            c.display=copy.deepcopy(smoke.display)
            c.display.mode=display
            c.timing=copy.deepcopy(smoke.timing)
            c.task=copy.deepcopy(smoke.task)
            c.subject="qa_"+name.replace("-","_")
            c.timing.polar_cycle_s=2
            c.timing.polar_repeats=1
            c.timing.eccentricity_cycle_s=2
            c.timing.eccentricity_rest_s=.4
            c.timing.eccentricity_repeats=1
            c.stimulus.bar_angles_deg=[0,90]
            if mode=="barf":
                c.timing.cycle_s=1
            if mode.endswith("i"):
                c.stimulus.object_source=object_config.stimulus.object_source
            if name.startswith("fix-"):
                c.task.fixation_type=name[4:];c.task.fixation_radius_px=16;c.task.enabled=False
            if name=="grid-gamma":
                c.display.background_type="grid"
                c.display.background_patch_count=[10,20]
                c.display.background_patch_size_px=[12,12]
                c.display.gamma_lut=[[0,0,0],[.55,.65,.75],[1,1,1]]
                c.task.fixation_type="concentric";c.task.fixation_radius_px=16;c.task.enabled=False
                c.display.use_measured_refresh=True
                c.display.marker_corner=2
            screenshot=output/("live-"+name+".png")
            try:
                directory=run(c,base/".runtime"/("qa-"+timestamp),capture_path=screenshot)
            except BaseException as exc:
                report["live"].append({"case":name,"mode":mode,"display":display,"status":"failed","error":str(exc)})
                write_json(output/"validation.json",report)
                raise
            summary=json.loads((directory/"summary.json").read_text(encoding="utf-8"))
            entry={"case":name,"mode":mode,"display":display,"status":summary["status"],
                   "timing":summary["timing"],"metadata":summary["metadata"],
                   "screenshot":screenshot.name}
            # Compare native GPU checker pixels against the independent software
            # compositor. Shape boundary/fixation rasterization may differ 1px.
            if mode in ("ccw","barf","ccwexpf","ccwi") or name=="anaglyph" or name.startswith("fix-") or name in ("grid-gamma","hrf-clock"):
                if c.display.use_measured_refresh:
                    c.display.refresh_hz=summary["design"].get("refresh_hz",c.display.refresh_hz)
                    # Run mutates this same config to the measured refresh.
                design=Design(c)
                reference=Scene(c,design,Rasterizer(c),TaskSchedule(c,design))
                expected=np.asarray(reference.at(summary["metadata"]["capture_planned_time_s"])[0][0])
                actual=np.asarray(Image.open(screenshot).convert("RGB"))
                delta=np.max(abs(expected.astype(int)-actual.astype(int)),axis=2)
                fraction=float(np.mean(delta>8))
                entry["fraction_pixels_differing_by_gt8"]=fraction
                if fraction>.02:
                    raise RuntimeError(f"GPU/reference mismatch for {name}: {fraction:.1%} pixels")
                reference.carrier.close()
            report["live"].append(entry)
            write_json(output/"validation.json",report)
            print(json.dumps(entry),flush=True)
    write_json(output/"validation.json",report)


if __name__=="__main__":
    main()
