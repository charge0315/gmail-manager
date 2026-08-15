# Mail Organizer

Mail Organizer は、最新の **Gemini 3.6 シリーズ (Flash) / 3.1 シリーズ (Pro)** を活用して、複数の Gmail アカウントおよび Outlook アカウントの受信トレイを賢く、自動的に整理するためのツールセットです。
新たに **MCP (Model Context Protocol) サーバー** としての機能が追加され、Claude Desktop などの AI アシスタントから直接メールを操作・整理できるようになりました。

過去のメール履歴を分析し、あなたのライフスタイルに最適なカテゴリ（例: 22個のカテゴリ）を自動生成。Gmail では色分けラベルとフィルタの作成、Outlook ではフォルダ自動作成とフォルダ移動を用いて、複雑な検索クエリを手動で書くことなく「Inbox Zero（受信トレイを空にする）」を100%確実に実現するための完全な反復的ワークフローを提供します。

---

## 🌟 主要な特徴

- **🤖 ハイブリッド AI モデル分析**:
  初期の広範なルール分析には高速・低コストな `gemini-3.6-flash` を使用し、未分類メールに基づいた高度なルール洗練には高性能な `gemini-3.1-pro` を使用するハイブリッド構成。
- **📧 複数アカウント＆マルチプロバイダ対応 (Gmail / Outlook)**:
  `accounts.json` にて定義された複数の Gmail アカウントおよび Outlook アカウントに対して一括して処理を実行可能です。
- **📂 プロバイダに適した分類方式**:
  Gmail では API による色付き「ラベル」と「自動振り分けフィルタ」を作成。フォルダ階層型の Outlook では、ラベルの代わりに「フォルダ」の動的作成とメールの「移動」による整理を行います。
- **🔌 MCP (Model Context Protocol) サーバー対応**:
  Docker ベース of MCP サーバーとして動作し、AI アシスタント (Claude Desktop 等) からメールの分析、適用、リセットを自然言語で直接実行可能。
- **🧹 安全な「完全リセット」機能**:
  作成したカスタムラベル/フォルダやフィルタを一括削除し、アーカイブ・移動されたすべてのメールを受信トレイに戻す「元通り」復元機能を完備。いつでも安全にやり直せます。

---

## 🛠️ システム構成と各スクリプトの役割

プロジェクトは以下のモジュールで構成されています：

*   **`mail_organizer.py`**: 全体を取りまとめるメインの統合 CLI エントリポイント。
*   **`accounts.json`**: 処理対象とする Gmail / Outlook アカウントの設定ファイル。
*   **`auth.py`**: Gmail OAuth 2.0 認証を管理し、アカウント別にトークンを保存。
*   **`auth_outlook.py`**: Outlook OAuth 2.0 認証 (XOAUTH2) を管理し、アカウント別にトークンを保存。
*   **`outlook_client.py`**: IMAP (XOAUTH2) 経由で Outlook アカウントを操作するクライアント。フォルダ名 Modified UTF-7 エンコード対応。
*   **`query_evaluator.py`**: Gmail風の検索クエリを Python 側で判定するエンジン（Outlook の分類時に使用）。
*   **`analyze.py`**: メールのメタデータを抽出し、Gemini API を使って分類ルールを生成するコアロジック。
*   **`apply_rules.py`**: `rules.json` に基づいて Gmail 側にラベルとフィルタを適用するロジック。
*   **`reset.py`**: Gmail のカスタムラベルとフィルタを完全削除し、全メッセージを受信トレイ（INBOX）へ安全に差し戻すリカバリ処理。
*   **`server.py`**: MCP サーバーのエントリポイント。
*   **`utils.py`**: 指数バックオフ付きリトライ処理など、メール操作通信を安定させるためのユーティリティ。

---

## 🔐 認証セットアップ

### 1. Gmail アカウントの準備 (OAuth 2.0)
Gmail API を操作するため、Google OAuth 2.0 クライアント認証を使用します。

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成し、**Gmail API** を有効化します。
2. 「OAuth 同意画面」を設定し、テストユーザーに自身の Gmail アドレスを追加します。
3. **OAuth 2.0 クライアント ID** (デスクトップアプリ) を作成し、JSON 形式でダウンロードします。
4. ダウンロードしたファイルを `credentials.json` という名前でプロジェクトのルートディレクトリに配置します。
5. 初回実行時にブラウザが起動し、アカウントごとに `token_<account_id>.json` が生成されます。

### 2. Outlook アカウントの準備 (OAuth 2.0 / XOAUTH2)
Microsoft 側の基本認証（アプリパスワード含む）廃止に伴い、OAuth 2.0 での接続が必要です。

