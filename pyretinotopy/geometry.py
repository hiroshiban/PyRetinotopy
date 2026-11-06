"""Analytic aperture/patch fields; no bitmap rotations or wraparound shifts."""
import numpy as np


class Geometry:
    def __init__(self, config):
        self.config=config

    def labels(self,x,y,components):
        s=self.config.stimulus
        ptb=s.spatial_convention=="ptb3"
        x,y=np.broadcast_arrays(np.asarray(x),np.asarray(y))
        radius=np.hypot(x,y)
        angle=np.degrees(np.arctan2(y,x))%360
        # Original excludes the central fixation footprint from stimulation.
        inner=max(s.min_radius_deg,self.config.task.fixation_radius_px/self.config.display.ppd)
        field=(radius>inner)&(radius<=s.max_radius_deg)
        ids=np.zeros(x.shape,dtype=np.int32)
        parity=np.zeros(x.shape,dtype=np.uint8)
        offset=0
        for comp in components:
            kind=comp[0]
            theta=(180-angle)%360 if kind=="wedge" and len(comp)>3 and comp[3]=="mirror_x" else angle
            clockwise=(-theta)%360
            angular=((clockwise-s.start_angle_deg+s.checker_phase_deg) if ptb else (theta+s.checker_phase_deg))%360
            opposite=np.zeros(x.shape,dtype=np.uint8)
            rows=np.floor((radius-s.min_radius_deg)/(s.max_radius_deg-s.min_radius_deg)*s.checker_rings).astype(int)
            rows=np.clip(rows,0,s.checker_rings-1)
            columns=np.floor(angular/360*s.checker_wedges).astype(int)
            cols=s.checker_wedges
            selected=field.copy()
            if kind in ("wedge","meridian"):
                start=comp[1] if kind=="wedge" else comp[1]-s.wedge_width_deg/2
                width=comp[2] if kind=="wedge" else s.wedge_width_deg
                if ptb and kind=="meridian":
                    relative=(clockwise-(comp[1]-width/2))%360
                    opposite=(relative>=180).astype(np.uint8)
                    selected &= relative%180 < width
                    checker_angle=(relative+s.checker_phase_deg)%360
                else:
                    relative=(theta-start)%360
                    if kind=="meridian":
                        relative=relative%180
                    selected &= relative < width
                    checker_angle=((width-relative+s.checker_phase_deg) if ptb else (relative+s.checker_phase_deg))%360
                columns=np.floor(checker_angle/width*s.checker_wedges).astype(int)
            elif kind=="ring":
                low,high,nominal_width=comp[1:]
                selected &= (radius>=low)&(radius<=high)
                dual=self.config.mode.startswith(("ccwexp","ccwcont","cwexp","cwcont"))
                width=s.dual_ring_width_deg if dual else s.wedge_width_deg
                wedges=s.dual_ring_checker_wedges if dual else s.checker_wedges
                cols=max(1,round(360/width*wedges))
                phase=s.dual_ring_phase_deg if dual else s.checker_phase_deg
                start=s.dual_ring_start_angle_deg if dual else s.start_angle_deg
                ring_angle=((clockwise-start+phase) if ptb else (theta+phase))%360
                columns=np.floor(ring_angle/360*cols).astype(int)
                nrings=s.dual_ring_checker_rings if dual else s.checker_rings
                rows=np.floor((radius-low)/nominal_width*nrings).astype(int)
                rows=np.clip(rows,0,nrings-1)
            elif kind=="bar":
                angle_rad=np.radians(comp[1])
                normal=x*np.cos(angle_rad)+y*np.sin(angle_rad)
                tangent=-x*np.sin(angle_rad)+y*np.cos(angle_rad)
                low=comp[2]-s.bar_width_deg/2
                selected &= (normal>=low)&(normal<low+s.bar_width_deg)
                phase=s.checker_phase_deg if ptb else 0
                if phase>360: phase%=360
                columns=np.floor((normal-low)/s.bar_width_deg*s.bar_checks_short+phase/360).astype(int)
                rows=np.floor((tangent+s.max_radius_deg)/(2*s.max_radius_deg)*s.bar_checks_long).astype(int)
                rows=np.clip(rows,0,s.bar_checks_long-1)
                cols=s.bar_checks_short
            elif kind=="multifocal":
                if ptb:
                    relative=(clockwise-s.start_angle_deg)%360
                    selected &= relative<s.wedge_width_deg
                    sector=np.floor(((relative+s.checker_phase_deg)%360)/s.wedge_width_deg*s.multifocal_sectors).astype(int)
                    columns=np.floor(angular/s.wedge_width_deg*s.checker_wedges).astype(int)
                else:
                    sector=np.floor(theta/360*s.multifocal_sectors).astype(int)
                ring=np.floor((radius-s.min_radius_deg)/(s.max_radius_deg-s.min_radius_deg)*s.multifocal_rings).astype(int)
                stride=s.multifocal_rings if s.multifocal_indexing=="ptb3" else s.multifocal_sectors
                region=sector+np.clip(ring,0,s.multifocal_rings-1)*stride
                selected &= np.isin(region,comp[1])
            elif kind in ("full","localizer"):
                if ptb:
                    selected &= (clockwise-s.start_angle_deg)%360 < s.wedge_width_deg
                    columns=np.floor(angular/s.wedge_width_deg*s.checker_wedges).astype(int)
                if kind=="localizer":
                    target=((radius>s.target_radii_deg[0])&(radius<s.target_radii_deg[1]) if ptb else
                            (radius>=s.target_radii_deg[0])&(radius<=s.target_radii_deg[1]))
                    selected &= target if comp[1]==0 else ~target
            else:
                raise ValueError(f"Unknown component {kind}")
            local=1+columns+rows*cols
            ids[selected]=local[selected]+offset
            parity[selected]=((rows+columns+opposite)%2)[selected]
            offset+=max(int(np.max(local,initial=0))+1,1)
        return ids,parity


