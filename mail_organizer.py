import sys
import os
import argparse
import logging
import time
import json
from auth import GmailAuthenticator
from auth_outlook import OutlookAuthenticator
from analyze import GmailAnalyzer
from apply_rules import GmailRuleApplier
from reset import GmailResetter
from outlook_client import OutlookIMAPClient
from utils import load_accounts

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MailOrganizerCLI:
    def __init__(self):
        self.accounts = load_accounts()

    def get_rules_filename(self, account_id, custom_output=None):
        """アカウントごとのルールファイル名を取得する"""
        if custom_output:
            return custom_output
        if account_id == "default":
            return "rules.json"
        return f"rules_{account_id}.json"

    def run_analyze(self, args):
        target_accounts = self.get_target_accounts(args.account)
        for acc in target_accounts:
            logger.info(f"\n==========================================")
            logger.info(f"アカウント分析を開始: {acc['name']} ({acc['type']})")
            logger.info(f"==========================================")
            
            rules_file = self.get_rules_filename(acc['id'], args.output if 'output' in args else None)
            
            if acc['type'] == 'gmail':
                auth = GmailAuthenticator(account_id=acc['id'] if acc['id'] != "default" else None)
                try:
                    service = auth.get_service()
                except Exception as e:
                    logger.error(f"Gmailの認証に失敗しました: {e}")
                    continue
                
                analyzer = GmailAnalyzer(model_name=args.model)
                email_data = analyzer.fetch_email_metadata(service, max_emails=args.max, query=args.query)
            
            elif acc['type'] == 'outlook':
                if "client_id" not in acc:
                    logger.error(f"アカウント {acc['name']} の client_id が accounts.json に指定されていません。")
                    continue
                
                try:
                    auth_outlook = OutlookAuthenticator(
                        account_id=acc['id'],
                        client_id=acc['client_id'],
                        username=acc['username']
                    )
                    access_token = auth_outlook.get_access_token()
                except Exception as e:
                    logger.error(f"Outlookの認証に失敗しました: {e}")
                    continue
                
                client = OutlookIMAPClient(
                    username=acc['username'],
                    access_token=access_token,
                    server=acc.get('imap_server', 'outlook.office365.com'),
                    port=acc.get('imap_port', 993)
                )
                try:
                    email_data = client.fetch_email_metadata(max_emails=args.max)
                except Exception as e:
                    logger.error(f"Outlookデータの取得に失敗しました: {e}")
                    continue
                finally:
                    client.close()
                    
                analyzer = GmailAnalyzer(model_name=args.model)
            else:
                logger.error(f"未サポートのアカウントタイプです: {acc['type']}")
                continue

            if not email_data:
                logger.warning(f"アカウント {acc['name']} の分析対象のメールが見つかりませんでした。")
                continue

            rules = analyzer.generate_rules(email_data, num_categories=args.num_categories, custom_instructions=args.prompt)
            if rules:
                with open(rules_file, 'w', encoding='utf-8') as f:
                    json.dump(rules, f, ensure_ascii=False, indent=2)
                logger.info(f"ルールを {rules_file} に保存しました。")

    def run_apply(self, args):
        target_accounts = self.get_target_accounts(args.account)
        for acc in target_accounts:
            logger.info(f"\n==========================================")
            logger.info(f"ルール適用を開始: {acc['name']} ({acc['type']})")
            logger.info(f"==========================================")
            
            rules_file = self.get_rules_filename(acc['id'], args.config if 'config' in args else None)
            if not os.path.exists(rules_file):
                fallback_file = 'rules.json'
                if not args.config and os.path.exists(fallback_file):
                    logger.warning(f"アカウント固有のルールファイル {rules_file} が存在しないため、共通の {fallback_file} をフォールバックとして使用します。")
                    rules_file = fallback_file
                else:
                    logger.error(f"ルールファイル {rules_file} が存在しません。先に analyze コマンドを実行してください。")
                    continue

            with open(rules_file, 'r', encoding='utf-8') as f:
                rules = json.load(f)

            if acc['type'] == 'gmail':
                auth = GmailAuthenticator(account_id=acc['id'] if acc['id'] != "default" else None)
                try:
                    service = auth.get_service()
                except Exception as e:
                    logger.error(f"Gmailの認証に失敗しました: {e}")
                    continue
                
                applier = GmailRuleApplier(service, dry_run=args.dry_run)
                
                # 重複防止安全チェック
                if not args.dry_run and not args.force_apply:
                    user_labels = [label for name, label in applier.existing_labels.items() if label.get('type') == 'user']
                    if user_labels:
                        logger.error(f"【警告】{acc['name']} にはすでにカスタムラベルが存在します。")
                        logger.error("重複を防ぐため、適用前に 'python mail_organizer.py reset' を実行して初期化することを推奨します。")
                        logger.error("強制適用する場合は、--force-apply オプションを指定して再実行してください。")
                        continue

                applied_labels = []
                for rule in rules:
                    logger.info(f"\n--- ルール適用: {rule['name']} ---")
                    label_id = applier.create_or_update_label(rule['name'], rule.get('color'))
                    if label_id:
                        applier.apply_query_to_messages(rule['query'], label_id, rule['name'], archive=args.archive)
                        applied_labels.append(rule['name'])
                        if args.filter:
                            applier.create_filter(rule['name'], rule['query'], label_id, archive=args.archive)
                
                # 未分類メールのフォールバック整理
                applier.apply_unclassified_fallback(applied_labels, archive=args.archive)

            elif acc['type'] == 'outlook':
                if args.filter:
                    logger.warning("【注意】Outlook (IMAP) では自動振り分けフィルタの作成はサポートされていません。スキップします。")
                
                if "client_id" not in acc:
                    logger.error(f"アカウント {acc['name']} の client_id が accounts.json に指定されていません。")
                    continue
                
                try:
                    auth_outlook = OutlookAuthenticator(
                        account_id=acc['id'],
                        client_id=acc['client_id'],
                        username=acc['username']
                    )
                    access_token = auth_outlook.get_access_token()
                except Exception as e:
                    logger.error(f"Outlookの認証に失敗しました: {e}")
                    continue

                client = OutlookIMAPClient(
                    username=acc['username'],
                    access_token=access_token,
                    server=acc.get('imap_server', 'outlook.office365.com'),
                    port=acc.get('imap_port', 993),
                    dry_run=args.dry_run
                )
                try:
                    client.apply_rules(rules, archive=args.archive)
                except Exception as e:
                    logger.error(f"Outlookでのルール適用中にエラーが発生しました: {e}")
                finally:
                    client.close()

    def run_reset(self, args):
        target_accounts = self.get_target_accounts(args.account)
        
        if not args.force:
            print("【警告】対象アカウントのカスタムフォルダ/ラベルをすべて削除し、すべてのメールを受信トレイに戻します。")
            ans = input("続行しますか？ (y/N): ")
            if ans.lower() != 'y':
                logger.info("キャンセルしました。")
                return

        for acc in target_accounts:
            logger.info(f"\n==========================================")
            logger.info(f"リセットを開始: {acc['name']} ({acc['type']})")
            logger.info(f"==========================================")
            
            if acc['type'] == 'gmail':
                auth = GmailAuthenticator(account_id=acc['id'] if acc['id'] != "default" else None)
                try:
                    service = auth.get_service()
                except Exception as e:
                    logger.error(f"Gmailの認証に失敗しました: {e}")
                    continue
                
                resetter = GmailResetter(service)
                resetter.reset_to_inbox()
                resetter.delete_all_filters_and_labels()
                logger.info(f"{acc['name']} のリセットが完了しました。")

            elif acc['type'] == 'outlook':
                if "client_id" not in acc:
                    logger.error(f"アカウント {acc['name']} の client_id が accounts.json に指定されていません。")
                    continue
                
                try:
                    auth_outlook = OutlookAuthenticator(
                        account_id=acc['id'],
                        client_id=acc['client_id'],
                        username=acc['username']
                    )
                    access_token = auth_outlook.get_access_token()
                except Exception as e:
                    logger.error(f"Outlookの認証に失敗しました: {e}")
                    continue

                client = OutlookIMAPClient(
                    username=acc['username'],
                    access_token=access_token,
                    server=acc.get('imap_server', 'outlook.office365.com'),
                    port=acc.get('imap_port', 993)
                )
                try:
                    client.reset_to_inbox()
                    logger.info(f"{acc['name']} のリセットが完了しました。")
                except Exception as e:
                    logger.error(f"Outlookのリセット中にエラーが発生しました: {e}")
                finally:
                    client.close()

    def get_target_accounts(self, account_id_arg):
        """指定されたアカウント引数に基づいて、対象のアカウントリストを返す"""
        if account_id_arg:
            matches = [a for a in self.accounts if a['id'] == account_id_arg]
            if not matches:
                logger.error(f"指定されたアカウント ID '{account_id_arg}' が accounts.json に見つかりません。")
                sys.exit(1)
            return matches
        return self.accounts

