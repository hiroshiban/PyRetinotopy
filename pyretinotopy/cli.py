"""One wrapper, retaining the original mode vocabulary."""
import argparse
import json
from pathlib import Path
import sys

from .config import defaults, load_config, load_subject_config, SUBJECTS_ROOT
from .design import Design
from .modes import DISPLAY_MODES, all_modes


def selected_config(args):
    if args.subjects_dir and not args.subject:
        raise ValueError("--subjects-dir requires --subject.")
    config=(load_subject_config(args.subject,args.mode or "ccwf",args.subjects_dir)
            if args.subject else load_config(args.config,args.mode))
    if getattr(args,"run",None) is not None:
        config.run=args.run
    return config.validate()


def main(argv=None):
    parser=argparse.ArgumentParser(prog="pyretinotopy",description="PyRetinotopy: binocular retinotopic mapping in PsychoPy")
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("list",help="List legacy-compatible stimulus names and display modes")
    session=sub.add_parser("session",help="Run a sequence of acquisitions, waiting for a trigger for each")
    session.add_argument("session_file",type=Path)
    session.add_argument("--if-exists",choices=("backup","error"),default="backup",
                         help="Existing results: numbered backup (default), or cancel without changes")
    session.add_argument("--output-root",type=Path,help="Optional separate result root; default is subjects/ID/results/YYMMDD")
    olts=sub.add_parser("export-olts",help="Copy the six original BrainVoyager color tables")
    olts.add_argument("--output",type=Path,required=True)
    conversion=sub.add_parser("convert-images",help="One-time lossless conversion of a legacy image database to native NumPy")
    conversion.add_argument("source",type=Path)
    conversion.add_argument("--output",required=True,type=Path)
    preparation=sub.add_parser("prepare-objects",help="Prepare complete native object movies before acquisition")
    preparation_source=preparation.add_mutually_exclusive_group(required=True)
    preparation_source.add_argument("--config",type=Path)
    preparation_source.add_argument("--subject")
    preparation.add_argument("--mode",default=None)
    preparation.add_argument("--subjects-dir",type=Path)
    preparation.add_argument("--cache-dir",type=Path)
    init=sub.add_parser("init",help="Create an editable participant configuration")
    init.add_argument("output",type=Path)
    init.add_argument("--mode",default="ccwf")
    init.add_argument("--subject",default="demo")
    participant=sub.add_parser("init-subject",help="Create an editable participant override directory")
    participant.add_argument("subject")
    participant.add_argument("--mode",default="ccwf")
    participant.add_argument("--subjects-dir",type=Path,default=SUBJECTS_ROOT)
    for command in ("validate","preview","export","run"):
        cmd=sub.add_parser(command)
        source=cmd.add_mutually_exclusive_group()
        source.add_argument("--config",type=Path)
        source.add_argument("--subject",help="Resolve subjects/_DEFAULT_ and participant overrides")
        cmd.add_argument("--subjects-dir",type=Path,help="Root for --subject (default: project subjects)")
        cmd.add_argument("--mode",help="Mode override; use init per protocol for family defaults")
        cmd.add_argument("--run",type=int,help="Positive run number; overrides the JSON run value")
        if command=="validate":
            cmd.add_argument("--save-config",type=Path,help="Write the fully resolved configuration for review/replay")
        if command in ("preview","export"):
            cmd.add_argument("--output",required=True,type=Path)
            cmd.add_argument("--resolution",type=int,default=128 if command=="export" else 384)
        if command=="preview":
            cmd.add_argument("--time",type=float)
            cmd.add_argument("--all-positions",action="store_true",help="Save every unique aperture position and a manifest to --output directory")
        if command=="export":
            cmd.add_argument("--prt",type=Path,help="Also export a BrainVoyager protocol from the same intervals")
            cmd.add_argument("--prt-unit",choices=("msec","Volumes"),default="msec")
            cmd.add_argument("--tr",type=float)
            cmd.add_argument("--frames",type=Path,help="Use this acquisition's actual frames.tsv")
        if command=="run":
            cmd.add_argument("--no-confirm",action="store_true",help="Skip the operator settings dialog (scanner trigger wait is unchanged)")
            cmd.add_argument("--if-exists",choices=("backup","error"),default="backup",
                             help="Existing results: numbered backup (default), or cancel without changes")
            cmd.add_argument("--output-root",type=Path,help="Optional separate result root; default is subjects/ID/results/YYMMDD")
            cmd.add_argument("--max-seconds",type=float,help="Explicitly stop early for a smoke test")
            cmd.add_argument("--capture",type=Path,help="Save the first active OpenGL framebuffer (QA only)")
    migration=sub.add_parser("migrate",help="Safely draft JSON from MATLAB subject settings; emits a review report")
    migration.add_argument("subject_directory",type=Path)
    migration.add_argument("--mode",required=True)
    migration.add_argument("--output",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command=="list":
            print("Stimuli (70 aliases):\n"+" ".join(all_modes()))
            print("\nDisplays:\n"+" ".join(DISPLAY_MODES))
            return 0
        if args.command=="session":
            from .session import run_session
            print(json.dumps(run_session(args.session_file,args.output_root,existing=args.if_exists),indent=2))
            return 0
        if args.command=="export-olts":
            from .brainvoyager import export_olts
            print(json.dumps([str(p.resolve()) for p in export_olts(args.output)],indent=2))
            return 0
        if args.command=="convert-images":
            from .convert_images import convert_images
            report=convert_images(args.source,args.output,
                       progress=lambda n,total:print(f"Converting image bank: {n}/{total}",flush=True))
            print(json.dumps(report,indent=2))
            return 0
        if args.command=="prepare-objects":
            from .geometry import Rasterizer
            from .modes import parse_mode
            from .object_cache import prepare_object_movie
            config=selected_config(args)
            if parse_mode(config.mode).carrier!="objects":
                raise ValueError("prepare-objects requires an object-image mode (*i).")
            print(prepare_object_movie(config,Design(config),Rasterizer(config),args.cache_dir,
                       progress=lambda n,total:print(f"Preparing object movie: {n}/{total}",flush=True)))
            return 0
        if args.command=="init":
            if args.output.exists():
                raise FileExistsError(f"Configuration already exists: {args.output}")
            c=defaults(args.mode)
            c.subject=args.subject
            c.validate()
            args.output.parent.mkdir(parents=True,exist_ok=True)
            c.save(args.output)
            print(args.output.resolve())
            return 0
        if args.command=="init-subject":
            c=defaults(args.mode)
            c.subject=args.subject
            c.validate()
            path=args.subjects_dir.resolve()/c.subject
            mode_path=path/(c.mode+".json")
            if mode_path.exists():
                raise FileExistsError(mode_path)
            path.mkdir(parents=True,exist_ok=True)
            common=path/"common.json"
            if not common.exists():
                with common.open("x",encoding="utf-8") as stream:
                    stream.write("{}\n")
            with mode_path.open("x",encoding="utf-8") as stream:
                stream.write('{"run": 1}\n')
            print(path)
            return 0
        if args.command=="migrate":
            from .legacy import migrate
            if args.output.exists():
                raise FileExistsError(args.output)
            print(json.dumps(migrate(args.subject_directory,args.mode,args.output),indent=2,ensure_ascii=False))
            return 0
        c=selected_config(args)
        if args.command=="validate":
            d=Design(c)
            d.check_frame_grid()
            if args.save_config:
                if args.save_config.exists():
                    raise FileExistsError(args.save_config)
                args.save_config.parent.mkdir(parents=True,exist_ok=True)
                c.save(args.save_config)
            print(json.dumps({**d.summary(),"configuration_sources":getattr(c,"_configuration_sources",[])},indent=2))
        elif args.command=="preview":
            from .export import preview,preview_positions
            if args.all_positions and args.time is not None:raise ValueError("Use either --time or --all-positions.")
            path=preview_positions(c,args.output,args.resolution) if args.all_positions else preview(c,args.output,args.time,args.resolution)
            print(path.resolve())
        elif args.command=="export":
            from .export import export_windows
            if args.prt:
                from .brainvoyager import export_prt
                export_prt(c,args.prt,args.frames,args.prt_unit,args.tr)
            windows,metadata=export_windows(c,args.output,args.tr,args.resolution,args.frames)
            print(json.dumps({"path":str(args.output.resolve()),"shape":windows.shape,"source":metadata["source"]}))
        elif args.command=="run":
            from .runner import run
            if args.capture:
                args.capture.parent.mkdir(parents=True,exist_ok=True)
            print(run(c,args.output_root,args.max_seconds,args.capture,existing=args.if_exists,confirm=False if args.no_confirm else None).resolve())
        return 0
    except (ValueError,TypeError,KeyError,OSError,RuntimeError,ImportError) as exc:
        print(f"PyRetinotopy: {exc}",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
