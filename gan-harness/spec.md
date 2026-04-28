# Product Specification: ZenMail Automator (禅メール・オートメーター)

> Generated from brief: "カレントディレクトリにある既存のPythonスクリプトと設定ファイルを活用し、Gmailを効率的に整理・自動化するための包括的な製品仕様と実装計画を策定してください。"

## Vision
「メールの山に、禅の静寂を。」
ZenMail Automatorは、AI（Gemini）の力を借りてカオス化した受信トレイを自動的に整理し、ユーザーが本当に集中すべき重要なコミュニケーションにのみフォーカスできる環境を提供します。単なるフィルタリングツールではなく、ユーザーのメール受信パターンを学習し、進化し続けるパーソナルなメール執事を目指します。

## Design Direction
- **Color palette**: 
  - Primary: `#2D3436` (Deep Charcoal - 落ち着きとプロフェッショナリズム)
  - Secondary: `#00B894` (Zen Green - 平穏とクリーンさ)
  - Accent: `#0984E3` (Clear Blue - 信頼感)
  - Background: `#F5F6FA` (Soft Gray - 視覚的ノイズの低減)
- **Typography**: 
  - メイン: "Inter", "Noto Sans JP" - 高い可読性とモダンな印象
  - コード/データ: "JetBrains Mono" - 処理結果の明瞭な表示
- **Layout philosophy**: 「ミニマル・ダッシュボード」
  - 複雑な設定は背後に隠し、ユーザーには「現在の整理状況」と「AIの提案」を視覚的に提示。余白を贅沢に使い、情報の過密を避ける。
- **Visual identity**: 
  - 幾何学的な「禅の円（円相）」をモチーフにしたアイコン。
  - グラデーションの多用を避け、フラットでマットな質感のデザイン。
- **Inspiration**: 
  - Superhuman (効率性とスピード)
  - Notion (クリーンなインターフェース)
  - Vercel (開発者フレンドリーな洗練さ)

## Features (prioritized)

### Must-Have (Sprint 1-2)
1. **AIインテリジェント・アナライザー**: `analyze.py`を強化。送信者、件名だけでなく、時間帯や受信頻度も考慮した高度な分類ルールの生成。
2. **ルールエンジン・プロセッサ**: `apply_rules.py`をベースに、既存メールの一括処理と、将来のメールに対する自動フィルタ設定の両立。
3. **セーフティ・ドライラン**: ルールを適用する前に、どのメールがどのラベルに分類されるかをシミュレーションし、ユーザーに確認を促す機能。
4. **クイック・リセット**: `delete_old_rules.py`を洗練させ、作成したラベルやフィルタを安全に一括削除し、元の状態に戻す機能。
5. **認証管理システム**: `auth.py`を堅牢化。トークンの期限切れ対応や、セキュアな認証情報の保管。

### Should-Have (Sprint 3-4)
1. **定期実行スケジューラー**: GitHub ActionsやLocal Cronと連携し、毎日決まった時間に整理を実行する仕組み。
2. **処理ログの可視化ダッシュボード**: どのラベルに何通のメールが移動したか、AIがどのように判断したかをサマリー表示。
3. **スマート・アンサブスクライバー**: ニュースレターや広告メールを特定し、ワンクリックで配信停止ページへの誘導やアーカイブを行う機能。
4. **カスタム・インストラクション**: AIへの指示出し機能。「仕事関係のメールはプロジェクト名で分けて」といったユーザーのこだわりをルール生成に反映。
5. **添付ファイル・インテリジェンス**: 大容量ファイルや領収書PDFなどが含まれるメールを特定し、専用ラベルを付与。

### Nice-to-Have (Sprint 5+)
1. **マルチアカウント統合**: 複数のGmailアカウントを一括で整理・管理。
2. **優先度自動判定 (Smart Priority)**: 単なるカテゴリ分けだけでなく、返信が必要な重要メールをAIが推論し、最上位に表示。
3. **ダークモード対応UI**: 集中力を高めるためのインターフェース切り替え。
4. **Webhook連携**: 特定のラベルが付与された際に、SlackやDiscordに通知を飛ばす機能。

## Technical Stack
- **Framework**: FastMCP (Python) - MCP サーバーインターフェース
- **Runtime**: Python 3.11+, Docker (Containerized)
- **AI**: Gemini 3.1 Pro / Flash (分析・ルール生成)
- **APIs**: Google Gmail API
- **Data Persistence**: `rules.json` (設定)

## Evaluation Criteria

### Design Quality (weight: 0.3)
- ラベル名に適切な絵文字が含まれ、視覚的にカテゴリが判別しやすいか。
- 実行時のコンソール出力またはUIが整理されており、ユーザーが状況を把握しやすいか。

### Originality (weight: 0.2)
- 単なる「キーワード検索」を超えた、AIによる意味的な分類（セマンティック・ラベリング）が実現できているか。
- ユーザーの手間を最小限に抑える「ゼロ・セッティング」に近い体験が提供できているか。

### Craft (weight: 0.3)
- エラーハンドリング（API制限、ネットワーク中断）が適切に行われ、途中で処理が止まっても再開可能か。
- `batchModify`等のAPIを適切に使い、大量のメールを効率的（低レートリミット負荷）に処理できているか。

### Functionality (weight: 0.2)
- 生成された`rules.json`が有効なGmailクエリとして機能しているか。
- フィルタ作成機能により、将来のメールも自動で整理されるようになっているか。

## Sprint Plan

### Sprint 1: Foundation & Safety
- **Goals**: 既存スクリプトの統合と、ドライラン機能による安全性の確保。
- **Features**: #1 (Analyzer強化), #3 (Dry Run), #5 (Auth堅牢化)
- **Definition of done**: 実際にラベルを貼る前に、結果のプレビューをコンソールまたはファイルに出力できる。

### Sprint 2: Execution & Automation
- **Goals**: ルール適用エンジンの完成と、フィルタ自動生成の実装。
- **Features**: #2 (Rule Processor), #4 (Reset), #9 (Custom Instructionの初期版)
- **Definition of done**: Gmail上に正しくラベルとフィルタが作成され、既存メールが1,000件以上正しく分類される。

### Sprint 3: Visibility & Intelligence
- **Goals**: 処理結果の可視化と、より高度な分類ロジックの導入。
- **Features**: #6 (Scheduler), #7 (Dashboard), #10 (Attachment Intelligence)
- **Definition of done**: 過去1週間の整理統計が表示され、添付ファイル付きメールが自動で分類される。
