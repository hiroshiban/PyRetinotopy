import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image
from scipy.io import savemat, loadmat

from pyretinotopy.carriers import CarrierRenderer, ObjectBank, dot_cloud
from pyretinotopy.config import defaults, load_config
from pyretinotopy.design import Design, legacy_multifocal_design
from pyretinotopy.export import export_windows
from pyretinotopy.geometry import Geometry, Rasterizer
from pyretinotopy.legacy import read_assignments
from pyretinotopy.modes import all_modes, parse_mode
from pyretinotopy.outputs import create_run_dir
from pyretinotopy.stereo import compose, eye_canvas, validate_layout, raster_center, eye_size
from pyretinotopy.tasks import TaskSchedule
from pyretinotopy.session import load_session
from pyretinotopy.convert_images import convert_images
from pyretinotopy.timing import AbsoluteTimeline, block_timing_rows


class DesignTests(unittest.TestCase):
    def test_bitmap_centers_match_pixel_canvas_at_odd_and_even_sizes(self):
        c=defaults()
        c.display.eye_offsets_px=[[3,-2],[-4,5]]
        for mode in ("mono","parallel","topbottom"):
            c.display.mode=mode
            w,h=eye_size(c.display)
            for n in (254,255,1031):
                for eye,(dx,dy) in enumerate(c.display.eye_offsets_px):
                    x,y=raster_center(c.display,n,eye)
                    self.assertEqual(w/2+x-n/2,round((w-n)/2+dx))
                    self.assertEqual(h/2-y-n/2,round((h-n)/2-dy))

    def test_absolute_timeline_does_not_accumulate_refresh_mismatch(self):
        deadlines=np.arange(60,1201,60)
        for actual_hz in (59.0,59.94,60.06,61.0):
            timeline=AbsoluteTimeline(60)
            observed=[]
            target=0
            for flip in np.arange(0,1201,1/actual_hz):
                slot=timeline.slot_at(float(flip))
                while target<len(deadlines) and slot>=deadlines[target]*60:
                    observed.append(flip-deadlines[target])
                    target+=1
            self.assertEqual(len(observed),len(deadlines))
            self.assertLess(max(abs(e) for e in observed),1/59)

    def test_absolute_timeline_catches_up_after_a_delay(self):
        timeline=AbsoluteTimeline(60)
        deadlines=np.arange(60,601,60)
        target=0
        errors=[]
        for flip in np.arange(0,601,1/60):
            if 240<=flip<241.4:
                continue
            slot=timeline.slot_at(float(flip))
            while target<len(deadlines) and slot>=deadlines[target]*60:
                errors.append(flip-deadlines[target])
                target+=1
        self.assertGreater(errors[3],1)
        self.assertLess(max(abs(e) for e in errors[4:]),1/60)
        self.assertEqual(AbsoluteTimeline(60).slot_at(.004),0)

    def test_every_protocol_uses_run_relative_block_boundaries(self):
        for mode in ("ccwf","cwf","expf","contf","barf","ccwexpf","ccwcontf",
                     "cwexpf","cwcontf","multifocalf","meridianf","lgnf","hrff","localizerf"):
            design=Design(defaults(mode))
            boundaries=design.block_boundaries()
            self.assertEqual(boundaries[0]["planned_onset_s"],0)
            self.assertEqual(boundaries[-1]["planned_onset_s"],design.duration)
            frames=[{"planned_time":b["planned_onset_s"],"flip_time":b["planned_onset_s"]+.003,
                     "frame":i} for i,b in enumerate(sorted(boundaries,key=lambda b:b["planned_onset_s"]))]
            errors=[row["error_s"] for row in block_timing_rows(design,frames)]
            np.testing.assert_allclose(errors,.003,atol=1e-9)

    def test_every_original_alias_builds(self):
        self.assertEqual(len(all_modes()),70)
        for mode in all_modes():
            with self.subTest(mode=mode):
                c=defaults(mode).validate()
                d=Design(c)
                self.assertGreater(d.duration,0)
                self.assertFalse(d.at(0).components)
                self.assertFalse(d.at(d.duration-0.01).components)
                self.assertAlmostEqual(sum(s.duration for s in d.segments),d.duration)
                d.check_frame_grid()

    def test_default_durations_include_all_sweeps(self):
        for mode,duration in {"ccwf":368,"expf":368,"barf":368,"ccwexpf":368,
                              "multifocalf":518,"meridianf":200,"lgnf":200,
                              "hrff":200,"localizerf":392}.items():
            self.assertAlmostEqual(Design(defaults(mode)).duration,duration)

    def test_wedge_direction_and_wraparound(self):
        for mode,direction in (("ccwf",1),("cwf",-1)):
            c=defaults(mode)
            d=Design(c)
            a=d.at(4.01).components[0][1]
            b=d.at(6.01).components[0][1]
            self.assertAlmostEqual(b-a,direction*12)
        c=defaults()
        ids,_=Geometry(c).labels(np.array([4,4]),np.array([.1,-.1]),(("wedge",350,20),))
        self.assertTrue(np.all(ids>0))

    def test_bar_angle_zero_and_ninety(self):
        c=defaults("barf")
        g=Geometry(c)
        right,_=g.labels(np.array([7.8,-7.8]),np.array([0,0]),(("bar",0,8),))
        self.assertTrue(right[0]>0 and right[1]==0)
        top,_=g.labels(np.array([0,0]),np.array([7.8,-7.8]),(("bar",90,8),))
        self.assertTrue(top[0]>0 and top[1]==0)

    def test_expansion_and_contraction_rest_position(self):
        expanding=Design(defaults("expf"))
        contracting=Design(defaults("contf"))
        self.assertTrue(expanding.at(4).components)
        self.assertFalse(expanding.at(55).components)
        self.assertFalse(contracting.at(4).components)
        self.assertTrue(contracting.at(14).components)
        self.assertLess(expanding.at(4).components[0][1],expanding.at(40).components[0][1])
        self.assertGreater(contracting.at(14).components[0][1],contracting.at(45).components[0][1])

    def test_dual_independent_periods_and_union(self):
        c=defaults("ccwexpf")
        d=Design(c)
        self.assertEqual(len(d.at(5).components),2)
        self.assertEqual(len(d.at(38).components),1)  # eccentricity rest
        raster=Rasterizer(c,64)
        components=d.at(5).components
        union=raster.mask(components)
        np.testing.assert_array_equal(union,raster.mask((components[0],))|raster.mask((components[1],)))
        c.timing.eccentricity_repeats=8
        with self.assertRaises(ValueError):
            c.validate()

    def test_msequence_balance_and_independent_shifts(self):
        design=legacy_multifocal_design()
        self.assertEqual(design.shape,(36,255))
        np.testing.assert_array_equal(design.sum(axis=1),np.full(36,128))
        self.assertEqual(len({row.tobytes() for row in design}),36)
        self.assertEqual(set(np.unique((design*2-1).astype(np.int8))),{-1,1})

    def test_multifocal_every_region_is_unique(self):
        c=defaults("multifocalf")
        g=Geometry(c)
        angles=np.radians(np.tile(np.arange(12)*30+15,3))
        radius=np.repeat([1.25,3.75,6.25],12)
        x,y=radius*np.cos(angles),-radius*np.sin(angles)
        for index in range(36):
            labels,_=g.labels(x,y,(("multifocal",(index,)),))
            self.assertEqual(np.flatnonzero(labels).tolist(),[index])

    def test_display_grid_does_not_delay_thirds_or_add_a_terminal_frame(self):
        c=defaults("expf")
        c.timing.cycle_s=40
        c.timing.rest_s=8
        d=Design(c)
        # The annulus steps every 4/3 seconds; rounding decimal boundary
        # 6.6666666667 must not delay a nominal 400/60s display slot.
        frame=400
        at=d.display_at(frame/60)
        self.assertAlmostEqual(at.onset,6.6666666667)
        c=defaults()
        c.timing.initial_fixation_s=.2
        c.timing.final_fixation_s=.2
        c.timing.cycle_s=2
        c.timing.repeats=1
        d=Design(c)
        self.assertEqual(d.frame_count(),144)
        self.assertIsNone(d.display_index_at(144/60))

    def test_localizer_target_and_complement_partition_field(self):
        c=defaults("localizerf")
        raster=Rasterizer(c,64)
        a=raster.mask((("localizer",0),))
        b=raster.mask((("localizer",1),))
        self.assertFalse(np.any(a&b))
        np.testing.assert_array_equal(a|b,raster.mask((("full",),)))


