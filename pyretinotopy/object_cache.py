"""Deterministic object movies prepared completely before acquisition."""
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import threading
import time

import numpy as np

from .carriers import CarrierRenderer
from .image_bank import ObjectBank
from .stereo import apply_gamma, gamma_table


MOVIE_SCHEMA = "pyretinotopy/object-movie/2"


def object_epochs(config, design):
    period = config.stimulus.object_update_s
    epochs = set()
    for segment in design.segments:
        if segment.components:
            epochs.update(range(int(np.floor(segment.onset / period + 1e-9)),
                                int(np.ceil((segment.onset + segment.duration) / period - 1e-9))))
    return sorted(epochs)


def movie_descriptor(config, design, raster):
    bank = ObjectBank(config.stimulus.object_source)
    try:
        source_id = bank.fingerprint()
    finally:
        bank.close()
    settings = asdict(config.stimulus)
    settings = {k: v for k, v in settings.items() if k in
                ("object_count", "object_scale", "object_disparity_arcmin", "noise_contrast")}
    mode = config.display.mode
    encoding = mode if mode in ("redgreen", "greenred", "redblue", "bluered") else "rgb"
    descriptor={"schema": MOVIE_SCHEMA, "source_id": source_id, "seed": config.seed,
            "settings": settings, "resolution": raster.resolution,
            "extent_deg": raster.extent_deg, "ppd": config.display.ppd,
            "binocular": mode != "mono", "encoding": encoding,
            "gamma": config.display.gamma, "epochs": object_epochs(config, design)}
    if config.display.gamma_lut:descriptor["gamma_lut"]=config.display.gamma_lut
    if config.display.gamma_lut_right:descriptor["gamma_lut_right"]=config.display.gamma_lut_right
    return descriptor


def encode_mosaic(rgb, eye, config):
    """Bake anaglyph projection and inverse gamma outside the presentation loop."""
    mode = config.display.mode
    if mode in ("redgreen", "greenred", "redblue", "bluered"):
        gains = ((1, 0, 0), (0, .6, 0)) if mode in ("redgreen", "greenred") else ((.4, 0, 0), (0, .2, .7))
        if mode in ("greenred", "bluered"):
            gains = gains[::-1]
        rgb = (rgb @ np.asarray([.2126, .7152, .0722], dtype=np.float32))[:, :, None] * gains[eye]
    if gamma_table(config.display,eye) or any(v != 1 for v in config.display.gamma):
        rgb = apply_gamma(rgb, config.display.gamma, gamma_table(config.display,eye))
    return np.uint8(np.clip(rgb * 255, 0, 255))


def prepare_object_movie(config, design, raster, cache_dir=None, progress=None):
    """Prepare a native uint8 movie once and reuse it for unchanged stimuli.

    No synthesis, rotation, FFT or source-image decoding runs during acquisition.
    The aperture is applied on the GPU, so a movie is reusable for the same set
    of epochs across compatible apertures. Failed builds are never accepted.
    """
    descriptor = movie_descriptor(config, design, raster)
    key = hashlib.sha256(json.dumps(descriptor, sort_keys=True).encode()).hexdigest()
    cache_dir = Path(cache_dir or config.stimulus.object_cache_dir).resolve()
    directory = cache_dir / ("objects-" + key[:20])
    manifest_path = directory / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("key") != key or manifest.get("descriptor") != descriptor:
            raise ValueError("Object movie manifest does not match the requested stimulus.")
        array = np.load(directory / "frames.npy", mmap_mode="r", allow_pickle=False)
        valid = array.dtype == np.uint8 and list(array.shape) == manifest["shape"]
        array._mmap.close()
        if not valid:
            raise ValueError("Object movie shape/type does not match its manifest.")
        return directory
    epochs = descriptor["epochs"]
    n = raster.resolution
    shape = (len(epochs), 2, n, n, 3)
    if not epochs:
        raise ValueError("Object protocol contains no active epochs.")
    directory.mkdir(parents=True, exist_ok=True)
    required = int(np.prod(shape))
    if shutil.disk_usage(directory).free < required + 128 * 1024**2:
        raise ValueError(f"Object cache needs {required / 1024**3:.2f} GiB of free disk space.")
    temporary = directory / "frames.partial.npy"
    if temporary.exists():
        raise FileExistsError(f"An unfinished/concurrent preparation exists: {temporary}")
    local = threading.local()
    renderers = []
    lock = threading.Lock()

    def make(epoch):
        if not hasattr(local, "renderer"):
            local.renderer = CarrierRenderer(config, raster)
            with lock:
                renderers.append(local.renderer)
        mosaics = local.renderer._object_mosaics(epoch)
        return np.stack([encode_mosaic(rgb, eye, config) for eye, rgb in enumerate(mosaics)])

    array = None
    started = time.perf_counter()
    try:
        array = np.lib.format.open_memmap(temporary, mode="w+", dtype=np.uint8, shape=shape)
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="retinotopy-prepare") as pool:
            pending = deque(pool.submit(make, epoch) for epoch in epochs[:2])
            for i, epoch in enumerate(epochs):
                pixels = pending.popleft().result()
                array[i] = pixels
                if i + 2 < len(epochs):
                    pending.append(pool.submit(make, epochs[i + 2]))
                if progress and ((i + 1) % 16 == 0 or i + 1 == len(epochs)):
                    progress(i + 1, len(epochs))
        array.flush()
        array._mmap.close()
        array = None
        temporary.rename(directory / "frames.npy")
        manifest = {"schema": MOVIE_SCHEMA, "key": key, "descriptor": descriptor,
                    "shape": list(shape), "array": "frames.npy", "axis_order": "epoch,eye,y,x,RGB",
                    "preparation_s": time.perf_counter() - started}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return directory
    finally:
        if array is not None:
            array._mmap.close()
        for renderer in renderers:
            renderer.close()
        if temporary.exists():
            temporary.unlink()
