
import json
import logging
from auth import GmailAuthenticator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def audit():
    auth = GmailAuthenticator()
    service = auth.get_service()
    
    # 1. ルールとラベルの読み込み
    with open('rules.json', 'r', encoding='utf-8') as f:
        rules = json.load(f)
    
    label_names = [r['name'] for r in rules]
    exclude_query = " ".join([f"-label:\"{name}\"" for name in label_names])
    unlabeled_query = f"label:INBOX {exclude_query}"
    
    print(f"\n--- 未分類メールの監査 ---")
    print(f"検索クエリ: {unlabeled_query}")
    
    results = service.users().messages().list(userId='me', q=unlabeled_query, maxResults=50).execute()
    messages = results.get('messages', [])
    total_unlabeled = results.get('resultSizeEstimate', 0)
    
    print(f"未分類のメール（推定）: {total_unlabeled} 件")
    
    for msg in messages[:10]:
        detail = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
        headers = detail.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '(Unknown Sender)')
        print(f" - {sender}: {subject}")

    # 2. フィルタの監査
    print(f"\n--- フィルタの監査 ---")
    filters_results = service.users().settings().filters().list(userId='me').execute()
    filters = filters_results.get('filter', [])
    print(f"合計フィルタ数: {len(filters)}")
    
    query_map = {}
    for f in filters:
        q = f['criteria'].get('query', '')
        if q in query_map:
            query_map[q].append(f['id'])
        else:
            query_map[q] = [f['id']]
    
    duplicates = {q: ids for q, ids in query_map.items() if len(ids) > 1}
    if duplicates:
        print(f"重複しているフィルタ（同じクエリ）: {len(duplicates)} 件")
    
    print("\n--- フィルタ詳細 (クエリ -> ラベルID) ---")
    for f in filters:
        q = f['criteria'].get('query', '')
        labels = f['action'].get('addLabelIds', [])
        print(f" - {q[:100]}... -> {labels}")

if __name__ == '__main__':
    audit()
