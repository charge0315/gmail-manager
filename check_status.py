
import logging
from auth import GmailAuthenticator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_status():
    auth = GmailAuthenticator()
    service = auth.get_service()
    
    # フィルタの確認
    filters = service.users().settings().filters().list(userId='me').execute()
    filter_list = filters.get('filter', [])
    print(f"\n--- フィルタ設定 ---")
    print(f"合計フィルタ数: {len(filter_list)}")
    
    # ラベルの確認とメール件数
    labels_results = service.users().labels().list(userId='me').execute()
    labels = labels_results.get('labels', [])
    
    print(f"\n--- ラベルとメール件数 ---")
    for l in labels:
        if l['type'] == 'user':
            label_id = l['id']
            # メッセージ一覧の取得（件数のみ確認）
            msgs = service.users().messages().list(userId='me', labelIds=[label_id], maxResults=1).execute()
            total = msgs.get('resultSizeEstimate', 0)
            print(f"ラベル: {l['name']} (ID: {label_id}) - 推定件数: {total}")

if __name__ == '__main__':
    check_status()
