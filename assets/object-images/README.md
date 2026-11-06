# PyRetinotopy native object-image bank

The runtime bank contains `images.npy` and `manifest.json`. The array is memory-mapped, uncompressed `uint8`, with shape **7493 × 256 × 256 × 4** (image, y, x, RGBA). All color and alpha values are preserved from the original data. It can be opened directly in Python without MATLAB, SciPy, h5py, or PsychoPy:

```python
import numpy as np
from PIL import Image

images = np.load("assets/object-images/images.npy", mmap_mode="r", allow_pickle=False)
image = Image.fromarray(images[0], "RGBA")
image.save("example.png")
```

Set `stimulus.object_source` to this directory, `manifest.json`, or `images.npy`. No original Retinotopy directory is needed after conversion.

To regenerate the native bank from a legacy database, use a new or empty output directory:

```shell
python -m pip install -e .[legacy]
python -m pyretinotopy convert-images path/to/object_image_database.mat --output assets/object-images
```

The importer supports legacy v5/v7 and v7.3 `img` arrays. It does not rescale, normalize, resize, or recompress pixels. Every output chunk is compared with the input, and the manifest records a SHA-256 of all channel values in native order. Existing banks and the original input are not overwritten.

`images.npy` is about **1.96 GB** (1.83 GiB). It is intentionally excluded from Git along with prepared movie caches. Distribute the data as a separate compressed data archive; extract the array before use so it can be memory-mapped. The small manifest and this guide may accompany the source repository. No data have been uploaded automatically.

The images originate from the databases credited to **Talia Konkle's research group** in Retinotopy by **Hiroshi Ban**. Preserve those acknowledgments and cite the applicable image-database papers in [NOTICE.md](../../NOTICE.md) and the [main README](../../README.md#Acknowledgments). The native format does not change the image data's terms.
