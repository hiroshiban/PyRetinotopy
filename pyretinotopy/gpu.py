"""PsychoPy GPU renderer: preloaded checker masks and batched stereo dots.

The software compositor remains the reference for previews and interleaving.
No full-screen image is rebuilt for checker color reversals or fixation tasks.
"""
import numpy as np
from PIL import Image

from .carriers import CarrierRenderer, dot_cloud
from .modes import parse_mode
from .stereo import eye_size, raster_center, apply_gamma, gamma_table
from .fixation import fixation_layers, fixation_color
from .background import background_image
from .timing import marker_on


FAST_DISPLAYS={"mono","parallel","cross","dualparallel","dualcross","dual",
               "shutter","topbottom","bottomtop","redgreen","greenred","redblue","bluered",
               "interleavedline","interleavedcolumn"}


class GPUScene:
    def __init__(self,config,design,raster,tasks,windows):
        from psychopy import visual
        self.visual=visual
        self.config,self.design,self.raster,self.tasks=config,design,raster,tasks
        self.mode=parse_mode(config.mode)
        self.windows=windows
        self.bitmap_centers=[raster_center(config.display,raster.resolution,eye) for eye in (0,1)]
        self.carrier=CarrierRenderer(config,raster)
        self.key=None
        self.target=None
        self.time=0
        self.epoch=0
        self.components=()
        self._dot_key=None
        self._cloud=None
        self._object_epoch=None
        self._object_stream=None
        self._object_textures=None
        if self.mode.carrier=="objects":
            from .object_stream import ObjectStream
            self._object_stream=ObjectStream(config,design,raster)
        self.resources=[]
        self.preloaded_bytes=0
        unique={seg.components for seg in design.segments if seg.components}
        estimate=len(unique)*2*raster.resolution**2*len(windows)
        if self.mode.carrier=="checker" and estimate>config.display.gpu_mask_limit_mb*1024*1024:
            raise ValueError(f"Checker mask preload needs approximately {estimate/1024**2:.0f} MiB; "
                             "review GPU memory and gpu_mask_limit_mb before presentation.")
        for win in windows:
            resource={"checks":{},"targets":{}}
            if config.display.mode in ("interleavedline","interleavedcolumn"):
                w,h=config.display.size_px
                pattern=(np.indices((h,w))[0 if config.display.mode=="interleavedline" else 1]%2)==0
                resource["stripes"]=tuple(self._fullscreen_mask(win,pattern if eye==0 else ~pattern) for eye in (0,1))
            resource["background"]=visual.Rect(win,width=1,height=1,units="pix",lineColor=None,
                                               fillColor=config.display.background,colorSpace="rgb1",autoLog=False)
            if config.display.background_type=="grid":
                resource["fusion_guides"]=[]
                for eye in (0,1):
                    rgb=background_image(config,(raster.resolution,raster.resolution),eye).astype(np.float32)/255
                    bitmap=Image.fromarray(np.uint8(self._color(rgb,eye)*255),"RGB")
                    resource["fusion_guides"].append(visual.ImageStim(win,image=bitmap,size=eye_size(config.display),
                        units="pix",interpolate=False,autoLog=False))
            if config.task.fixation_rendering=="ptb3":
                resource["fixation_layers"]=tuple(self._mask(win,v) for v in fixation_layers(
                    config.task.fixation_radius_px,config.task.fixation_type))
            radius=config.task.fixation_radius_px
            if config.task.fixation_type=="square":
                fix=visual.Rect(win,width=radius*2,height=radius*2,lineColor=None,units="pix",autoLog=False)
            else:
                fix=visual.Circle(win,radius=radius,edges=64,lineColor=None,units="pix",autoLog=False)
            resource["fixation"]=fix
            resource["inner"]=visual.Circle(win,radius=max(1,radius//2),edges=64,lineColor=None,
                                            fillColor="black",units="pix",autoLog=False)
            resource["center"]=visual.Circle(win,radius=1,edges=32,lineColor=None,units="pix",autoLog=False)
            resource["marker"]=visual.Rect(win,width=config.display.marker_size_px,height=config.display.marker_size_px,
                                             units="pix",lineColor=None,autoLog=False)
            if self.mode.carrier=="checker":
                for components in unique:
                    labels,parity=raster.fields(components)
                    resource["checks"][components]=tuple(self._mask(win,(labels>0)&(parity==p)) for p in (0,1))
                for target in tasks.targets:
                    if not target.patch:
                        continue
                    comp=design.at(target.onset).components
                    labels,parity=raster.fields(comp)
                    key=(comp,target.patch)
                    if key not in resource["targets"]:
                        resource["targets"][key]=tuple(self._mask(win,(labels==target.patch)&(parity==p),crop=True) for p in (0,1))
            elif self.mode.carrier=="disparity":
                s=config.stimulus
                pixels=round((2*s.max_radius_deg*config.display.ppd)**2)
                mean=pixels*s.dot_density_percent/100
                capacity=int(np.ceil(mean+10*np.sqrt(mean)+20))
                resource["dot_capacity"]=capacity
                resource["dots"]=visual.ElementArrayStim(win,units="pix",nElements=capacity,
                      fieldShape="square",fieldSize=config.display.size_px,xys=np.zeros((capacity,2)),
                      sizes=s.dot_radius_deg*2*config.display.ppd,colors=np.ones((capacity,3)),
                      colorSpace="rgb1",opacities=np.zeros(capacity),elementTex=None,elementMask="circle",
                      interpolate=False,autoLog=False)
            elif self.mode.carrier=="objects":
                resource["apertures"]={components:self._mask(win,raster.mask(components)) for components in unique}
            self.resources.append(resource)
        if self.mode.carrier=="objects":
            from .object_textures import ObjectTextures
            self._object_textures=ObjectTextures(config,self._object_stream,windows,raster.resolution)

    def _mask(self,win,selected,crop=False):
        n=selected.shape[0]
        x0,y0,x1,y1=0,0,n,n
        if crop:
            ys,xs=np.nonzero(selected)
            if not len(ys):
                return None
            x0,x1=int(xs.min()),int(xs.max())+1
            y0,y1=int(ys.min()),int(ys.max())+1
        # PsychoPy 2024.2's PIL-L alpha upload changes dataType to float and
        # subsequently reads it as bytes. RGB input follows its safe L conversion
        # path and uploads an actual unsigned-byte mask (verified on screen).
        bitmap=Image.fromarray(np.uint8(np.clip(selected[y0:y1,x0:x1],0,1)*255),"L").convert("RGB")
        self.preloaded_bytes+=bitmap.width*bitmap.height
        stim=self.visual.ImageStim(win,image=np.ones((1,1),dtype=np.float32),mask=bitmap,
                    size=(x1-x0,y1-y0),units="pix",interpolate=False,autoLog=False,colorSpace="rgb1")
        offset=((x0+x1)/2-n/2,n/2-(y0+y1)/2)
        return stim,offset

    def _fullscreen_mask(self,win,selected):
        h,w=selected.shape
        bitmap=Image.fromarray(np.uint8(selected)*255,"L").convert("RGB")
        return self.visual.ImageStim(win,image=np.ones((1,1),dtype=np.float32),mask=bitmap,
                                     size=(w,h),units="pix",interpolate=False,autoLog=False)

    def _update_objects(self):
        if self._object_epoch==self.epoch:
            return
        pairs=self._object_textures.activate(self.epoch)
        for resource,images in zip(self.resources,pairs):
            resource["mosaics"]=images
        self._object_epoch=self.epoch

    def service(self):
        if self._object_textures:
            self._object_textures.service(self.epoch)

    def at(self,time_s):
        self.time=time_s
        segment=self.design.display_at(time_s)
        self.components=segment.components
        self.target=self.tasks.active(time_s)
        self.marker=marker_on(self.config,segment,time_s)
        self.epoch=self.carrier.epoch(max(0,time_s),self.mode.carrier)
        patch=self.target.patch if self.target and self.mode.task=="stimulus" else 0
        self.key=(self.components,self.epoch,patch,self.target.index if self.target else None,self.marker)
        if self.mode.carrier=="disparity":
            dotkey=(self.components,self.epoch,patch)
            if self._dot_key!=dotkey:
                self._cloud=dot_cloud(self.config,self.components,self.epoch,patch)
                self._dot_key=dotkey
        if self.mode.carrier=="objects" and self.components:
            self._update_objects()
        return None,self.key,self.target,self.epoch

    def _placement(self,eye):
        d=self.config.display
        w,h=d.size_px
        ew,eh=eye_size(d)
        index=eye
        if d.mode in ("cross","dualcross","bottomtop"):
            index=1-eye
        if d.mode in ("parallel","cross","dualparallel","dualcross"):
            center=(w*(index-.5)/2,0)
        elif d.mode in ("topbottom","bottomtop"):
            center=(0,h*(.5-index)/2)
        else:
            center=(0,0)
        offset=d.eye_offsets_px[eye]
        sign=(-1 if d.mirror_x[eye] else 1,-1 if d.mirror_y[eye] else 1)
        position=(center[0]+sign[0]*offset[0],center[1]+sign[1]*offset[1])
        return center,position,sign,(ew,eh)

    def _color(self,color,eye):
        d=self.config.display
        value=np.asarray(color,dtype=np.float32)
        if d.mode in ("redgreen","greenred","redblue","bluered"):
            gains=((1,0,0),(0,.6,0)) if d.mode in ("redgreen","greenred") else ((.4,0,0),(0,.2,.7))
            if d.mode in ("greenred","bluered"):
                gains=gains[::-1]
            value=(value@np.asarray([.2126,.7152,.0722]))[...,None]*gains[eye]
        return apply_gamma(value,d.gamma,gamma_table(d,eye))

    def _draw_mask(self,item,color,eye,position,sign):
        if item is None:
            return
        stim,offset=item
        stim.pos=(position[0]+sign[0]*offset[0],position[1]+sign[1]*offset[1])
        stim.flipHoriz=sign[0]<0
        stim.flipVert=sign[1]<0
        stim.setColor(self._color(color,eye),colorSpace="rgb1",log=False)
        stim.draw()

    def draw(self):
        """Draw each eye without flipping; the runner records each output swap."""
        from pyglet import gl
        d,s,k=self.config.display,self.config.stimulus,self.config.task
        if d.mode in ("redgreen","greenred","redblue","bluered"):
            # Clear unused channels too (e.g. blue in red/green). Otherwise the
            # window's gray clear color survives and contaminates both eyes.
            win=self.windows[0]
            win._setCurrent()
            win.scissor=(0,0,*d.size_px)
            gl.glColorMask(True,True,True,True)
            background=self.resources[0]["background"]
            background.pos=(0,0)
            background.size=d.size_px
            background.setFillColor(apply_gamma(np.array([0,0,0]),d.gamma,d.gamma_lut),colorSpace="rgb1",log=False)
            background.draw()
        count=1 if d.mode=="mono" else 2
        for eye in range(count):
            win_index=eye if d.mode=="dual" else 0
            win=self.windows[win_index]
            resource=self.resources[win_index]
            # PsychoPy uses this context switch internally in every Stim.draw.
            # It is also needed before our stencil/scissor commands in dual mode.
            win._setCurrent()
            if d.mode=="shutter":
                win.setBuffer("left" if eye==0 else "right",clear=True)
            center,position,sign,(ew,eh)=self._placement(eye)
            bitmap_position=tuple(center[i]+sign[i]*self.bitmap_centers[eye][i] for i in (0,1))
            win.scissor=(round(center[0]+d.size_px[0]/2-ew/2),round(center[1]+d.size_px[1]/2-eh/2),ew,eh)
            win.scissorTest=True
            clipping=d.mode in ("interleavedline","interleavedcolumn") or self.mode.carrier=="objects"
            if clipping:
                win.stencilTest=True
                gl.glStencilMask(255)
                gl.glClearStencil(0)
                gl.glClear(gl.GL_STENCIL_BUFFER_BIT)
                gl.glColorMask(False,False,False,False)
                gl.glEnable(gl.GL_ALPHA_TEST)
                gl.glAlphaFunc(gl.GL_GREATER,.5)
                gl.glStencilOp(gl.GL_KEEP,gl.GL_KEEP,gl.GL_REPLACE)
                bits=0
                if "stripes" in resource:
                    gl.glStencilMask(1)
                    gl.glStencilFunc(gl.GL_ALWAYS,1,255)
                    resource["stripes"][eye].draw()
                    bits|=1
                if self.mode.carrier=="objects" and self.components:
                    gl.glStencilMask(2)
                    gl.glStencilFunc(gl.GL_ALWAYS,2,255)
                    self._draw_mask(resource["apertures"][self.components],[1,1,1],eye,bitmap_position,sign)
                    bits|=2
                gl.glDisable(gl.GL_ALPHA_TEST)
                gl.glColorMask(True,True,True,True)
                gl.glStencilMask(0)
                # Objects' background is full viewport, then aperture clipping
                # is selected below only for noise and objects.
                gl.glStencilFunc(gl.GL_EQUAL,bits&1,1 if bits&1 else 0)
                gl.glStencilOp(gl.GL_KEEP,gl.GL_KEEP,gl.GL_KEEP)
            # Draw activates the window context before a GL color mask is set.
            bg=resource["background"]
            bg.pos=center
            bg.size=(ew,eh)
            bg.setFillColor(self._color(d.background,eye),colorSpace="rgb1",log=False)
            if d.mode in ("redgreen","greenred","redblue","bluered"):
                red_eye=eye==(0 if d.mode in ("redgreen","redblue") else 1)
                channels=np.array([1,0,0],dtype=bool) if red_eye else np.array([0,1,int(d.mode in ("redblue","bluered"))],dtype=bool)
                gl.glColorMask(bool(channels[0]),bool(channels[1]),bool(channels[2]),True)
            bg.draw()
            if "fusion_guides" in resource:
                guide=resource["fusion_guides"][eye]
                guide.pos=center;guide.flipHoriz=sign[0]<0;guide.flipVert=sign[1]<0
                guide.draw()
            if self.mode.carrier=="checker" and self.components:
                pair=(self.epoch//2)%(len(s.colors)//2)
                colors=np.asarray(s.colors[pair*2:pair*2+2])
                for p,item in enumerate(resource["checks"][self.components]):
                    self._draw_mask(item,colors[p^(self.epoch%2)],eye,bitmap_position,sign)
                if self.target and self.target.patch:
                    for p,item in enumerate(resource["targets"][(self.components,self.target.patch)]):
                        self._draw_mask(item,colors[p^(self.epoch%2)]*k.dim_ratio,eye,bitmap_position,sign)
            elif self.mode.carrier=="disparity":
                dots=resource["dots"]
                cloud=self._cloud
                order=np.argsort(-cloud.disparities_arcmin,kind="stable")
                coords=(cloud.left if eye==0 else cloud.right)[order]
                colors=(cloud.left_colors if eye==0 else cloud.right_colors)[order]
                capacity=resource["dot_capacity"]
                n=len(coords)
                if n>capacity:
                    raise RuntimeError("Dot buffer capacity exceeded.")
                points=np.zeros((capacity,2),dtype=np.float32)
                points[:n]=coords*d.ppd*sign+position
                rgba=np.zeros((capacity,3),dtype=np.float32)
                rgba[:n]=self._color(np.asarray(s.dot_colors)[colors.astype(int)],eye)
                opacity=np.zeros(capacity,dtype=np.float32)
                opacity[:n]=1
                dots.xys=points
                dots.colors=rgba
                dots.opacities=opacity
                dots.draw()
            elif self.mode.carrier=="objects" and self.components:
                gl.glStencilFunc(gl.GL_EQUAL,bits,bits)
                mosaic=resource["mosaics"][eye]
                mosaic.pos=bitmap_position
                mosaic.flipHoriz=sign[0]<0
                mosaic.flipVert=sign[1]>0  # raw video rows start at the top
                mosaic.draw()
                gl.glStencilFunc(gl.GL_EQUAL,bits&1,1 if bits&1 else 0)
            dim=self.target is not None and self.mode.task=="fixation"
            if k.fixation_rendering=="ptb3":
                disk,ink=resource["fixation_layers"]
                self._draw_mask(disk,d.background,eye,position,sign)
                self._draw_mask(ink,fixation_color(self.config,dim),eye,position,sign)
            else:
                color=self._color(np.asarray(k.fixation_color)*(k.dim_ratio if dim else 1),eye)
                fix=resource["fixation"]
                fix.pos=position
                fix.setFillColor(color,colorSpace="rgb1",log=False)
                fix.draw()
                if k.fixation_type=="concentric":
                    resource["inner"].pos=position
                    resource["inner"].draw()
                    resource["center"].pos=position
                    resource["center"].setFillColor(color,colorSpace="rgb1",log=False)
                    resource["center"].draw()
            if d.marker_corner:
                marker=resource["marker"]
                mx=(-ew/2+d.marker_size_px/2) if d.marker_corner in (1,3) else (ew/2-d.marker_size_px/2)
                my=(eh/2-d.marker_size_px/2) if d.marker_corner in (1,2) else (-eh/2+d.marker_size_px/2)
                marker.pos=(center[0]+sign[0]*mx,center[1]+sign[1]*my)
                marker.setFillColor(self._color([1,1,1] if self.marker else [0,0,0],eye),colorSpace="rgb1",log=False)
                marker.draw()
            gl.glColorMask(True,True,True,True)
            if clipping:
                win.stencilTest=False
                gl.glStencilMask(255)
            win.scissor=(0,0,*d.size_px)

    def close(self):
        self.carrier.close()
        if self._object_stream:
            self._object_stream.close()
        # PsychoPy 2024.2 ImageStim destructors call OpenGL. Drop the scene's
        # references before destroying a GLFW window/context.
        import gc
        for win,resource in zip(self.windows,self.resources):
            win._setCurrent()
            resource.clear()
            gc.collect()
        if self._object_textures:
            self._object_textures.close()
        self.resources.clear()
