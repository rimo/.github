# .github

.github リポジトリの中の設定は、github全体に適用される設定として機能するらしい。

https://docs.github.com/ja/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file

そこで、以下の内容のファイルを置いていく。

- 共通で使いたいIssue や Pull Request のテンプレート
- 共通でやりたいCIルール

## Gitleaks(秘密情報スキャン)について

org 全体の gitleaks workflow(ruleset の required workflow と、初回 push の事後検知)は
**`rimo/rimo-develop` の `.github/workflows/` に置いてある**(`docs/gitleaks.ja.md` 参照)。
この repo は public で org secret が使えず内容も公開されるため、2026-08 に移した。
