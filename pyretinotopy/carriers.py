"""Checker, correlated RDS and object-image carriers in a common aperture."""
from dataclasses import dataclass
from bisect import bisect_right

import numpy as np
from PIL import Image, ImageDraw

from .geometry import Geometry
from .image_bank import ObjectBank


def epoch_rng(seed,stream,epoch):
    return np.random.default_rng(np.random.SeedSequence([seed,stream,max(0,int(epoch))]))


@dataclass
class DotCloud:
    left: np.ndarray
    right: np.ndarray
    left_colors: np.ndarray
    right_colors: np.ndarray
    patches: np.ndarray
    disparities_arcmin: np.ndarray


def dot_cloud(config,components,epoch,target_patch=0):
    """Cyclopean dot positions, paired eyes; negative disparity is crossed/near.

    Retains PTB's sign: negative disparity shifts left-eye dots rightward.
    Dot identity and polarity are shared across eyes; no circular image rolling.
    Background dots, when enabled, have zero disparity.
    """
    s=config.stimulus
    if not components and s.temporal_convention=="ptb3":
        return DotCloud(np.empty((0,2)),np.empty((0,2)),np.empty(0),np.empty(0),
                        np.empty(0,dtype=np.int32),np.empty(0))
    rng=epoch_rng(config.seed,20,epoch)
    area=(2*s.max_radius_deg)**2
    # Original RDSDense is the probability of a dot CENTER at each native pixel,
    # not the fraction of the display covered by the finite-radius dots.
    n=max(1,int(rng.binomial(round(area*config.display.ppd**2),s.dot_density_percent/100)))
    xy=rng.uniform(-s.max_radius_deg,s.max_radius_deg,(n,2))
    patches,parity=Geometry(config).labels(xy[:,0],xy[:,1],components)
    inside=np.hypot(xy[:,0],xy[:,1])<=s.max_radius_deg
    background=(np.ones(len(patches),dtype=bool) if s.disparity_assignment=="ptb3" else inside)
    visible=background if s.dot_background else patches>0
    xy,patches,parity=xy[visible],patches[visible],parity[visible]
    levels=np.linspace(*s.disparity_arcmin[:2],int(s.disparity_arcmin[2]))
    if s.disparity_assignment=="ptb3":
        phase=int(epoch)%len(levels)
        depth=np.where(parity==0,levels[phase],levels[len(levels)-1-phase])
        depth=np.where(patches==0,0,depth)
    else:
        # One depth per checker patch; changing the dot epoch also refreshes depths.
        depth_rng=epoch_rng(config.seed,21,epoch)
        patch_levels=depth_rng.choice(levels,max(int(patches.max(initial=0))+1,1))
        patch_levels[0]=0
        depth=patch_levels[patches]
    if target_patch:
        # A task should remain visible even when the sampled depth is zero.
        magnitude=max(abs(s.disparity_arcmin[0]),abs(s.disparity_arcmin[1]))
        sign=-1 if s.disparity_assignment=="ptb3" else np.where(depth>=0,1,-1)
        depth=np.where(patches==target_patch,sign*magnitude*config.task.depth_multiplier,depth)
    shift=depth/60/2
    left,right=xy.copy(),xy.copy()
    left[:,0]-=shift
    right[:,0]+=shift
    colors=rng.integers(0,2,len(xy)).astype(np.float32)
    right_colors=colors.copy()
    reverse=rng.random(len(xy))<(1-s.dot_correlation)/2
    right_colors[reverse]=1-right_colors[reverse]
    return DotCloud(left,right,colors,right_colors,patches,depth)


def pink_noise(shape,rng,contrast):
    """1/f amplitude noise, independent of aperture and object selection."""
    h,w=shape
    white=rng.normal(size=shape)
    fy=np.fft.fftfreq(h)[:,None]
    fx=np.fft.rfftfreq(w)[None,:]
    frequency=np.hypot(fx,fy)
    frequency[0,0]=1
    spectrum=np.fft.rfft2(white)/frequency
    spectrum[0,0]=0
    noise=np.fft.irfft2(spectrum,s=shape)
    noise=noise/max(noise.std(),1e-12)
    return np.uint8(np.clip((0.5+noise*contrast)*255,0,255))


