import logging
import socket
from auth import GmailAuthenticator
from utils import execute_with_retry

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# タイムアウト設定
socket.setdefaulttimeout(60)

class GmailResetter:
    """Gmailのラベルやフィルタをクリーンアップし、受信トレイを初期化するためのクラス"""

    def __init__(self, service):
        self.service = service

    def reset_to_inbox(self):
        """すべてのユーザーラベルを削除し、すべてのメールを受信トレイに戻す"""
        logger.info("ユーザー定義ラベルと全てのメッセージを特定しています...")
        
        # 1. ユーザーラベルの取得
        results = execute_with_retry(lambda: self.service.users().labels().list(userId='me'))
        labels = results.get('labels', [])
        user_label_ids = [l['id'] for l in labels if l.get('type') == 'user']
        
        # 2. 全メッセージの取得
        messages = []
        results = execute_with_retry(lambda: self.service.users().messages().list(userId='me', maxResults=500))
        if results and 'messages' in results:
            messages.extend(results['messages'])
        
        while results and 'nextPageToken' in results:
            results = execute_with_retry(lambda: self.service.users().messages().list(
                userId='me', pageToken=results['nextPageToken'], maxResults=500))
            if results and 'messages' in results:
                messages.extend(results['messages'])

        if not messages:
            logger.info("処理対象のメールが見つかりませんでした。")
            return

        logger.info(f"合計 {len(messages)} 件のメールを処理します。ユーザーラベルを削除し、受信トレイ(INBOX)に戻します...")
        
        message_ids = [msg['id'] for msg in messages]
        batch_size = 1000
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i+batch_size]
            # removeLabelIds にユーザーラベル、addLabelIds に 'INBOX' を指定
            body = {
                "ids": batch,
                "removeLabelIds": user_label_ids,
                "addLabelIds": ['INBOX']
            }
            try:
                execute_with_retry(lambda: self.service.users().messages().batchModify(userId='me', body=body))
                logger.info(f"  -> {min(i + batch_size, len(message_ids))} / {len(message_ids)} 件完了")
            except Exception as e:
                logger.error(f"バッチ処理中にエラーが発生しました: {e}")

    def delete_all_filters_and_labels(self):
        """フィルタとラベルの定義自体を削除する"""
        logger.info("自動振り分けフィルタを削除中...")
        try:
            results = execute_with_retry(lambda: self.service.users().settings().filters().list(userId='me'))
            filters = results.get('filter', [])
            for f in filters:
                execute_with_retry(lambda: self.service.users().settings().filters().delete(userId='me', id=f['id']))
            logger.info(f"{len(filters)} 個のフィルタを削除しました。")
        except Exception as e:
            logger.error(f"フィルタ削除エラー: {e}")

        logger.info("カスタムラベル定義を削除中...")
        try:
            results = execute_with_retry(lambda: self.service.users().labels().list(userId='me'))
            labels = results.get('labels', [])
            for l in labels:
                if l.get('type') == 'user':
                    execute_with_retry(lambda: self.service.users().labels().delete(userId='me', id=l['id']))
            logger.info("カスタムラベルをすべて削除しました。")
        except Exception as e:
            logger.error(f"ラベル削除エラー: {e}")

if __name__ == '__main__':
    # 単体実行時の動作
    import sys
    auth = GmailAuthenticator()
    service = auth.get_service()
    resetter = GmailResetter(service)
    
    print("【警告】すべてのカスタムラベルとフィルタを削除し、全てのメールをアーカイブ解除します。")
    ans = input("実行しますか？ (y/n): ")
    if ans.lower() == 'y':
        resetter.reset_to_inbox()
        resetter.delete_all_filters_and_labels()
        print("リセットが完了しました。")
