import json
import logging
import argparse
import os
import sys
from auth import GmailAuthenticator
from analyze import GmailAnalyzer
from outlook_client import OutlookIMAPClient
from auth_outlook import OutlookAuthenticator
from utils import load_accounts

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='未分類のメールメタデータを抽出して保存します。')
    parser.add_argument('--account', help='処理対象とするアカウントID。指定しない場合はすべて処理。')
    args = parser.parse_args()

    accounts = load_accounts()
    
    # 対象アカウントの特定
    if args.account:
        target_accounts = [a for a in accounts if a['id'] == args.account]
        if not target_accounts:
            logger.error(f"アカウント ID '{args.account}' が見つかりません。")
            sys.exit(1)
    else:
        target_accounts = accounts

    for acc in target_accounts:
        logger.info(f"\n未分類メール抽出を開始: {acc['name']} ({acc['type']})")
        
        output_file = 'unclassified_emails.json' if acc['id'] == 'default' else f'unclassified_emails_{acc["id"]}.json'
        
        if acc['type'] == 'gmail':
            auth = GmailAuthenticator(account_id=acc['id'] if acc['id'] != "default" else None)
            try:
                service = auth.get_service()
            except Exception as e:
                logger.error(f"Gmailの認証に失敗しました: {e}")
                continue
            
            analyzer = GmailAnalyzer()
            # 受信トレイのメールを取得
            unclassified_data = analyzer.fetch_email_metadata(service, query="label:INBOX")
            
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
                unclassified_data = client.fetch_email_metadata()
            except Exception as e:
                logger.error(f"Outlookデータの取得に失敗しました: {e}")
                continue
            finally:
                client.close()
        else:
            logger.error(f"未サポートのアカウントタイプです: {acc['type']}")
            continue

        if unclassified_data:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(unclassified_data, f, ensure_ascii=False, indent=2)
            logger.info(f"アカウント '{acc['name']}' の {len(unclassified_data)} 件の未分類メールデータを {output_file} に保存しました。")
        else:
            logger.info(f"アカウント '{acc['name']}' に未分類のメールは見つかりませんでした。")

if __name__ == '__main__':
    main()
