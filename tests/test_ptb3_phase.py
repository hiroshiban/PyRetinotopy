"""Regressions for source-derived PTB3 starting positions and scan order."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from pyretinotopy.config import defaults, load_config
from pyretinotopy.design import Design
from pyretinotopy.geometry import Geometry
from pyretinotopy.modes import all_modes
from reference_ptb3 import aperture


def sample_points(n=2048):
    return np.random.default_rng(34170).uniform(-8.1,8.1,(2,n))


def comparison_times(config, design):
    # Include independent random times, every scheduled position, rest and edges.
    middle=[s.onset+s.duration*.37 for s in design.segments]
    random=np.random.default_rng(34170).uniform(0,design.duration,45)
    return np.unique(np.r_[0,random,middle,design.duration-1e-5,design.duration])


class PTB3PhaseTests(unittest.TestCase):
    def compare(self,c,times):
        d=Design(c)
        g=Geometry(c)
        x,y=sample_points()
        for t in times:
            actual=g.labels(x,y,d.at(float(t)).components)[0]>0
            expected=aperture(c,float(t),x,y,d.multifocal)
            np.testing.assert_array_equal(actual,expected,err_msg=f'{c.mode} at {t:.9g}s')

    def test_default_polar_first_centers_include_reversed_list_offset(self):
        for mode,center,step in [('cw',90,-12),('ccw',102,12)]:
            c=defaults(mode)
            d=Design(c)
            a=d.at(4.01).components[0]
            b=d.at(6.01).components[0]
            self.assertAlmostEqual((a[1]+a[2]/2)%360,center)
            self.assertAlmostEqual(b[1]-a[1],step)
            self.compare(c,np.arange(4.01,124,2))

    def test_all_70_modes_match_source_apertures_through_every_position(self):
        for mode in all_modes():
            with self.subTest(mode=mode):
                c=defaults(mode)
                self.compare(c,comparison_times(c,Design(c)))

    def test_custom_start_width_and_step_use_image_clockwise_angles(self):
        for mode in ('ccw','cw','hrff','localizerf'):
            c=defaults(mode)
            c.stimulus.start_angle_deg=17
            c.stimulus.wedge_width_deg=60
            c.stimulus.step_angle_deg=15
            c.stimulus.checker_phase_deg=23
            self.compare(c,np.arange(4.03,124,.71))

    def test_dual_ring_uses_shared_polar_dwell_and_sixteen_positions(self):
        for mode in ('ccwexp','ccwcont','cwexp','cwcont'):
            c=defaults(mode)
            d=Design(c)
            rings=[s for s in d._tracks if s[2][0]=='ring']
            self.assertEqual(len(rings),16*9)
            self.assertTrue(all(abs(end-start-2)<1e-9 for start,end,_,_ in rings))
            self.assertTrue(all(abs(comp[3]-1)<1e-9 for _,_,comp,_ in rings))
            self.compare(c,np.arange(4.01,124,.53))

    def test_reverse_rest_is_before_scan_and_forward_rest_is_after(self):
        for mode in ('ccw','cw','exp','cont'):
            c=defaults(mode)
            c.timing.rest_s=10
            self.compare(c,np.arange(.01,125,.29))

    def test_all_nine_bar_directions_and_sixteen_positions(self):
        c=defaults('barf')
        self.compare(c,np.arange(4.01,364,1.07))
        d=Design(c)
        for j,angle in enumerate(c.stimulus.bar_angles_deg):
            self.assertEqual(d.at(4+j*40+.01).components,(('bar',angle,8.0),))

    def test_custom_lgn_second_block_reflects_horizontally(self):
        c=defaults('lgnf')
        c.stimulus.start_angle_deg=25
        c.stimulus.wedge_width_deg=80
        self.compare(c,np.arange(4.01,196,.73))
        d=Design(c)
        self.assertEqual(d.at(20.01).components[0][3],'mirror_x')

    def test_multifocal_clockwise_regions_and_literal_ptb3_id_option(self):
        for indexing in ('corrected','ptb3'):
            c=defaults('multifocalf')
            c.stimulus.multifocal_indexing=indexing
            self.compare(c,4+np.arange(255)*2+.01)
        c=defaults('multifocalf')
        theta=np.deg2rad(np.tile(np.arange(12)*30+15,3))
        r=np.repeat([1.25,3.75,6.25],12)
        x,y=r*np.cos(theta),-r*np.sin(theta)
        g=Geometry(c)
        for i in range(36):
            mask=g.labels(x,y,(('multifocal',(i,)),))[0]>0
            np.testing.assert_array_equal(np.flatnonzero(mask),[i])
        c.stimulus.multifocal_indexing='ptb3'
        # The original ndivsE stride aliases first-ring region 3 and second-ring 0.
        mask=Geometry(c).labels(x,y,(('multifocal',(3,)),))[0]>0
        np.testing.assert_array_equal(np.flatnonzero(mask),[3,12])

    def test_overlap_checker_polarity_is_taken_from_wedge(self):
        c=defaults('ccwexp')
        comp=Design(c).at(10.01).components
        self.assertEqual([p[0] for p in comp],['ring','wedge'])
        x,y=sample_points(8192)
        g=Geometry(c)
        ids,p=g.labels(x,y,comp)
        ring=g.labels(x,y,(comp[0],))[0]>0
        wedge,pw=g.labels(x,y,(comp[1],))
        overlap=ring&(wedge>0)
        self.assertGreater(np.count_nonzero(overlap),0)
        np.testing.assert_array_equal(p[overlap],pw[overlap])

    def test_old_acquisition_snapshot_replay_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            c=defaults('ccwexpf')
            raw=c.to_dict()
            del raw['stimulus']['spatial_convention']
            (root/'config.json').write_text(json.dumps(raw),encoding='utf-8')
            (root/'summary.json').write_text(json.dumps({'version':'0.2.2'}),encoding='utf-8')
            old=load_config(root/'config.json')
            self.assertEqual(old.stimulus.spatial_convention,'legacy-python')
            self.assertEqual(len([s for s in Design(old)._tracks if s[2][0]=='ring']),24*9)
            raw['stimulus']['spatial_convention']='ptb3'
            (root/'config.json').write_text(json.dumps(raw),encoding='utf-8')
            self.assertEqual(load_config(root/'config.json').stimulus.spatial_convention,'ptb3')
            # A user settings file without a recorded version adopts the correction.
            del raw['stimulus']['spatial_convention']
            (root/'settings.json').write_text(json.dumps(raw),encoding='utf-8')
            self.assertEqual(load_config(root/'settings.json').stimulus.spatial_convention,'ptb3')

    def test_invalid_conventions_and_incompatible_literal_grid_fail(self):
        for attr,value in [('spatial_convention','typo'),('multifocal_indexing','typo')]:
            c=defaults()
            setattr(c.stimulus,attr,value)
            with self.assertRaises(ValueError):c.validate()
        c=defaults('multifocalf')
        c.stimulus.multifocal_indexing='ptb3'
        c.stimulus.checker_phase_deg=5
        with self.assertRaises(ValueError):c.validate()
        c=defaults('ccwexpf')
        c.timing.eccentricity_rest_s=7
        with self.assertRaisesRegex(ValueError,'integral'):Design(c)

    def test_spatial_correction_preserves_run_and_block_deadlines(self):
        for mode in all_modes():
            c=defaults(mode)
            new=Design(c)
            old=copy.deepcopy(c)
            old.stimulus.spatial_convention='legacy-python'
            old=Design(old)
            self.assertEqual(new.duration,old.duration)
            self.assertEqual(new.block_boundaries(),old.block_boundaries())


if __name__=='__main__':unittest.main()
