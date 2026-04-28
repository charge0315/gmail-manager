
from auth import GmailAuthenticator

def cleanup_filters():
    auth = GmailAuthenticator()
    service = auth.get_service()
    
    results = service.users().settings().filters().list(userId='me').execute()
    filters = results.get('filter', [])
    
    count = 0
    for f in filters:
        # アクションにラベルが含まれていないフィルタを特定
        if not f.get('action', {}).get('addLabelIds'):
            print(f"空のフィルタを削除中: {f['id']} (Query: {f['criteria'].get('query', '')[:50]}...)")
            service.users().settings().filters().delete(userId='me', id=f['id']).execute()
            count += 1
            
    print(f"合計 {count} 個の不要なフィルタを削除しました。")

if __name__ == '__main__':
    cleanup_filters()
