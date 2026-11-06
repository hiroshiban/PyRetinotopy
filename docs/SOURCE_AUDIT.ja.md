# 原版調査記録

調査日: 2026-11-06。対象は共有フォルダ `E:\PyRetinotopy\Retinotopy` と [公開リポジトリ](https://github.com/hiroshiban/Retinotopy)。ローカルHEADは `34170a20c64dddc3aa656b099f0bf1847b42b64d`、2024-10-31のdual-display multiflip修正です。

共有版には既存の `Presentation/cretinotopy.m` の変更、複数の被験者設定・実験結果・説明資料・展開済み画像データがあります。これらを初期状態として扱いました。原版をreset、clean、編集、更新していません。開始時のMATLAB・Markdown・テキスト計503ファイルのSHA-256とgit statusをローカルの `source-baseline.json` に保存し、`tools/verify_source.py` で照合します。このファイルは被験者設定のパスを含むためgitignoreしています。

## 目的と構成

原版は、phase-encoded retinotopy、pRF、multifocal GLM、視覚野localizer、HRF評価に利用する視覚刺激の集合です。刺激呈示のコードであり、fMRI画像処理・pRFモデル推定の一式ではありません。`pRF` のOLTs／PRTsと刺激窓はBrainVoyager等の後段解析への接続を担います。

| 原版 | 役割と確認事項 |
|---|---|
| `Presentation/retinotopy.m` | subject・mode・acquisitionを指定する単一窓口。複数モード／run、刺激窓出力を振り分ける |
| `Presentation/c*.m` | カラー／輝度チェッカー。刺激内の変化課題と `_fixtask` の2種類 |
| `Presentation/d*.m` | 視差で定義するRDS。奥行き変化課題と注視課題 |
| `Presentation/i*_fixtask.m` | 物体画像を配置してマスクする刺激。注視課題 |
| `Presentation/subjects/_DEFAULT_` | displayfile、sizeparams、9種類の刺激設定。被験者ごとにコピーして編集する運用 |
| `Generation` | 楔形、環状、バー、multifocalのチェッカー番号・極性・窓生成 |
| `Common/InitializePTBDisplays.m` | 単眼、左右／上下分割、2画面、anaglyph、シャッター、interleaved、PROPixx |
| `Common/eventlogger.m`, `responselogger*.m` | イベント、入力、検出成績と時刻の管理 |
| `Common/mseq.m` | multifocal等の最大長系列 |
| `object_images` | 分割圧縮データと出典。共有版には展開済みv7.3 `img` も存在 |
| `doc/markdowns`, `doc/html` | 設定変数、生成関数、実行スクリプトの説明 |
| `m2html` | MATLABコードのHTML文書化ツール。刺激呈示の移植対象とは分離 |

## 維持すべき特徴

刺激形状は、楔形、環状、バー、楔形＋環状、multifocal、子午線、LGN、HRF、iso-eccentricity localizerの9ファミリーです。方向別に分けると14の基本モードです。チェッカー＋刺激課題、チェッカー＋注視課題、RDS＋刺激課題、RDS＋注視課題、物体画像＋注視課題の5系統を組み合わせ、70のモード名になります。コードは40本の呈示関数と4本の窓生成関数に分かれています。

特に次の実験上の意味を移植対象にしました。

- 楔形の角幅、回転ステップ、開始角、極角／離心度のチェック分割。
- 楔形の角幅と周期に関連付けて環状刺激の幅を決め、視野各点の刺激時間を揃える考え方。
- 拡大と縮小／時計回りの前後で休止の置き方が変わること。
- バーの角度は走査法線。0度は右から左、90度は上から下。各方向後に休止する。
- 楔形＋環状のそれぞれの総時間を一致させつつ、異なる周期を使うこと。
- 注視点だけでなく、刺激内パッチに注意を向ける課題を用意すること。
- 同じ刺激を単眼・両眼装置で利用し、刺激と表示パラダイムを独立させること。

## 原版の主な既定値

| ファミリー | 主な設定 | 前後4秒を含む総時間 |
|---|---|---:|
| 楔形 | 半径8度、幅48度、12度刻み、60秒×6 | 368秒 |
| 環状 | 半径8度、60秒中10秒休止×6 | 368秒 |
| バー | 直径16度、幅1.5度、16位置、40秒中8秒休止、9方向 | 368秒 |
| 複合 | 楔形60秒×6、環状40秒中8秒休止×9、半径7.5度 | 368秒 |
| multifocal | 12極角×3離心度、255試行、各2秒、mseq(2,8,1,1) | 518秒 |
| 子午線 | 幅24度の対向楔形、水平／垂直各16秒×6組 | 200秒 |
| LGN | 幅140度、左右各16秒×6組 | 200秒 |
| HRF | 32秒中16秒休止×6 | 200秒 |
| 離心度localizer | 半径2.7〜3.8度、target／complement各32秒中16秒休止×6組 | 392秒 |

RDSは通常±12 arcminを5段階、ドット中心密度0.5%、半径0.05度、課題時の奥行き倍率2です。**負の視差が手前、正が奥**という符号を引き継ぎます。RDSDenseは面積占有率ではなく、ネイティブ画素ごとのドット中心の出現確率です。

物体画像は通常120枚を1画面に配置し、250 msごとに更新、元画像の0.2〜0.5倍に拡縮、±12 arcminの視差を与えます。共有データは `img` がHDF5上で `(7493,4,256,256)`、すなわち7493枚・256角・RGBAです。元スクリプトは背景ノイズを縦横1/4の解像度で作って拡大しています。説明中のpink/brownianという呼び方は一定せず、ノイズ関数の実際の振幅指数も確認対象です。

## 書き方と運用から読み取れる方針

明文化された独立のスタイル規約やAGENTS.mdは見つかりませんでした。以下はヘッダ、README、設定ファイルと実装からの解釈です。

1. subject/mode/runを渡す単純な入口と、編集しやすい被験者別設定を重視する。
2. ヘッダで目的・引数・戻り値・履歴・出典を説明し、処理を初期化、生成、呈示、保存、終了に分ける。
3. 時間精度のため、刺激形状・テクスチャを先に生成する。色反転はCLUT、反応はキューを使う。
4. 刺激を後から画像回転して済ませず、解析的な極座標場から作り、境界の画像劣化を避ける。
5. 装置差をCommonへまとめ、刺激関数の引数を揃える。
6. 乱数・設定・時刻・取得結果を保存し、例外時に画面を閉じる。
7. READMEのTODOはコード重複の削減とオブジェクト指向化を挙げる。Python移植では刺激×課題×表示のクローンを増やさない。
8. BSDライセンス、画像データ・m系列等の出典と引用を保つ。

## 発見した差分・注意点

`Generation/mf_GenerateCheckerBoard1D.m` のmultifocal領域ID生成では、非位相シフト時に `true_nwedges=ndivsE` を代入し、離心度方向のオフセットへ使っています。極角12・離心度3の場合、領域IDが重複し得ます。Python版の既定は `sector + ring * sectors` に修正しました。v0.3.0では `multifocal_indexing: "ptb3"` も用意し、ゼロ位相・全周条件の原版ID重複を再現できます。元MATLABは変更していません。過去の刺激窓との比較には採用するID規則を明示してください。

元コードは画像行の下向きy、回転順の反転、サイクル内の初期位置処理を組み合わせています。v0.3.0では設定開始角を元の時計回り規約で解釈し、視野座標へ変換しています。cwは中心90度、ccwは配列全体の逆順により中心102度から開始します。複合環は極角側の保持時間を使う16位置・2秒刻みへ修正しました。全70モードの位置式を独立照合しています。詳しい範囲と境界画素等の限界は [位置対応の記録](PTB3_PARITY.ja.md) を参照してください。

MATLABのMEX群、BrainVoyager OLT／PRT、EyeLink等の補助ユーティリティ、PROPixx/Datapixx制御、平行ポートの電圧入力はPython版の機能と同一視しません。現時点の対応範囲はMIGRATION文書に記録しました。

## 採用した名称

| 候補 | 意図 |
|---|---|
| **PyRetinotopy** ＋識別子 `pyretinotopy` | 採用。Python版であることが伝わり、原版Retinotopyと大小文字以外で区別できる |
| **RetinoStereoPy** | 両眼立体視とPythonを名称で伝える。やや長いが特徴が分かりやすい |
| **RetinoMapPy** | retinotopic mappingの用途が伝わる。刺激呈示以外の解析パッケージとも解釈され得る |

正式表示名・プロジェクトディレクトリ名はPyRetinotopy、配布・import・コマンド名は `pyretinotopy` としました。公開APIでの名称確認は [NAME_CHECK.ja.md](NAME_CHECK.ja.md) を参照してください。

検索時は `Hiroshi Ban PyRetinotopy PsychoPy binocular retinotopy` のように著者・用途・依存ツールを併記できます。類似の [psychopy-retinotopy](https://github.com/Matt-A-Bennett/psychopy-retinotopy) は既に存在するので、名称だけでなくREADMEの著者・原版URL・立体視対応の説明で区別します。検索結果の有無から名称の独占性を断定していません。


## v0.4.0での全設定・手続き再調査

ラン引数と一括バックアップ、原版注視点の実形状、課題、背景ガイド、gamma、色と視差の時間系列、マーカー、実測refresh、PRT/OLTとDEBUG代替を再照合しました。[機能継承表](PTB3_FEATURES.ja.md) と [全96項目の対応](PTB3_PARAMETER_MAP.ja.md) を参照してください。機器アダプタの未対応とGPU実測待ちも明記しています。
