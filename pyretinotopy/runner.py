"""PsychoPy presentation with actual flip/keyboard timestamps and cleanup.

PsychoPy is imported here only. Analysis, configuration and tests remain usable
in a plain Python environment. No parallel-port or PROPixx calls are emulated.
"""
import traceback
import gc
import json

import numpy as np
from PIL import Image

from .carriers import CarrierRenderer
from .design import Design
from .geometry import Rasterizer
from .modes import parse_mode
from .outputs import reserve_run, save_run, write_json
from .stereo import apply_gamma, gamma_table, compose, eye_canvas, validate_layout
from .tasks import TaskSchedule
from .timing import AbsoluteTimeline, marker_on


class Scene:
    def __init__(self,config,design,raster,tasks):
        self.config,self.design,self.raster,self.tasks=config,design,raster,tasks
        self.mode=parse_mode(config.mode)
        self.carrier=CarrierRenderer(config,raster)
        self.key=None
        self.images=None
        self._carrier_key=None
        self._eyes=None

    def at(self,time_s):
        seg=self.design.display_at(time_s)
        target=self.tasks.active(time_s)
        marker=marker_on(self.config,seg,time_s)
        patch=target.patch if target and self.mode.task=="stimulus" else 0
        epoch=self.carrier.epoch(max(0,time_s),self.mode.carrier)
        carrier_key=(seg.components,epoch,patch)
        # Blank checker/object scenes don't need a newly generated texture.
        if not seg.components and not (self.mode.carrier=="disparity" and self.config.stimulus.dot_background
                                      and self.config.stimulus.temporal_convention=="legacy-python"):
            carrier_key=((),0,0)
        key=(carrier_key,target.index if target else None,marker)
        if key!=self.key:
            if carrier_key!=self._carrier_key:
                if carrier_key==((),0,0):
                    empty=np.zeros((self.raster.resolution,self.raster.resolution,4),dtype=np.float32)
                    self._eyes=(empty,empty)
                else:
                    self._eyes=self.carrier.render(self.mode.carrier,seg.components,max(0,time_s),patch)
                self._carrier_key=carrier_key
            fixation_dim=target is not None and self.mode.task=="fixation"
            eyes=[eye_canvas(self.config,self._eyes[i],i,fixation_dim,marker) for i in (0,1)]
            encoded=compose(*eyes,self.config.display.mode)
            if not isinstance(encoded,tuple):
                encoded=(encoded,)
            self.images=tuple(Image.fromarray(np.uint8(apply_gamma(im,self.config.display.gamma,gamma_table(self.config.display,eye))*255),"RGB")
                              for eye,im in enumerate(encoded))
            self.key=key
        return self.images,key,target,epoch


class AcquisitionCancelled(RuntimeError):
    """Operator cancelled before reserving or backing up a result directory."""


def confirm_acquisition(config):
    from psychopy import gui
    dialog=gui.Dlg(title="PyRetinotopy - acquisition settings")
    dialog.addText(f"Subject: {config.subject}   Mode: {config.mode}   Run: {config.run}")
    dialog.addText("Continue to prepare this run using the selected result policy?")
    dialog.show()
    return dialog.OK


def run(config,output_root=None,max_seconds=None,capture_path=None,existing="backup",confirm=None):
    """Run an acquisition. max_seconds/capture_path are explicit smoke-test aids."""
    config.validate(presentation=True)
    if max_seconds is not None and (not np.isfinite(max_seconds) or max_seconds<=0):
        raise ValueError("max_seconds must be positive and finite.")
    design=Design(config)
    design.check_frame_grid()
    raster=Rasterizer(config)
    validate_layout(config,raster)
    tasks=TaskSchedule(config,design)
    should_confirm=config.timing.operator_confirm if confirm is None else confirm
    if should_confirm:
        if not confirm_acquisition(config):
            raise AcquisitionCancelled("Cancelled by operator; existing results unchanged.")
    with reserve_run(output_root,config,existing) as reservation:
        return _present(config,design,raster,tasks,reservation,output_root,max_seconds,capture_path,existing)


