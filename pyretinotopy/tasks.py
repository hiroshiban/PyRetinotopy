"""Seeded detection tasks and scoring against actual displayed flip onsets."""
from bisect import bisect_right
from dataclasses import asdict, dataclass

import numpy as np

from .carriers import epoch_rng
from .geometry import Geometry


@dataclass
class Target:
    index: int
    onset: float
    duration: float
    patch: int
    actual_onset: float = None
    actual_offset: float = None
    response_time: float = None


class TaskSchedule:
    def __init__(self,config,design):
        self.config=config
        self.targets=[]
        self.responses=[]
        self._onsets=[]
        if not config.task.enabled or design.mode.task=="none":
            return
        rng=epoch_rng(config.seed,10,0)
        if config.task.schedule=="ptb3" and design.mode.task=="fixation":
            # PTB3 first slot is normal; after a dim slot force one normal slot.
            duration=config.task.duration_s
            previous=False
            for slot in range(1,int(np.floor(design.duration/duration))):
                active=(not previous and rng.integers(config.task.fixation_frequency)==0 and rng.integers(2)==1)
                if active:self.targets.append(Target(len(self.targets),slot*duration,duration,0))
                previous=active
            self._onsets=[e.onset for e in self.targets]
            return
        t=config.timing.initial_fixation_s
        end=t+design.active_duration
        axis=np.linspace(-config.stimulus.max_radius_deg,config.stimulus.max_radius_deg,97)
        x,y=np.meshgrid(axis,axis)
        geometry=Geometry(config)
        if config.task.schedule=="ptb3" and design.mode.task=="stimulus":
            # Each position has two task windows, as in nframe_movement/2.
            # Preserve the no-consecutive-do_task rule and the random half flag.
            previous=False
            slot=0
            for segment in design.segments:
                if not segment.components:continue
                labels,_=geometry.labels(x,y,segment.components)
                visible=np.unique(labels[labels>0])
                if design.mode.family in ("hrf","meridian","lgn","localizer"):
                    window=(len(config.stimulus.colors)/2/config.stimulus.flicker_hz if design.mode.carrier=="checker" else
                            2*config.stimulus.disparity_arcmin[2]/config.stimulus.dot_refresh_hz)
                else:window=segment.duration/2
                for part in range(int(np.ceil(segment.duration/window-1e-9))):
                    half=part%2
                    selected=(slot>0 and not previous and rng.integers(2)==1)
                    flag=int(rng.integers(2))
                    if selected and flag==half and len(visible):
                        onset=segment.onset+part*window
                        duration=min(window,segment.onset+segment.duration-onset)
                        self.targets.append(Target(len(self.targets),onset,duration,int(rng.choice(visible))))
                    previous=selected;slot+=1
            self._onsets=[e.onset for e in self.targets]
            return
        while True:
            t+=rng.uniform(*config.task.interval_s)
            if t+config.task.duration_s>end:
                break
            segment=design.at(t)
            if not segment.components:
                continue
            patch=0
            if design.mode.task=="stimulus":
                # Avoid targets being cut short by a moving aperture step.
                if segment.onset+segment.duration<t+config.task.duration_s:
                    continue
                labels,_=geometry.labels(x,y,segment.components)
                visible=np.unique(labels[labels>0])
                if not len(visible):
                    continue
                patch=int(rng.choice(visible))
            target=Target(len(self.targets),float(t),config.task.duration_s,patch)
            self.targets.append(target)
        self._onsets=[e.onset for e in self.targets]

    def active(self,time_s):
        index=bisect_right(self._onsets,time_s)-1
        if index>=0:
            target=self.targets[index]
            if time_s<target.onset+target.duration:
                return target
        return None

    def presented(self,target,time_s):
        """Called after a real flip, never at the nominal scheduled onset."""
        for event in self.targets:
            if event.actual_onset is not None and event.actual_offset is None and event is not target:
                event.actual_offset=time_s
        if target is not None and target.actual_onset is None:
            target.actual_onset=time_s

    def respond(self,time_s,key):
        eligible=[e for e in self.targets if e.actual_onset is not None and
                  0<=time_s-e.actual_onset<=self.config.task.response_window_s and e.response_time is None]
        event=eligible[-1] if eligible else None
        if event:
            event.response_time=time_s
        response={"onset":time_s,"key":key,"classification":"hit" if event else "false_alarm",
                  "target":event.index if event else None,
                  "rt":time_s-event.actual_onset if event else None}
        self.responses.append(response)
        return response

    def summary(self):
        presented=[e for e in self.targets if e.actual_onset is not None]
        hits=[e for e in presented if e.response_time is not None]
        return {"planned_targets":len(self.targets),"presented_targets":len(presented),
                "unpresented_targets":len(self.targets)-len(presented),"hits":len(hits),
                "misses":len(presented)-len(hits),
                "false_alarms":sum(r["classification"]=="false_alarm" for r in self.responses)}

    def rows(self):
        return [asdict(t) for t in self.targets]
