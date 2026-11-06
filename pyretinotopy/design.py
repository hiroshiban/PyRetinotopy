"""Deterministic interval schedules, shared by display and analysis exports."""
from bisect import bisect_right
from dataclasses import dataclass
import math

import numpy as np

from .modes import parse_mode


def legacy_multifocal_design(sectors=12, rings=3):
    """Port of _DEFAULT_/c_multifocal.m: mseq(2,8,1,1), fixed tap order.

    Retains the original alternating first/last shift order. Region indexing is
    deliberately corrected to polar + eccentricity * sectors (see audit).
    """
    if sectors*rings>255:
        raise ValueError("Default multifocal m-sequence supports at most 255 regions; supply a design.")
    register=np.ones(8,dtype=np.uint8)
    sequence=[]
    for _ in range(255):
        bit=int(register[[0,1,6,7]].sum()%2)
        sequence.append(bit)
        register[1:]=register[:-1]
        register[0]=bit
    sequence=np.roll(np.asarray(sequence,dtype=np.uint8),-1)
    pending=list(range(sectors*rings))
    shifts=[]
    while pending:
        shifts.append(pending.pop(0 if len(shifts)%2==0 else -1))
    return np.stack([np.roll(sequence,-shift) for shift in shifts])


@dataclass(frozen=True)
class Segment:
    onset: float
    duration: float
    components: tuple
    condition: str