def _present(config,design,raster,tasks,reservation,output_root,max_seconds,capture_path,existing):
    output=reservation.path
    if reservation.backup is not None:
        print(f"Previous results backed up: {reservation.backup.resolve()}",flush=True)
    print(f"Results: {output.resolve()}",flush=True)
    frames,events,windows,stimuli=[],[],[],[]
    metadata={"subject":config.subject,"mode":config.mode,"run":config.run,
              "acquisition_id":reservation.acquisition_id,"existing_results_policy":existing,
              "previous_results_backup":str(reservation.backup.resolve()) if reservation.backup is not None else None,
              "display_mode":config.display.mode,
              "result_directory":str(output.resolve()),
              "result_layout":"participant_results" if output_root is None else "explicit_root",
              "configuration_sources":getattr(config,"_configuration_sources",[]),
              "dual_sync":"independent swaps; consult eye_skew_s" if config.display.mode=="dual" else "single window swap"}
    status,error="failed",None
    pending_triggers=[]
    origin=None
    clock=None
    keyboard_device=None
    captured=False
    fast=False
    priority_active=False
    gc_suspended=False
    scene=None
    try:
        scene=Scene(config,design,raster,tasks)
        from .backend import require_backend,backend_options,dispatch_backend_events
        require_backend(config.display.backend)
        if parse_mode(config.mode).carrier=="objects":
            from .object_cache import prepare_object_movie
            movie=prepare_object_movie(config,design,raster,
                    progress=lambda n,total:print(f"Preparing object movie: {n}/{total}",flush=True))
            metadata["object_movie_cache"]=str(movie)
            metadata["object_source_format"]="native image bank / image files"
        from psychopy import core, visual, logging, __version__ as psychopy_version
        from psychopy.hardware import keyboard
        clock=core.Clock()
        flip_clock_offset=logging.defaultClock.getLastResetTime()-clock.getLastResetTime()
        metadata["flip_timestamp_source"]="PsychoPy Window.flip return, converted to the keyboard clock"
        keyboard_device=keyboard.Keyboard(clock=clock)
        metadata["psychopy"]=psychopy_version
        latest_draw_cpu_s=0
        display=config.display
        count=2 if display.mode=="dual" else 1
        backend_conf=backend_options(config)
        for i in range(count):
            win=visual.Window(size=display.size_px,screen=display.screens[i],
                    fullscr=display.full_screen,units="pix",winType=display.backend,
                    color=display.background,colorSpace="rgb1",waitBlanking=True,
                    stereo=display.mode=="shutter",allowGUI=not display.full_screen,
                    checkTiming=False,allowStencil=True,autoLog=False,backendConf=backend_conf,
                    title=f"PyRetinotopy / {config.subject} / eye {i+1}")
            windows.append(win)
            if i==0:
                from pyglet import gl
                import ctypes
                metadata["gl_renderer"]=ctypes.cast(gl.glGetString(gl.GL_RENDERER),ctypes.c_char_p).value.decode()
                metadata["gl_version"]=ctypes.cast(gl.glGetString(gl.GL_VERSION),ctypes.c_char_p).value.decode()
                if "GDI Generic" in metadata["gl_renderer"]:
                    raise RuntimeError("Hardware OpenGL is unavailable (GDI Generic). Run from the GPU-enabled local desktop; Remote Desktop may expose only software OpenGL.")
                metadata["window_backend"]=display.backend
                metadata["event_poll_outside_flip"]=display.backend=="glfw"
            if display.mode=="shutter":
                from pyglet import gl
                import ctypes
                stereo_flag=gl.GLboolean()
                gl.glGetBooleanv(gl.GL_STEREO,ctypes.byref(stereo_flag))
                if not win.stereo or not stereo_flag.value:
                    raise RuntimeError("Quad-buffer stereo is unavailable. Shutter mode cannot fall back to mono.")
            if tuple(int(v) for v in win.size)!=tuple(display.size_px):
                raise RuntimeError(f"Actual framebuffer {win.size} differs from size_px {display.size_px}; calibrate first.")
            dispatch_backend_events(display.backend)
            measured=win.getActualFrameRate(nIdentical=10,nMaxFrames=120,nWarmUpFrames=10,infoMsg=None)
            metadata[f"measured_refresh_eye_{i}"]=measured
            if measured is None:
                raise RuntimeError("Could not measure a stable display refresh rate.")
            if not display.use_measured_refresh and abs(measured-display.refresh_hz)/display.refresh_hz>0.03:
                raise RuntimeError(f"Measured {measured:.3f} Hz differs from configured {display.refresh_hz:g} Hz.")
            win.monitorFramePeriod=1.0/measured
            stimuli.append(visual.ImageStim(win,image=Image.new("RGB",display.size_px),
                         size=display.size_px,units="pix",interpolate=False,autoLog=False))
            win.mouseVisible=False
        if display.use_measured_refresh:
            measured=metadata["measured_refresh_eye_0"]
            if any(abs(metadata[f"measured_refresh_eye_{i}"]-measured)/measured>.03 for i in range(count)):
                raise RuntimeError("Physical display refresh rates do not match.")
            design.set_refresh_hz(measured)
            metadata["nominal_refresh_selected_from_measurement"]=measured
            # Store actual resolved timing before the scanner can start.
            snapshot=json.loads((output/"config.json").read_text(encoding="utf-8"))
            snapshot["display"]["refresh_hz"]=measured
            write_json(output/"config.json",snapshot)
        from .gpu import GPUScene, FAST_DISPLAYS
        use_fast=display.mode in FAST_DISPLAYS
        if use_fast:
            scene.carrier.close()
            scene=GPUScene(config,design,raster,tasks,windows)
            fast=True
            metadata["renderer"]={"checker":"gpu_masks","disparity":"gpu_dots","objects":"gpu_prepared_object_movie"}[parse_mode(config.mode).carrier]
            metadata["preloaded_mask_bytes"]=scene.preloaded_bytes
        else:
            metadata["renderer"]="software_compositor"
        # Warm the first scene before waiting for the scanner.
        first_active=next((seg.onset for seg in design.segments if seg.components),0)
        scene.at(first_active)
        scene.at(0)
        if display.high_priority:
            priority_active=True
            metadata["priority_mode_requested"]="realtime" if display.realtime_priority else "high"
            enabled=bool(core.rush(True,realtime=display.realtime_priority))
            if not enabled and display.realtime_priority:
                enabled=bool(core.rush(True))
                metadata["priority_mode_active"]="high_fallback"
            else:
                metadata["priority_mode_active"]=metadata["priority_mode_requested"] if enabled else "normal"
            metadata["high_priority_enabled"]=enabled
        if gc.isenabled():
            gc.collect()
            gc.disable()
            gc_suspended=True
            metadata["automatic_gc_suspended"]=True
        def set_images(images):
            if fast:
                return
            if display.mode=="shutter":
                # Two persistent stimuli, separate back buffers, one swap.
                if len(stimuli)==1:
                    stimuli.append(visual.ImageStim(windows[0],image=images[1],size=display.size_px,
                                    units="pix",interpolate=False,autoLog=False))
                for stim,image in zip(stimuli,images):
                    stim.setImage(image,log=False)
            else:
                for stim,image in zip(stimuli,images):
                    stim.setImage(image,log=False)

        def draw_and_flip():
            nonlocal latest_draw_cpu_s
            stamps=[]
            draw_started=clock.getTime()
            def flip(win):
                stamp=win.flip()
                if stamp is None:
                    raise RuntimeError("Window.flip returned no synchronization timestamp.")
                stamps.append(stamp+flip_clock_offset)
            if fast:
                scene.draw()
                latest_draw_cpu_s=clock.getTime()-draw_started
                for win in windows:
                    flip(win)
            elif display.mode=="shutter":
                for eye,name in enumerate(("left","right")):
                    windows[0].setBuffer(name,clear=True)
                    stimuli[eye].draw()
                latest_draw_cpu_s=clock.getTime()-draw_started
                flip(windows[0])
            else:
                # Draw both eyes before issuing either display's swap.
                for stim in stimuli:
                    stim.draw()
                latest_draw_cpu_s=clock.getTime()-draw_started
                for win in windows:
                    flip(win)
            dispatch_backend_events(display.backend)
            return stamps

        def get_keys():
            return sorted(keyboard_device.getKeys(waitRelease=False,clear=True),key=lambda key:key.rt)

        images,_,_,_=scene.at(-1)
        set_images(images)
        keyboard_device.clearEvents()
        mouse=None
        if config.timing.start=="mouse":
            from psychopy import event
            mouse=event.Mouse(win=windows[0])
        started=config.timing.start=="immediate"
        skipped=0
        while not started:
            draw_and_flip()
            for key in get_keys():
                if key.name in config.timing.abort_keys:
                    status="aborted_before_start"
                    return output
                if key.name in config.timing.trigger_keys:
                    pending_triggers.append((key.rt,key.name))
                    if config.timing.start=="trigger":
                        skipped+=1
                        if skipped>config.timing.skip_triggers:
                            started=True
                if config.timing.start=="key" and key.name in ("space","return"):
                    started=True
            if mouse is not None and mouse.getPressed()[0]:
                started=True
        last_scene_key=None
        last_flip=None
        last_segment=None
        frame=0
        hz=display.refresh_hz
        timeline=AbsoluteTimeline(hz)
        metadata["timing_reference"]="one run-onset clock; absolute cumulative deadlines for every protocol"
        limit=min(design.duration,max_seconds) if max_seconds is not None else design.duration
        if limit<=0:
            raise ValueError("max_seconds must be positive.")
        frame_limit=round(limit*hz)
        while True:
            # A missed flip does not slow down the protocol. Advance to the
            # next refresh slot on the run clock and log what was actually held.
            predicted=0 if origin is None else windows[0].getFutureFlipTime(clock=clock)-origin
            planned_frame=timeline.slot_at(predicted)
            planned=planned_frame/hz
            if planned_frame>=frame_limit:
                break
            update_started=clock.getTime()
            images,key,target,epoch=scene.at(planned)
            update_cpu_s=clock.getTime()-update_started
            if key!=last_scene_key:
                set_images(images)
                last_scene_key=key
            stamps=draw_and_flip()
            if origin is None:
                origin=stamps[0]
                events.extend({"onset":t-origin,"duration":None,"trial_type":"trigger","value":name} for t,name in pending_triggers)
            actual=stamps[0]-origin
            segment=design.display_index_at(planned)
            if segment!=last_segment:
                if last_segment is not None:
                    for ev in reversed(events):
                        if ev["trial_type"] in ("stimulus","blank"):
                            ev["duration"]=actual-ev["onset"]
                            break
                seg=design.segments[segment]
                events.append({"onset":actual,"duration":None,
                               "trial_type":"stimulus" if seg.components else "blank",
                               "value":seg.condition,"segment":segment,
                               "planned_onset":seg.onset,"onset_error_s":actual-seg.onset})
                last_segment=segment
            new_target=target is not None and target.actual_onset is None
            tasks.presented(target,actual)
            if new_target:
                events.append({"onset":actual,"duration":target.duration,"trial_type":"target","value":target.index})
            frames.append({"frame":frame,"planned_time":planned,"flip_time":actual,
                           "interval":None if last_flip is None else stamps[0]-last_flip,
                           "segment":segment,"condition":design.segments[segment].condition,
                           "carrier_epoch":epoch,"target":target.index if target else None,
                           "update_cpu_s":update_cpu_s,"draw_cpu_s":latest_draw_cpu_s,
                           "second_eye_flip_time":stamps[1]-origin if len(stamps)>1 else None,
                           "eye_skew_s":stamps[1]-stamps[0] if len(stamps)>1 else None})
            last_flip=stamps[0]
            frame+=1
            if capture_path and not captured and design.at(planned).components:
                # Capture the actual OpenGL framebuffer once, for visual QA.
                windows[0].getMovieFrame(buffer="front")
                windows[0].saveMovieFrames(str(capture_path))
                captured=True
                metadata["capture_planned_time_s"]=planned
                metadata["capture_frame"]=frame-1
            abort=False
            for pressed in get_keys():
                onset=pressed.rt-origin
                if pressed.name in config.timing.abort_keys:
                    events.append({"onset":onset,"trial_type":"abort","value":pressed.name})
                    abort=True
                elif pressed.name in config.timing.trigger_keys:
                    events.append({"onset":onset,"trial_type":"trigger","value":pressed.name})
                elif pressed.name in config.timing.response_keys:
                    response=tasks.respond(onset,pressed.name)
                    events.append({"onset":onset,"trial_type":"response","value":response["classification"]})
            if abort:
                status="aborted"
                break
            if fast and hasattr(scene,"service"):
                # Future eye textures are transferred after the current flip,
                # one eye per refresh, rather than at the next image onset.
                upload_started=clock.getTime()
                scene.service()
                frames[-1]["upload_cpu_s"]=clock.getTime()-upload_started
        if status!="aborted":
            status="completed" if max_seconds is None or max_seconds>=design.duration else "stopped_at_limit"
        # A terminal blank flip defines how long the final image was held.
        images,_,_,_=scene.at(design.duration+1)
        set_images(images)
        end_stamps=draw_and_flip()
        if origin is not None:
            end=end_stamps[0]-origin
            tasks.presented(None,end)
            for ev in reversed(events):
                if ev["trial_type"] in ("stimulus","blank"):
                    ev["duration"]=end-ev["onset"]
                    break
            events.append({"onset":end,"trial_type":"end","value":status})
            # An abort has not reached the requested run end. Keep unvisited
            # block boundaries unobserved in block_timing.tsv.
            terminal_plan=planned if status=="aborted" else limit
            frames.append({"frame":frame,"planned_time":terminal_plan,"flip_time":end,
                           "interval":end_stamps[0]-last_flip if last_flip is not None else None,
                           "segment":None,"condition":"end","carrier_epoch":None,"target":None,
                           "second_eye_flip_time":end_stamps[1]-origin if len(end_stamps)>1 else None,
                           "eye_skew_s":end_stamps[1]-end_stamps[0] if len(end_stamps)>1 else None})
    except BaseException as exc:
        status="aborted" if isinstance(exc,KeyboardInterrupt) else "failed"
        error=f"{type(exc).__name__}: {exc}"
        metadata["traceback"]=traceback.format_exc()
        raise
    finally:
        if priority_active:
            core.rush(False)
        if keyboard_device is not None:
            try:
                keyboard_device.stop()
            except Exception:
                pass
        if scene is not None:
            if hasattr(scene,"close"):
                scene.close()
            else:
                scene.carrier.close()
        # Release unused/software-path ImageStim objects before their contexts.
        while stimuli:
            stim=stimuli.pop()
            stim.win._setCurrent()
            del stim
        gc.collect()
        for win in reversed(windows):
            try:
                win.mouseVisible=True
                win.close()
            except Exception:
                pass
        if gc_suspended:
            gc.enable()
        save_run(output,config,design,tasks,frames,events,status,error,metadata)
    return output
