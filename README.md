# ZenMail Automator

ZenMail Automator は、Gemini 3.1 Pro (最新の AI モデル) を活用して Gmail の受信トレイを賢く、自動的に整理するためのツールセットです。
新たに **MCP (Model Context Protocol) サーバー** としての機能が追加され、Claude Desktop などの AI アシスタントから直接 Gmail を操作・整理できるようになりました。

過去のメール履歴を分析し、あなたのライフスタイルに最適な **16 個のカテゴリ**（15の主要カテゴリ + 「📁 その他・未分類」）を自動生成。複雑な検索クエリを手動で書くことなく、「Inbox Zero（受信トレイを空にする）」を実現するための完全なワークフローを提供します。

## 主な機能

- **🤖 AI による高度な分析**: Gemini 3.1 Pro が送信者や件名の傾向を読み取り、最適なラベル名、カラー、検索クエリを提案します。
- **🔌 MCP サーバー対応**: Docker ベースの MCP サーバーとして動作し、AI アシスタント (Claude 等) から Gmail のリセット、分析、整理ルール適用を直接実行可能。
- **📥 一括整理とアーカイブ**: `--archive` オプションにより、ラベル付けと同時に受信トレイからアーカイブし、瞬時に受信トレイをクリーンアップできます。
- **🔄 反復的なルール強化**: 未分類メールを抽出・分析する専用ツールにより、既存のルールを破壊することなく、AI が学習を繰り返して精度を高めます。
- **🛡️ ネットワーク安定化**: IPv4 強制設定、リクエスト待機 (Pacing)、自動リトライ機能により、大量のメール処理でも通信エラーを最小限に抑えます。
- **🧹 かんたんリセット**: 作成したラベルやフィルタを一括削除し、すべてのメールを受信トレイに戻す「元通り」機能も完備。

## MCP サーバーの利用ガイド

ZenMail Automator は MCP サーバーとして Docker コンテナ上で動作します。これにより、ローカル環境を汚さずに AI アシスタントから Gmail 操作ツールを利用できます。

### 1. 準備
- `credentials.json` をプロジェクトのルートディレクトリに配置します。
- 最初に一度だけ、ローカルで `python auth.py` を実行して `token.json` を生成しておく必要があります（認証ブラウザを開くため）。

### 2. Docker イメージのビルド
```bash
docker build -t gmail-manager .
```

### 3. Claude Desktop への登録
`%APPDATA%\Claude\claude_desktop_config.json` (Windows) または `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) に以下の設定を追加します。

```json
{
  "mcpServers": {
    "gmail-manager": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "C:\\Users\\yourname\\path\\to\\gmail-manager:/app",
        "-e", "GEMINI_API_KEY=your_api_key_here",
        "gmail-manager"
      ]
    }
  }
}
```
※ パスや環境変数はご自身の環境に合わせて置き換えてください。

### 4. 利用可能なツール
- `reset_gmail`: Gmail の初期化（ラベル・フィルタ削除、全メール INBOX 戻し）。
- `analyze_emails`: メールの分析と `rules.json` の生成。
- `apply_classification_rules`: ルールの適用とメールのアーカイブ。

---

## CLI クイックスタート (ローカル実行)

### 1. セットアップ
```bash
pip install -r requirements.txt
```

### 2. Inbox Zero への 4 ステップ
統合 CLI `zenmail.py` を使用して、以下のワークフローで整理を完了します。

#### ステップ 1: メールの分析
過去 1 年間のメールを分析し、整理ルール (`rules.json`) を生成します。
```bash
python zenmail.py analyze --max 1000
```

#### ステップ 2: ルールの適用（アーカイブ実行）
生成されたルールに基づき、Gmail にラベルを作成し、メールをアーカイブします。
```bash
# --archive で受信トレイを空に、--filter で今後のメールも自動振り分け
python zenmail.py apply --archive --filter
```

#### ステップ 3: 未分類メールの抽出とルールの洗練
どのカテゴリにも属さなかったメールを抽出し、ルールを強化します。
```bash
python extract_unclassified.py
python refine_rules.py
```

#### ステップ 4: リセット
```bash
python zenmail.py reset
```

## 技術スタック

- **MCP Framework**: [FastMCP](https://github.com/jlowin/fastmcp) (Python) - MCP サーバーの迅速な構築。
- **Runtime**: Python 3.11 / Docker (slim-image) - 隔離された安全な実行環境。
- **LLM**: Gemini 3.1 Pro / Flash (Google GenAI SDK) - 高度なメールコンテキスト分析。
- **Gmail API**: Google API Python Client - ラベル、フィルタ、メッセージ操作。
- **Network**: IPv4 Force Patch - Windows 環境での安定した API 通信。

## 整理カテゴリの定義 (16 カテゴリ)

| ラベル名 | 説明 |
| :--- | :--- |
| 🏦 金融・銀行 | 銀行口座、クレジットカード、証券、仮想通貨関連 |
| 💳 決済・ポイント | 電子マネー、Pay系、ポイントサービス、領収書通知 |
| 🛒 ショッピング | ECサイトの注文確認、セール、お買い物情報 |
| 📦 配送・トラッキング | Amazon配送、ヤマト、佐川などのお荷物追跡 |
| 💻 開発・クラウド | GitHub, AWS, Google Cloud, 開発ツール通知 |
| 🤖 AI・トレンド | Claude, Perplexity, OpenAI, IT系ニュース |
| 🌐 Web・SEO | WordPress, SEOツール, Webサイト運営関連 |
| 🎮 ゲーム・配信 | Twitch, Steam, Nintendo, オンラインゲーム |
| 🎬 映像・エンタメ | 動画配信サービス (Netflix等), チケット情報 |
| 🔐 セキュリティ | ログイン通知、二段階認証コード、パスワード変更 |
| 💼 仕事・副業 | クラウドワークス、業務委託、仕事関連の連絡 |
| 🏢 生活・公的機関 | 自治体、保険、年金、住居管理、インフラ情報 |
| 📅 予約・スケジュール | カレンダー通知、店舗予約確認、リマインダー |
| 🎨 クリエイティブ | Adobe, デザイン、音楽制作ツール関連 |
| 📱 SNS・アプリ | SNS通知、通信キャリア、Google Play情報 |
| 📁 その他・未分類 | 上記に当てはまらない、またはエラー通知など |

---
**ZenMail Automator** - *Less Clutter, More Focus.*
