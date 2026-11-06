"""Independent continuous-coordinate aperture oracle translated from PTB3 source.

References: Presentation/cretinotopy.m, cdual.m, cbar.m, cmeridian.m,
clgnlocalizer.m, cmultifocal.m, chrf.m, clocalizer.m; Generation/pol_*,
ecc_*, bar_*, mf_*. This oracle never calls the port's Design or Geometry.
Pixel-grid/ceil boundaries and the fixation footprint are excluded from claims
of MATLAB framebuffer equality. Multifocal may use either the corrected stride
or the actual original zero-phase ndivsE stride, according to configuration.
"""
import math
import numpy as np
from pyretinotopy.modes import parse_mode


def aperture(config,time_s,x,y,design=None):
    s,t=config.stimulus,config.timing
    mode=parse_mode(config.mode)
    x,y=np.broadcast_arrays(np.asarray(x),np.asarray(y))
    radius=np.sqrt(x*x+y*y)
    theta=np.mod(np.arctan2(-y,x)*180/np.pi,360)  # MATLAB image y is downward
    field=(radius>max(s.min_radius_deg,config.task.fixation_radius_px/config.display.ppd))&(radius<=s.max_radius_deg)
    zero=np.zeros(x.shape,dtype=bool)
    time=time_s-t.initial_fixation_s
    if time<0: return zero
    if mode.family=='bar': duration=len(s.bar_angles_deg)*t.cycle_s*t.repeats
    elif mode.family=='dual': duration=t.polar_cycle_s*t.polar_repeats
    elif mode.family=='multifocal':
        if design is None: raise ValueError('Supply the fixed multifocal design, not a spatial mask')
        duration=design.shape[1]*t.trial_s
    elif mode.family in ('meridian','lgn','localizer'): duration=t.block_s*2*t.repeats
    else: duration=t.cycle_s*t.repeats
    if time>=duration: return zero

    def polar(start,width,mirror=False):
        angle=np.mod(np.arctan2(-y,-x if mirror else x)*180/np.pi,360)
        return field&(np.mod(angle-start,360)<width)

    def track(kind,period,rest,reverse,width,dual=False):
        phase=time%period
        delay=rest if reverse else 0
        if not delay<=phase<delay+period-rest: return zero
        if kind=='polar': n=round(360/s.step_angle_deg)
        elif dual: n=round((360/s.step_angle_deg)*(period-rest)/(t.polar_cycle_s-t.polar_rest_s))
        else: n=round((period-rest)/(period/(360/s.step_angle_deg)))
        k=min(n-1,math.floor((phase-delay)/((period-rest)/n)))
        if kind=='polar':
            # ccw reverses the entire pre-generated clockwise array.
            index=n-1-k if reverse is False else k
            return polar(s.start_angle_deg+index*s.step_angle_deg,width)
        index=n-1-k if reverse else k
        edge=(s.max_radius_deg-s.min_radius_deg)/(n-1)
        step=s.dual_ring_step_angle_deg if dual else s.step_angle_deg
        thickness=edge*width/step
        center=s.min_radius_deg+index*edge
        return field&(radius>=max(s.min_radius_deg,center-thickness/2))&(radius<=min(s.max_radius_deg,center+thickness/2))

    if mode.family=='polar':
        # Rest-before applies to cw, while image-list reversal applies to ccw.
        return track('polar',t.cycle_s,t.rest_s,mode.base=='cw',s.wedge_width_deg)
    if mode.family=='eccentricity':
        return track('ring',t.cycle_s,t.rest_s,mode.base=='cont',s.wedge_width_deg)
    if mode.family=='dual':
        return (track('polar',t.polar_cycle_s,t.polar_rest_s,mode.base.startswith('cw'),s.wedge_width_deg,True)|
                track('ring',t.eccentricity_cycle_s,t.eccentricity_rest_s,mode.base.endswith('cont'),s.dual_ring_width_deg,True))
    if mode.family=='bar':
        sweep=int(time//t.cycle_s)%len(s.bar_angles_deg)
        phase=time%t.cycle_s
        if phase>=t.cycle_s-t.rest_s: return zero
        k=min(s.bar_steps-1,int(phase/((t.cycle_s-t.rest_s)/s.bar_steps)))
        position=np.linspace(s.max_radius_deg,-s.max_radius_deg,s.bar_steps)[k]
        a=np.deg2rad(s.bar_angles_deg[sweep])
        normal=x*np.cos(a)-(-y)*np.sin(a)
        tangent=x*np.cos(a+np.pi/2)-(-y)*np.sin(a+np.pi/2)
        return field&(abs(tangent)<=s.max_radius_deg)&(normal>=position-s.bar_width_deg/2)&(normal<position+s.bar_width_deg/2)
    if mode.family=='multifocal':
        trial=int(time//t.trial_s)
        if time%t.trial_s>=t.trial_s-t.rest_s:return zero
        relative=np.mod(theta-s.start_angle_deg+s.checker_phase_deg,360)
        sector=np.floor(relative/s.wedge_width_deg*s.multifocal_sectors).astype(int)
        ring=np.floor((radius-s.min_radius_deg)/(s.max_radius_deg-s.min_radius_deg)*s.multifocal_rings).astype(int)
        stride=s.multifocal_rings if s.multifocal_indexing=='ptb3' else s.multifocal_sectors
        region=sector+np.clip(ring,0,s.multifocal_rings-1)*stride
        return field&(np.mod(theta-s.start_angle_deg,360)<s.wedge_width_deg)&np.isin(region,np.flatnonzero(design[:,trial]))
    if mode.family=='hrf':
        return polar(s.start_angle_deg,s.wedge_width_deg) if time%t.cycle_s<t.cycle_s-t.rest_s else zero
    block=int(time//t.block_s)
    if time%t.block_s>=t.block_s-t.rest_s:return zero
    if mode.family=='meridian':
        start=-s.wedge_width_deg/2+90*(block%2)
        return polar(start,s.wedge_width_deg)|polar(start+180,s.wedge_width_deg)
    if mode.family=='lgn':
        return polar(s.start_angle_deg,s.wedge_width_deg,bool(block%2))
    target=(radius>s.target_radii_deg[0])&(radius<s.target_radii_deg[1])
    return polar(s.start_angle_deg,s.wedge_width_deg)&(target if block%2==0 else ~target)
