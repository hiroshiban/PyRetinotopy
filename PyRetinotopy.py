"""Open in PsychoPy Coder and Run; or use `python -m pyretinotopy`."""
from pathlib import Path
import sys

from pyretinotopy.cli import main


if __name__=="__main__":
    if len(sys.argv)>1:
        raise SystemExit(main())
    from psychopy import gui
    from pyretinotopy.config import load_config
    from pyretinotopy.runner import run

    base=Path(__file__).resolve().parent
    chosen=gui.fileOpenDlg(tryFilePath=str(base/"examples"),allowed="JSON files (*.json)|*.json")
    if chosen:
        run(load_config(chosen[0]))
