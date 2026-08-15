import imaplib
import email
import logging
import socket
import time
import os
import base64
from email.header import decode_header
from query_evaluator import evaluate_gmail_query

logger = logging.getLogger(__name__)

# タイムアウト設定
socket.setdefaulttimeout(60)

def encode_imap_utf7(s: str) -> bytes:
    """
    文字列をIMAP Modified UTF-7形式のバイト列にエンコードする。
    """
    result = bytearray()
    in_unicode = False
    unicode_buffer = []
    
    def flush_unicode():
        nonlocal in_unicode, unicode_buffer
        if unicode_buffer:
            u_str = "".join(unicode_buffer)
            utf16_bytes = u_str.encode('utf-16-be')
            b64_bytes = base64.b64encode(utf16_bytes)
            b64_str = b64_bytes.decode('ascii').replace('/', ',').rstrip('=')
            result.extend(f"&{b64_str}-".encode('ascii'))
            unicode_buffer = []
            in_unicode = False

    for char in s:
        ord_c = ord(char)
        if 0x20 <= ord_c <= 0x7e:
            if char == '&':
                flush_unicode()
                result.extend(b'&-')
            else:
                flush_unicode()
                result.append(ord_c)
        else:
            in_unicode = True
            unicode_buffer.append(char)
            
    flush_unicode()
    return bytes(result)

def decode_imap_utf7(b: bytes) -> str:
    """
    IMAP Modified UTF-7形式のバイト列をデコードして文字列に戻す。
    """
    s = b.decode('ascii', errors='ignore')
    result = []
    
    i = 0
    while i < len(s):
        char = s[i]
        if char == '&':
            if i + 1 < len(s) and s[i+1] == '-':
                result.append('&')
                i += 2
                continue
            
            end = s.find('-', i)
            if end == -1:
                result.append(s[i:])
                break
            
            b64_str = s[i+1:end]
            b64_str = b64_str.replace(',', '/')
            pad_len = (4 - len(b64_str) % 4) % 4
            b64_str += '=' * pad_len
            
            try:
                utf16_bytes = base64.b64decode(b64_str.encode('ascii'))
                result.append(utf16_bytes.decode('utf-16-be'))
            except Exception:
                result.append(s[i:end+1])
            
            i = end + 1
        else:
            result.append(char)
            i += 1
            
    return "".join(result)

def decode_mime_header(header_val) -> str:
    if not header_val:
        return ""
    decoded_parts = decode_header(header_val)
    parts = []
    for text, encoding in decoded_parts:
        if isinstance(text, bytes):
            if encoding:
                try:
                    parts.append(text.decode(encoding, errors='ignore'))
                except LookupError:
                    parts.append(text.decode('utf-8', errors='ignore'))
            else:
                parts.append(text.decode('utf-8', errors='ignore'))
        else:
            parts.append(str(text))
    return "".join(parts)

def quote_folder_name(encoded_name: bytes) -> bytes:
    """IMAPフォルダ名をダブルクォーテーションで囲む"""
    if not encoded_name.startswith(b'"'):
        return b'"' + encoded_name + b'"'
    return encoded_name


