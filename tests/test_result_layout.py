"""Participant/date storage, overwrite protection, and settings coexistence."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pyretinotopy.cli import main
from pyretinotopy.config import defaults, load_config, load_subject_config, SUBJECTS_ROOT
from pyretinotopy.outputs import create_run_dir, result_directory
from pyretinotopy.session import load_session


class ResultLayoutTests(unittest.TestCase):
    def test_default_results_live_under_participant_and_local_date(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pyretinotopy.outputs.result_day',return_value='261106'):
            root=Path(tmp)/'subjects'
            c=load_subject_config('HB','ccwf',root)
            path=create_run_dir(None,c)
            self.assertEqual(path,root/'HB/results/261106/ccwf_run-01')
            self.assertEqual(json.loads((path/'config.json').read_text())['subject'],'HB')
            (path/'result.txt').write_text('keep this acquisition')
            with self.assertRaises(FileExistsError):
                create_run_dir(None,c,existing="error")
            self.assertEqual((path/'result.txt').read_text(),'keep this acquisition')

    def test_different_dates_are_independent_and_explicit_root_keeps_old_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            c=load_subject_config('HB','ccwf',root/'subjects')
            a=result_directory(c,day='261106')
            b=result_directory(c,day='261107')
            self.assertNotEqual(a,b)
            explicit=create_run_dir(root/'separate',c)
            self.assertEqual(explicit,root/'separate/sub-HB/ccwf_run-01')
            for day in ('../../','2026-11-06','261332'):
                with self.assertRaises(ValueError):
                    result_directory(c,day=day)

    def test_explicit_participant_config_and_inherited_settings_share_the_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            subjects=Path(tmp)/'laboratory-settings'
            participant=subjects/'HB'
            participant.mkdir(parents=True)
            c=defaults(); c.subject='HB'; c.save(participant/'ccwf.json')
            explicit=load_config(participant/'ccwf.json')
            inherited=load_subject_config('HB','ccwf',subjects)
            self.assertEqual(result_directory(explicit,day='261106'),result_directory(inherited,day='261106'))

    def test_saved_acquisition_snapshot_keeps_its_participant_root_on_replay(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pyretinotopy.outputs.result_day',return_value='261106'):
            subjects=Path(tmp)/'subjects'
            c=load_subject_config('HB','ccwf',subjects)
            path=create_run_dir(None,c)
            replay=load_config(path/'config.json')
            self.assertEqual(result_directory(replay),path)

    def test_session_preflight_uses_participant_date_paths_and_optional_existing_error(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pyretinotopy.outputs.result_day',return_value='261106'):
            root=Path(tmp)
            session=root/'session.json'
            session.write_text(json.dumps({'runs':[{'subject':'HB','mode':'ccwf','subjects_dir':'subjects'}]}))
            c=load_session(session)[0]
            self.assertEqual(result_directory(c),root/'subjects/HB/results/261106/ccwf_run-01')
            create_run_dir(None,c)
            self.assertEqual(len(load_session(session)),1)
            with self.assertRaises(ValueError):
                load_session(session,existing="error")

    def test_settings_can_be_added_after_results_without_overwriting_either(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            root=Path(tmp)
            result=root/'HB/results/261106/ccwf_run-01'
            result.mkdir(parents=True)
            (result/'summary.json').write_text('{"status":"completed"}')
            args=['init-subject','HB','--subjects-dir',str(root)]
            self.assertEqual(main(args),0)
            common=root/'HB/common.json'
            common.write_text('{"seed":9}')
            self.assertEqual(main(args),2)
            self.assertEqual(main(args+['--mode','expf']),0)
            self.assertEqual(common.read_text(),'{"seed":9}')
            self.assertEqual((result/'summary.json').read_text(),'{"status":"completed"}')

    def test_demo_uses_project_subjects_instead_of_writing_to_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            example=Path(tmp)/'smoke.json'
            defaults().save(example)
            c=load_config(example)
            self.assertEqual(result_directory(c,day='261106'),SUBJECTS_ROOT/'demo/results/261106/ccwf_run-01')


if __name__=='__main__':
    unittest.main()
