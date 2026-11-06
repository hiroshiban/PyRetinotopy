# PTB3からの機能継承 - v0.4.0

PyRetinotopyは、原版Retinotopyの実験上の機能を継承し、実装基盤をMATLAB Psychtoolbox 3からPython／PsychoPyへ置き換えるプロジェクトです。同じ目的を、共通の刺激定義・累積時刻・事前準備・独立乱数列・一括バックアップによって実装しています。

OpenAIの生成AI（Codex等）が調査・実装・検証・文書作成を支援し、作者・責任者の番浩志が機能継承の確認と動作チェックを行いながら改訂を進めています。ソフトウェアと公開の責任は作者が担います。下記の実施済み・未実施を区別します。

## 調査範囲

原版のPresentation直下46ファイル（呈示関数40本、共通入口、刺激窓生成4本、補助スクリプト）、_DEFAULT_の11設定ファイル、Generation・CommonとpRF補助資産を確認しました。プライベートな被験者設定を除くMATLAB278ファイルをハッシュ付きで一覧化し、参照されるdparam 15項目・sparam 81項目をすべて分類しました。「未分類0」は機器を含む全検証の完了を意味しません。

[96項目の個別対応表](PTB3_PARAMETER_MAP.ja.md) / [関数別・ソース別の監査JSON](qa/ptb3-feature-audit.json)。原版503ファイルの保全確認は別途継続します。

## 機能の対応

| 機能 | 継承・改善した実装 | 検証・制約 |
|---|---|---|
| 9刺激群・14方向別モード・5 carrier/task系統 | 全70名と10 windows名を共通Design/Geometryへ集約 | 全70の連続座標マスク照合。MATLAB画素の完全一致は未確認 |
| 楔形・環・複合・バーの開始と走査 | 画像座標、ccw全配列逆順、複合16環位置、楔形優先 | 元の式から独立照合済み |
| 被験者別・既定値fallback | _DEFAULT_→ID差分。部分JSON、family/mode設定、独立保存設定 | 相対パス・継承順・旧取得再現を試験 |
| ラン番号・繰り返し撮像 | --run N、config/summary/acquisition/フォルダに反映 | 同じ刺激でもrun 1/2/3を別に保存 |
| 同じランの再試行 | フォルダ全体を_old-01、02…へ退避、原名へ最新試行 | 全ファイルのバイト列・時刻、他run・旧backupの不変を試験 |
| 実行前確認・中止・異常終了 | ID/mode/run確認、取消は退避前。Escape/Q、失敗ログ | OSロックは準備から最終保存まで保持。プロセスクラッシュで解放 |
| 注視点1：円 | 原版の円形alphaと前景 | 大きさ・色・暗色を設定可能 |
| 注視点2：rectangular | 原版CreateFixationImgMonoの枠＋目盛状十字（cross） | 以前の単純square解釈を修正。squareは追加選択として保持 |
| 注視点3：concentric | 中央円と切れ目のある外周・円形背景 | 以前の黒い同心円を修正。描画は事前計算 |
| 注視課題 | fixtaskfreq、duration、通常slot、64/255の暗色。前後注視・休止も対象 | ptb3/interval方式を選択。MATLABと同じ乱数列は主張しない |
| 刺激内課題 | 半位置窓、localizer/HRF等の短い色・視差窓、可視パッチの輝度／奥行き変化 | 実際のflipからRT。未呈示課題をmissにしない |
| 色列・更新頻度 | 最初の活動時刻から開始、休止で停止。原版の既定Hzを修正 | バー4、子午線5、LGN/HRF3.75 Hzの完全色反転対 |
| RDS | 対向checker面が5段階等を循環、負視差が手前。密度・半径・色・背景・課題倍率 | 従来random割当も選べる。小角度の視差を直接degreeへ変換し、循環画像シフトを廃止 |
| 物体画像 | 120枚、倍率・視差・250 ms更新・有色ノイズ、native NumPy、事前合成 | 7,493枚のRGBA値一致。乱数配置・補間はMATLABと同一ではない |
| 背景の周辺固視ガイド | plain/grid、patchサイズ・数・2色、中央透明域、左右共通乱数 | 読込時に眼領域への収まりを検査。GPU描画の再確認はローカル接続時 |
| 単眼／両眼表示 | 15表示方式、左右上下分割、anaglyph、interleaved、dual、shutter | ソフトウェア眼割当試験。実機同期・crosstalk・quad-bufferは別確認 |
| gamma | RGB指数、任意N×3 JSON表、dual第2画面表 | OS全体を書き換えず局所適用。測光校正は装置で実施 |
| 開始操作 | Space/Enter、左クリック、scanner key、任意named key、即時開始 | parallel-port電圧入力は未対応。数値PTBキーコードを推測変換しない |
| refresh／待機 | force_frame_rate相当の指定・実測採用、全refreshで状態更新判定 | skip_sync_testの検査無効化は継承せず、実測と設定の整合性を検査 |
| フォトダイオード用marker | 4隅、サイズ、半位置保持（既定）／任意秒 | 光学到達時刻は実測が必要 |
| 時間・反応・結果 | 単一t0から累積期限、events/frames/block_timing、statusとUUID | 別ブロックの実測終了を起点にしない |
| 刺激窓・TR・低解像度再構成 | planned/actualフリップ、TR内露出積分、npz/mat、resolution変更 | 元のTR瞬間取り出しから露出積分へ改善 |
| PRT／OLT | 共通時系列からmsec/VolumesのPRT、原版6 OLTを無変更配布 | ファイル構造試験済み。BrainVoyager本体での読込確認は残る |
| DEBUG／刺激確認 | preview --time、--all-positionsとmanifest、14刺激gallery | subject名による暗黙debugを明示的なofflineコマンドへ置換 |

PRT形式は [BrainVoyagerの一次資料](https://helpdesk.brainvoyager.com/729383-The-Format-of-PRT-Files) に基づきます。Volumesは1始まりの両端を含む区間、msecはラン開始からのミリ秒で出力します。実測flip等でTR境界に一致しない区間はVolumesへ丸めずエラーにします。

## 残る機器依存・補助機能

PROPixx/Datapixxの専用初期化・VESA/blue-line制御とparallel-port pin電圧入力は、現在のPCに対象機器がなく、検証済みアダプタを用意できていません。対応しない方式へ黙って置換しません。2画面swapとシャッターの物理同期、スキャナ・反応箱、gammaと光学時刻は使用装置で確認します。

CommonにはEyeLink・MEG・音声・画像処理などの汎用補助関数も付属します。全278ファイルの同名Python翻訳はしていません。m2htmlによるMATLAB HTML生成もPython移植の機能とは分けています。刺激呈示の入口から使う機能を上表へ統合しています。

## 再現と検証状況

v0.3.0以前の取得設定はsummaryの版を調べ、未記載の旧座標・色時計・RDS割当・注視点・課題・marker設定を補います。通常の設定ファイルは新既定値を使います。新しい取得には採用した全設定が保存されます。

96件の自動テストが成功しています。今回のRDP接続ではpygletがGDI Generic、GLFWがWGL非対応となり、v0.4.0の実画面試験は開始前に失敗しました。ローカルGPUでの12条件試験を次に実行します。過去v0.3.0の8条件、v0.2.0の368秒測定を今回の成功として扱いません。[検証記録](VALIDATION.ja.md) を参照してください。
