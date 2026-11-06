"""Acquisition reruns retain all data; run selection reaches saved outputs."""
from contextlib import redirect_stdout,redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pyretinotopy.cli import main
from pyretinotopy.config import defaults,load_subject_config
from pyretinotopy.outputs import create_run_dir,reserve_run,result_directory
from pyretinotopy.runner import run
from pyretinotopy.session import load_session


def contents(path):
    return {str(p.relative_to(path)):(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns)
            for p in path.rglob('*') if p.is_file()}


class RerunTests(unittest.TestCase):
    def test_repeated_runs_archive_whole_directory_without_editing_old_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=defaults('ccw')
            path=create_run_dir(tmp,c)
            (path/'frames.tsv').write_bytes(b'first frame log')
            (path/'nested').mkdir()
            (path/'nested/image.bin').write_bytes(bytes(range(256)))
            before=contents(path)
            for number in (1,2,3):
                with reserve_run(tmp,c) as reserved:
                    self.assertEqual(reserved.path,path)
                    self.assertEqual(reserved.backup.name,f'ccw_run-01_old-{number:02d}')
                    self.assertEqual(contents(reserved.backup),before)
                    acquisition=json.loads((path/'acquisition.json').read_text())
                    self.assertEqual(Path(acquisition['previous_results_backup']),reserved.backup.resolve())
                    (path/'frames.tsv').write_text(f'trial {number}')
                before=contents(path)
            self.assertEqual((path.with_name('ccw_run-01_old-01')/'frames.tsv').read_bytes(),b'first frame log')

    def test_backup_counter_skips_occupied_names_and_never_renumbers_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=defaults();path=create_run_dir(tmp,c)
            occupied=path.with_name(path.name+'_old-07');occupied.write_bytes(b'keep file')
            (path.with_name(path.name+'_old-03')).mkdir()
            with reserve_run(tmp,c) as r:self.assertTrue(r.backup.name.endswith('_old-08'))
            self.assertEqual(occupied.read_bytes(),b'keep file')

    def test_error_policy_cancels_without_archiving_or_changing_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=defaults();path=create_run_dir(tmp,c);before=contents(path)
            with self.assertRaises(FileExistsError):create_run_dir(tmp,c,existing='error')
            self.assertEqual(contents(path),before)
            self.assertFalse(any(path.parent.glob('*_old-*')))

    def test_file_collision_and_invalid_policy_do_not_move_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=defaults();path=result_directory(c,tmp)
            path.parent.mkdir(parents=True);path.write_bytes(b'not a directory')
            with self.assertRaises(ValueError):create_run_dir(tmp,c)
            self.assertEqual(path.read_bytes(),b'not a directory')
            with self.assertRaises(ValueError):create_run_dir(tmp,c,existing='overwrite')

    def test_active_run_is_not_archived_by_another_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=defaults()
            with reserve_run(tmp,c) as r:
                before=contents(r.path)
                code=("from pyretinotopy.outputs import create_run_dir,AcquisitionInProgressError; "
                      "from pyretinotopy.config import defaults\n"
                      "try: create_run_dir("+repr(tmp)+",defaults())\n"
                      "except AcquisitionInProgressError: raise SystemExit(42)\n")
                child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=20)
                self.assertEqual(child.returncode,42,child.stderr)
                self.assertEqual(contents(r.path),before)
                self.assertFalse(any(r.path.parent.glob('*_old-*')))
            create_run_dir(tmp,c)  # released lock permits the subsequent rerun

    def test_os_releases_lock_after_process_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            code=("from pyretinotopy.outputs import reserve_run; from pyretinotopy.config import defaults; import os\n"
                  "with reserve_run("+repr(tmp)+",defaults()): os._exit(0)\n")
            child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=20)
            self.assertEqual(child.returncode,0,child.stderr)
            with reserve_run(tmp,defaults()) as r:
                self.assertIsNotNone(r.backup)
                self.assertTrue((r.backup/'config.json').is_file())

    def test_failed_initialization_preserves_old_run_and_saves_failure(self):
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()):
            c=defaults();c.timing.operator_confirm=False;path=create_run_dir(tmp,c)
            (path/'summary.json').write_text('{"status":"completed"}')
            before=contents(path)
            with patch('pyretinotopy.backend.require_backend',side_effect=RuntimeError('test backend failure')):
                with self.assertRaisesRegex(RuntimeError,'test backend failure'):run(c,tmp)
            archived=path.with_name(path.name+'_old-01')
            self.assertEqual(contents(archived),before)
            report=json.loads((path/'summary.json').read_text())
            self.assertEqual(report['status'],'failed')
            self.assertEqual((report['subject'],report['mode'],report['run']),('demo','ccwf',1))
            with reserve_run(tmp,c) as r:self.assertTrue(r.backup.name.endswith('_old-02'))

    def test_run_numbers_have_separate_directories_and_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=defaults('ccw');a=create_run_dir(tmp,c)
            c.run=2;b=create_run_dir(tmp,c);before=contents(b)
            c.run=1;create_run_dir(tmp,c)
            self.assertEqual(a.name,'ccw_run-01');self.assertEqual(b.name,'ccw_run-02')
            self.assertEqual(contents(b),before)
            self.assertEqual(json.loads((b/'config.json').read_text())['run'],2)

    def test_cli_run_override_wins_over_inherited_and_standalone_json(self):
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            root=Path(tmp);participant=root/'subjects/HB';participant.mkdir(parents=True)
            (participant/'ccw.json').write_text('{"run":9}')
            source=['--subject','HB','--subjects-dir',str(root/'subjects'),'--mode','ccw']
            target=root/'resolved.json'
            self.assertEqual(main(['validate',*source,'--run','2','--save-config',str(target)]),0)
            self.assertEqual(json.loads(target.read_text())['run'],2)
            with patch('pyretinotopy.runner.run',return_value=root) as presentation:
                self.assertEqual(main(['run',*source,'--run','3','--if-exists','error']),0)
                self.assertEqual(presentation.call_args.args[0].run,3)
                self.assertEqual(presentation.call_args.kwargs['existing'],'error')
            with patch('pyretinotopy.runner.run',return_value=root) as presentation:
                self.assertEqual(main(['run','--config',str(target),'--run','4']),0)
                self.assertEqual(presentation.call_args.args[0].run,4)
            self.assertEqual(json.loads(target.read_text())['run'],2)

    def test_invalid_cli_run_is_rejected_before_start(self):
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),patch('pyretinotopy.runner.run') as presentation:
            self.assertEqual(main(['run','--run','0']),2)
            self.assertEqual(main(['run','--run','-1']),2)
            presentation.assert_not_called()

    def test_session_accepts_existing_runs_without_moving_them_at_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);session=root/'session.json'
            session.write_text(json.dumps({'runs':[
                {'subject':'HB','mode':'ccw','subjects_dir':'subjects','run':i} for i in [1,2]]}))
            configs=load_session(session)
            paths=[create_run_dir(None,c) for c in configs];before=[contents(p) for p in paths]
            self.assertEqual([c.run for c in load_session(session)],[1,2])
            self.assertEqual([contents(p) for p in paths],before)
            with self.assertRaises(ValueError):load_session(session,existing='error')
            session.write_text(json.dumps({'runs':[{'subject':'HB','mode':'ccw','run':1}]*2}))
            with self.assertRaisesRegex(ValueError,'Duplicate'):load_session(session)

    def test_replay_of_archived_config_keeps_participant_and_date_layout(self):
        from pyretinotopy.config import load_config
        with tempfile.TemporaryDirectory() as tmp:
            c=load_subject_config('HB','ccw',Path(tmp)/'subjects')
            c.run=3;path=create_run_dir(None,c)
            with reserve_run(None,c) as r:archived=r.backup
            replay=load_config(archived/'config.json')
            self.assertEqual(result_directory(replay),path)
            self.assertEqual(replay.run,3)


if __name__=='__main__':unittest.main()
