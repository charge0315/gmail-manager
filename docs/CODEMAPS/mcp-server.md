# MCP Server Codemap

**最終更新日:** 2026-04-28
**エントリーポイント:** `server.py`

## 概要
FastMCP フレームワークを使用して、ZenMail Automator の機能を外部（Claude Desktop 等）から呼び出し可能なツールとして提供します。Docker コンテナ内で動作することを前提としています。

## 公開ツール (Exposed Tools)

| ツール名 | 引数 | 説明 | 内部呼び出し |
| :--- | :--- | :--- | :--- |
| `reset_gmail` | なし | 全ラベル/フィルタ削除、INBOX 戻し。 | `GmailResetter` |
| `analyze_emails` | `query`, `max_emails` | メールの分析と rules.json 生成。 | `GmailAnalyzer` |
| `apply_classification_rules` | `archive`, `create_filters` | 生成されたルールの適用。 | `GmailRuleApplier` |

## 動作フロー

1. **起動**: Docker コンテナが起動し、`python server.py` が実行される。
2. **接続**: 標準入出力 (`stdio`) を通じて MCP クライアントと接続。
3. **認証**: `auth.py` が `token.json` を読み込む。コンテナ実行時はホストの `token.json` がマウントされている必要がある。
4. **実行**: クライアント（AI）からの要求に応じて、各ツールのロジックを実行し、結果をテキストで返す。

## Docker 設定

- **Base Image**: `python:3.11-slim`
- **User**: `appuser` (UID: 1000相当)
- **Environment**:
    - `GEMINI_API_KEY`: Gemini API キー
- **Volume Mount**:
    - `/app`: ソイスコードおよび `token.json` / `rules.json` の永続化・共有用。

## 依存関係
- `fastmcp`: MCP サーバーの実装。
- `mcp[cli]`: MCP プロトコルのコア。
- 内部モジュール (`auth.py`, `analyze.py`, `apply_rules.py`, `reset.py`)。

## 注意事項
- 初回認証（OAuth の同意）はブラウザが必要なため、ホスト側で `python auth.py` を実行して `token.json` を作成しておく必要がある。
- `FastMCP` は非同期実行をサポートしているが、現在は同期的に各ツールを実行している。