class CarrierTests(unittest.TestCase):
    def test_rds_signed_disparity_and_correspondence(self):
        c=defaults("hrfdf")
        c.display.mode="parallel"
        c.stimulus.disparity_arcmin=[-12,-12,1]
        dots=dot_cloud(c,(("full",),),0)
        self.assertGreater(len(dots.left),0)
        np.testing.assert_allclose(dots.left[:,0]-dots.right[:,0],.2)
        np.testing.assert_array_equal(dots.left[:,1],dots.right[:,1])
        np.testing.assert_array_equal(dots.left_colors,dots.right_colors)
        # The carrier is not identical in the two eye images.
        self.assertTrue(np.all(dots.left[:,0]>dots.right[:,0]))

    def test_rds_anticorrelation_and_zero_background(self):
        c=defaults("ccwdf")
        c.stimulus.dot_background=True
        c.stimulus.dot_correlation=-1
        dots=dot_cloud(c,(("wedge",0,48),),2)
        np.testing.assert_array_equal(dots.left_colors,1-dots.right_colors)
        self.assertTrue(np.any(dots.patches==0))
        self.assertTrue(np.all(dots.disparities_arcmin[dots.patches==0]==0))

    def test_randomness_reproducible_and_stream_independent(self):
        c=defaults("ccwdf")
        components=Design(c).at(5).components
        a=dot_cloud(c,components,5)
        TaskSchedule(c,Design(c))
        b=dot_cloud(c,components,5)
        np.testing.assert_array_equal(a.left,b.left)
        c.seed+=1
        other=dot_cloud(c,components,5)
        self.assertNotEqual(a.left.tobytes(),other.left.tobytes())

    def test_checker_reversal_and_patch_task(self):
        c=defaults("hrf")
        r=Rasterizer(c,64)
        components=(("full",),)
        a=r.checker(components,0)
        b=r.checker(components,1/(c.stimulus.flicker_hz*2))
        mask=r.mask(components)
        # First RGB pair is red/green and polarity reverses on each half cycle.
        np.testing.assert_allclose((a[:,:,:3]+b[:,:,:3])[mask],np.tile([1,1,0],(mask.sum(),1)))
        labels,_=r.fields(components)
        patch=int(labels[mask][0])
        dim=r.checker(components,0,patch)
        np.testing.assert_allclose(dim[:,:,:3][labels==patch],a[:,:,:3][labels==patch]*c.task.dim_ratio)
        np.testing.assert_array_equal(dim[labels!=patch],a[labels!=patch])

    def test_matlab_img_shape_and_object_stereo(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"images.mat"
            images=np.zeros((24,32,3,2),dtype=np.uint8)
            images[:,:,0,0]=255
            images[:,:,2,1]=255
            savemat(path,{"img":images})
            convert_images(path,Path(tmp)/"native")
            bank=ObjectBank(Path(tmp)/"native")
            self.assertEqual(bank.count,2)
            self.assertEqual(bank.image(0).size,(32,24))
            self.assertEqual(bank.image(1).getpixel((0,0)),(0,0,255))
            bank.close()
            c=defaults("hrfi")
            c.display.mode="parallel"
            c.stimulus.object_source=str(Path(tmp)/"native")
            c.stimulus.object_count=10
            c.stimulus.object_scale=[4,4]
            c.stimulus.object_disparity_arcmin=[-60,-60]
            renderer=CarrierRenderer(c,Rasterizer(c,64))
            left,right=renderer.render("objects",(("full",),),5)
            self.assertEqual(left.shape,(64,64,4))
            self.assertFalse(np.array_equal(left,right))
            renderer.close()


class StereoTests(unittest.TestCase):
    def test_stereo_encodings_preserve_eye_identity(self):
        l=np.full((4,6,3),.2,dtype=np.float32)
        r=np.full((4,6,3),.8,dtype=np.float32)
        for mode in ("parallel","dualparallel"):
            image=compose(l,r,mode)
            np.testing.assert_array_equal(image[:,:6],l)
            np.testing.assert_array_equal(image[:,6:],r)
        image=compose(l,r,"cross")
        np.testing.assert_array_equal(image[:,:6],r)
        image=compose(l,r,"topbottom")
        np.testing.assert_array_equal(image[:4],l)
        image=compose(l,r,"bottomtop")
        np.testing.assert_array_equal(image[:4],r)
        for mode in ("interleavedline","interleavedcolumn"):
            image=compose(l,r,mode)
            if mode.endswith("line"):
                np.testing.assert_array_equal(image[::2],l[::2])
                np.testing.assert_array_equal(image[1::2],r[1::2])
            else:
                np.testing.assert_array_equal(image[:,::2],l[:,::2])
                np.testing.assert_array_equal(image[:,1::2],r[:,1::2])
        for mode in ("dual","shutter"):
            a,b=compose(l,r,mode)
            np.testing.assert_array_equal(a,l)
            np.testing.assert_array_equal(b,r)

    def test_anaglyph_reversed_gains(self):
        l=np.ones((3,3,3),dtype=np.float32)
        r=np.zeros_like(l)
        red=compose(l,r,"redgreen")
        green=compose(l,r,"greenred")
        self.assertTrue(np.all(red[:,:,0]>.99))
        self.assertTrue(np.all(red[:,:,1:]==0))
        self.assertTrue(np.all(green[:,:,1]>.59))

    def test_mirror_and_alignment_and_no_squeezing(self):
        c=defaults()
        c.display.size_px=[80,80]
        c.task.fixation_radius_px=1
        rgba=np.zeros((8,8,4),dtype=np.float32)
        rgba[0,0]=[1,0,0,1]
        c.display.eye_offsets_px=[[4,2],[0,0]]
        a=eye_canvas(c,rgba,0)
        self.assertEqual(tuple(a[34,40]),(1,0,0))
        c.display.mirror_x[0]=True
        b=eye_canvas(c,rgba,0)
        np.testing.assert_array_equal(b,a[:,::-1])
        c.display.mode="parallel"
        with self.assertRaises(ValueError):
            validate_layout(c,Rasterizer(c,64))


class ExportAndTaskTests(unittest.TestCase):
    def test_tr_exposure_is_time_average_not_snapshot(self):
        c=defaults("hrff")
        c.timing.initial_fixation_s=1
        c.timing.final_fixation_s=0
        c.timing.cycle_s=2
        c.timing.rest_s=1
        c.timing.repeats=1
        with tempfile.TemporaryDirectory() as tmp:
            windows,metadata=export_windows(c,Path(tmp)/"window.npz",tr_s=2,resolution=32)
            mask=Rasterizer(c,32).mask((("full",),))
            np.testing.assert_allclose(windows[0][mask],.5)
            self.assertFalse(np.any(windows[1]))
            export_windows(c,Path(tmp)/"window.mat",tr_s=2,resolution=32)
            np.testing.assert_allclose(loadmat(Path(tmp)/"window.mat")["stim_windows"],windows.transpose(1,2,0))

    def test_actual_export_holds_aperture_across_a_dropped_frame(self):
        c=defaults("hrff")
        d=Design(c)
        active=d.index_at(4.1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"frames.tsv"
            path.write_text("flip_time\tsegment\n0\t0\n1\t"+str(active)+"\n2.5\tn/a\n",encoding="utf-8")
            windows,metadata=export_windows(c,Path(tmp)/"actual.npz",2,32,path)
            mask=Rasterizer(c,32).mask((("full",),))
            np.testing.assert_allclose(windows[0][mask],.5)
            np.testing.assert_allclose(windows[1][mask],.25)
            self.assertEqual(metadata["source"],"recorded_flips")

    def test_detection_scored_from_presented_not_nominal_time(self):
        c=defaults("hrff")
        tasks=TaskSchedule(c,Design(c))
        target=tasks.targets[0]
        self.assertEqual(tasks.respond(target.onset,"r")["classification"],"false_alarm")
        tasks.presented(target,target.onset+.2)
        response=tasks.respond(target.onset+.3,"r")
        self.assertEqual(response["classification"],"hit")
        self.assertAlmostEqual(response["rt"],.1)
        self.assertEqual(tasks.respond(target.onset+.4,"r")["classification"],"false_alarm")

    def test_configs_fail_for_invalid_or_misspelled_values(self):
        for edit in (lambda c:setattr(c.timing,"rest_s",c.timing.cycle_s),
                     lambda c:setattr(c.display,"width_cm",float("nan")),
                     lambda c:setattr(c,"subject","../data"),
                     lambda c:setattr(c.stimulus,"step_angle_deg",13),
                     lambda c:setattr(c.timing,"trigger_keys",["r"])):
            c=defaults()
            edit(c)
            with self.assertRaises(ValueError):
                c.validate()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.json"
            path.write_text('{"display":{"distance_cmm":96}}',encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)

    def test_reserve_acquisition_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_run_dir(tmp,defaults())
            with self.assertRaises(FileExistsError):
                create_run_dir(tmp,defaults(),existing="error")

    def test_matlab_reader_does_not_execute_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"test.m"
            path.write_text("sparam.width=48;\nsparam.startangle=-sparam.width/2-90;\nsparam.bad=system('touch unsafe');\n",encoding="utf-8")
            values,unknown=read_assignments(path)
            self.assertEqual(values["startangle"],-114)
            self.assertNotIn("bad",values)
            self.assertEqual(unknown[0]["field"],"bad")

    def test_v73_rgba_preserves_alpha_and_orientation(self):
        import h5py
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"images.mat"
            data=np.zeros((2,4,5,3),dtype=np.uint8)
            data[0,:,1,2]=[200,100,50,128]
            with h5py.File(path,"w") as f:
                f.create_dataset("img",data=data)
            # scipy cannot identify a synthetic HDF5 file without MATLAB's user
            # block, so construct a real v7.3 header in the reserved userblock.
            with h5py.File(path,"w",userblock_size=512) as f:
                f.create_dataset("img",data=data)
            header=b"MATLAB 7.3 MAT-file, Platform: test, Created by PyRetinotopy tests"
            with path.open("r+b") as f:
                f.write(header.ljust(116,b" ")+b"\x00"*8+b"\x00\x02IM")
            convert_images(path,Path(tmp)/"native")
            bank=ObjectBank(Path(tmp)/"native")
            image=bank.image(0)
            self.assertEqual(image.mode,"RGBA")
            self.assertEqual(image.size,(5,3))
            self.assertEqual(image.getpixel((1,2)),(200,100,50,128))
            bank.close()

    def test_session_rejects_duplicate_acquisitions_before_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            defaults().save(directory/"c.json")
            session=directory/"session.json"
            session.write_text(json.dumps({"runs":[{"config":"c.json"},{"config":"c.json"}]}),encoding="utf-8")
            with self.assertRaises(ValueError):
                load_session(session,directory/"data")
            session.write_text(json.dumps({"runs":[{"config":"c.json","run":1},{"config":"c.json","run":2}]}),encoding="utf-8")
            self.assertEqual([c.run for c in load_session(session,directory/"data")],[1,2])

    def test_object_stream_is_bounded_deterministic_and_consumed_once(self):
        from pyretinotopy.object_stream import ObjectStream, ImageSource
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            Image.new("RGBA",(12,12),(255,0,0,128)).save(path/"object.png")
            c=defaults("hrfi")
            c.stimulus.object_source=str(path)
            c.stimulus.object_count=3
            c.stimulus.object_cache_dir=str(path/"cache")
            c.timing.initial_fixation_s=0
            c.timing.final_fixation_s=0
            c.timing.cycle_s=2
            c.timing.rest_s=0
            c.timing.repeats=1
            raster=Rasterizer(c,32)
            stream=ObjectStream(c,Design(c),raster,capacity=4)
            try:
                frame=stream.get(0)
                self.assertIs(stream.get(0),frame)
                reference=CarrierRenderer(c,raster)
                expected=reference._object_mosaics(0)
                np.testing.assert_array_equal(frame[0].pixels,np.uint8(expected[0]*255))
                reference.close()
                source=ImageSource(32)
                source.push(frame[0])
                self.assertIs(source.getVideoFrame(),frame[0])
                self.assertIsNone(source.getVideoFrame())
                self.assertLessEqual(len(stream.frames),4)
                with self.assertRaises(RuntimeError):
                    stream.get(999)
            finally:
                stream.close()

    def test_native_bank_conversion_is_lossless_and_does_not_overwrite(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            source=path/"source.mat"
            pixels=np.random.default_rng(45).integers(0,256,(7,11,4,5),dtype=np.uint8)
            savemat(source,{"img":pixels})
            before=hashlib.sha256(source.read_bytes()).hexdigest()
            report=convert_images(source,path/"bank")
            native=np.load(path/"bank/images.npy",allow_pickle=False)
            np.testing.assert_array_equal(native,pixels.transpose(3,0,1,2))
            self.assertEqual(report["channels"],"RGBA")
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
            with self.assertRaises(FileExistsError):
                convert_images(source,path/"bank")

    def test_native_bank_rejects_legacy_live_input_and_nonpixel_arrays(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            with self.assertRaisesRegex(ValueError,"convert-images"):
                ObjectBank(path/"images.mat")
            np.save(path/"bad.npy",np.zeros((4,8,8,4),dtype=float),allow_pickle=False)
            with self.assertRaises(ValueError):
                ObjectBank(path/"bad.npy")

    def test_conversion_recreates_a_source_only_checkout_safely(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            pixels=np.random.default_rng(12).integers(0,256,(8,9,4,2),dtype=np.uint8)
            savemat(path/"source.mat",{"img":pixels})
            manifest=convert_images(path/"source.mat",path/"original")
            clone=path/"checkout"
            clone.mkdir()
            shutil.copy2(path/"original/manifest.json",clone/"manifest.json")
            (clone/"README.md").write_text("Image bank instructions",encoding="utf-8")
            result=convert_images(path/"source.mat",clone)
            self.assertEqual(result["pixels_sha256"],manifest["pixels_sha256"])
            self.assertTrue((clone/"images.npy").is_file())
            self.assertEqual((clone/"README.md").read_text(),"Image bank instructions")

    def test_prepared_movie_reuse_and_stimulus_invalidation(self):
        from pyretinotopy.object_cache import prepare_object_movie
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            Image.new("RGBA",(16,20),(200,30,100,128)).save(path/"object.png")
            c=defaults("hrfi")
            c.stimulus.object_source=str(path)
            c.stimulus.object_cache_dir=str(path/"cache")
            c.stimulus.object_count=5
            c.timing.initial_fixation_s=0
            c.timing.final_fixation_s=0
            c.timing.cycle_s=1
            c.timing.rest_s=0
            c.timing.repeats=1
            design=Design(c)
            raster=Rasterizer(c,32)
            first=prepare_object_movie(c,design,raster)
            stamp=(first/"frames.npy").stat().st_mtime_ns
            self.assertEqual(prepare_object_movie(c,design,raster),first)
            self.assertEqual((first/"frames.npy").stat().st_mtime_ns,stamp)
            movie=np.load(first/"frames.npy",allow_pickle=False)
            renderer=CarrierRenderer(c,raster)
            expected=renderer._object_mosaics(0)
            np.testing.assert_array_equal(movie[0,0],np.uint8(expected[0]*255))
            renderer.close()
            c.seed+=1
            self.assertNotEqual(prepare_object_movie(c,design,raster),first)

    def test_native_presentation_pipeline_does_not_import_legacy_io(self):
        import builtins
        from unittest.mock import patch
        from pyretinotopy.object_cache import prepare_object_movie
        real_import=builtins.__import__
        def no_legacy(name,*args,**kwargs):
            if name.split(".")[0] in ("scipy","h5py"):
                raise AssertionError("Legacy I/O imported in the native pipeline: "+name)
            return real_import(name,*args,**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            np.save(path/"bank.npy",np.full((3,16,16,4),255,dtype=np.uint8),allow_pickle=False)
            c=defaults("hrfi")
            c.stimulus.object_source=str(path/"bank.npy")
            c.stimulus.object_cache_dir=str(path/"cache")
            c.stimulus.object_count=2
            c.timing.cycle_s=1
            c.timing.rest_s=0
            c.timing.repeats=1
            with patch("builtins.__import__",side_effect=no_legacy):
                prepared=prepare_object_movie(c,Design(c),Rasterizer(c,32))
                self.assertTrue((prepared/"frames.npy").is_file())


if __name__=="__main__":
    unittest.main()
