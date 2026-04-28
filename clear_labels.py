import sys
from auth import get_gmail_service

def clear_recent_labels(service):
    print("ラベルの情報を取得しています...")
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    
    user_label_ids = []
    for label in labels:
        if label.get('type') == 'user':
            user_label_ids.append(label.get('id'))
    
    if not user_label_ids:
        print("ユーザー定義のラベルが見つかりません。クリア処理を終了します。")
        return
        
    print(f"{len(user_label_ids)}個のユーザー定義ラベルを対象として処理します。")

    # すべてのメールを検索
    print("すべてのメールを検索しています...")
    
    messages = []
    response = service.users().messages().list(userId='me', maxResults=500).execute()
    if 'messages' in response:
        messages.extend(response['messages'])

    while 'nextPageToken' in response:
        page_token = response['nextPageToken']
        print(f"次のページを取得中... (現在 {len(messages)} 件)")
        response = service.users().messages().list(userId='me', pageToken=page_token, maxResults=500).execute()
        if 'messages' in response:
            messages.extend(response['messages'])

    if not messages:
        print("メールは見つかりませんでした。")
        return
        
    print(f"合計 {len(messages)} 件のメールが見つかりました。ラベルを一括クリアします...")
    
    message_ids = [msg['id'] for msg in messages]
    batch_size = 1000
    for i in range(0, len(message_ids), batch_size):
        batch_ids = message_ids[i:i+batch_size]
        body = {
            "ids": batch_ids,
            "removeLabelIds": user_label_ids
        }
        try:
            service.users().messages().batchModify(userId='me', body=body).execute()
            print(f"  -> {i+1}〜{i+len(batch_ids)}件目の処理完了")
        except Exception as e:
            print(f"ラベルの削除中にエラーが発生しました: {e}")
            
    print("ラベルのクリア処理がすべて完了しました！")

if __name__ == "__main__":
    service = get_gmail_service()
    if not service:
        sys.exit(1)
    
    clear_recent_labels(service)
