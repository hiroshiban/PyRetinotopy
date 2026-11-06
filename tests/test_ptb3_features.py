"""Experiment-facing PTB3 controls, native migration and analysis outputs."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from pyretinotopy.config import defaults,load_config
from pyretinotopy.design import Design
from pyretinotopy.fixation import fixation_layers
from pyretinotopy.geometry import Rasterizer
from pyretinotopy.legacy import migrate,read_assignments
from pyretinotopy.outputs import create_run_dir
from pyretinotopy.runner import run,Scene
from pyretinotopy.stereo import eye_canvas,apply_gamma,gamma_table,validate_layout
from pyretinotopy.tasks import TaskSchedule
from pyretinotopy.timing import marker_on
from pyretinotopy.brainvoyager import export_prt,export_olts


def prt_conditions(path):
    lines=[v.strip() for v in path.read_text().splitlines() if v.strip()]
    index=next(i for i,v in enumerate(lines) if v.startswith('NrOfConditions:'))
    n=int(lines[index].split(':')[1]);index+=1;result={}
    for _ in range(n):
        name=lines[index];count=int(lines[index+1]);index+=2
        result[name]=[tuple(map(int,v.split())) for v in lines[index:index+count]]
        index+=count
        assert lines[index].startswith('Color:');index+=1
    return result


class PTB3FeatureTests(unittest.TestCase):
    def test_numeric_fixation_types_and_original_cross_geometry(self):
        for number,name in [(1,'circle'),(2,'cross'),(3,'concentric')]:
            c=defaults();c.task.fixation_type=number;c.validate()
            self.assertEqual(c.task.fixation_type,name)
        layers={name:fixation_layers(20,name) for name in ('circle','cross','concentric','square')}
        self.assertGreater(layers['circle'][1][20,20],.9)
        self.assertLess(layers['cross'][1][20,20],.1)  # frame with tick marks; hollow center
        self.assertGreater(layers['concentric'][1][20,20],.9)
        self.assertLess(layers['concentric'][1][20,26],.1)  # horizontal quadrant gap
        self.assertGreater(layers['concentric'][1][26,26],.9)
        self.assertGreater(layers['square'][1][0,0],.9)
        self.assertLess(layers['circle'][0][0,0],.1)

    def test_fixation_dim_color_is_independent_of_stimulus_dim_ratio(self):
        c=defaults('ccwf');c.display.size_px=[80,80];c.task.fixation_color=[.8,.5,.2]
        c.task.dim_ratio=.8
        empty=np.zeros((20,20,4),dtype=np.float32)
        image=eye_canvas(c,empty,0,fixation_dim=True)
        np.testing.assert_allclose(image[40,40],[64/255]*3,atol=1/255)
        c.task.fixation_rendering='legacy-python'
        old=eye_canvas(c,empty,0,fixation_dim=True)
        self.assertGreater(float(old[40,40,0]),.6)

    def test_markers_follow_half_position_or_explicit_fixed_duration(self):
        c=defaults();segment=Design(c).at(4.01)
        self.assertTrue(marker_on(c,segment,4.99));self.assertFalse(marker_on(c,segment,5.01))
        c.display.marker_timing='fixed';c.display.marker_duration_s=.1
        self.assertTrue(marker_on(c,segment,4.09));self.assertFalse(marker_on(c,segment,4.11))
        self.assertFalse(marker_on(c,Design(c).at(0),0))

    def test_grid_guides_are_seeded_binocular_and_clear_the_aperture(self):
        c=defaults();d=c.display;d.size_px=[320,240];d.background_type='grid'
        d.background_patch_count=[12,16];d.background_patch_size_px=[8,8]
        empty=np.zeros((64,64,4),dtype=np.float32)
        left=eye_canvas(c,empty,0);right=eye_canvas(c,empty,1)
        np.testing.assert_array_equal(left,right)
        self.assertGreater(len(np.unique(left.reshape(-1,3),axis=0)),2)
        np.testing.assert_allclose(left[100:110,180:190],np.full((10,10,3),128/255),atol=1/255)
        d.mirror_x[1]=True
        np.testing.assert_array_equal(eye_canvas(c,empty,1),left[:,::-1])

    def test_invalid_grid_fails_before_archiving_an_existing_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=defaults();old=create_run_dir(tmp,c)
            (old/'keep.txt').write_text('keep')
            c.display.background_type='grid';c.display.background_patch_size_px=[9999,9999]
            with self.assertRaisesRegex(ValueError,'Background patches'):run(c,tmp,max_seconds=.1)
            self.assertEqual((old/'keep.txt').read_text(),'keep')
            self.assertFalse(any(old.parent.glob('*_old-*')))

    def test_gamma_lut_interpolates_each_channel_and_selects_physical_display(self):
        lut=[[0,.1,.2],[.25,.4,.5],[1,.8,.9]]
        actual=apply_gamma(np.array([[.25,.5,1]]),[2,2,2],lut)
        np.testing.assert_allclose(actual,[[.125,.4,.9]],atol=1e-7)
        c=defaults();c.display.mode='dual';c.display.gamma_lut=lut
        c.display.gamma_lut_right=[[0,0,0],[.5,.5,.5]]
        self.assertEqual(gamma_table(c.display,0),lut)
        self.assertEqual(gamma_table(c.display,1),c.display.gamma_lut_right)
        c.display.mode='parallel'
        with self.assertRaises(ValueError):c.validate()

    def test_object_cache_fingerprint_and_encoding_include_gamma_tables(self):
        from pyretinotopy.object_cache import movie_descriptor,encode_mosaic
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);Image.new('RGBA',(4,4),'red').save(path/'image.png')
            c=defaults('hrfi');c.stimulus.object_source=str(path)
            d=Design(c);r=Rasterizer(c,16);before=movie_descriptor(c,d,r)
            c.display.gamma_lut=[[0,0,0],[.5,.6,.7]]
            after=movie_descriptor(c,d,r)
            self.assertNotEqual(before,after)
            rgb=np.ones((2,2,3),dtype=np.float32)
            np.testing.assert_array_equal(encode_mosaic(rgb,0,c)[0,0],[127,153,178])

    def test_fixation_probability_duration_gap_and_rest_period_tasks(self):
        c=defaults('hrff');c.task.fixation_frequency=1
        d=Design(c);frequent=TaskSchedule(c,d)
        self.assertGreater(len(frequent.targets),50)
        self.assertTrue(all(t.onset>=t.duration-1e-9 for t in frequent.targets))
        self.assertTrue(all(abs(t.onset/t.duration-round(t.onset/t.duration))<1e-7 for t in frequent.targets))
        self.assertTrue(all(b.onset-a.onset>=2*c.task.duration_s-1e-8 for a,b in zip(frequent.targets,frequent.targets[1:])))
        self.assertTrue(any(not d.at(t.onset).components for t in frequent.targets))
        c.task.fixation_frequency=8;infrequent=TaskSchedule(c,d)
        self.assertLess(len(infrequent.targets),len(frequent.targets)/3)
        self.assertEqual([t.onset for t in infrequent.targets],[t.onset for t in TaskSchedule(c,d).targets])

    def test_stimulus_tasks_use_visible_patches_in_half_position_windows(self):
        c=defaults('ccw');d=Design(c);tasks=TaskSchedule(c,d)
        self.assertGreater(len(tasks.targets),0)
        for t in tasks.targets:
            segment=d.at(t.onset+1e-8)
            self.assertAlmostEqual(t.duration,segment.duration/2)
            self.assertLessEqual(t.onset+t.duration,segment.onset+segment.duration+1e-8)
            self.assertGreater(t.patch,0)

    def test_old_recorded_snapshot_keeps_released_task_and_marker_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=defaults().to_dict()
            for key in ('schedule','fixation_rendering'):del raw['task'][key]
            for key in ('temporal_convention','disparity_assignment'):del raw['stimulus'][key]
            del raw['timing']['operator_confirm']
            del raw['display']['marker_timing']
            (root/'config.json').write_text(json.dumps(raw));(root/'summary.json').write_text('{"version":"0.3.0"}')
            c=load_config(root/'config.json')
            self.assertEqual((c.task.schedule,c.task.fixation_rendering,c.display.marker_timing),('interval','legacy-python','fixed'))
            self.assertEqual(c.stimulus.spatial_convention,'ptb3')
            self.assertEqual((c.stimulus.temporal_convention,c.stimulus.disparity_assignment),('legacy-python','random'))
            self.assertFalse(c.timing.operator_confirm)

    def test_migration_maps_fixation_grid_frequency_and_missing_file_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);default=root/'_DEFAULT_';default.mkdir();subject=root/'HB';subject.mkdir()
            (default/'sizeparams.m').write_text('sparam.pix_per_cm=40;sparam.vdist=96;sparam.ipd=6.4;')
            (default/'retinotopy_display.m').write_text('dparam.ScrWidth=1280;dparam.ScrHeight=1080;dparam.start_method=0;')
            (subject/'c_pol.m').write_text('sparam.fixtype=2;sparam.fixtaskfreq=7;sparam.bgtype=2;sparam.patch_size=[8,8];sparam.patch_num=[12,16];sparam.patch_color1=[200,100,50];')
            report=migrate(subject,'ccwf',root/'migrated.json');c=load_config(root/'migrated.json')
            self.assertEqual(c.task.fixation_type,'cross');self.assertEqual(c.task.fixation_frequency,7)
            self.assertEqual(c.display.background_type,'grid');self.assertEqual(c.timing.start,'key')
            np.testing.assert_allclose(c.display.background_patch_colors[0],[200/255,100/255,50/255])
            self.assertEqual(len(report['source_files']),3)
            self.assertTrue(any('_DEFAULT_' in p for p in report['source_files']))

    def test_static_matlab_reader_handles_safe_size_math_and_color_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'settings.m';p.write_text('sparam.colors=[128,128,128;255,0,0;0,255,0];\nsparam.bgcolor=sparam.colors(1,:);\nsparam.waitframes=60/(size(sparam.colors,1)-1);\nsparam.evil=system(1);')
            values,unresolved=read_assignments(p)
            self.assertEqual(values['bgcolor'],[128,128,128]);self.assertEqual(values['waitframes'],30)
            self.assertEqual([v['field'] for v in unresolved],['evil'])

    def test_prt_uses_current_run_and_inclusive_volume_intervals(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=defaults('cw');c.run=3
            p=export_prt(c,Path(tmp)/'cw.prt',unit='Volumes')
            self.assertIn('run 3',p.read_text())
            conditions=prt_conditions(p)
            self.assertEqual(len(conditions),31)
            self.assertEqual(conditions['Fixation'],[(1,2),(183,184)])
            first=conditions['polar_center_090.000deg']
            self.assertEqual(first,[(3,3),(33,33),(63,63),(93,93),(123,123),(153,153)])

    def test_multifocal_prt_exports_each_independent_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=defaults('multifocalf');p=export_prt(c,Path(tmp)/'mf.prt')
            conditions=prt_conditions(p);self.assertEqual(len(conditions),37)
            for i in range(36):self.assertEqual(sum(b-a for a,b in conditions[f'region_{i+1:02d}']),256000)

    def test_actual_prt_holds_state_across_a_missed_flip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c=defaults('ccw');d=Design(c)
            frames=root/'frames.tsv'
            with frames.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,['flip_time','segment'],delimiter='\t');writer.writeheader()
                writer.writerows([{'flip_time':0,'segment':0},{'flip_time':4.01,'segment':1},{'flip_time':7.25,'segment':None}])
            p=export_prt(c,root/'actual.prt',frames)
            conditions=prt_conditions(p)
            self.assertEqual(conditions['Fixation'],[(0,4010)])
            self.assertEqual(conditions['polar_center_102.000deg'],[(4010,7250)])
            with self.assertRaisesRegex(ValueError,'align to TR'):export_prt(c,root/'bad.prt',frames,unit='Volumes')
            self.assertFalse((root/'bad.prt').exists())

    def test_six_original_olt_files_copy_without_edits_or_overwriting(self):
        import pyretinotopy
        original=Path(pyretinotopy.__file__).parent/'data/brainvoyager'
        with tempfile.TemporaryDirectory() as tmp:
            files=export_olts(tmp);self.assertEqual(len(files),6)
            for p in files:
                self.assertEqual(p.read_bytes(),(original/p.name).read_bytes())
                self.assertEqual(len([s for s in p.read_text().splitlines() if s.startswith('Color')]),20)
            with self.assertRaises(FileExistsError):export_olts(tmp)

    def test_measured_refresh_updates_frame_grid_without_moving_deadlines(self):
        c=defaults('ccwf');d=Design(c);before=d.block_boundaries()
        d.set_refresh_hz(59.94)
        self.assertEqual(d.block_boundaries(),before)
        self.assertEqual(d.display_onsets,[round(t*59.94) for t in d.onsets])
        self.assertEqual(d.frame_count(),round(368*59.94))
        with self.assertRaises(ValueError):d.set_refresh_hz(0)

    def test_checker_clock_starts_on_first_color_and_pauses_during_rest(self):
        from pyretinotopy.carriers import CarrierRenderer
        c=defaults('barf');r=Rasterizer(c,32);renderer=CarrierRenderer(c,r)
        try:
            self.assertEqual(renderer.epoch(4,'checker'),0)
            self.assertEqual(renderer.epoch(36,'checker'),256)
            self.assertEqual(renderer.epoch(44,'checker'),256)
            comp=Design(c).at(4.01).components
            actual=renderer.render('checker',comp,4.01)[0]
            expected=r.checker(comp,.01)
            np.testing.assert_array_equal(actual,expected)
        finally:renderer.close()

    def test_ptb_rds_uses_opposing_checker_planes_and_cycles_all_steps(self):
        from pyretinotopy.carriers import dot_cloud
        from pyretinotopy.geometry import Geometry
        c=defaults('hrfdf');comp=(('full',),)
        for epoch in range(5):
            cloud=dot_cloud(c,comp,epoch)
            cyclopean=(cloud.left+cloud.right)/2
            _,parity=Geometry(c).labels(cyclopean[:,0],cyclopean[:,1],comp)
            levels=np.linspace(-12,12,5)
            expected=np.where(parity==0,levels[epoch],levels[4-epoch])
            np.testing.assert_array_equal(cloud.disparities_arcmin,expected)
        c.stimulus.dot_background=True
        cloud=dot_cloud(c,comp,0)
        xy=(cloud.left+cloud.right)/2
        self.assertTrue(np.any(np.hypot(xy[:,0],xy[:,1])>c.stimulus.max_radius_deg))
        np.testing.assert_array_equal(cloud.disparities_arcmin[cloud.patches==0],0)
        self.assertEqual(len(dot_cloud(c,(),0).left),0)  # PTB3 rest periods remain blank

    def test_source_default_temporal_rates(self):
        for mode,flicker,refresh in [('ccwf',5,10),('barf',4,8),('multifocalf',5,10),
                                     ('meridianf',5,10),('lgnf',3.75,7.5),('hrff',3.75,7.5),('localizerf',5,10)]:
            c=defaults(mode)
            self.assertEqual((c.stimulus.flicker_hz,c.stimulus.dot_refresh_hz),(flicker,refresh))

    def test_operator_cancel_preserves_existing_results_before_backup(self):
        from unittest.mock import patch
        from pyretinotopy.runner import AcquisitionCancelled
        with tempfile.TemporaryDirectory() as tmp:
            c=defaults();path=create_run_dir(tmp,c);old=(path/'config.json').read_bytes()
            with patch('pyretinotopy.runner.confirm_acquisition',return_value=False) as dialog:
                with self.assertRaises(AcquisitionCancelled):run(c,tmp,max_seconds=.1)
                dialog.assert_called_once()
            self.assertEqual((path/'config.json').read_bytes(),old)
            self.assertFalse(any(path.parent.glob('*_old-*')))


if __name__=='__main__':unittest.main()
