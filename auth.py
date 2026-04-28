import os.path
import logging
import socket
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# IPv4 を強制する (IPv6 接続不良によるタイムアウト回避)
orig_getaddrinfo = socket.getaddrinfo

def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = getaddrinfo_ipv4

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# グローバルなタイムアウトを延長
socket.setdefaulttimeout(300)

class GmailAuthenticator:
    """Gmail APIの認証を管理するクラス"""
    
    SCOPES = [
        'https://mail.google.com/',
        'https://www.googleapis.com/auth/gmail.settings.basic'
    ]
    TOKEN_FILE = 'token.json'
    CREDENTIALS_FILE = 'credentials.json'

    def __init__(self):
        self.creds = None

    def get_credentials(self):
        """有効な資格情報を取得する。必要に応じてリフレッシュやログインを行う。"""
        if os.path.exists(self.TOKEN_FILE):
            self.creds = Credentials.from_authorized_user_file(self.TOKEN_FILE, self.SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    logger.info("トークンをリフレッシュしています...")
                    self.creds.refresh(Request())
                except Exception as e:
                    logger.error(f"トークンのリフレッシュに失敗しました: {e}")
                    self.creds = None
            
            if not self.creds:
                if not os.path.exists(self.CREDENTIALS_FILE):
                    logger.error(f"{self.CREDENTIALS_FILE} が見つかりません。")
                    raise FileNotFoundError(f"{self.CREDENTIALS_FILE} is required for authentication.")
                
                logger.info("ブラウザで認証フローを開始します...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.CREDENTIALS_FILE, self.SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            with open(self.TOKEN_FILE, 'w') as token:
                token.write(self.creds.to_json())
                logger.info(f"新しいトークンを {self.TOKEN_FILE} に保存しました。")

        return self.creds

    def get_service(self):
        """認証済みのGmail APIサービスインスタンスを返す。"""
        creds = self.get_credentials()
        return build('gmail', 'v1', credentials=creds)

def get_gmail_service():
    """既存コードとの互換性のためのヘルパー関数"""
    try:
        auth = GmailAuthenticator()
        return auth.get_service()
    except Exception as e:
        logger.error(f"認証中にエラーが発生しました: {e}")
        return None

if __name__ == '__main__':
    logger.info("Gmail 認証のテストを開始します...")
    service = get_gmail_service()
    if service:
        logger.info("認証が完了しました。")
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        logger.info(f"現在、{len(labels)} 個のラベルが存在します。")
