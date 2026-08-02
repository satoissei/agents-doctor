# agents-doctor

**AI コーディングエージェントが `AGENTS.md` から実際に読み込む内容を表示します — 黙って捨てられている部分も含めて。**

エージェントはリポジトリのルートから作業ディレクトリまでの `AGENTS.md` を連結し、
バイト予算で打ち切ります。打ち切りは UI に表示されません。ルート側が先に連結されるため、
**編集中のコードに最も近い、最も具体的な指示から先に消えます。**

## インストール

まだ PyPI には公開していません。GitHub のタグ付きリリース、またはチェックアウトから
インストールしてください。

```console
pipx install "git+https://github.com/satoissei/agents-doctor.git@v0.2.1"

# 開発用チェックアウト
git clone https://github.com/satoissei/agents-doctor.git
cd agents-doctor
pipx install .                  # または: uv tool install .
```

## 使い方

```console
agents-doctor check      # 問題を報告し、あれば終了コード 1   (CI 向け)
agents-doctor explain    # このディレクトリで何が読まれるか   (人間向け)
agents-doctor budget     # リポジトリ全体の予算圧迫状況       (monorepo 向け)
agents-doctor explain --format json  # 読み込み計画を JSON で出力
agents-doctor --codex-config ~/.codex/config.toml explain  # Codex の設定を利用
agents-doctor check --format sarif > agents-doctor.sarif  # GitHub Code Scanning 用
```

`.git` 以外のマーカーでプロジェクトルートを判定する場合は、
`--root-marker NAME` を指定できます。複数指定にも対応しています。

```console
agents-doctor --root-marker .hg explain path/to/package
```

Codex の設定をそのまま使う場合は、`--codex-config` で `config.toml` を渡せます。
`project_doc_max_bytes`、`project_doc_fallback_filenames`、
`project_root_markers` を読み込みます。`--max-bytes` や `--root-marker` などの
コマンドライン指定が優先されます。

## 日本語で指示を書いている場合

予算は**文字数ではなくバイト数**で数えられ、UTF-8 の日本語は1文字3バイトです。
英語なら約3万字入る 32 KiB に、**日本語は約1万字しか入りません。**上限に3倍速く到達します。

さらに打ち切りはバイト位置で行われ、その結果が寛容にデコードされるため、
**マルチバイト文字の途中で切れるとその文字が `U+FFFD` に化けます。**

`agents-doctor` はバイト数と併せて文字数を報告し、文字を破壊する切断を明示します。

## ルール

| ID | 名前 | 既定 | 検出内容 |
|----|------|------|---------|
| `AD001` | `lost-instructions` | error | 予算切れで指示が切断・全損している |
| `AD002` | `broken-path-reference` | error | 指示内で参照しているパスが存在しない |
| `AD004` | `empty-instructions` | warning | 指示に見えて中身が無いファイル |

## 詳細

設定は [docs/configuration.md](docs/configuration.md)、今後の予定は [ROADMAP.md](ROADMAP.md)
を参照してください。完全なドキュメントは英語版 [README.md](README.md) にあります。

## プライバシーと安全性

この CLI はローカルで動作し、ネットワーク通信やテレメトリ送信、読み込んだ指示の実行は
行いません。一方、出力にはリポジトリ相対パス・ファイルサイズ・参照先のパスが含まれるため、
公開共有前に内容を確認してください。実際のローダーに合わせてシンボリックリンクをたどるため、
信頼できないチェックアウトには実行しないでください。

データの扱いは [PRIVACY.md](PRIVACY.md)、脆弱性の非公開報告は
[SECURITY.md](SECURITY.md)、利用上の質問は [SUPPORT.md](SUPPORT.md) を参照してください。

## 検証の範囲について

再現している挙動は openai/codex のソース（コミット `2b5bdcf`）を読んで実装したもので、
実行中のエージェントを計測して確認したものではありません。実挙動との差異を見つけた場合は
[issue](https://github.com/satoissei/agents-doctor/issues) で報告してください。
このプロジェクトにとって最も価値のあるバグ報告です。

## ライセンス

[MIT](LICENSE)。互換性実装の帰属情報は [NOTICE](NOTICE) を参照してください。
