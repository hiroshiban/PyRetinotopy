# PyRetinotopy — Retinotopy for PsychoPy

[English](USAGE.md) | [日本語](USAGE.ja.md)

番浩志が開発・公開してきたMATLAB Psychtoolbox 3版Retinotopy刺激セット（[https://github.com/hiroshiban/Retinotopy](https://github.com/hiroshiban/Retinotopy)）を基にした、PsychoPy用のPython版です。表示名とプロジェクトディレクトリ名は **PyRetinotopy**、配布・Python import・コマンド名は **pyretinotopy** です。

**現在は v0.4.0 です。** PTB3の画像座標・逆順配列に合わせ、開始位置と複合刺激の環状位置を修正しました。既定結果保存先は原版と同じ被験者別・日付別の構成です。画像データはNumPy形式へ独立させ、取得前の全画像準備とGPU先行転送を使います。全刺激をラン開始からの累積経過時間で制御します。機器依存の制約は [機能対応表](PTB3_FEATURES.ja.md) を参照してください。

旧版のMATLABソースへのパスは、任意の一度限りの変換で使用する例です。通常の刺激呈示には元のRetinotopyディレクトリは必要ありません。

## 実装した刺激

| 基本モード | 刺激 |
|---|---|
| `ccw`, `cw` | 反時計回り／時計回りの楔形 |
| `exp`, `cont` | 拡大／縮小する環状刺激 |
| `bar` | 複数方向のバー走査 |
| `ccwexp`, `ccwcont`, `cwexp`, `cwcont` | 独立した周期の楔形＋環状刺激の和集合 |
| `multifocal` | 極角×離心度の領域別m系列／指定デザイン |
| `meridian` | 水平／垂直子午線の対向する楔形 |
| `lgn` | 左右半視野のLGN localizer |
| `hrf` | HRF推定用の刺激／休止 |
| `localizer` | 指定離心度帯とその補領域 |

元版と同じ接尾辞を使います。接尾辞なし＝カラーチェッカー＋刺激内の輝度検出、`f`＝チェッカー＋注視課題、`d`＝RDS＋刺激内の奥行き検出、`df`＝RDS＋注視課題、`i`＝物体画像＋注視課題です。計70通りの名前を解釈します。`*windows` は `export` で使います。

表示設定は刺激と独立しています。`mono`, `parallel`, `cross`, `dual`, `dualparallel`, `dualcross`, `topbottom`, `bottomtop`, `redgreen`, `greenred`, `redblue`, `bluered`, `interleavedline`, `interleavedcolumn`, `shutter` を用意しました。`shutter` はPsychoPyのquad-buffer stereoを利用する実装で、対応GPU・ドライバ・眼鏡の実機確認が必要です。PROPixx／Datapixx専用制御は未実装です。

## 起動

以下はWindows版PsychoPyに同梱されたPythonを使用する例です。プロジェクトとPythonのパスは、実際の配置に合わせて変更してください。

```powershell
Set-Location 'E:\PyRetinotopy\PyRetinotopy'
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy list
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy validate --config examples\ccwf.json
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --config examples\smoke.json
```

`smoke.json` は640×480の短い自動開始デモです。計測用の設定ではありません。同じsubject/mode/runを再実行すると、前の結果フォルダ全体を `_old-01`、`_old-02`…へ退避し、最新の試行を元の名前へ保存します。別の撮像には `--run 2` 等で異なる番号を指定します。

通常のPython環境では、PsychoPyが動作する環境で `python -m pip install -e .` とします。基本依存はPython 3.10以上、NumPy、Pillowです。呈示にはPsychoPyを使います。旧画像変換とMAT互換出力を使うときは `pip install -e .[legacy]` でSciPy/h5pyを追加します。動作確認したPsychoPyは **2024.2.4 / Python 3.10.11 / Windows** です。

Windowsの撮像用にはGLFW＋全画面を推奨します。PsychoPy本体を変更せず、バックエンドをプロジェクト内に置く場合は次を実行します。

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pip install --target optional-libs --no-deps psychopy-glfw==0.0.2 glfw==2.8.0
```

`examples/object-images-fullscreen.json` は2560×1440画面での性能確認用です。`width_cm` と `distance_cm` は実験装置に合わせた実測値へ変更してください。例の寸法は校正済みの値を意味しません。

PsychoPy Coderでは `PyRetinotopy.py` を開いてRunすると、JSON設定ファイルを選択できます。

## ラン番号とやり直し

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --subject HB --mode ccw --run 1
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --subject HB --mode ccw --run 2
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --subject HB --mode ccw --run 1
```

`--run` がJSONの値に優先し、設定・summary・保存先へ反映されます。同じ番号の再実行時には `ccw_run-01_old-01/` 等へ前のフォルダを移します。既存バックアップと別の番号のランは変更しません。完走・中止・失敗のいずれも保持します。最新の試行が成功したとは限らないため、採用データは各 `summary.json` のstatusとログで確認してください。

既定は `--if-exists backup` です。`--if-exists error` なら既存結果があると取消します。実行中の同一取得はOSロックで保護します。`.lock` ファイルは終了後も残る再利用可能な管理ファイルです。取得ごとの `acquisition.json` に一意IDと直前結果の退避先を保存します。

既定の `timing.operator_confirm: true` は退避・準備の前にID・mode・runを確認します。取消時は元データを動かしません。`--no-confirm` または同項目falseで省略でき、スキャナトリガー待ちは別に維持されます。sessionは各項目のrun番号を使い、過去の取得があっても再実行できます。単一session内の同一取得重複は区別できるrun番号へ修正してください。

## 被験者ごとの設定と呈示

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy init-subject HB --mode ccwf
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy validate --subject HB --mode ccwf
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --subject HB --mode ccwf
```

JSONの `display`、`timing`、`stimulus`、`task` を編集します。単位は秒、視角度、視差のarcmin、0〜1のRGBです。継承方式では `--mode` から刺激ファミリーの既定ファイルを選びます。独立JSON方式ではプロトコルごとに `init --mode` で設定を作成してください。独立JSONへの `--mode` の上書きは、そのファイル内の他のパラメータを変更しません。

原版の `Presentation/subjects/_DEFAULT_` に対応する [subjects/_DEFAULT_](../subjects/_DEFAULT_) を追加しました。`--subject HB --mode ccwf` は既定フォルダの `common.json` → `retinotopy_display.json` → `c_pol.json` → 任意の `ccwf.json` を読み、その後に被験者フォルダの同名ファイルを同じ順で重ねます。未指定ファイル・項目は既定値を使い、被験者側は差分だけ記載できます。リストは全体を置き換えます。9種類の刺激別ファイルは原版と対応する名前です。

`init-subject` が作る `HB/common.json` は空の差分、`HB/ccwf.json` はrun番号だけです。表示補正は `HB/retinotopy_display.json`、楔形共通の条件は `HB/c_pol.json` 等へ記載できます。構造・優先順位・例・sessionでの使用は [被験者設定ガイド](../subjects/README_ja.md) を参照してください。

以前からの `init FILE --subject HB --mode ccwf` と `--config FILE` も使用できます。こちらは全項目を持つ独立JSONを使う方式で、他の既定ファイルを探索しません。保存済み取得条件を再現するため、この動作は維持しています。`validate --subject HB --mode ccwf --save-config resolved.json` で継承後の全設定も保存できます。

既定では `t` または `5` のトリガーで開始し、反応は `r`／`g`、中止はEscape／Qです。`skip_triggers` で開始前に無視するパルス数を指定します。開始方式はトリガー、Space/Enter、左クリック、自動開始から選べます。平行ポートの電圧を直接読んでトリガーとする機能は未実装です。

複数取得を順に実行する場合は、`examples/session.json` のように設定ファイルとrun番号を列挙し、`session examples/session.json` を使います。各取得で開始トリガーを待ち、中止すると以降の取得を止めます。

視角は `display.size_px[0] / width_cm * distance_cm * tan(1度)` で換算します。`width_cm` は **size_px全体に対応する物理的な幅**です。左右分割で表示画像を縮小しないため、片眼領域に収まらない設定はエラーになります。`stereo-rds.json` の寸法は設定方法の例であり、使用機器に合わせて実測値へ変更してください。

`dual` は異なるscreen IDの2ウィンドウです。左右swapの時刻差を保存しますが、ハードウェア同期を保証するものではありません。`dualparallel`／`dualcross` は、1枚の横長フレームバッファを左右に分割する方式です。各眼の位置ずれ、水平・垂直反転も設定できます。

## 開始位置とPTB3との対応

`stimulus.spatial_convention` の既定値は `"ptb3"` です。設定の `start_angle_deg` は原版と同じ画像座標の時計回り角です。既定ではcwの中心は真上90度、ccwは102度（真上から反時計回りへ12度）です。ccwで生成画像を全体反転する原版の規則を維持しています。複合刺激の環は16位置・2秒刻み・公称幅1度となります。

multifocalは時計回りの領域配置とし、`multifocal_indexing: "corrected"` では36領域の重複を解消します。原版の領域ID重複まで再現するには同フィールドを `"ptb3"` とします（phase 0、幅360度のみ）。

v0.2.2以前の呈示を再現する場合は `spatial_convention: "legacy-python"` を使います。保存済み `config.json` にこの項目がなく、隣の `summary.json` がv0.2.2以前なら自動選択します。通常の設定JSONには新しい既定値を適用します。詳しい開始位置一覧・検証範囲は [PTB3との位置対応](PTB3_PARITY.ja.md) を参照してください。

## 画像刺激とMATLAB設定の移行

`examples/object-images.json` は、Pythonプロジェクト内の `assets/object-images/manifest.json` を参照します。使用前に対応するNumPy画像バンクを準備してください。約1.96 GBの `images.npy` はGit管理から除外されています。バンクは7,493枚のRGBA画像を含み、配列順は画像×縦×横×RGBAです。呈示では元のMATファイルを読みません。通常のPNG等の画像ディレクトリも指定できます。詳しくは [画像バンクのガイド](../assets/object-images/README_ja.md) を参照してください。

別のPCで旧データから再変換する場合は次を一度実行します。入力は読み取り専用で、色・alphaを全データ照合します。

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy convert-images ..\Retinotopy\object_images\object_image_database.mat --output assets\object-images
```

取得前に全画像を合成したNumPy動画を準備します。同じ画像・seed・条件なら再利用します。相対キャッシュパスはJSONのディレクトリを基準に解決します。設定例はプロジェクト直下の `cache/object-movies` を使います。

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy prepare-objects --config examples\object-images-fullscreen.json
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --config examples\object-images-fullscreen.json
```

`run` も未準備の動画を画面初期化前に自動生成します。標準360秒・1031角の左右像では約9.2 GBのキャッシュを使います。呈示中は既成画像の先読みとGPUリングの更新だけを行い、切替時には転送済みの画像を選択します。

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy migrate ..\Retinotopy\Presentation\subjects\_DEFAULT_ --mode ccwf --output subjects\demo\migrated-ccwf.json
```

`migrate` はMATLABコードを実行せず、定数と単純な算術式を移します。未解釈式と確認項目を `.migration.json` に残します。screen ID、キーコード、機器固有設定を推測して適用しません。生成物は確認用のドラフトです。

## プレビュー、刺激窓、取得ログ

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy preview --config examples\stereo-rds.json --output rds-preview.png
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy export --config examples\barf.json --output bar-windows.npz --tr 2 --resolution 128
```

刺激窓はTR内の露出時間を積分した0〜1の値です。`.npz` の軸順は時間×y×x、`.mat` の `stim_windows` は原版に合わせてy×x×時間です。上側の行が視野上方です。注視点、ノイズ、物体、視差自体は解析用の幾何学的刺激窓には含みません。

取得後は `export --config subjects/HB/results/261106/ccwf_run-01/config.json --frames subjects/HB/results/261106/ccwf_run-01/frames.tsv --output actual-windows.npz` のように、実測flipから刺激窓を再構成できます。フレーム落ちの間は直前に表示されていた刺激が保持されたものとして計算します。実装上の左右差や表示機器の光学的遅延は含みません。

各取得に `config.json`, `frames.tsv`, `events.tsv`, `block_timing.tsv`, `targets.tsv`, `responses.tsv`, `summary.json` を保存します。第1実測flipを0秒とし、それ以前のトリガーは負の時刻で残します。全刺激がラン開始からの累積経過時間を使い、前ブロックの終了を次ブロックの起点にはしません。遅れた場合はその時刻の状態に追いつき、速いrefreshでは必要に応じて状態を保持します。

`block_timing.tsv` の `planned_onset_s`、`actual_onset_s`、`error_s` で後半ほどズレが増えていないことを確認できます。`frames.tsv` には状態更新、描画、先行転送のCPU時間も保存します。ログは完全なBIDSデータセットを生成するものではありません。

## 文書と確認

- [プロジェクト・実験ガイド（日本語PDF）](PyRetinotopy_Experiment_Guide_ja.pdf)
- [Project and Experiment Guide（English PDF）](PyRetinotopy_Experiment_Guide_en.pdf)
- [呈示時刻とブロック境界の設計](PRESENTATION_TIMING.ja.md)
- [原版からの機能対応と制約](PTB3_FEATURES.ja.md)
- [原版設定とPython設定の対応](PTB3_PARAMETER_MAP.ja.md)
- [開始位置・走査順と旧版との互換性](PTB3_PARITY.ja.md)

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m unittest discover -s tests -v
& 'C:\Program Files\PsychoPy\python.exe' tools\qa.py --live
```

`qa.py --live` は短い呈示ウィンドウを順に開きます。画面キャプチャは検証専用で、通常の取得では使用しません。

元版のBSDライセンスを保持しています。利用・引用は [LICENSE.txt](../LICENSE.txt) と [NOTICE.md（英語）](../NOTICE.md) を参照してください。

## 結果の保存場所

`--output-root` を省略すると `subjects/ID/results/YYMMDD/モード_run番号/` へ保存します。例：`subjects/HB/results/261106/ccwf_run-01/`。日付は実験PCのローカル日付で、ランの開始処理時に決まります。被験者設定と結果を同じIDフォルダで管理できます。

継承設定の `--subjects-dir` も結果へ反映します。明示JSONがIDフォルダ内にある場合は、その設定ルートを使います。デモ等はプロジェクトのsubjectsを使います。CoderのPyRetinotopy.pyも同じ既定動作です。同じ取得の再実行はフォルダ全体を連番退避し、init-subjectは先に結果があるIDにも設定を追加できます。

別保存先を意図的に使うときだけ `--output-root ROOT` を指定します。この場合は従来の `ROOT/sub-ID/モード_run番号/` です。既存のdataフォルダと過去の取得ログは自動移動しません。上記の解析出力例の261106は実際の取得日に置き換えてください。


## 原版から継承した機能

注視点は `task.fixation_type` のcircle／cross／concentric（数値1／2／3も可）です。原版タイプ2は枠と目盛状の十字、タイプ3は中央点と切れ目のある外周を再現します。`fixation_radius_px` と `fixation_color` を指定し、課題時の暗色は既定で64/255です。

`task.schedule: "ptb3"` では、注視課題の `fixation_frequency`（既定4）、`duration_s`（既定0.3秒）と連続課題を避ける通常スロットを使います。前後注視・休止中も課題を出せます。刺激内課題は原版の位置／色／視差の半期間を使います。`"interval"` は従来Python版の `interval_s` による方式です。

周辺固視ガイドは `display.background_type: "grid"` とpatch設定、半期間マーカーは `marker_timing: "half"`、実測refreshの採用は `use_measured_refresh: true` で設定します。任意のgamma表は `gamma_lut`、dualの第2物理画面は `gamma_lut_right` にN×3のRGBを与えます。詳しい一覧は [機能継承表](PTB3_FEATURES.ja.md) と [全96設定項目](PTB3_PARAMETER_MAP.ja.md) を参照してください。

`preview --all-positions` で全位置とmanifest、`export --prt FILE` で予定／実flipに基づくPRT、`export-olts --output DIR` で原版6色表を出力できます。刺激呈示にはハードウェアOpenGLが必要です。リモートデスクトップでは利用できない場合があるため、実験にはGPUが利用できるローカルデスクトップを使用してください。

本改訂はOpenAIの生成AI（Codex等）の支援を受け、作者・責任者である番浩志が機能継承の確認と動作チェックを行いながら進めています。ソフトウェアと公開版の責任は作者にあります。

[プロジェクトの日本語README](../README_ja.md)
