"""A small GPU ring: upload future eye images away from their onset flips."""
from collections import deque

from .object_stream import ImageSource


class ObjectTextures:
    def __init__(self, config, stream, windows, resolution):
        from psychopy import visual
        self.stream = stream
        self.windows = windows
        self.slots = []
        self.jobs = deque()
        self.loading = None
        self.next_index = 0
        self.current_epoch = None
        self.uploads = 0
        count = min(config.stimulus.object_texture_slots, len(stream.epochs))
        for _ in range(count):
            entries = []
            for win in windows:
                sources = [ImageSource(resolution) for _ in (0, 1)]
                images = [visual.ImageStim(win, image=source, size=(resolution, resolution),
                          units="pix", interpolate=False, autoLog=False) for source in sources]
                entries.append((sources, images))
            slot = {"epoch": None, "ready": False, "entries": entries}
            self.slots.append(slot)
            self._begin(slot, stream.epochs[self.next_index])
            self.next_index += 1
            # Initial ring is transferred before waiting for the scanner.
            while self.jobs:
                self._one_upload()

    def _begin(self, slot, epoch):
        pair = self.stream.get(epoch)
        slot["epoch"] = epoch
        slot["ready"] = False
        self.loading = slot
        for win, (sources, images) in zip(self.windows, slot["entries"]):
            for eye in (0, 1):
                self.jobs.append((win, sources[eye], images[eye], pair[eye]))

    def _one_upload(self):
        win, source, image, frame = self.jobs.popleft()
        win._setCurrent()
        source.push(frame)
        # Drawing with zero opacity exercises PsychoPy's PBO subimage upload
        # without displaying the future frame or reallocating its texture.
        image.opacity = 0
        image.draw()
        image.opacity = 1
        self.uploads += 1
        if not self.jobs:
            self.loading["ready"] = True
            self.loading = None

    def activate(self, epoch):
        slot = next((s for s in self.slots if s["epoch"] == epoch and s["ready"]), None)
        if slot is None:
            raise RuntimeError(f"Object epoch {epoch} was not uploaded before its onset; acquisition stopped.")
        self.current_epoch = epoch
        return [entry[1] for entry in slot["entries"]]

    def service(self, time_epoch):
        """Transfer at most ONE future eye image per display refresh."""
        if not self.jobs and self.next_index < len(self.stream.epochs):
            obsolete = [s for s in self.slots if s["epoch"] < time_epoch
                        and s["epoch"] != self.current_epoch]
            if obsolete:
                self._begin(min(obsolete, key=lambda s: s["epoch"]), self.stream.epochs[self.next_index])
                self.next_index += 1
        if self.jobs:
            self._one_upload()

    def close(self):
        """Release each texture while its owning OpenGL context still exists."""
        import gc
        self.jobs.clear()
        self.loading = None
        for index, win in enumerate(self.windows):
            win._setCurrent()
            for slot in self.slots:
                sources, images = slot["entries"][index]
                images.clear()
                sources.clear()
                slot["entries"][index] = None
            gc.collect()
        self.slots.clear()
