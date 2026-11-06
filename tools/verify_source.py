"""Verify that the shared MATLAB sources retain their initial SHA-256 hashes."""
import hashlib
import json
from pathlib import Path
import subprocess

base=Path(__file__).resolve().parents[1]
manifest=json.loads((base/"docs/source-baseline.json").read_text(encoding="utf-8"))
root=base.parent/"Retinotopy"
if not root.is_dir():
    root=Path(manifest["source_root"])
changed=[]
for relative,digest in manifest["sha256"].items():
    path=root/relative
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        changed.append(relative)
status=subprocess.check_output(["git","-C",str(root),"status","--porcelain"],text=True)
print(json.dumps({"files_checked":len(manifest["sha256"]),"changed":changed,
                  "git_status_unchanged":status==manifest["git_status"]},indent=2))
raise SystemExit(1 if changed or status!=manifest["git_status"] else 0)
