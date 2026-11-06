# 検証記録

2026-11-06。Python 3.10.11、PsychoPy 2024.2.4、NumPy 1.26.4、SciPy 1.14.1、Windows上で確認しました。PsychoPy同梱Pythonを使用し、試験用設定・キャッシュ・ログはPython版の `.runtime` に分離しました。

機械可読の記録は [qa/validation.json](qa/validation.json) です。試験用の画面取得はOpenGLのfront bufferを保存しています。ディスプレイの光学測定や、眼鏡を通して左右が正しく分離するかの検証は行っていません。

## 自動テスト

`python -m unittest discover -s tests -v` : **27件成功**。

- 70のモード名すべてのスケジュール構築、既定総時間、前後注視。
- 楔形の回転方向、0度を跨ぐマスク、バーの走査法線。
- 環状刺激の移動と休止位置、独立周期の複合刺激の和集合。
- リフレッシュ境界への丸め。1/3秒等の小数誤差で状態変化を1フレーム遅らせないこと。
- multifocalの36領域の独立性、m系列の長さ・バランス・異なるシフト。
- 離心度localizerと補領域による視野の分割。
- RDSの負の視差＝手前、左右対応、極性相関／反相関、背景の視差0。
- 課題とcarrierの乱数streamの独立性、seed再現性。
- チェッカー反転と局所パッチの輝度低下。
- MATLAB v5とv7.3の画像形状、RGBAのalpha、画像方向。
- 画像の先行生成キューの上限、並列生成時の再現性、動画用フレームの一度だけの消費。
- 左右／上下／行／列の眼割当、anaglyphのgain、鏡像・位置補正。
- TR内の時間積分、実測flip間で保持された刺激、MATの軸順。
- 実測課題開始を基準にしたRTとhit／false alarm。
- 不正設定、結果上書き、重複取得sessionの拒否。
- MATLAB設定中の関数呼出しを実行しないこと。

Pythonファイルのcompile確認も成功しています。コアのimport／テストにはPsychoPyを読み込みません。CI定義は追加しましたが、GitHub Actions上での実行はまだ行っていません。

原版の9ファミリーすべてについて `_DEFAULT_` の設定から変換ドラフトと移行レポートを作り、ドラフトの設定検査が通ることを確認しました。これは元MATLABの実行結果との一致確認ではありません。

## ネイティブ呈示の短時間試験

640×480、60 Hz設定、各2.4秒。各試験には前後注視、実際の画像取得を含みます。ソフトウェアの高優先度設定は有効でした。

| 刺激／表示 | 描画経路 | 記録flip数（終端blankを含む） | 長い間隔 | 推定欠落フレーム |
|---|---|---:|---:|---:|
| `ccw` / mono、刺激内検出課題 | GPU masks | 145 | 0 | 0 |
| `barf` / mono | GPU masks | 145 | 0 | 0 |
| `ccwexpf` / mono | GPU masks | 145 | 0 | 0 |
| `ccwdf` / parallel | GPU dots | 145 | 0 | 0 |
| `ccwdf` / interleavedline | GPU dots + stencil | 145 | 0 | 0 |
| `ccwf` / redgreen | GPU masks + channel分離 | 145 | 0 | 0 |
| `ccwi` / parallel、実画像120枚 | GPU object stream + stencil | 145 | 0 | 0 |

「長い間隔」は指定refreshの1.5周期を超えたflip間隔です。「推定欠落」は各間隔から推定した追加refresh数であり、物理的に測定したドロップ数ではありません。

チェッカー、バー、複合刺激、anaglyphのGPU画面を独立したソフトウェア参照compositorと比較しました。RGBの差が8/255を超える画素は、画面全体の0.23%以下でした。境界と注視点のラスタライズ等の差を含みます。MATLAB版との画素比較ではありません。

代表画像: [チェッカー](qa/live-checker.png)、[バー](qa/live-bar.png)、[楔形＋環状](qa/live-dual-aperture.png)、[RDS左右像](qa/live-rds.png)、[行交互RDS](qa/live-interleaved.png)、[anaglyph](qa/live-anaglyph.png)、[物体画像左右像](qa/live-objects.png)。全14基本形状の静止画は [stimulus-gallery.png](qa/stimulus-gallery.png) にまとめています。

## 高解像度の物体画像負荷試験

1280×1080ウィンドウ、刺激ラスタ1031×1031、物体120枚、250 ms更新、60 Hz、mono、10.4秒。共有のv7.3画像データを使用し、高優先度設定を有効にしました。画面キャプチャは行っていません。

- 取得は完走し、先行生成の不足による停止はありませんでした。
- 記録620 flip、長い間隔6回、推定欠落7フレーム、最大間隔51.333 msでした。
- **この条件を撮像用の性能検証済みとは扱いません。** 画像数・サイズ・周期、専用PCの負荷、fullscreen、GPU／OSの表示設定を含む調整と長時間の再検証が残ります。

画像準備が追いつかない場合の例外終了とログ保存も開発中の負荷試験で確認しました。正常終了した場合でも、`summary.json` のフレーム間隔と実際の呈示ログを確認する必要があります。

## 未完了の検証と未実装の機器経路

- MATLABと同一設定での全時系列・最初の位相・境界画素の照合。
- 通常run長（約200〜518秒）での全刺激・全表示方式の負荷試験。
- 実際のスキャナトリガー、反応箱、フォトダイオードによる時刻照合。
- 2画面の左右swap差と光学的同期、シャッターのquad buffer対応、眼鏡の分離とcrosstalk。
- interleavedcolumn／上下分割／鏡像装置等の実際の表示機器での眼割当。これらの符号化そのものは単体テストの対象です。
- 物体画像＋anaglyphの性能確認。現在この組み合わせは参照compositor経路です。
- PROPixx/Datapixxの専用制御、平行ポート電圧トリガー、任意gamma LUT、BrainVoyager OLT／PRTの生成。

## 原版の保全

開始時に記録したMATLAB・Markdown・テキスト503ファイルについて、最終確認時のSHA-256差分は0件でした。共有版の元から存在した変更を含め、git statusも開始時と同一です。MATLAB刺激コード、被験者設定、実験結果への書き込みは行っていません。
