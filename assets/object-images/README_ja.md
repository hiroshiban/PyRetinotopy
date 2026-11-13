# PyRetinotopyのNumPy物体画像バンク

[English](README.md) | [日本語](README_ja.md)

実行時の画像バンクは `images.npy` と `manifest.json` で構成します。画像配列は非圧縮の `uint8` で、形状は **7493 × 256 × 256 × 4**（画像、y、x、RGBA）です。元データの色とalphaを保持し、メモリマップで読み込めます。MATLAB、SciPy、h5py、PsychoPyを使わず、Pythonから直接開くこともできます。

```python
import numpy as np
from PIL import Image

images = np.load("assets/object-images/images.npy", mmap_mode="r", allow_pickle=False)
image = Image.fromarray(images[0], "RGBA")
image.save("example.png")
```

`stimulus.object_source` には、このディレクトリ、`manifest.json`、または `images.npy` を指定します。一度変換すれば、元のRetinotopyディレクトリは不要です。

旧データベースからNumPyバンクを作成する場合は、新規または空の出力ディレクトリを使用します。

```shell
python -m pip install -e .[legacy]
python -m pyretinotopy convert-images path/to/object_image_database.mat --output assets/object-images
```

変換はMATLAB v5/v7およびv7.3の `img` 配列に対応します。画素を拡大縮小、正規化、再圧縮しません。出力の各チャンクを入力と照合し、配列順に並べた全チャンネル値のSHA-256をmanifestへ記録します。既存バンクと入力データは上書きしません。

`images.npy` は約 **1.96 GB**（1.83 GiB）あり、事前合成した動画キャッシュとともにGit管理から除外しています。画像データはソースコードと別の圧縮アーカイブ等で配布し、使用前に展開してメモリマップできるようにしてください。小さいmanifestと本ガイドはソースレポジトリに含められます。データの自動アップロードは行いません。

画像は、番浩志による原版Retinotopyで謝辞を記載した **Talia Konkle氏の研究グループ**のデータベースに由来します。元の謝辞を保持し、利用した画像データベースの論文を引用してください。[NOTICE.md（英語）](../../NOTICE.md) と [日本語READMEの謝辞](../../README_ja.md#acknowledgments) を参照してください。形式の変換は、画像データの利用条件を変更しません。