def main():
    cli = MailOrganizerCLI()
    
    # 共通の親パーサー（各サブパーサーに引数を引き継ぐ）
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('--account', help='処理対象とするアカウントID (accounts.json で定義したもの)。指定しない場合はすべて処理。')

    parser = argparse.ArgumentParser(description='Mail Organizer: AIによるGmail/Outlookメール整理ツール')
    subparsers = parser.add_subparsers(dest='command', help='コマンド')

    # analyze
    p_analyze = subparsers.add_parser('analyze', parents=[parent_parser], help='メールを分析してルールを作成')
    p_analyze.add_argument('--max', type=int, default=500, help='分析対象の最大メール数')
    p_analyze.add_argument('--query', default='newer_than:1y', help='分析対象を絞り込むGmailクエリ (Gmailのみ、例: newer_than:1y)')
    p_analyze.add_argument('--model', type=str, default='gemini-3.6-flash', help='使用するモデル')
    p_analyze.add_argument('--num-categories', type=int, default=15, help='生成するカテゴリ数')
    p_analyze.add_argument('--prompt', type=str, help='AIへの追加指示')
    p_analyze.add_argument('--output', help='出力ファイル名（指定しない場合は rules_{account_id}.json）')

    # apply
    p_apply = subparsers.add_parser('apply', parents=[parent_parser], help='ルールをメールボックスに適用')
    p_apply.add_argument('--config', help='ルール設定ファイル（指定しない場合は rules_{account_id}.json）')
    p_apply.add_argument('--dry-run', action='store_true', help='変更をプレビュー')
    p_apply.add_argument('--filter', action='store_true', help='自動振り分けフィルタも作成 (Gmailのみ)')
    p_apply.add_argument('--archive', action='store_true', help='ラベル付与/フォルダ移動時に受信トレイから移動')
    p_apply.add_argument('--force-apply', action='store_true', help='既存ラベルが存在する場合でも強制的に適用 (Gmailのみ)')

    # reset
    p_reset = subparsers.add_parser('reset', parents=[parent_parser], help='ラベルやフォルダ、フィルタを初期化')
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
