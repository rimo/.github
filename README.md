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
