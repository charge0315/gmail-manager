import sys
import argparse
import logging
import time
import socket
from auth import GmailAuthenticator
from analyze import GmailAnalyzer
from apply_rules import GmailRuleApplier
from reset import GmailResetter

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def retry_on_network_error(max_retries=3, initial_wait=5):
    """ネットワークエラー時にリトライするデコレータ"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (socket.timeout, ConnectionResetError, TimeoutError) as e:
                    if attempt == max_retries - 1:
                        logger.error(f"最大リトライ回数に達しました: {e}")
                        raise
                    wait = initial_wait * (attempt + 1)
                    logger.warning(f"通信エラー発生。{wait}秒後に再試行します... ({attempt + 1}/{max_retries})")
                    time.sleep(wait)
            return None
        return wrapper
    return decorator

class ZenMailCLI:
    def __init__(self):
        self.auth = GmailAuthenticator()
        self._service = None

    @property
    def service(self):
        if self._service is None:
            self._service = self.auth.get_service()
        return self._service

    def run_analyze(self, args):
        analyzer = GmailAnalyzer(model_name=args.model)
        email_data = analyzer.fetch_email_metadata(self.service, max_emails=args.max, query=args.query)
        if not email_data:
            logger.warning("分析対象のメールが見つかりませんでした。")
            return
        rules = analyzer.generate_rules(email_data, num_categories=args.num_categories, custom_instructions=args.prompt)
        if rules:
            with open(args.output, 'w', encoding='utf-8') as f:
                import json
                json.dump(rules, f, ensure_ascii=False, indent=2)
            logger.info(f"ルールを {args.output} に保存しました。")

    def run_apply(self, args):
        applier = GmailRuleApplier(self.service, dry_run=args.dry_run)
        
        # 重複防止安全チェック: 既存のカスタムラベルが存在する場合に警告し終了する
        if not args.dry_run and not args.force_apply:
            user_labels = [label for name, label in applier.existing_labels.items() if label.get('type') == 'user']
            if user_labels:
                logger.error("【警告】Gmail 側にすでにカスタムラベルが存在します。")
                logger.error("このまま適用すると、前回の古いラベルと重複してメールが分類される原因になります。")
                logger.error("重複を防ぐため、適用前に 'python zenmail.py reset' を実行して初期化することを強く推奨します。")
                logger.error("このまま強制適用する場合は、--force-apply オプションを指定して再実行してください。")
                sys.exit(1)

        with open(args.config, 'r', encoding='utf-8') as f:
            import json
            rules = json.load(f)
        
        applied_labels = []
        for rule in rules:
            logger.info(f"\n--- ルール適用: {rule['name']} ---")
            label_id = applier.create_or_update_label(rule['name'], rule.get('color'))
            if label_id:
                applier.apply_query_to_messages(rule['query'], label_id, rule['name'], archive=args.archive)
                applied_labels.append(rule['name'])
                if args.filter:
                    applier.create_filter(rule['name'], rule['query'], label_id, archive=args.archive)

        # 未分類メールのフォールバック整理を実行
        applier.apply_unclassified_fallback(applied_labels, archive=args.archive)

    def run_reset(self, args):
        resetter = GmailResetter(self.service)
        if not args.force:
            print("【警告】すべてのユーザー定義ラベルとフィルタを削除し、すべてのメールを受信トレイに戻します。")
            ans = input("続行しますか？ (y/N): ")
            if ans.lower() != 'y':
                logger.info("キャンセルしました。")
                return

        resetter.reset_to_inbox()
        resetter.delete_all_filters_and_labels()
        logger.info("リセットが完了しました。")

def main():
    cli = ZenMailCLI()
    parser = argparse.ArgumentParser(description='ZenMail Automator: AIによるGmail整理ツール')
    subparsers = parser.add_subparsers(dest='command', help='コマンド')

    # analyze
    p_analyze = subparsers.add_parser('analyze', help='メールを分析してルールを作成')
    p_analyze.add_argument('--max', type=int, default=500, help='分析対象の最大メール数')
    p_analyze.add_argument('--query', default='newer_than:1y', help='分析対象を絞り込むGmailクエリ (例: newer_than:1y)')
    p_analyze.add_argument('--model', type=str, default='gemini-3.6-flash', help='使用するモデル')
    p_analyze.add_argument('--num-categories', type=int, default=15, help='生成するカテゴリ数')
    p_analyze.add_argument('--prompt', type=str, help='AIへの追加指示')
    p_analyze.add_argument('--output', default='rules.json', help='出力ファイル名')

    # apply
    p_apply = subparsers.add_parser('apply', help='ルールをGmailに適用')
    p_apply.add_argument('--config', default='rules.json', help='ルール設定ファイル')
    p_apply.add_argument('--dry-run', action='store_true', help='変更をプレビュー')
    p_apply.add_argument('--filter', action='store_true', help='自動振り分けフィルタも作成')
    p_apply.add_argument('--archive', action='store_true', help='ラベル付与時に受信トレイからアーカイブ')
    p_apply.add_argument('--force-apply', action='store_true', help='既存ラベルが存在する場合でも強制的に適用')

    # reset
    p_reset = subparsers.add_parser('reset', help='ラベルとフィルタを初期化')
    p_reset.add_argument('--force', action='store_true', help='確認なしで実行')

    args = parser.parse_args()

    if args.command == 'analyze':
        cli.run_analyze(args)
    elif args.command == 'apply':
        cli.run_apply(args)
    elif args.command == 'reset':
        cli.run_reset(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