class OutlookIMAPClient:
    """IMAP経由でOutlookのメール操作（分析、ルール適用、リセット）を行うクラス"""

    def __init__(self, username, access_token, server="outlook.office365.com", port=993, dry_run=False):
        self.username = username
        self.access_token = access_token
        self.server = server
        self.port = port
        self.dry_run = dry_run
        self.imap = None

    def connect(self):
        """IMAPサーバーに接続してXOAUTH2で認証する"""
        if self.imap:
            try:
                self.imap.noop()
                return
            except Exception:
                self.close()

        logger.info(f"Outlook IMAPサーバー ({self.server}:{self.port}) に接続中...")
        for attempt in range(3):
            try:
                self.imap = imaplib.IMAP4_SSL(self.server, self.port)
                
                # XOAUTH2認証文字列の生成
                # フォーマット: user={email}\x01auth=Bearer {token}\x01\x01
                auth_string = f"user={self.username}\x01auth=Bearer {self.access_token}\x01\x01"
                self.imap.authenticate('XOAUTH2', lambda x: auth_string.encode('utf-8'))
                
                logger.info(f"Outlook アカウント {self.username} にXOAUTH2認証でログイン成功。")
                return
            except (socket.timeout, ConnectionResetError, TimeoutError, imaplib.IMAP4.error) as e:
                logger.warning(f"接続失敗: {e}。再試行します... ({attempt + 1}/3)")
                time.sleep(3 * (attempt + 1))
        raise ConnectionError(f"Outlook IMAPサーバーへの接続に失敗しました: {self.username}")

    def close(self):
        """接続を閉じる"""
        if self.imap:
            try:
                self.imap.logout()
            except Exception:
                pass
            self.imap = None

    def execute_imap_cmd(self, func, *args, **kwargs):
        """IMAPコマンドを実行し、通信エラー時にリトライするヘルパー"""
        self.connect()
        for attempt in range(3):
            try:
                status, data = func(*args, **kwargs)
                time.sleep(0.1)  # レート制限対策のウェイト
                return status, data
            except (socket.timeout, ConnectionResetError, TimeoutError, BrokenPipeError) as e:
                if attempt == 2:
                    logger.error(f"IMAPコマンド実行エラー（リトライ上限超過）: {e}")
                    raise
                logger.warning(f"通信エラー発生。再試行します... ({attempt + 1}/3): {e}")
                time.sleep(3 * (attempt + 1))
                self.connect()
            except Exception as e:
                raise e

    def fetch_email_metadata(self, max_emails=500, query_since=None) -> list:
        """
        受信トレイ(INBOX)のメールを収集し、送信者、件名、日付を抽出する。
        """
        logger.info(f"Outlookメールデータを収集しています (最大 {max_emails} 件)...")
        self.connect()
        
        # INBOXの選択
        status, _ = self.execute_imap_cmd(self.imap.select, "INBOX")
        if status != "OK":
            logger.error("INBOXの選択に失敗しました。")
            return []

        # 検索条件
        search_key = "ALL"
        if query_since:
            # query_since は "newer_than:1y" などから日付形式に変換されたものを期待するが、
            # 簡易的に IMAP の SINCE クエリを使う (例: SINCE "16-Aug-2025")
            search_key = f'SINCE "{query_since}"'

        status, data = self.execute_imap_cmd(self.imap.uid, 'search', None, search_key)
        if status != "OK" or not data[0]:
            logger.warning("対象メールが見つかりませんでした。")
            return []

        uids = data[0].split()
        # 最新のメールから順に取得するため、UIDを逆順にする
        uids.reverse()
        target_uids = uids[:max_emails] if max_emails else uids
        
        email_data = []
        logger.info(f"メールメタデータを取得中 (対象: {len(target_uids)} 件)...")
        
        for i, uid in enumerate(target_uids):
            try:
                # メタデータ（From, Subject, Dateヘッダー）のみを取得して高速化
                status, fetch_data = self.execute_imap_cmd(
                    self.imap.uid, 'fetch', uid, '(BODY[HEADER.FIELDS (FROM SUBJECT DATE)])'
                )
                if status != "OK" or not fetch_data or not fetch_data[0]:
                    continue

                header_bytes = fetch_data[0][1]
                header_text = header_bytes.decode('utf-8', errors='ignore')
                msg = email.message_from_string(header_text)

                sender = decode_mime_header(msg.get('From', ''))
                subject = decode_mime_header(msg.get('Subject', ''))
                date_str = msg.get('Date', '')

                email_data.append({
                    "uid": uid.decode('utf-8'),
                    "sender": sender,
                    "subject": subject,
                    "date": date_str
                })

                if len(email_data) % 100 == 0:
                    logger.info(f"  -> {len(email_data)} 件の詳細を取得完了")
            except Exception as e:
                logger.warning(f"UID {uid} のフェッチ中にエラー: {e}")
                continue

        logger.info(f"合計 {len(email_data)} 件のメールメタデータを抽出しました。")
        return email_data

    def apply_rules(self, rules, archive=True):
        """
        rules.json を読み込み、メールを分類する。
        - フォルダがない場合は作成
        - クエリに合致する INBOX のメールを対応フォルダに移動 (コピー ＋ 削除)
        """
        self.connect()
        
        # 1. 既存のフォルダ構造（メールボックス一覧）の取得
        status, folder_list = self.execute_imap_cmd(self.imap.list)
        existing_folders = set()
        if status == "OK":
            for folder_info in folder_list:
                # IMAPのLIST応答を解析してフォルダ名を取り出す
                parts = folder_info.decode('utf-8', errors='ignore').split(' "/" ')
                if len(parts) > 1:
                    folder_name = parts[-1].strip('"')
                    # デコードして保持
                    existing_folders.add(decode_imap_utf7(folder_name.encode('ascii')))

        # 2. INBOX 内のすべてのメール (UID) をフェッチしてメモリに載せる
        status, _ = self.execute_imap_cmd(self.imap.select, "INBOX")
        if status != "OK":
            logger.error("INBOXの選択に失敗しました。")
            return

        status, data = self.execute_imap_cmd(self.imap.uid, 'search', None, 'ALL')
        if status != "OK" or not data[0]:
            logger.info("受信トレイにメールはありません。")
            return

        inbox_uids = data[0].split()
        inbox_emails = []
        for uid in inbox_uids:
            try:
                status, fetch_data = self.execute_imap_cmd(
                    self.imap.uid, 'fetch', uid, '(BODY[HEADER.FIELDS (FROM SUBJECT)])'
                )
                if status != "OK" or not fetch_data or not fetch_data[0]:
                    continue
                header_bytes = fetch_data[0][1]
                header_text = header_bytes.decode('utf-8', errors='ignore')
                msg = email.message_from_string(header_text)
                
                inbox_emails.append({
                    "uid": uid,
                    "sender": decode_mime_header(msg.get('From', '')),
                    "subject": decode_mime_header(msg.get('Subject', ''))
                })
            except Exception as e:
                logger.warning(f"UID {uid} のヘッダー読み込みエラー: {e}")

        logger.info(f"受信トレイの全 {len(inbox_emails)} 件のメールに対して分類ルールを適用します。")

        # 3. ルールごとの処理
        applied_uids = set()
        for rule in rules:
            folder_name = rule['name']
            query = rule['query']
            logger.info(f"\n--- ルール処理: {folder_name} ---")

            # 3.1. フォルダの作成
            encoded_folder = quote_folder_name(encode_imap_utf7(folder_name))
            if folder_name not in existing_folders:
                if self.dry_run:
                    logger.info(f"[DRY-RUN] 新しいフォルダ [{folder_name}] を作成予定です。")
                else:
                    logger.info(f"新しいフォルダ [{folder_name}] を作成します。")
                    status, _ = self.execute_imap_cmd(self.imap.create, encoded_folder)
                    if status == "OK":
                        existing_folders.add(folder_name)
                    else:
                        logger.error(f"フォルダ [{folder_name}] の作成に失敗しました。")
                        continue
            else:
                logger.info(f"フォルダ [{folder_name}] は既に存在します。")

            # 3.2. マッチするメールの特定
            matched_emails = []
            for email_meta in inbox_emails:
                if email_meta['uid'] in applied_uids:
                    continue
                if evaluate_gmail_query(query, email_meta['sender'], email_meta['subject']):
                    matched_emails.append(email_meta)

            if not matched_emails:
                logger.info("  -> 一致するメールはありませんでした。")
                continue

            if self.dry_run:
                logger.info(f"[DRY-RUN] {len(matched_emails)} 件のメールを [{folder_name}] に移動予定です。")
                for m in matched_emails:
                    applied_uids.add(m['uid'])
                continue

            # 3.3. メールの移動 (コピー -> 削除マーク)
            logger.info(f"  -> {len(matched_emails)} 件のメールを [{folder_name}] へ移動中...")
            success_count = 0
            for email_meta in matched_emails:
                uid = email_meta['uid']
                try:
                    # コピー
                    status, _ = self.execute_imap_cmd(self.imap.uid, 'copy', uid, encoded_folder)
                    if status == "OK":
                        # 削除マーク
                        self.execute_imap_cmd(self.imap.uid, 'store', uid, '+FLAGS', '\\Deleted')
                        applied_uids.add(uid)
                        success_count += 1
                    else:
                        logger.error(f"UID {uid} をフォルダ [{folder_name}] にコピーできませんでした。")
                except Exception as e:
                    logger.error(f"UID {uid} の移動中にエラー: {e}")

            logger.info(f"  -> {success_count} 件の移動完了")

        # 4. 未分類メールのフォールバック (📁 その他・未分類)
        fallback_folder_name = "📁 その他・未分類"
        unclassified_emails = [m for m in inbox_emails if m['uid'] not in applied_uids]
        
        if unclassified_emails:
            logger.info(f"\n--- 未分類メールの自動「その他」整理処理を開始 ---")
            encoded_fallback = quote_folder_name(encode_imap_utf7(fallback_folder_name))
            if fallback_folder_name not in existing_folders:
                if self.dry_run:
                    logger.info(f"[DRY-RUN] 新しいフォルダ [{fallback_folder_name}] を作成予定です。")
                else:
                    logger.info(f"新しいフォルダ [{fallback_folder_name}] を作成します。")
                    status, _ = self.execute_imap_cmd(self.imap.create, encoded_fallback)
                    if status != "OK":
                        logger.error(f"フォルダ [{fallback_folder_name}] の作成に失敗しました。")
                        return
            
            if self.dry_run:
                logger.info(f"[DRY-RUN] {len(unclassified_emails)} 件の未分類メールを [{fallback_folder_name}] に移動予定です。")
            else:
                logger.info(f"  -> {len(unclassified_emails)} 件の未分類メールを [{fallback_folder_name}] へ移動中...")
                success_count = 0
                for email_meta in unclassified_emails:
                    uid = email_meta['uid']
                    try:
                        status, _ = self.execute_imap_cmd(self.imap.uid, 'copy', uid, encoded_fallback)
                        if status == "OK":
                            self.execute_imap_cmd(self.imap.uid, 'store', uid, '+FLAGS', '\\Deleted')
                            success_count += 1
                    except Exception as e:
                        logger.error(f"UID {uid} の移動中にエラー: {e}")
                logger.info(f"  -> {success_count} 件の移動完了")

        # 5. 最後に EXPUNGE を実行して削除を物理反映
        if not self.dry_run:
            logger.info("削除されたメッセージをクリーンアップ中 (EXPUNGE)...")
            self.execute_imap_cmd(self.imap.expunge)

    def reset_to_inbox(self):
        """
        作成されたカスタムフォルダを特定し、その中の全メールを受信トレイ(INBOX)に戻す。
        その後、カスタムフォルダを削除する。
        """
        self.connect()

        # 1. フォルダ一覧の取得
        status, folder_list = self.execute_imap_cmd(self.imap.list)
        if status != "OK":
            logger.error("フォルダ一覧の取得に失敗しました。")
            return

        target_folders = []
        for folder_info in folder_list:
            parts = folder_info.decode('utf-8', errors='ignore').split(' "/" ')
            if len(parts) > 1:
                folder_raw = parts[-1].strip('"')
                folder_name = decode_imap_utf7(folder_raw.encode('ascii'))
                # カスタムフォルダの判定：絵文字を含む、または「フォルダ」名に特定の文字が含まれる
                # 今回は、ルール名に絵文字が含まれることや、リセット対象のフォルダを検知する。
                # ユーザーが指定した rules.json から判定するのも手だが、
                # 絵文字から始まるフォルダ、または「📁 その他・未分類」のようなフォルダを自動検出して初期化するのが最もスマート。
                # 基本的なシステムフォルダ（INBOX, Sent, Drafts, Trash, Junk, Archive等）を除外する。
                system_folders = ["INBOX", "Sent", "Drafts", "Trash", "Junk", "Archive", "Deleted Items", "Outbox", "Notes", "Sync Issues"]
                if folder_name not in system_folders and not any(folder_name.startswith(sf) for sf in system_folders):
                    target_folders.append((folder_name, folder_raw))

        if not target_folders:
            logger.info("削除対象のカスタムフォルダは見つかりませんでした。")
            return

        logger.info(f"以下のカスタムフォルダ内のメールを受信トレイに戻し、フォルダを削除します:")
        for name, _ in target_folders:
            logger.info(f"  - {name}")

        for name, raw_name in target_folders:
            encoded_folder = quote_folder_name(raw_name.encode('ascii'))
            logger.info(f"\n[{name}] の処理中...")

            # フォルダを選択
            status, data = self.execute_imap_cmd(self.imap.select, encoded_folder)
            if status != "OK":
                logger.warning(f"フォルダ [{name}] を選択できませんでした。スキップします。")
                continue

            # メール (UID) の検索
            status, search_data = self.execute_imap_cmd(self.imap.uid, 'search', None, 'ALL')
            if status == "OK" and search_data[0]:
                uids = search_data[0].split()
                logger.info(f"  -> {len(uids)} 件のメールを受信トレイ(INBOX)に戻します...")
                
                success_count = 0
                for uid in uids:
                    try:
                        # INBOX にコピー
                        status, _ = self.execute_imap_cmd(self.imap.uid, 'copy', uid, "INBOX")
                        if status == "OK":
                            # 元フォルダから削除マーク
                            self.execute_imap_cmd(self.imap.uid, 'store', uid, '+FLAGS', '\\Deleted')
                            success_count += 1
                    except Exception as e:
                        logger.error(f"UID {uid} の復元中にエラー: {e}")
                
                # クリーンアップ
                self.execute_imap_cmd(self.imap.expunge)
                logger.info(f"  -> {success_count} 件を復元完了")
            else:
                logger.info("  -> メールはありません。")

            # フォルダの削除
            # フォルダを削除する前にアンセレクト（INBOXなど他のフォルダを選択）する必要がある
            self.execute_imap_cmd(self.imap.select, "INBOX")
            logger.info(f"フォルダ [{name}] を削除しています...")
            status, _ = self.execute_imap_cmd(self.imap.delete, encoded_folder)
            if status == "OK":
                logger.info(f"フォルダ [{name}] を削除しました。")
            else:
                logger.error(f"フォルダ [{name}] の削除に失敗しました。")
