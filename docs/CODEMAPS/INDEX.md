# ZenMail Automator Codemap

**最終更新日:** 2026-04-28
**エントリーポイント:** `zenmail.py` (CLI), `server.py` (MCP Server)

## アーキテクチャ

```mermaid
graph TD
    subgraph Client
        cli[zenmail.py (CLI)]
        mcp_client[Claude Desktop / MCP Client]
    end

    subgraph "MCP Server (Docker)"
        server[server.py (FastMCP)]
        docker[Dockerfile / appuser]
    end

    cli --> auth[auth.py (OAuth/Network)]
    server --> auth
    
    auth --> analyze[analyze.py (Gemini API)]
    auth --> apply[apply_rules.py (Gmail API)]
    auth --> reset[reset.py (Cleanup)]

    extract[extract_unclassified.py] --> apply
    refine[refine_rules.py] --> analyze

    rules[(rules.json)] <--> analyze
    rules <--> apply
    server <--> rules

    subgraph Google APIs
        gmail[Gmail API]
        gemini[Gemini 3.1 API]
    end

    auth --> gmail
    analyze --> gemini
    apply --> gmail
    reset --> gmail
```

## 主要モジュール

| モジュール | 役割 | 主要な依存関係 |
| :--- | :--- | :--- |
| `server.py` | **MCPサーバーコア**。FastMCP を使用し、Gmail 操作ツールを AI に提供。 | `fastmcp`, `auth`, `analyze`, `apply_rules`, `reset` |
| `zenmail.py` | 統合CLI。`analyze`, `apply`, `reset` のローカル実行用インターフェース。 | `auth`, `analyze`, `apply_rules`, `reset` |
| `auth.py` | Google OAuth2 認証、IPv4 強制パッチ。 | `google-auth`, `google-api-python-client` |
| `analyze.py` | メールの分析、Gemini 3.1 を用いた `rules.json` 生成。 | `google-genai`, `auth` |
| `apply_rules.py` | ラベル作成、メール移動（アーカイブ対応）、フィルタ作成。 | `auth`, `googleapiclient` |
| `reset.py` | ラベルやフィルタの削除、受信トレイへの完全復元。 | `auth`, `googleapiclient` |
| `utils.py` | リトライロジック、パケット待機、ロギングなどの共通ユーティリティ。 | `time`, `logging` |

## データフロー

1. **初期化 (Reset)**: `reset.py` が既存のラベル/フィルタを消去し、INBOX をクリーンにする。
2. **分析 (Analyze)**: `analyze.py` が過去のメールを収集し、Gemini 3.1 が `rules.json` を提案。
3. **適用 (Apply)**: `apply_rules.py` が `rules.json` を元に Gmail 側を再構築。
4. **MCP 経由の操作**: AI アシスタントが `server.py` を通じて上記のフローをオンデマンドで実行。

## 技術的知見
- **Docker 化**: セキュリティのため非特権ユーザー `appuser` を使用。`-v` マウントにより `token.json` を共有。
- **FastMCP**: ツール定義デコレータ `@mcp.tool()` により、既存の Python ロジックを即座に MCP ツール化。

## 関連ドキュメント
- [README.md](../../README.md): 全体概要と利用ガイド
- [mcp-server.md](./mcp-server.md): MCP サーバーの詳細仕様

