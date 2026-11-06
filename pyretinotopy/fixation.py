"""Precomputed PTB3 fixation geometry, shared by GPU and software previews."""
from functools import lru_cache
import math
import numpy as np
from PIL import Image


@lru_cache(maxsize=32)
def fixation_layers(radius,kind):
    """Return background/foreground coverage of the original three targets.

    Type 2 is the framed cross from CreateFixationImgMono, not a filled square.
    Type 3 preserves the quadrant gaps and central disk. Supersampling happens
    once, before acquisition; no image generation is added to the flip loop.
    """
    scale=4
    n=2*radius*scale
    axis=np.arange(1,n+1)-n/2
    x,y=np.meshgrid(axis,axis)
    r=np.hypot(x,y)
    background=r<=radius*scale
    if kind=='circle':foreground=r<radius*scale
    elif kind=='square':foreground=np.ones_like(background)
    elif kind=='concentric':
        foreground=(r<math.ceil(.8*radius)*scale)&(abs(x)>2*scale)&(abs(y)>2*scale)
        foreground|=r<2*scale
    elif kind=='cross':
        width=2*scale
        height=math.ceil(.4*radius)*scale
        outer=int(math.floor(2*radius*scale*math.sqrt(2)/3+.5));outer+=outer%2
        inner=int(math.floor(2*radius*scale*math.sqrt(2)/3+.5))-2*width;inner+=inner%2
        foreground=np.zeros_like(background)
        def rect(cx,cy,w,h,value=True):
            xa=max(0,int(n/2+cx-w/2));xb=min(n,int(n/2+cx+w/2))
            ya=max(0,int(n/2+cy-h/2));yb=min(n,int(n/2+cy+h/2))
            if xb>xa and yb>ya:foreground[ya:yb,xa:xb]=value
        rect(0,0,outer,outer)
        if inner>0:rect(0,0,inner,inner,False)
        for sign in (-1,1):
            rect(0,sign*outer/2,width,height)
            rect(sign*outer/2,0,height,width)
    else:raise ValueError(f'Unknown fixation type: {kind}')
    # square is a Python extension; the PTB3 types all have circular alpha.
    if kind=='square':background=np.ones_like(background)
    foreground&=background
    result=[]
    for layer in (background,foreground):
        im=Image.fromarray(np.uint8(layer)*255).resize((2*radius,2*radius),Image.Resampling.LANCZOS)
        value=np.asarray(im,dtype=np.float32)/255
        value.setflags(write=False);result.append(value)
    return tuple(result)


def fixation_color(config,dim=False):
    k=config.task
    if dim and k.fixation_rendering=='ptb3':return np.asarray(k.fixation_dim_color)
    return np.asarray(k.fixation_color)*(k.dim_ratio if dim else 1)
