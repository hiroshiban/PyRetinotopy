"""Bounded prefetch of prepared native movies; no synthesis during acquisition."""
import threading
import time
from dataclasses import dataclass

import numpy as np

import json
from .object_cache import prepare_object_movie


@dataclass
class PreparedImage:
    pixels: np.ndarray

    @property
    def size(self):
        return self.pixels.shape[1],self.pixels.shape[0]

    @property
    def colorData(self):
        return self.pixels.reshape(-1)


class ImageSource:
    """PsychoPy ImageStim's camera/video-frame protocol, backed by ready pixels.

    This uses ImageStim's existing asynchronous PBO/subimage upload path rather
    than allocating a new OpenGL texture with setImage at every epoch.
    """
    def __init__(self,resolution):
        self.frameSize=(resolution,resolution)
        self.pending=None

    def push(self,frame):
        self.pending=frame

    def getVideoFrame(self):
        frame=self.pending
        self.pending=None
        return frame


class ObjectStream:
    """Read prepared uint8 frames into bounded RAM ahead of presentation.

    The only work in this worker is a sequential byte copy from the native
    movie. Image decoding, transforms, noise, gamma and anaglyph are precomputed.
    """
    def __init__(self, config, design, raster, capacity=8):
        self.directory = prepare_object_movie(config, design, raster)
        manifest = json.loads((self.directory / "manifest.json").read_text(encoding="utf-8"))
        self.epochs = manifest["descriptor"]["epochs"]
        self.movie = np.load(self.directory / "frames.npy", mmap_mode="r", allow_pickle=False)
        self.capacity = capacity
        self.frames = {}
        self.current_epoch = None
        self.current = None
        self.error = None
        self.stop = False
        self.condition = threading.Condition()
        self.thread = threading.Thread(target=self._produce, name="retinotopy-movie-prefetch", daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 60
        try:
            with self.condition:
                while len(self.frames) < min(capacity, len(self.epochs)) and self.error is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeError("Timed out prefetching prepared object frames.")
                    self.condition.wait(min(remaining, 1))
                if self.error:
                    raise RuntimeError(f"Object movie prefetch failed: {self.error}") from self.error
        except BaseException:
            self.close()
            raise

    def _produce(self):
        try:
            for index, epoch in enumerate(self.epochs):
                with self.condition:
                    while len(self.frames) >= self.capacity and not self.stop:
                        self.condition.wait(.1)
                    if self.stop:
                        break
                pixels = np.array(self.movie[index], copy=True)
                pair = tuple(PreparedImage(pixels[eye]) for eye in (0, 1))
                with self.condition:
                    self.frames[epoch] = pair
                    self.condition.notify_all()
        except BaseException as exc:
            with self.condition:
                self.error = exc
                self.condition.notify_all()
        finally:
            self.movie._mmap.close()

    def get(self, epoch):
        if epoch == self.current_epoch:
            return self.current
        with self.condition:
            if self.error:
                raise RuntimeError(f"Object movie prefetch failed: {self.error}") from self.error
            for old in [e for e in self.frames if e < epoch]:
                del self.frames[old]
            self.condition.notify_all()
            if epoch not in self.frames:
                raise RuntimeError(f"Prepared object movie prefetch fell behind at epoch {epoch}; "
                                   "check cache disk throughput. Acquisition logs were saved.")
            self.current = self.frames.pop(epoch)
            self.current_epoch = epoch
            self.condition.notify_all()
            return self.current

    def close(self):
        with self.condition:
            self.stop = True
            self.condition.notify_all()
        self.thread.join(timeout=5)


