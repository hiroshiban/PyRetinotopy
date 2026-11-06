# TortoiseGitでの管理とGitHubへの公開

TortoiseGitはGitの`.gitignore`を利用します。既存ファイルをTortoiseGitへインポートする操作は不要です。レポジトリのルートに置くと、その下の未追跡ファイルへ適用されます。`.gitignore`自体もコミットして共有してください。[TortoiseGit公式説明](https://tortoisegit.org/docs/tortoisegit/tgit-dug-ignore.html)

## このプロジェクトのルート

README.md、pyproject.toml、.gitignore、pyretinotopy/、docs/、subjects/が並ぶディレクトリをルートにします。共有環境では `E:\PyRetinotopy\PyRetinotopy` です。MATLAB原版RetinotopyとPython版が並ぶ親ディレクトリとは区別してください。

## 最初の登録

1. エクスプローラーで上記ルートを開き、右クリックから **Git Create repository here...** を選びます。作業ファイルを管理する通常のレポジトリとして作成し、Bareにはしません。[作成手順](https://tortoisegit.org/docs/tortoisegit/tgit-dug-create.html)
2. **TortoiseGit → Check for modifications** またはコミット画面で、未追跡ファイルを確認します。`.gitignore`、コード、subjects/_DEFAULT_のJSON、docsのPDF、pyretinotopy/data/brainvoyager/の6色表が追加候補になります。表示対象でignoredを選ぶと、除外された項目も確認できます。[状態の表示](https://tortoisegit.org/docs/tortoisegit/tgit-dug-wcstatus.html)
3. 追加対象を選択し、最初のコミットを作成します。通常の操作ではignoredファイルを強制追加する必要はありません。
4. GitHubで用意した空のレポジトリへ、**TortoiseGit → Push...** から送信します。Push先には登録したremoteまたはGitHubのレポジトリURLを指定できます。初回にREADME等をGitHub側で別途作ると履歴が分かれるため、このローカル一式を最初のコミットにする構成が扱いやすくなります。[Pushの公式説明](https://tortoisegit.org/docs/tortoisegit/tgit-dug-push.html)

## 配布するもの・除外するもの

| Gitに含める | Gitから除外する |
|---|---|
| .gitignore、コード、LICENSE.txt、NOTICE.md | 被験者ごとの設定と実験結果（subjects/_DEFAULT_とREADMEを除く） |
| subjects/_DEFAULT_の共通設定 | images.npy等の大容量画像バンク |
| docsの日本語・英語PDFと編集元 | cache、.runtime、tmp、build、optional-libs |
| pyretinotopy/data/brainvoyager/の6つのOLT | ルート直下のdata/、ローカル原版保全記録 |

`/data/`はレポジトリ直下だけを除外します。先頭スラッシュのない`data/`では、配布に必要なパッケージ内のdataディレクトリも除外されるため区別しています。

画像バンクと事前合成動画はコードと分けて配布・準備します。GitHubは通常のGitで100 MiBを超えるファイルを受け付けないため、約1.96 GBのimages.npyを通常コミットへ含めません。[GitHubのファイルサイズ制限](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)

カスタムの結果保存先をレポジトリ内に作る場合は、そのディレクトリも除外します。TortoiseGitの **Add to Ignore List** から、共有する設定はルートの.gitignore、ローカルだけの設定は.git/info/excludeを選べます。[除外リストの設定](https://tortoisegit.org/docs/tortoisegit/tgit-dug-ignore.html)

## 既に追加・コミットしたファイル

.gitignoreは既にGitが追跡しているファイルには作用しません。誤って追跡したローカルデータを残す場合は、TortoiseGitの拡張コンテキストメニュー **Delete (keep local)** で追跡を外し、その変更をコミットします。必要に応じてShiftを押しながら右クリックすると拡張項目が表示されます。データを消す通常のDeleteとは区別してください。[TortoiseGitの説明](https://tortoisegit.org/docs/tortoisegit/tgit-dug-delete-copy-move.html)、[Gitの追跡済みファイルと.gitignore](https://git-scm.com/docs/gitignore)

既に公開した履歴からの機密情報・大容量データの除去は、現在の追跡を外す操作とは別です。最初のコミット前に追加候補を確認してください。

## コマンドでの再確認

```powershell
& 'C:\Program Files\PsychoPy\python.exe' tools\check_publication.py
```

この検査は一時Git管理領域だけを使い、本体のレポジトリ初期化・Add・Commit・Pushは行いません。実際の.gitignoreで、必要な色表・設定・PDFが除外されず、実験データ・画像バンク・キャッシュが除外されることを確認します。結果はdocs/qa/publication-gitignore-review.jsonへ保存します。
