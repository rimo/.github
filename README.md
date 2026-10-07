# .github

.github リポジトリの中の設定は、github全体に適用される設定として機能するらしい。

https://docs.github.com/ja/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file

そこで、以下の内容のファイルを置いていく。

- 共通で使いたいIssue や Pull Request のテンプレート
- 共通でやりたいCIルール

## Gitleaks(秘密情報スキャン)について

- `.github/workflows/gitleaks.yml` は org ruleset `Gitleaks` の required workflow 本体で、
  **org 全 repo の PR で実行される**。GitHub は private repo の workflow を public repo では
  実行しないため、public repo も守れるようにこの public repo に置いている。secret は使わない
  (`GITHUB_TOKEN` の `contents: read` のみ)ので、public でも問題ない
- ruleset はこのファイルを **commit SHA に固定**して参照している。ここを変更して merge しても、
  org admin が ruleset の SHA を更新するまで反映されない
- 初回 push の事後検知(`gitleaks-unguarded-push.yml`)は org secret が必要なため
  `rimo/rimo-develop` に置いてある。詳細は rimo-develop の `docs/gitleaks.ja.md` を参照

## Cloud Run env guard について

- `.github/workflows/cloud-run-env-guard.yml` は、PR で **追加された行**に Cloud Run の env /
  secret 参照を書く操作があると fail する check。Cloud Run の env は `rimo/iac-google-cloud` の
  terraform が持つので、app repo の deploy が env を書いて定義が 2 か所になるのを防ぐ。
  検査の対象・通し方(人が付ける label)・自身のエラーでは fail しないことは、ファイル冒頭の
  コメントが正
- Gitleaks と同じく org ruleset の required workflow として使う前提で、ruleset は **commit SHA に
  固定**して参照する。ここを変更して merge しても、org admin が ruleset の SHA を更新するまで
  反映されない
- 検査の本体は workflow に埋め込んだ Python で、test は `tests/`(`python3 -m unittest discover -s tests`)
