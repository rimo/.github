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
| `gitleaks-unguarded-push.yml` | ruleset を通らずに default branch へ届いた push(新規 repo の初回 push・admin bypass)を全履歴スキャンし、検出時は該当 repo に issue を作成して `#rimo-voice` に通知 | この repo の `schedule`(毎週月曜 10:00 JST、直近 8 日の push が対象)/ `workflow_dispatch` |

ruleset は「Do not require workflows on creation」を有効にしてある(無効だと新規 repo の
`main` を一度も push できない)。その代わりに初回 push は `gitleaks-unguarded-push.yml` が
事後検知する。「ruleset を通っていない repo」の判定は **default branch に merged PR が 1 件も無い**
こと(= 内容が直接 push だけで届いている)。一度でも PR が merge されれば以後は ruleset が守る。

必要な secrets: org secret の `RIMO_GITHUB_APP_ID` / `RIMO_GITHUB_APP_PRIVATE_KEY`
(既存の org 横断 GitHub App `rimo-github-actions`。全 repo に install 済み)と、同じく org secret の
`SLACK_BOT_TOKEN`(`chat.postMessage` で `#rimo-voice` へ投稿。追加の secret 登録は不要)。
誤検知は対象 repo 直下の `.gitleaks.toml` で allowlist する(両 workflow 共通)。

## Gitleaks(秘密情報スキャン)について

org 全体の gitleaks workflow(ruleset の required workflow と、初回 push の事後検知)は
**`rimo/rimo-develop` の `.github/workflows/` に置いてある**(`docs/gitleaks.ja.md` 参照)。
この repo は public で org secret が使えず内容も公開されるため、2026-08 に移した。
