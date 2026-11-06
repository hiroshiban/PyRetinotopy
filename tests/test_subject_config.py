"""Default-file fallback and participant overrides, independent of PsychoPy."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest

from pyretinotopy.cli import main
from pyretinotopy.config import defaults, load_config, load_subject_config
from pyretinotopy.design import Design
from pyretinotopy.modes import all_modes
from pyretinotopy.session import load_session


class SubjectConfigTests(unittest.TestCase):
    def write(self,root,name,value):
        p=root/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value),encoding="utf-8")
        return p

    def test_missing_participant_falls_back_without_creating_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            default=self.write(root,"_DEFAULT_/retinotopy_display.json",{"display":{"width_cm":40}})
            c=load_subject_config("NEW","ccwf",root)
            self.assertEqual(c.subject,"NEW")
            self.assertEqual(c.display.width_cm,40)
            self.assertEqual(c._configuration_sources,[str(default)])
            self.assertFalse((root/"NEW").exists())

    def test_participant_layers_override_default_family_and_lists_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.write(root,"_DEFAULT_/common.json",{"seed":12,"task":{"interval_s":[3,8]}})
            self.write(root,"_DEFAULT_/c_pol.json",{"stimulus":{"wedge_width_deg":48}})
            self.write(root,"HB/common.json",{"stimulus":{"wedge_width_deg":60}})
            self.write(root,"HB/retinotopy_display.json",{"display":{"mirror_x":[True,False]}})
            self.write(root,"HB/c_pol.json",{"timing":{"cycle_s":90}})
            self.write(root,"HB/ccwf.json",{"run":3,"task":{"interval_s":[4,9]}})
            c=load_subject_config("HB","ccwf",root)
            self.assertEqual((c.seed,c.run,c.stimulus.wedge_width_deg,c.timing.cycle_s),(12,3,60,90))
            self.assertEqual(c.display.mirror_x,[True,False])
            self.assertEqual(c.task.interval_s,[4,9])
            # The same polar-family settings also serve the opposite direction.
            other=load_subject_config("HB","cwi",root)
            self.assertEqual(other.timing.cycle_s,90)
            self.assertEqual(other.task.interval_s,[3,8])

    def test_relative_paths_follow_the_layer_that_defines_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.write(root,"_DEFAULT_/c_pol.json",{"stimulus":{
                "object_source":"bank/manifest.json","object_cache_dir":"../../movies"}})
            self.write(root,"HB/common.json",{"seed":3})
            c=load_subject_config("HB","ccwi",root)
            self.assertEqual(Path(c.stimulus.object_source),root/"_DEFAULT_/bank/manifest.json")
            self.assertEqual(Path(c.stimulus.object_cache_dir),(root/"../movies").resolve())
            self.write(root,"HB/ccwi.json",{"stimulus":{"object_source":"images"}})
            c=load_subject_config("HB","ccwi",root)
            self.assertEqual(Path(c.stimulus.object_source),root/"HB/images")

    def test_bad_subjects_and_malformed_overrides_never_silently_fall_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(ValueError):
                load_subject_config("../outside","ccwf",root)
            for raw in ({"display":{"width_cmm":20}}, {"mode":"expf"}, {"subject":"WRONG"}, []):
                self.write(root,"HB/common.json",raw)
                with self.assertRaises(ValueError):
                    load_subject_config("HB","ccwf",root)

    def test_saved_resolved_config_is_independent_of_changed_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.write(root,"_DEFAULT_/c_pol.json",{"timing":{"cycle_s":70}})
            c=load_subject_config("HB","ccwf",root)
            c.save(root/"snapshot.json")
            self.write(root,"_DEFAULT_/c_pol.json",{"timing":{"cycle_s":90}})
            snapshot=load_config(root/"snapshot.json")
            self.assertEqual(snapshot.to_dict(),c.to_dict())
            self.assertEqual(load_subject_config("HB","ccwf",root).timing.cycle_s,90)

    def test_cli_creates_subject_and_exports_resolved_configuration(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            root=Path(tmp)
            self.assertEqual(main(["init-subject","HB","--subjects-dir",str(root)]),0)
            self.write(root,"_DEFAULT_/c_pol.json",{"timing":{"cycle_s":75}})
            target=root/"resolved.json"
            self.assertEqual(main(["validate","--subject","HB","--subjects-dir",str(root),
                                   "--save-config",str(target)]),0)
            self.assertEqual(load_config(target).timing.cycle_s,75)
            self.assertEqual(main(["init-subject","HB","--subjects-dir",str(root)]),2)
            self.assertEqual(main(["validate","--subjects-dir",str(root)]),2)

    def test_sessions_can_resolve_participants_with_relative_subject_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.write(root,"settings/_DEFAULT_/c_pol.json",{"timing":{"cycle_s":80}})
            path=self.write(root,"session.json",{"runs":[
                {"subject":"HB","mode":"ccwf","subjects_dir":"settings","run":2}]})
            c=load_session(path,root/"data")[0]
            self.assertEqual((c.subject,c.run,c.timing.cycle_s),("HB",2,80))

    def test_shipped_file_defaults_retain_all_70_builtin_protocols(self):
        for mode in all_modes():
            c=load_subject_config("TEST",mode)
            expected=defaults(mode)
            self.assertEqual(Design(c).segments,Design(expected).segments)
            self.assertEqual(c.display,expected.display)
            self.assertEqual(c.task,expected.task)
            a,b=c.stimulus.__dict__.copy(),expected.stimulus.__dict__.copy()
            for key in ("object_source","object_cache_dir"):
                a.pop(key); b.pop(key)
            self.assertEqual(a,b)


if __name__=="__main__":
    unittest.main()
