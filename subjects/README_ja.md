# 被験者設定と既定値の継承

[English](README.md) | [日本語](README_ja.md)

原版の `Presentation/subjects/_DEFAULT_` に対応する場所は、このPython版の **`subjects/_DEFAULT_/`** です。MATLABファイルの代わりにJSONを使用します。

```text
subjects/
  _DEFAULT_/
    common.json                 # seed、run、課題の共通既定値
    retinotopy_display.json      # display設定
    c_pol.json                  # 楔形
    c_ecc.json                  # 環状刺激
    c_dual.json                 # 楔形＋環状
    c_bar.json
    c_multifocal.json
    c_meridian.json
    c_lgnlocalizer.json
    c_hrf.json
    c_localizer.json
  HB/
    common.json                 # 被験者共通の差分（任意）
    retinotopy_display.json      # 被験者の表示設定の差分（任意）
    c_pol.json                  # 被験者の楔形設定の差分（任意）
    ccwf.json                   # このモードだけの差分（任意）
```

## 作成・確認・実行

プロジェクト直下で、PsychoPyのPythonを使います。

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy init-subject HB --mode ccwf
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy validate --subject HB --mode ccwf
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --subject HB --mode ccwf
```

`init-subject` は空の `HB/common.json` と、run番号だけを持つ `HB/ccwf.json` を作成します。既存の設定ファイルは上書きしません。結果だけが存在する被験者フォルダにも設定を追加でき、既存common.jsonは保持します。被験者フォルダや個別ファイルが存在しなくても、`--subject HB` は既定値で動作します。読み込んだファイルは `validate` の `configuration_sources` に表示されます。

## 読込み順序

以下の順に、**指定された項目だけを上書き**します。

1. Python内蔵の刺激ファミリー別既定値。
2. `_DEFAULT_/common.json` → `retinotopy_display.json` → 対応する `c_*.json` → `<mode>.json`（あれば）。
3. `HB/common.json` → `retinotopy_display.json` → 対応する `c_*.json` → `<mode>.json`（あれば）。

被験者側の値は、既定ファミリーファイルの値より優先します。同じ被験者内では後のファイルが優先します。辞書は項目ごとに重ね、リストは全体を置き換えます。省略したファイル・項目は既定値を使いますが、存在するファイルの構文エラーや未知の項目名はエラーとして通知します。

たとえば `HB/retinotopy_display.json` には、その被験者の位置補正だけを記載できます。

```json
{
  "display": {
    "eye_offsets_px": [[3, -2], [-4, 5]],
    "mirror_x": [false, false]
  }
}
```

`HB/c_pol.json` に下記を書くと、`ccw` / `cw` の全キャリアと課題に共通して適用されます。

```json
{
  "stimulus": {"wedge_width_deg": 60},
  "timing": {"cycle_s": 60, "repeats": 6}
}
```

`HB/ccwi.json` は物体画像の楔形だけに適用する設定です。`mode` や `subject` をJSONにも書く場合は、コマンドの指定と一致させてください。

画像・キャッシュの相対パスは、**その値を定義したJSONの場所**から解決します。被験者側で別の値を指定しなければ、既定ファイルのパスは被験者フォルダを基準に再解釈しません。

## ファミリーの対応

| ファイル | 基本モード |
|---|---|
| `c_pol.json` | ccw, cw |
| `c_ecc.json` | exp, cont |
| `c_dual.json` | ccwexp, ccwcont, cwexp, cwcont |
| `c_bar.json` | bar |
| `c_multifocal.json` | multifocal |
| `c_meridian.json` | meridian |
| `c_lgnlocalizer.json` | lgn |
| `c_hrf.json` | hrf |
| `c_localizer.json` | localizer |

配布の `retinotopy_display.json` は全画面・実機校正済みの設定ではありません。撮像前に解像度・物理幅・距離・表示方式・refresh・開始信号を装置へ合わせてください。

## 確定設定、画像準備、セッション

```powershell
python -m pyretinotopy validate --subject HB --mode ccwf --save-config resolved-HB-ccwf.json
python -m pyretinotopy prepare-objects --subject HB --mode ccwi
python -m pyretinotopy run --subject HB --mode ccwi
```

`--save-config` は全項目を展開したJSONを保存します。通常の取得でも `subjects/ID/results/YYMMDD/モード_run番号/config.json` に展開済みの設定を保存し、`summary.json` に設定元の一覧を残します。既定ファイルを後から編集しても、`--config 保存済みのconfig.json` による再実行の条件は変わりません。

**`--config FILE` は独立した明示設定**です。この方法では `_DEFAULT_` や被験者の別ファイルを探索せず、JSONで省略された項目にはPython内蔵の既定値だけを使います。継承を使う実行は `--subject ID --mode MODE`、保存済み条件の再実行は `--config FILE` と区別します。両オプションの同時指定は拒否します。

`--subjects-dir PATH` で設定ルートを変更できます。指定先に `_DEFAULT_` がない場合は内蔵値へ戻るので、共有の既定値も引き継ぐ場合は `_DEFAULT_` を配置してください。カスタムルートと被験者設定は自動生成しません。

セッションの各runでも `config` の代わりに以下を指定できます。`subjects_dir` は任意で、記載した場合はsession.jsonの場所が基準です。

```json
{
  "runs": [
    {"subject": "HB", "mode": "ccwf", "run": 1},
    {"subject": "HB", "mode": "expf", "run": 1}
  ]
}
```

被験者フォルダはGit管理から除外し、配布する `_DEFAULT_` と本書だけを含める設定です。実験室の設定は適切にバックアップしてください。

## 被験者内にまとめる結果保存

既定保存先は `subjects/ID/results/YYMMDD/モード_run番号/` です。例：`subjects/HB/results/261106/ccwf_run-01/`。日付はラン開始処理時の実験PCのローカル日付です。設定を先に作成していない場合でも被験者フォルダを自動作成します。

`--subjects-dir` を使う継承設定では、その設定ルートのIDフォルダ内へ保存します。明示JSONが被験者IDのフォルダ内にあれば、その設定ルートを使います。`examples/smoke.json` 等はプロジェクトの `subjects/demo/` へ保存します。

保存ファイル名がラン間で衝突しないよう、日付の下に各モード・runのサブフォルダを設けています。同じ日・ID・モード・runを再実行すると、既存フォルダ全体を `_old-01`、`_old-02`…へ退避して新しい試行を保存します。`run --run N` はJSONのrun値に優先します。異なるrun番号は別フォルダです。既定は自動backupで、`--if-exists error` は既存時に取消します。`--output-root ROOT` を明示した場合だけ、従来の `ROOT/sub-ID/モード_run番号/` へ保存します。既存のdataフォルダは変更しません。

## 関連ドキュメント

- [プロジェクトの日本語README](../README_ja.md)
- [日本語の使い方ガイド](../docs/USAGE.ja.md)
- [原版設定とPython設定の対応](../docs/PTB3_PARAMETER_MAP.ja.md)
