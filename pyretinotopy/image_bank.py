"""Native, lossless RGB(A) image banks; presentation never imports MATLAB I/O."""
from collections import OrderedDict
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


BANK_SCHEMA = "pyretinotopy/image-bank/1"


class ObjectBank:
    """Read a memory-mapped N x H x W x RGB(A) uint8 .npy bank or images.

    A bank directory/manifest is preferred, because it carries source attribution
    and a lossless-conversion digest. PNG alpha is preserved. Pickle is disabled.
    """
    def __init__(self, source):
        source = Path(source).resolve()
        self.source = source
        self.files = None
        self.array = None
        self.manifest = None
        self._cache = OrderedDict()
        if source.is_dir() and (source / "manifest.json").is_file():
            source = source / "manifest.json"
        if source.suffix.lower() == ".json":
            self.manifest = json.loads(source.read_text(encoding="utf-8"))
            if self.manifest.get("schema") != BANK_SCHEMA:
                raise ValueError("Unsupported image-bank manifest schema.")
            filename = Path(self.manifest["array"])
            if filename.is_absolute() or ".." in filename.parts:
                raise ValueError("Image-bank array must be inside its manifest directory.")
            source = source.parent / filename
        if source.suffix.lower() == ".npy":
            self.array = np.load(source, mmap_mode="r", allow_pickle=False)
            if (self.array.ndim != 4 or self.array.dtype != np.uint8
                    or self.array.shape[3] not in (3, 4) or min(self.array.shape) < 1):
                raise ValueError("Native image bank must be uint8 N x H x W x RGB(A).")
            if self.manifest and list(self.array.shape) != self.manifest["shape"]:
                raise ValueError("Image-bank shape disagrees with its manifest.")
            self.count = self.array.shape[0]
            self.size = self.array.shape[2], self.array.shape[1]
            self._array_path = source
        elif source.is_dir():
            self.files = sorted(p for p in source.iterdir() if p.suffix.lower() in
                                (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"))
            self.count = len(self.files)
            if not self.count:
                raise ValueError(f"No images or native image-bank manifest found in {source}")
            with Image.open(self.files[0]) as image:
                self.size = image.size
        else:
            raise ValueError("object_source must be a native .npy bank, its manifest/directory, "
                             "or an image directory. Convert legacy MAT data with convert-images first.")

    def image(self, index):
        index = int(index) % self.count
        if index in self._cache:
            self._cache.move_to_end(index)
            return self._cache[index].copy()
        if self.files is not None:
            with Image.open(self.files[index]) as image:
                result = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        else:
            pixels = self.array[index]
            result = Image.fromarray(pixels, "RGBA" if pixels.shape[2] == 4 else "RGB")
        self._cache[index] = result.copy()
        while len(self._cache) > 256:
            self._cache.popitem(last=False)
        return result.copy()

    def fingerprint(self):
        """Fast invalidation key; conversion manifest supplies a pixel digest."""
        paths = self.files if self.files is not None else [self._array_path]
        records = [(p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
        value = {"files": records, "pixels_sha256": (self.manifest or {}).get("pixels_sha256")}
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def close(self):
        self._cache.clear()
        if isinstance(self.array, np.memmap):
            self.array._mmap.close()
        self.array = None
