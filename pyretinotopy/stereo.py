"""Pixel-exact per-eye placement, followed by a separate stereo encoding step."""
import numpy as np
from PIL import Image, ImageDraw
from .fixation import fixation_layers, fixation_color
from .background import background_image


def eye_size(display):
    w,h=display.size_px
    if display.mode in ("parallel","cross","dualparallel","dualcross"):
        return w//2,h
    if display.mode in ("topbottom","bottomtop"):
        return w,h//2
    return w,h


def raster_center(display,resolution,eye):
    """Align bitmap texels to the same integer pixels as the CPU compositor."""
    w,h=eye_size(display)
    dx,dy=display.eye_offsets_px[eye]
    return (round((w-resolution)/2+dx)+resolution/2-w/2,
            h/2-round((h-resolution)/2-dy)-resolution/2)


def validate_layout(config,raster):
    d=config.display
    w,h=eye_size(d)
    n=raster.resolution
    if d.background_type=="grid":
        for eye in (0,1):background_image(config,(n,n),eye)
    for x,y in d.eye_offsets_px:
        if n+2*abs(x)>w or n+2*abs(y)>h:
            raise ValueError(f"Stimulus ({n}px) exceeds eye viewport ({w}x{h}px). "
                             "Adjust physical calibration, field radius or window size; images are never squeezed.")
    if d.mode in ("parallel","cross","dualparallel","dualcross","interleavedcolumn") and d.size_px[0]%2:
        raise ValueError("This stereo mode requires even window width.")
    if d.mode in ("topbottom","bottomtop","interleavedline") and d.size_px[1]%2:
        raise ValueError("This stereo mode requires even window height.")


def eye_canvas(config,rgba,eye,fixation_dim=False,marker=False):
    """Place an unscaled stimulus into a physical per-eye viewport.

    Mirror flags apply to the complete eye scene including fixation/marker.
    Offsets are physical pixels, x rightward, y upward.
    """
    d,k=config.display,config.task
    w,h=eye_size(d)
    bg=np.asarray(d.background,dtype=np.float32)
    canvas=background_image(config,rgba.shape[:2],eye).astype(np.float32)/255
    n,m=rgba.shape[:2]
    dx,dy=d.eye_offsets_px[eye]
    x0=round((w-m)/2+dx)
    y0=round((h-n)/2-dy)
    xa,ya=max(0,x0),max(0,y0)
    xb,yb=min(w,x0+m),min(h,y0+n)
    if xb>xa and yb>ya:
        crop=rgba[ya-y0:yb-y0,xa-x0:xb-x0]
        alpha=crop[:,:,3:4]
        canvas[ya:yb,xa:xb]=crop[:,:,:3]*alpha+bg*(1-alpha)
    image=Image.fromarray(np.uint8(np.clip(canvas*255,0,255)),"RGB")
    draw=ImageDraw.Draw(image)
    color=np.asarray(k.fixation_color)*(k.dim_ratio if fixation_dim else 1)
    color=tuple(int(round(v*255)) for v in color)
    radius=k.fixation_radius_px
    cx,cy=round(w/2+dx),round(h/2-dy)
    box=(cx-radius,cy-radius,cx+radius,cy+radius)
    if k.fixation_rendering=="ptb3":
        disk,foreground=fixation_layers(radius,k.fixation_type)
        patch=np.asarray(image).copy()
        x0,y0=cx-radius,cy-radius
        xa,ya=max(0,x0),max(0,y0);xb,yb=min(w,cx+radius),min(h,cy+radius)
        if xb>xa and yb>ya:
            alpha=disk[ya-y0:yb-y0,xa-x0:xb-x0,None]
            ink=foreground[ya-y0:yb-y0,xa-x0:xb-x0,None]
            region=patch[ya:yb,xa:xb].astype(float)
            region=region*(1-alpha)+np.asarray(d.background)*255*alpha
            region=region*(1-ink)+fixation_color(config,fixation_dim)*255*ink
            patch[ya:yb,xa:xb]=np.uint8(np.clip(np.rint(region),0,255))
        image=Image.fromarray(patch,"RGB");draw=ImageDraw.Draw(image)
    else:
        if k.fixation_type=="square":
            draw.rectangle(box,fill=color)
        elif k.fixation_type=="concentric":
            draw.ellipse(box,fill=color)
            inner=max(1,radius//2)
            draw.ellipse((cx-inner,cy-inner,cx+inner,cy+inner),fill=(0,0,0))
            draw.ellipse((cx-1,cy-1,cx+1,cy+1),fill=color)
        else:
            draw.ellipse(box,fill=color)
    if d.marker_corner:
        size=d.marker_size_px
        mx=0 if d.marker_corner in (1,3) else w-size
        my=0 if d.marker_corner in (1,2) else h-size
        draw.rectangle((mx,my,mx+size-1,my+size-1),fill=(255,255,255) if marker else (0,0,0))
    result=np.asarray(image,dtype=np.float32)/255
    if d.mirror_x[eye]:
        result=result[:,::-1]
    if d.mirror_y[eye]:
        result=result[::-1]
    return np.ascontiguousarray(result)


def compose(left,right,mode):
    """Return one canvas, or an explicit (left,right) pair for hardware outputs."""
    if left.shape!=right.shape:
        raise ValueError("Eye canvases must have identical shapes.")
    if mode=="mono":
        return left
    if mode in ("dual","shutter"):
        return left,right
    if mode in ("parallel","dualparallel"):
        return np.concatenate((left,right),axis=1)
    if mode in ("cross","dualcross"):
        return np.concatenate((right,left),axis=1)
    if mode=="topbottom":
        return np.concatenate((left,right),axis=0)
    if mode=="bottomtop":
        return np.concatenate((right,left),axis=0)
    if mode in ("interleavedline","interleavedcolumn"):
        result=right.copy()
        if mode=="interleavedline":
            result[::2]=left[::2]
        else:
            result[:,::2]=left[:,::2]
        return result
    if mode in ("redgreen","greenred","redblue","bluered"):
        # Luminance projection prevents a red carrier disappearing in a blue eye.
        # Original PTB gains retained; redblue is actually red / cyan-blue.
        luma=np.asarray([0.2126,0.7152,0.0722],dtype=np.float32)
        l=left@luma
        r=right@luma
        gains=((1,0,0),(0,.6,0)) if mode in ("redgreen","greenred") else ((.4,0,0),(0,.2,.7))
        if mode in ("greenred","bluered"):
            gains=gains[::-1]
        return np.clip(l[:,:,None]*gains[0]+r[:,:,None]*gains[1],0,1).astype(np.float32)
    raise ValueError(f"Unknown stereo encoding: {mode}")


def apply_gamma(image,gamma,table=None):
    # Software inverse-gamma LUT; do not mutate a workstation's global gamma ramp.
    image=np.clip(image,0,1)
    if table:
        lut=np.asarray(table,dtype=np.float32)
        levels=np.linspace(0,1,len(lut))
        return np.stack([np.interp(image[...,i],levels,lut[:,i]) for i in range(3)],axis=-1).astype(np.float32)
    return np.power(image,1/np.asarray(gamma,dtype=np.float32)).astype(np.float32)


def gamma_table(display,eye=0):
    return display.gamma_lut_right if display.mode=="dual" and eye==1 and display.gamma_lut_right else display.gamma_lut