1. **[Azure ポータル](https://portal.azure.com/) にサインイン**します（Microsoft アカウントで無料で利用可能です）。
2. 「**Microsoft Entra ID**」を選択します。
3. 左側メニューの「**アプリの登録**」をクリックし、「**新規登録**」を選択します。
4. 以下のように設定して「登録」をクリックします：
    *   **名前**: `Mail-Organizer` (任意)
    *   **サポートされているアカウントの種類**: 「**任意の組織のディレクトリ内のアカウントと、個人用の Microsoft アカウント (Skype、Xbox など)**」（※個人アカウントと組織アカウント両方に対応させるため必須）
    *   **リダイレクト URI**: 種類に「**パブリック クライアント/ネイティブ (モバイルとデスクトップ)**」を選択し、値に `http://localhost` と入力。
5. 登録完了画面に表示される「**アプリケーション (クライアント) ID**」（36桁のGUID）をコピーし、`accounts.json` の `client_id` に設定します。
6. 左側メニューの「**API のアクセス許可**」をクリックし、「**アクセス許可の追加**」を選択します。
    *   「**所属する組織が使用する API**」タブを選択し、検索窓に `Office 365 Exchange Online` と入力して選択します。
    *   「**委任されたアクセス許可**」を選択し、アクセス許可の一覧から **`IMAP.AccessAsUser.All`** にチェックを入れ、「アクセス許可の追加」をクリックします。
7. 初回実行時、ブラウザが起動し Microsoft アカウントのサインインと承認を求める画面が表示されます。認証完了後、アカウントごとに `token_outlook_<account_id>.json` が生成されます。

---

## ⚙️ アカウント設定 (`accounts.json`)

ルートディレクトリに `accounts.json` を作成し、整理対象のアカウント情報を以下のように定義します。

```json
[
  {
    "id": "gmail_personal",
    "name": "Gmail 個人用",
    "type": "gmail",
    "email": "yourname@gmail.com"
  },
  {
    "id": "outlook_work",
    "name": "Outlook 仕事用",
    "type": "outlook",
    "email": "yourname@outlook.com",
    "imap_server": "outlook.office365.com",
    "imap_port": 993,
    "username": "yourname@outlook.com",
    "client_id": "YOUR_AZURE_CLIENT_ID"
  }
]
```
- **Gmail アカウント**: `id`, `name`, `type: "gmail"`, `email` を指定します。
- **Outlook アカウント**: `id`, `name`, `type: "outlook"`, `email`, `username`, `client_id` を指定します。

---

## 💻 CLI 利用ガイド

### 1. 依存関係のインストール
```bash
pip install -r requirements.txt
```

### 2. 整理ワークフローの実行

#### **ステップ 1: メールの収集と AI 分析**
過去のメールデータを分析し、各アカウント用の分類ルール（`rules_{account_id}.json`）を生成します。
```bash
# すべてのアカウントを分析する場合
python mail_organizer.py analyze --max 500

# 特定のアカウント（ID: gmail_personal）のみ分析する場合
python mail_organizer.py analyze --account gmail_personal --max 500
```

#### **ステップ 2: ルール適用のシミュレーションと実行**
生成されたルールに基づき、ラベルやフォルダの作成、およびメールの分類整理を行います。

> [!TIP]
> **安全なシミュレーションを実行する (Dry-Run)**
> `--dry-run` を指定することで、実際のメールボックスに変更を加えることなく、どのメールがどのように分類されるかのログを事前に確認できます。
> ```bash
> python mail_organizer.py apply --dry-run
> ```

**本本適用（アーカイブ ＆ フォルダ移動）:**
```bash
# Gmailはアーカイブし、Outlookはフォルダ移動で整理
python mail_organizer.py apply --archive --filter
```
- `--archive`: メールの移動（アーカイブ）を行います。
- `--filter`: 今後届くメールにも自動でルールが適用されるよう、Gmail の「自動振り分けフィルタ」を作成します（Gmail アカウントのみで有効）。

#### **ステップ 3: 環境のクリーンアップ（リセット）**
もし設定を元に戻したくなった場合は、以下のコマンドで安全に元通りに復元できます。
```bash
# すべてのアカウントをリセット（カスタムラベル/フォルダを削除し、全メールを受信トレイに戻す）
python mail_organizer.py reset

# 特定のアカウントのみリセット
python mail_organizer.py reset --account outlook_work
```

---

## 🔌 MCP (Model Context Protocol) サーバー設定

Docker コンテナ上で動作する MCP サーバーとして起動し、AI アシスタントと連携できます。

### 1. Docker イメージのビルド
```bash
docker build -t mail-organizer .
```

### 2. Claude Desktop への登録
`claude_desktop_config.json` に以下の設定を追加します。

```json
{
  "mcpServers": {
    "mail-organizer": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "C:\\Users\\<あなたのユーザー名>\\path\\to\\gmail-manager:/app",
        "-e", "GEMINI_API_KEY=あなたのGEMINI_API_KEY",
        "mail-organizer"
      ]
    }
  }
}
```

---
**Mail Organizer** - *Simplify Your Inbox.*