class Rasterizer:
    def __init__(self,config,resolution=None,cache_bytes=256*1024*1024):
        self.config=config
        self.geometry=Geometry(config)
        n=int(np.ceil(2*config.stimulus.max_radius_deg*config.display.ppd)) if resolution is None else resolution
        if n<8 or n>4096:
            raise ValueError("Raster resolution must be between 8 and 4096 pixels.")
        self.resolution=n
        # Images have top row at positive visual y, never implicitly flipped.
        self.extent_deg=(n/config.display.ppd if resolution is None else 2*config.stimulus.max_radius_deg)
        axis=(np.arange(n)+0.5-n/2)/n*self.extent_deg
        self.x,self.y=np.meshgrid(axis,axis[::-1])
        self._cache={}
        self._bytes=0
        self.cache_bytes=cache_bytes

    def fields(self,components):
        if components in self._cache:
            return self._cache[components]
        value=self.geometry.labels(self.x,self.y,components)
        size=sum(a.nbytes for a in value)
        if self._bytes+size<=self.cache_bytes:
            self._cache[components]=value
            self._bytes+=size
        return value

    def checker(self,components,time_s,target_patch=0):
        ids,parity=self.fields(components)
        s=self.config.stimulus
        half=int(np.floor(time_s*s.flicker_hz*2+1e-9))
        pair=(half//2)%(len(s.colors)//2)
        colors=np.asarray(s.colors[2*pair:2*pair+2],dtype=np.float32)
        rgb=colors[parity^(half%2)].copy()
        if target_patch:
            rgb[ids==target_patch]*=self.config.task.dim_ratio
        alpha=(ids>0).astype(np.float32)
        return np.dstack((rgb,alpha))

    def mask(self,components):
        return self.fields(components)[0]>0
