"""Verify project ignore rules using an isolated Git index and actual work tree.

No Git initialization, staging, commit, or push is performed on the project.
The temporary metadata and index are confined to the ignored .runtime folder.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def check(git):
    runtime=ROOT/'.runtime'
    runtime.mkdir(exist_ok=True)
    project_git_existed=(ROOT/'.git').exists()
    with tempfile.TemporaryDirectory(prefix='publication-ignore-',dir=runtime) as tmp:
        admin=Path(tmp).resolve()
        # Check the absolute cleanup target before TemporaryDirectory removes it.
        if admin.parent!=runtime.resolve():raise ValueError('Temporary metadata escaped .runtime')
        repo=admin/'admin.git'
        subprocess.run([git,'init','--bare','--quiet',str(repo)],check=True)
        empty=admin/'empty-excludes';empty.write_text('')
        cmd=[git,'--git-dir',str(repo),'--work-tree',str(ROOT),'-c','core.bare=false',
             '-c','core.excludesFile='+str(empty)]
        required=['.gitignore','README.md','LICENSE.txt','NOTICE.md','pyproject.toml','PyRetinotopy.py',
                  '.github/workflows/tests.yml','subjects/README.md',
                  'docs/PyRetinotopy_Experiment_Guide_ja.pdf','docs/PyRetinotopy_Experiment_Guide_en.pdf']
        required += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'subjects/_DEFAULT_').glob('*.json')]
        required += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'pyretinotopy/data/brainvoyager').glob('*.olt')]
        excluded=['data/example.tsv','.runtime/example.json','cache/example.npy','tmp/example.png',
                  'optional-libs/example.py','build/example.py','pyretinotopy.egg-info/PKG-INFO',
                  'assets/object-images/images.npy','docs/source-baseline.json',
                  'subjects/EXAMPLE/common.json','subjects/EXAMPLE/results/261106/ccw_run-01/frames.tsv',
                  'subjects/EXAMPLE/results/261106/ccw_run-01_old-01/summary.json',
                  'pyretinotopy/__pycache__/config.cpython-310.pyc']
        names=required+excluded
        # NUL-delimited bytes avoid Windows newline conversion adding CR to paths.
        result=subprocess.run(cmd+['check-ignore','--no-index','-z','--stdin'],
                              input=('\0'.join(names)+'\0').encode('utf-8'),capture_output=True,cwd=ROOT)
        if result.returncode not in (0,1):raise RuntimeError(result.stderr.decode('utf-8','replace'))
        ignored=set(result.stdout.decode('utf-8').rstrip('\0').split('\0')) if result.stdout else set()
        wrong_required=[p for p in required if p in ignored or not (ROOT/p).is_file()]
        wrong_excluded=[p for p in excluded if p not in ignored]
        candidates=subprocess.run(cmd+['ls-files','--others','--exclude-standard','-z'],capture_output=True,check=True,cwd=ROOT)
        paths=[p for p in candidates.stdout.decode('utf-8').split('\0') if p]
        sizes=sorted([(p,(ROOT/p).stat().st_size) for p in paths if (ROOT/p).is_file()],key=lambda item:-item[1])
        large=[{'path':p,'bytes':n} for p,n in sizes if n>100*1024**2]
        if wrong_required or wrong_excluded or large:
            raise RuntimeError(json.dumps({'required_missing_or_ignored':wrong_required,'not_excluded':wrong_excluded,'over_100_MiB':large}))
        if any(p.startswith('subjects/') and not (p=='subjects/README.md' or p.startswith('subjects/_DEFAULT_/')) for p in paths):
            raise RuntimeError('Participant files appeared among publication candidates')
        report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'git_version':subprocess.check_output([git,'--version'],text=True).strip(),
                'project_git_existed_before':project_git_existed,'project_git_exists_after':(ROOT/'.git').exists(),
                'project_index_and_working_files_modified':False,'rules_source':'.gitignore (global excludes disabled for reproducibility)',
                'required_files_verified':required,'excluded_examples_verified':excluded,
                'candidate_count_at_check':len(paths),'candidate_total_bytes':sum(n for _,n in sizes),
                'largest_candidates':[{'path':p,'bytes':n} for p,n in sizes[:8]],'over_100_MiB':large,
                'olt_files_included':len([p for p in paths if p.startswith('pyretinotopy/data/brainvoyager/') and p.endswith('.olt')]),
                'candidate_files':sorted(paths)}
        if report['olt_files_included']!=6:raise RuntimeError('Expected all six original OLT resources')
        if report['project_git_exists_after']!=project_git_existed:raise RuntimeError('Project Git metadata was unexpectedly created')
    out=ROOT/'docs/qa/publication-gitignore-review.json'
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--git-exe',default=shutil.which('git'))
    args=parser.parse_args()
    if not args.git_exe:parser.error('Git executable not found; supply --git-exe')
    report=check(args.git_exe)
    print(json.dumps({k:report[k] for k in ['candidate_count_at_check','candidate_total_bytes','olt_files_included','over_100_MiB','project_git_exists_after']},indent=2))


if __name__=='__main__':main()
