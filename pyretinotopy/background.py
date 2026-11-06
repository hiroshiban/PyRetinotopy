"""Seeded static peripheral fusion guides, prepared before presentation."""
from functools import lru_cache
import math
import numpy as np


@lru_cache(maxsize=4)
def _image(size,shape,offset,patch_size,count,colors,bg,seed,kind):
    w,h=size
    image=np.empty((h,w,3),dtype=np.uint8);image[:]=np.rint(np.array(bg)*255)
    if kind=='grid':
        ph,pw=patch_size;ny,nx=count
        sy,sx=h//ny,w//nx
        if min(sy,sx)<1 or ph>sy or pw>sx:
            raise ValueError('Background patches do not fit the per-eye grid; adjust size/count.')
        rng=np.random.default_rng(np.random.SeedSequence([seed,40,0]))
        for row in range(ny):
            cy=(h%ny)/2+sy*(row+.5)
            for col in range(nx):
                cx=(w%nx)/2+sx*(col+.5)
                state=int(rng.integers(3))
                if state<2:
                    x0,y0=round(cx-pw/2),round(cy-ph/2)
                    image[y0:y0+ph,x0:x0+pw]=np.rint(np.array(colors[state])*255)
        # Clear a rectangle aligned to grid cells around the stimulus aperture.
        ah=2*sy*math.ceil(shape[0]/2/sy);aw=2*sx*math.ceil(shape[1]/2/sx)
        cx,cy=w/2+offset[0],h/2-offset[1]
        x0,x1=max(0,round(cx-aw/2)),min(w,round(cx+aw/2))
        y0,y1=max(0,round(cy-ah/2)),min(h,round(cy+ah/2))
        image[y0:y1,x0:x1]=np.rint(np.array(bg)*255)
    image.setflags(write=False)
    return image


def background_image(config,shape,eye=0):
    from .stereo import eye_size
    d=config.display
    return _image(tuple(eye_size(d)),tuple(shape),tuple(d.eye_offsets_px[eye]),
                  tuple(d.background_patch_size_px),tuple(d.background_patch_count),
                  tuple(map(tuple,d.background_patch_colors)),tuple(d.background),config.seed,d.background_type)