class CarrierRenderer:
    def __init__(self,config,rasterizer):
        self.config=config
        self.raster=rasterizer
        self.bank=None
        self._object_cache={}
        from .design import Design
        active=[s for s in Design(config).segments if s.components]
        self._active_onsets=[s.onset for s in active]
        self._active_durations=[s.duration for s in active]
        self._active_totals=np.r_[0,np.cumsum(self._active_durations)]

    def active_time(self,time_s):
        i=bisect_right(self._active_onsets,time_s)-1
        if i<0:return 0.0
        return float(self._active_totals[i]+min(max(0,time_s-self._active_onsets[i]),self._active_durations[i]))

    def close(self):
        if self.bank:
            self.bank.close()

    def epoch(self,time_s,carrier):
        s=self.config.stimulus
        if carrier in ("checker","disparity") and s.temporal_convention=="ptb3":time_s=self.active_time(time_s)
        rate={"checker":2*s.flicker_hz,"disparity":s.dot_refresh_hz,"objects":1/s.object_update_s}[carrier]
        return int(np.floor(time_s*rate+1e-9))

    def render(self,carrier,components,time_s,target_patch=0):
        if carrier=="checker":
            clock=self.active_time(time_s) if self.config.stimulus.temporal_convention=="ptb3" else time_s
            rgba=self.raster.checker(components,clock,target_patch)
            return rgba,rgba
        if carrier=="disparity":
            return self._dots(components,time_s,target_patch)
        if carrier=="objects":
            return self._objects(components,time_s)
        raise ValueError(carrier)

    def _dots(self,components,time_s,target_patch):
        c,s=self.config,self.config.stimulus
        cloud=dot_cloud(c,components,self.epoch(time_s,"disparity"),target_patch)
        n=self.raster.resolution
        ppd=n/self.raster.extent_deg
        images=[]
        for positions,colors in ((cloud.left,cloud.left_colors),(cloud.right,cloud.right_colors)):
            # Transparent dots; display background is applied by the compositor.
            image=Image.new("RGBA",(n,n),(0,0,0,0))
            draw=ImageDraw.Draw(image)
            radius=max(0.5,s.dot_radius_deg*ppd)
            # Far dots first, near dots last: deterministic occlusion order.
            for i in np.argsort(-cloud.disparities_arcmin,kind="stable"):
                x=positions[i,0]*ppd+n/2
                y=-positions[i,1]*ppd+n/2
                color=tuple(int(round(v*255)) for v in s.dot_colors[int(colors[i])])
                draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(*color,255))
            images.append(np.asarray(image,dtype=np.float32)/255)
        return tuple(images)

    def _object_mosaics(self,epoch):
        if epoch in self._object_cache:
            return self._object_cache[epoch]
        c,s=self.config,self.config.stimulus
        if self.bank is None:
            self.bank=ObjectBank(s.object_source)
        n=self.raster.resolution
        ppd=n/self.raster.extent_deg
        rng=epoch_rng(c.seed,30,epoch)
        # Original i* scripts generate the RGB noise at quarter resolution and
        # enlarge it. Retain that bandwidth and avoid full-resolution FFTs in
        # the acquisition preparation thread.
        noise_rng=epoch_rng(c.seed,31,epoch)
        small=max(8,n//4)
        noise=np.stack([pink_noise((small,small),noise_rng,s.noise_contrast) for _ in range(3)],axis=2)
        noise_image=Image.fromarray(noise,"RGB").resize((n,n),Image.Resampling.BILINEAR)
        images=[noise_image.copy() for _ in range(2)]
        positions=rng.uniform(0,n,(s.object_count,2))
        sizes=rng.uniform(*s.object_scale,s.object_count)
        depths=rng.uniform(*s.object_disparity_arcmin,s.object_count)
        if c.display.mode=="mono":
            depths[:]=0
        rotations=rng.uniform(0,360,s.object_count)
        indices=rng.integers(0,self.bank.count,s.object_count)
        for i in np.argsort(-depths,kind="stable"):
            original=self.bank.image(indices[i]).convert("RGBA")
            # Original imRatio scales source pixels. Retain this meaning at the
            # native display resolution, then scale proportionally for preview.
            ratio=sizes[i]*(ppd/c.display.ppd)
            size=tuple(max(1,round(v*ratio)) for v in original.size)
            tile=original.resize(size,Image.Resampling.LANCZOS).rotate(float(rotations[i]),
                         resample=Image.Resampling.BICUBIC,expand=True,fillcolor=(0,0,0,0))
            shift=-depths[i]/60/2*ppd
            for eye,sign in enumerate((1,-1)):
                x=round(positions[i,0]+sign*shift-tile.width/2)
                y=round(positions[i,1]-tile.height/2)
                images[eye].paste(tile,(x,y),tile.getchannel("A"))
        value=tuple(np.asarray(im,dtype=np.float32)/255 for im in images)
        # Keep only the current epoch; don't accumulate full movies in RAM.
        self._object_cache={epoch:value}
        return value

    def _objects(self,components,time_s):
        mosaics=self._object_mosaics(self.epoch(time_s,"objects"))
        mask=self.raster.mask(components).astype(np.float32)
        return tuple(np.dstack((rgb,mask)) for rgb in mosaics)
