"""Resolve an optional display backend without changing a PsychoPy installation."""
import importlib
from pathlib import Path
import sys


def require_backend(name):
    if name != "glfw":
        return
    if importlib.util.find_spec("psychopy_glfw") is None:
        local = Path(__file__).resolve().parents[1] / "optional-libs"
        if local.is_dir():
            sys.path.insert(0, str(local))
            importlib.invalidate_caches()
    if importlib.util.find_spec("psychopy_glfw") is None or importlib.util.find_spec("glfw") is None:
        raise RuntimeError("GLFW requires psychopy-glfw and glfw. Install the presentation extra or use "
                           "pip install --target optional-libs --no-deps psychopy-glfw==0.0.2 glfw==2.8.0")
    # The official 0.0.2 plugin predates Window.mouseVisible in PsychoPy 2024.2.
    # Supply the missing public property in memory, without editing its files.
    from psychopy_glfw import GLFWBackend
    import glfw
    if not hasattr(GLFWBackend,"mouseVisible"):
        GLFWBackend.mouseVisible=property(
            lambda self:glfw.get_input_mode(self.winHandle,glfw.CURSOR)==glfw.CURSOR_NORMAL)
    if not getattr(GLFWBackend,"_retinotopy_deferred_events",False):
        # The official plugin polls OS events AFTER swap_buffers but BEFORE
        # Window.flip samples its timestamp. A slow event poll can therefore
        # produce a long interval followed by a short one, even without a lost
        # refresh. Keep swap/glFinish timing intact and poll explicitly after
        # Window.flip has returned its timestamp in our acquisition runner.
        def swap_without_event_poll(self,flipThisFrame=True):
            self.setCurrent()
            self.GL.glTranslatef(0.0,0.0,-5.0)
            if flipThisFrame:
                glfw.swap_buffers(self.winHandle)
        GLFWBackend.swapBuffers=swap_without_event_poll
        GLFWBackend._retinotopy_deferred_events=True


def dispatch_backend_events(name):
    if name=="glfw":
        import glfw
        glfw.poll_events()


def backend_options(config):
    if config.display.backend!="glfw":
        return None
    import glfw
    glfw.init()
    screens=glfw.get_monitors()
    index=config.display.screens[0]
    if index>=len(screens):
        raise ValueError("Requested GLFW screen does not exist.")
    native=glfw.get_video_mode(screens[index])
    requested=config.display.refresh_hz
    # Windows commonly enumerates a 59.94 Hz native mode as integer 59. Use
    # that exact native mode when it matches the requested nominal refresh.
    refresh=native.refresh_rate if abs(native.refresh_rate-requested)/requested<.03 else round(requested)
    return {"refreshHz":refresh}
