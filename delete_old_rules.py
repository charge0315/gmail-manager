import sys
from auth import get_gmail_service

def delete_old_custom_labels_and_filters(service):
    # ラベルの削除
    print("\n既存のカスタムラベル本体（サイドバーのもの）を削除しています...")
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    for label in labels:
        if label.get('type') == 'user':
            print(f"  -> ラベル [{label['name']}] を削除中...")
            try:
                service.users().labels().delete(userId='me', id=label['id']).execute()
            except Exception as e:
                print(f"     エラー: {e}")

    # フィルタの削除
    print("\n既存のフィルタ（自動振り分け設定）を削除しています...")
    try:
        results = service.users().settings().filters().list(userId='me').execute()
        filters = results.get('filter', [])
        if not filters:
            print("  -> 削除するフィルタはありませんでした。")
        for f in filters:
            print(f"  -> フィルタID [{f.get('id')}] を削除中...")
            try:
                service.users().settings().filters().delete(userId='me', id=f['id']).execute()
            except Exception as e:
                 print(f"     エラー: {e}")
    except Exception as e:
        print(f"フィルタの取得中にエラーが発生しました: {e}")

if __name__ == "__main__":
    service = get_gmail_service()
    if not service:
        sys.exit(1)
        
    print("【警告】これまでご自身で作成された「すべてのカスタムラベル（サイドバーの項目）」と「すべての自動振り分けフィルタ設定」をGmailから完全に削除します。")
    ans = input("本当によろしいですか？（今回作成した10個の新しいルールだけにしたい場合は推奨です） (y/n): ")
    if ans.strip().lower() == 'y':
        delete_old_custom_labels_and_filters(service)
        print("\n既存ルールの削除（初期化）が完了しました！")
    else:
        print("キャンセルしました。")
