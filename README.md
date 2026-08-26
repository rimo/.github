# .github

.github リポジトリの中の設定は、github全体に適用される設定として機能するらしい。

https://docs.github.com/ja/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file

そこで、以下の内容のファイルを置いていく。

- 共通で使いたいIssue や Pull Request のテンプレート
- 共通でやりたいCIルール

## Gitleaks(秘密情報スキャン)

2 本の workflow で org 全 repo を守っている。

| workflow | 役割 | 起動 |
|---|---|---|
| `gitleaks.yml` | PR の差分をスキャン。org ruleset `Gitleaks` により default branch への merge に必須 | 各 repo の `pull_request`(ruleset 経由) |
| `gitleaks-unguarded-push.yml` | ruleset を通らずに default branch へ届いた push(新規 repo の初回 push・admin bypass)を全履歴スキャンし、検出時は該当 repo に issue を作成して `#rimo-voice` に通知 | この repo の `schedule`(毎時)/ `workflow_dispatch` |

ruleset は「Do not require workflows on creation」を有効にしてある(無効だと新規 repo の
`main` を一度も push できない)。その代わりに初回 push は `gitleaks-unguarded-push.yml` が
事後検知する。「ruleset を通っていない repo」の判定は **default branch に merged PR が 1 件も無い**
こと(= 内容が直接 push だけで届いている)。一度でも PR が merge されれば以後は ruleset が守る。

必要な secrets(この repo): `GITLEAKS_SCANNER_APP_ID` / `GITLEAKS_SCANNER_APP_PRIVATE_KEY`
(全 repo に install した GitHub App: Contents read / Metadata read / Pull requests read / Issues write)、
`SLACK_WEBHOOK_URL`(`#rimo-voice` 向け Incoming Webhook)。
誤検知は対象 repo 直下の `.gitleaks.toml` で allowlist する(両 workflow 共通)。
