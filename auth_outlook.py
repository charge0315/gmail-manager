import msal
import os
import logging

logger = logging.getLogger(__name__)

class OutlookAuthenticator:
    """IMAP XOAUTH2に必要なMicrosoft OAuth 2.0認証トークンの取得・管理を行うクラス"""

    def __init__(self, account_id, client_id, username=None):
        self.account_id = account_id
        self.client_id = client_id
        self.username = username
        self.cache_file = f"token_outlook_{account_id}.json"
        
        # IMAP接続用のスコープ (MSALは暗黙的に offline_access 等を要求するため、明示指定は不要です)
        self.scopes = ["https://outlook.office.com/IMAP.AccessAsUser.All"]
        
        # トークンキャッシュの構築
        self.cache = msal.SerializableTokenCache()
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    self.cache.deserialize(f.read())
            except Exception as e:
                logger.warning(f"キャッシュデシリアライズエラー: {e}")

        # MSAL公開クライアントの初期化
        self.app = msal.PublicClientApplication(
            self.client_id,
            authority="https://login.microsoftonline.com/common",
            token_cache=self.cache
        )

    def _save_cache(self):
        if self.cache.has_state_changed:
            try:
                with open(self.cache_file, "w") as f:
                    f.write(self.cache.serialize())
            except Exception as e:
                logger.error(f"トークンキャッシュの保存に失敗しました: {e}")

    def get_access_token(self) -> str:
        """
        有効なアクセストークンを取得する。
        キャッシュがあればサイレント更新を試み、無効な場合はブラウザを起動してサインインを促す。
        """
        accounts = self.app.get_accounts(username=self.username)
        result = None
        
        if accounts:
            logger.info(f"[{self.account_id}] キャッシュされた資格情報からサイレントにトークンを取得しています...")
            result = self.app.acquire_token_silent(self.scopes, account=accounts[0])
            
        if not result or "access_token" not in result:
            logger.info(f"[{self.account_id}] ブラウザを起動してサインイン認証フローを開始します...")
            # ローカルサーバー経由でリダイレクト結果を受け取る
            # Azureアプリ側で「http://localhost」がリダイレクトURIとして登録されている必要があります。
            result = self.app.acquire_token_interactive(
                scopes=self.scopes,
                login_hint=self.username
            )
            
        if result and "access_token" in result:
            self._save_cache()
            return result["access_token"]
        else:
            error_msg = result.get("error_description") or result.get("error") or "Unknown error"
            logger.error(f"Outlook OAuth2 トークン取得エラー: {error_msg}")
            raise Exception(f"Failed to acquire Outlook OAuth2 token: {error_msg}")
