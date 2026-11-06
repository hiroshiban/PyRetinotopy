"""One-time legacy import. scipy/h5py are optional and absent from presentation."""
from datetime import datetime
import hashlib
import json
from pathlib import Path

import numpy as np

from .image_bank import BANK_SCHEMA


class LegacyMatImages:
    """Read-only source for conversion, with explicit MATLAB axis handling."""
    def __init__(self, path):
        self.path = Path(path)
        self.h5 = None
        try:
            import h5py
            if h5py.is_hdf5(self.path):
                self.h5 = h5py.File(self.path, "r")
        except ImportError:
            pass
        if self.h5 is not None:
            self.array = self.h5["img"]
            if self.array.ndim != 4 or self.array.shape[1] not in (3, 4):
                self.close()
                raise ValueError("v7.3 img must have on-disk shape N x RGB(A) x W x H.")
            n, c, w, h = self.array.shape
            self.shape = (n, h, w, c)
        else:
            try:
                from scipy.io import loadmat
                self.array = loadmat(self.path, variable_names=["img"])["img"]
            except (ImportError, NotImplementedError) as exc:
                raise ValueError("Legacy conversion requires the optional legacy dependencies: "
                                 "pip install -e .[legacy]") from exc
            if self.array.ndim != 4 or self.array.shape[2] not in (3, 4):
                raise ValueError("Legacy img must have shape H x W x RGB(A) x N.")
            h, w, c, n = self.array.shape
            self.shape = (n, h, w, c)
        if self.array.dtype != np.uint8:
            self.close()
            raise ValueError("Lossless conversion requires uint8 input; no implicit normalization is performed.")

    def read(self, start, end):
        if self.h5 is not None:
            return np.ascontiguousarray(self.array[start:end].transpose(0, 3, 2, 1))
        return np.ascontiguousarray(self.array[:, :, :, start:end].transpose(3, 0, 1, 2))

    def close(self):
        if self.h5 is not None:
            self.h5.close()
            self.h5 = None


def convert_images(source, output, progress=None):
    """Convert all pixels and verify every output chunk against its input.

    The manifest is published only after the array has been flushed and checked.
    Existing output files are never overwritten. Original input is read-only.
    """
    source = Path(source).resolve()
    output = Path(output).resolve()
    if output.exists() and any(p.name not in ("README.md","manifest.json") for p in output.iterdir()):
        raise FileExistsError(f"Image data already exist or output contains unrelated files: {output}")
    output.mkdir(parents=True, exist_ok=True)
    expected_path=output/"manifest.json"
    expected=json.loads(expected_path.read_text(encoding="utf-8")) if expected_path.is_file() else None
    reader = LegacyMatImages(source)
    array_path = output / "images.npy"
    temporary = output / "images.npy.partial"
    digest = hashlib.sha256()
    array=None
    try:
        if expected and (expected.get("schema")!=BANK_SCHEMA or expected.get("shape")!=list(reader.shape)):
            raise ValueError("Input does not match the distributed image-bank manifest.")
        array = np.lib.format.open_memmap(temporary, mode="w+", dtype=np.uint8, shape=reader.shape)
        for start in range(0, reader.shape[0], 32):
            end = min(start + 32, reader.shape[0])
            pixels = reader.read(start, end)
            array[start:end] = pixels
            digest.update(pixels.tobytes())
            if not np.array_equal(array[start:end], pixels):
                raise RuntimeError(f"Lossless image conversion verification failed at {start}.")
            if progress and (end % 512 == 0 or end == reader.shape[0]):
                progress(end, reader.shape[0])
        array.flush()
        if expected and expected.get("pixels_sha256")!=digest.hexdigest():
            raise ValueError("Converted pixels do not match the distributed image-bank digest.")
        array._mmap.close()
        array=None
        temporary.rename(array_path)
        manifest = {"schema": BANK_SCHEMA, "array": "images.npy", "shape": list(reader.shape),
                    "dtype": "uint8", "axis_order": "image,y,x,channel",
                    "channels": "RGBA" if reader.shape[3] == 4 else "RGB",
                    "pixels_sha256": digest.hexdigest(), "verified_pixels": int(np.prod(reader.shape)),
                    "source_filename": source.name, "conversion": "lossless; original pixel values and alpha preserved",
                    "created_at": datetime.now().astimezone().isoformat(),
                    "attribution": "Object images from Talia Konkle's research group, as credited in Retinotopy by Hiroshi Ban. See NOTICE.md for references."}
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest
    finally:
        if array is not None:
            array._mmap.close()
        if temporary.exists():
            temporary.unlink()
        reader.close()
