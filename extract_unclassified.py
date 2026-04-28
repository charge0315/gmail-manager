import json
import logging
import argparse
from auth import GmailAuthenticator
from analyze import GmailAnalyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # 受信トレイにあるメールを直接指定
    search_query = "label:INBOX"
    
    logger.info(f"受信トレイのメール検索クエリ: {search_query}")
    
    auth = GmailAuthenticator()
    service = auth.get_service()
    
    analyzer = GmailAnalyzer()
    # 制限なしで受信トレイのメールを取得
    unclassified_data = analyzer.fetch_email_metadata(service, query=search_query)
    
    if unclassified_data:
        with open('unclassified_emails.json', 'w', encoding='utf-8') as f:
            json.dump(unclassified_data, f, ensure_ascii=False, indent=2)
        logger.info(f"{len(unclassified_data)} 件の未分類メールデータを保存しました。")
    else:
        logger.info("未分類のメールは見つかりませんでした。")

if __name__ == '__main__':
    main()