class Design:
    def __init__(self, config):
        self.config=config.validate()
        self.mode=parse_mode(config.mode)
        self.multifocal=None
        self._tracks=[]
        self.active_duration=self._build()
        self.duration=config.timing.initial_fixation_s+self.active_duration+config.timing.final_fixation_s
        boundaries={0.0,self.duration,config.timing.initial_fixation_s,
                    config.timing.initial_fixation_s+self.active_duration}
        for onset,end,_,_ in self._tracks:
            boundaries.update((onset,end))
        # Merge only machine precision noise, preserving actual sub-frame steps.
        boundaries=sorted({round(b,10) for b in boundaries})
        self.segments=[]
        for a,b in zip(boundaries,boundaries[1:]):
            if b-a<1e-9:
                continue
            mid=(a+b)/2
            tracks=[v for v in self._tracks if v[0]<=mid<v[1]]
            components=tuple(v[2] for v in tracks)
            condition="+".join(v[3] for v in tracks) or "blank"
            self.segments.append(Segment(a,b-a,components,condition))
        self.onsets=[s.onset for s in self.segments]
        self.display_onsets=[round(t*config.display.refresh_hz) for t in self.onsets]

    def _add(self, start,end,component,label):
        if end>start:
            origin=self.config.timing.initial_fixation_s
            self._tracks.append((start+origin,end+origin,component,label))

    def _phase(self,kind,cycle,rest,repeats,direction,width=None):
        s=self.config.stimulus
        step=s.dual_ring_step_angle_deg if kind=="ring" and self.mode.family=="dual" else s.step_angle_deg
        if kind=="wedge":
            count=round(360/step)
        else:
            if s.spatial_convention=="ptb3" and self.mode.family=="dual":
                # cdual.m uses the POLAR position dwell for both tracks.
                dwell=(self.config.timing.polar_cycle_s-self.config.timing.polar_rest_s)/(360/s.step_angle_deg)
                positions=(cycle-rest)/dwell
            else:
                positions=(cycle-rest)/(cycle/(360/step))
            if s.spatial_convention=="ptb3" and not math.isclose(positions,round(positions),abs_tol=1e-8):
                raise ValueError("PTB3 annulus positions must be integral; align active duration with the position dwell.")
            count=round(positions)
            if count<2:
                raise ValueError("Annulus requires at least two positions per active cycle.")
        dwell=(cycle-rest)/count
        edge=(s.max_radius_deg-s.min_radius_deg)/max(1,count-1)
        ring_width=edge*((width or s.wedge_width_deg)/step)
        for repeat in range(repeats):
            # Reversed scans place their blank before the active scan, as PTB.
            delay=rest if direction<0 else 0
            for i in range(count):
                idx=i if direction>0 else count-1-i
                a=repeat*cycle+delay+i*dwell
                if kind=="wedge":
                    # PTB generators use image y-down angles. ccw presents the
                    # COMPLETE generated array in reverse, including its first slot.
                    if s.spatial_convention=="ptb3":
                        source_index=count-1-i if direction>0 else i
                        angle=-s.start_angle_deg-source_index*step-(width or s.wedge_width_deg)
                    else:
                        angle=s.start_angle_deg+direction*i*s.step_angle_deg
                    component=("wedge",angle,width or s.wedge_width_deg)
                else:
                    center=s.min_radius_deg+idx*edge
                    component=("ring",max(s.min_radius_deg,center-ring_width/2),
                               min(s.max_radius_deg,center+ring_width/2),ring_width)
                self._add(a,a+dwell,component,f"{kind}_{i:02d}")

    def _build(self):
        s,t=self.config.stimulus,self.config.timing
        base,family=self.mode.base,self.mode.family
        if family=="polar":
            self._phase("wedge",t.cycle_s,t.rest_s,t.repeats,1 if base=="ccw" else -1)
            return t.cycle_s*t.repeats
        if family=="eccentricity":
            self._phase("ring",t.cycle_s,t.rest_s,t.repeats,1 if base=="exp" else -1)
            return t.cycle_s*t.repeats
        if family=="dual":
            def polar():
                self._phase("wedge",t.polar_cycle_s,t.polar_rest_s,t.polar_repeats,
                            1 if base.startswith("ccw") else -1)
            if s.spatial_convention=="legacy-python":
                polar()
            self._phase("ring",t.eccentricity_cycle_s,t.eccentricity_rest_s,
                        t.eccentricity_repeats,1 if base.endswith("exp") else -1,
                        s.dual_ring_width_deg)
            if s.spatial_convention=="ptb3":
                polar()  # PTB overwrites the annulus with the polar checker.
            return t.polar_cycle_s*t.polar_repeats
        if family=="bar":
            for repeat in range(t.repeats):
                for j,angle in enumerate(s.bar_angles_deg):
                    start=(repeat*len(s.bar_angles_deg)+j)*t.cycle_s
                    dwell=(t.cycle_s-t.rest_s)/s.bar_steps
                    for i in range(s.bar_steps):
                        center=s.max_radius_deg*(1-2*i/(s.bar_steps-1))
                        self._add(start+i*dwell,start+(i+1)*dwell,("bar",angle,center),f"bar_{j:02d}_{i:02d}")
            return len(s.bar_angles_deg)*t.cycle_s*t.repeats
        if family=="multifocal":
            self.multifocal=(np.asarray(s.multifocal_design,dtype=np.uint8) if s.multifocal_design
                             else legacy_multifocal_design(s.multifocal_sectors,s.multifocal_rings))
            for i in range(self.multifocal.shape[1]):
                active=tuple(int(v) for v in np.flatnonzero(self.multifocal[:,i]))
                self._add(i*t.trial_s,(i+1)*t.trial_s-t.rest_s,("multifocal",active),f"multifocal_{i:03d}")
            return self.multifocal.shape[1]*t.trial_s
        if family=="hrf":
            for i in range(t.repeats):
                self._add(i*t.cycle_s,(i+1)*t.cycle_s-t.rest_s,("full",),"hrf")
            return t.cycle_s*t.repeats
        for i in range(t.repeats*2):
            a=i*t.block_s
            if family=="meridian":
                comp=("meridian",0 if i%2==0 else 90)
            elif family=="lgn":
                if s.spatial_convention=="ptb3":
                    start=-s.start_angle_deg-s.wedge_width_deg
                    comp=("wedge",start,s.wedge_width_deg) if i%2==0 else ("wedge",start,s.wedge_width_deg,"mirror_x")
                else:
                    comp=("wedge",s.start_angle_deg+180*(i%2),s.wedge_width_deg)
            else:
                comp=("localizer",i%2)
            self._add(a,a+t.block_s-t.rest_s,comp,f"{family}_{i%2}")
        return t.block_s*t.repeats*2

    def index_at(self,t):
        if t<0 or t>=self.duration:
            return None
        return min(len(self.segments)-1,bisect_right(self.onsets,t)-1)

    def at(self,t):
        index=self.index_at(t)
        return self.segments[index] if index is not None else Segment(t,0,(),"outside")

    def display_index_at(self,t):
        """Nearest-refresh boundaries, without float comparison drift at thirds."""
        frame=round(t*self.config.display.refresh_hz)
        if frame<0 or frame>=self.frame_count():
            return None
        return min(len(self.segments)-1,bisect_right(self.display_onsets,frame)-1)

    def display_at(self,t):
        index=self.display_index_at(t)
        return self.segments[index] if index is not None else Segment(t,0,(),"outside")

    def set_refresh_hz(self,hz):
        if not math.isfinite(hz) or hz<=0:raise ValueError("Refresh rate must be positive and finite.")
        self.config.display.refresh_hz=hz
        self.display_onsets=[round(t*hz) for t in self.onsets]
        self.check_frame_grid()

    def frame_count(self,hz=None):
        return round(self.duration*(hz or self.config.display.refresh_hz))

    def block_boundaries(self):
        """Cycle/sweep/trial boundaries, all measured from the same run onset."""
        t,s=self.config.timing,self.config.stimulus
        origin=t.initial_fixation_s
        rows=[{"series":"run_start","block":0,"planned_onset_s":0.0}]
        def add(series,count,period):
            rows.extend({"series":series,"block":i+1,"planned_onset_s":origin+i*period}
                        for i in range(count))
        family=self.mode.family
        if family=="dual":
            add("polar_cycle",t.polar_repeats,t.polar_cycle_s)
            add("eccentricity_cycle",t.eccentricity_repeats,t.eccentricity_cycle_s)
        elif family=="bar":
            add("bar_sweep",len(s.bar_angles_deg)*t.repeats,t.cycle_s)
        elif family=="multifocal":
            add("multifocal_trial",self.multifocal.shape[1],t.trial_s)
        elif family in ("meridian","lgn","localizer"):
            add(family+"_block",t.repeats*2,t.block_s)
        else:
            add(family+"_cycle",t.repeats,t.cycle_s)
        rows.extend([{"series":"stimulus_end","block":0,"planned_onset_s":origin+self.active_duration},
                     {"series":"run_end","block":0,"planned_onset_s":self.duration}])
        return rows

    def check_frame_grid(self,hz=None):
        hz=hz or self.config.display.refresh_hz
        for seg in self.segments:
            if round((seg.onset+seg.duration)*hz)<=round(seg.onset*hz):
                raise ValueError(f"Segment at {seg.onset:g}s is shorter than one display frame.")

    def summary(self):
        return {"subject":self.config.subject,"run":self.config.run,"mode":self.mode.name,"carrier":self.mode.carrier,"task":self.mode.task,
                "duration_s":self.duration,"segments":len(self.segments),
                "frames":self.frame_count(),"pixels_per_degree":self.config.display.ppd,
                "angle_convention":("components: 0=right, positive=CCW, +y=up; PTB3 start parameters: clockwise"
                                    if self.config.stimulus.spatial_convention=="ptb3" else
                                    "legacy Python: 0=right, positive=CCW, +y=up"),
                "spatial_convention":self.config.stimulus.spatial_convention}
