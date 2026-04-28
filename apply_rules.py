import json
import logging
import argparse
import socket
from auth import GmailAuthenticator
from googleapiclient.errors import HttpError
from utils import execute_with_retry

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# タイムアウト設定を延長
socket.setdefaulttimeout(60)

class GmailRuleApplier:
    """rules.json を読み込み、Gmailにラベルとフィルタを適用するクラス"""

    def __init__(self, service, dry_run=False):
        self.service = service
        self.dry_run = dry_run
        self._existing_labels = None

    @property
    def existing_labels(self):
        if self._existing_labels is None:
            results = execute_with_retry(lambda: self.service.users().labels().list(userId='me'))
            labels = results.get('labels', [])
            self._existing_labels = {label['name']: label for label in labels}
        return self._existing_labels

    def create_or_update_label(self, name, color=None):
        """ラベルを作成または更新する"""
        label_body = {
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show"
        }
        if color:
            label_body["color"] = color

        if name in self.existing_labels:
            label_id = self.existing_labels[name]['id']
            if self.existing_labels[name].get('type') == 'system':
                logger.info(f"[{name}] はシステムラベルのためスキップします。")
                return label_id
            
            if self.dry_run:
                logger.info(f"[DRY-RUN] ラベル [{name}] を更新予定です。")
                return "dry-run-label-id"
            
            try:
                label = execute_with_retry(lambda: self.service.users().labels().update(userId='me', id=label_id, body=label_body))
                return label['id']
            except HttpError as e:
                logger.warning(f"ラベル更新エラー: {e}")
                if "color" in label_body:
                    del label_body["color"]
                    label = execute_with_retry(lambda: self.service.users().labels().update(userId='me', id=label_id, body=label_body))
                    return label['id']
        else:
            if self.dry_run:
                logger.info(f"[DRY-RUN] 新しいラベル [{name}] を作成予定です。")
                return "dry-run-label-id"
            
            try:
                label = execute_with_retry(lambda: self.service.users().labels().create(userId='me', body=label_body))
                self._existing_labels[name] = label
                return label['id']
            except HttpError as e:
                logger.warning(f"ラベル作成エラー: {e}")
                if "color" in label_body:
                    del label_body["color"]
                    label = execute_with_retry(lambda: self.service.users().labels().create(userId='me', body=label_body))
                    self._existing_labels[name] = label
                    return label['id']
        return None

    def apply_query_to_messages(self, query, label_id, label_name, archive=False):
        """クエリに一致する既存メールにラベルを付与する（オプションでアーカイブ）"""
        logger.info(f"クエリ「{query}」で検索中...")
        
        messages = []
        try:
            results = execute_with_retry(lambda: self.service.users().messages().list(userId='me', q=query, maxResults=500))
            if results and 'messages' in results:
                messages.extend(results['messages'])
            
            while results and 'nextPageToken' in results:
                results = execute_with_retry(lambda: self.service.users().messages().list(
                    userId='me', q=query, pageToken=results['nextPageToken'], maxResults=500))
                if results and 'messages' in results:
                    messages.extend(results['messages'])
        except Exception as e:
            logger.error(f"検索エラー: {e}")
            return

        if not messages:
            logger.info("  -> 一致するメールはありませんでした。")
            return

        if self.dry_run:
            action = "ラベル付与とアーカイブ" if archive else "ラベル付与"
            logger.info(f"[DRY-RUN] {len(messages)} 件のメールに [{label_name}] を {action} 予定です。")
            return

        logger.info(f"  -> {len(messages)} 件を処理中 (ラベル付与{'+アーカイブ' if archive else ''})...")
        message_ids = [msg['id'] for msg in messages]
        batch_size = 1000
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i+batch_size]
            body = {
                "ids": batch, 
                "addLabelIds": [label_id]
            }
            if archive:
                body["removeLabelIds"] = ["INBOX"]
                
            try:
                execute_with_retry(lambda: self.service.users().messages().batchModify(userId='me', body=body))
            except Exception as e:
                logger.error(f"バッチ処理エラー: {e}")

    def create_filter(self, name, query, label_id, archive=False):
        """自動振り分けフィルタを作成する（オプションでアーカイブ設定）"""
        if self.dry_run:
            action = "ラベル付与＋アーカイブ" if archive else "ラベル付与"
            logger.info(f"[DRY-RUN] クエリ 「{query}」 に対して {action} のフィルタを作成予定です。")
            return

        filter_body = {
            "criteria": {"query": query},
            "action": {
                "addLabelIds": [label_id]
            }
        }
        if archive:
            # 受信トレイをスキップ
            filter_body["action"]["removeLabelIds"] = ["INBOX"]

        try:
            execute_with_retry(lambda: self.service.users().settings().filters().create(userId='me', body=filter_body))
            logger.info(f"  -> [{name}] のフィルタを作成しました。")
        except HttpError as e:
            if e.resp.status == 409:
                logger.info(f"  -> [{name}] のフィルタは既に存在します。")
            else:
                logger.error(f"フィルタ作成エラー: {e}")

def main():
    parser = argparse.ArgumentParser(description='提案されたルールをGmailに適用します。')
    parser.add_argument('--dry-run', action='store_true', help='実際の変更を行わずに、実行予定の内容を表示します')
    parser.add_argument('--filter', action='store_true', help='今後のメールにも適用されるフィルタを作成します')
    parser.add_argument('--config', default='rules.json', help='ルール設定ファイルのパス')
    args = parser.parse_args()

    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            rules = json.load(f)
    except FileNotFoundError:
        logger.error(f"{args.config} が見つかりません。先に analyze.py を実行してください。")
        sys.exit(1)

    auth = GmailAuthenticator()
    service = auth.get_service()
    applier = GmailRuleApplier(service, dry_run=args.dry_run)

    if args.dry_run:
        logger.info("=== DRY-RUN モードで実行中 (変更は行われません) ===")
    
    for rule in rules:
        name = rule['name']
        logger.info(f"\n--- ルール処理: {name} ---")
        
        label_id = applier.create_or_update_label(name, rule.get('color'))
        if label_id:
            applier.apply_query_to_messages(rule['query'], label_id, name)
            if args.filter:
                applier.create_filter(name, rule['query'], label_id)

    logger.info("\nすべての処理が完了しました！")

if __name__ == '__main__':
    main()
