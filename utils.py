import time
import socket
import logging
import json
import os
import sys

logger = logging.getLogger(__name__)

ACCOUNTS_CONFIG = 'accounts.json'

def execute_with_retry(func, max_retries=3, initial_wait=5):
    """
    Gmail API 実行用の共通リトライロジック。
    通信エラー（タイムアウト等）が発生した場合に指定回数リトライします。
    """
    for attempt in range(max_retries):
        try:
            result = func().execute()
            # 成功後、レート制限を考慮して少し待機
            time.sleep(0.5)
            return result
        except (socket.timeout, ConnectionResetError, TimeoutError, BrokenPipeError) as e:
            if attempt == max_retries - 1:
                logger.error(f"最大リトライ回数に達しました: {e}")
                raise
            wait = (attempt + 1) * initial_wait
            logger.warning(f"通信エラーが発生しました。{wait}秒後に再試行します... ({attempt + 1}/{max_retries}: {e})")
            time.sleep(wait)
        except Exception as e:
            # その他の例外はそのまま投げる（呼び出し側でハンドリング）
            raise e
    return None

def load_accounts():
    """アカウント情報をaccounts.jsonから読み込む。存在しない場合はデフォルトのGmailを返す。"""
    if os.path.exists(ACCOUNTS_CONFIG):
        try:
            with open(ACCOUNTS_CONFIG, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"アカウント設定ファイル {ACCOUNTS_CONFIG} の読み込みに失敗しました: {e}")
            sys.exit(1)
    else:
        logger.info(f"{ACCOUNTS_CONFIG} が見つからないため、デフォルトのGmailアカウント（単一）を使用します。")
        return [{
            "id": "default",
            "name": "デフォルト Gmail",
            "type": "gmail"
        }]


