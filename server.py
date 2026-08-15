import os
import json
import logging
import sys
from mcp.server.fastmcp import FastMCP
from auth import GmailAuthenticator
from reset import GmailResetter
from analyze import GmailAnalyzer
from apply_rules import GmailRuleApplier
from outlook_client import OutlookIMAPClient
from auth_outlook import OutlookAuthenticator
from utils import load_accounts

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MCPサーバの初期化
mcp = FastMCP("Mail-Organizer")

def get_account_by_id(account_id: str):
    """アカウントIDからアカウント情報を取得する。見つからない場合は例外を発生させる。"""
    accounts = load_accounts()
    for acc in accounts:
        if acc['id'] == account_id:
            return acc
    raise ValueError(f"アカウント ID '{account_id}' が見つかりません。")

def get_rules_filename(account_id: str) -> str:
    """アカウントごとのルールファイル名を取得する"""
    if account_id == "default":
        return "rules.json"
    return f"rules_{account_id}.json"

@mcp.tool()
def reset_emails(account_id: str = "default") -> str:
    """指定されたアカウントの全てのカスタムフォルダ/ラベルを削除し、全てのメールを受信トレイに戻します（初期化）。"""
    try:
        acc = get_account_by_id(account_id)
        
        if acc['type'] == 'gmail':
            auth = GmailAuthenticator(account_id=acc['id'] if acc['id'] != "default" else None)
            service = auth.get_service()
            resetter = GmailResetter(service)
            
            resetter.reset_to_inbox()
            resetter.delete_all_filters_and_labels()
            return f"Gmailアカウント '{acc['name']}' の初期化が完了しました。"
            
        elif acc['type'] == 'outlook':
            if "client_id" not in acc:
                return f"アカウント {acc['name']} の client_id が accounts.json に指定されていません。"
            
            try:
                auth_outlook = OutlookAuthenticator(
                    account_id=acc['id'],
                    client_id=acc['client_id'],
                    username=acc['username']
                )
                access_token = auth_outlook.get_access_token()
            except Exception as e:
                return f"Outlookの認証に失敗しました: {str(e)}"

            client = OutlookIMAPClient(
                username=acc['username'],
                access_token=access_token,
                server=acc.get('imap_server', 'outlook.office365.com'),
                port=acc.get('imap_port', 993)
            )
            try:
                client.reset_to_inbox()
                return f"Outlookアカウント '{acc['name']}' の初期化が完了しました。"
            finally:
                client.close()
        else:
            return f"未サポートのアカウントタイプです: {acc['type']}"
            
    except Exception as e:
        logger.error(f"リセットエラー: {e}")
        return f"リセット中にエラーが発生しました: {str(e)}"

@mcp.tool()
def analyze_emails(account_id: str = "default", query: str = "newer_than:1y", max_emails: int = 500, num_categories: int = 15) -> str:
    """メールを分析し、最適な分類ルールをAIで生成して rules_<account_id>.json に保存します。"""
    try:
        acc = get_account_by_id(account_id)
        rules_file = get_rules_filename(account_id)
        
        if acc['type'] == 'gmail':
            auth = GmailAuthenticator(account_id=acc['id'] if acc['id'] != "default" else None)
            service = auth.get_service()
            analyzer = GmailAnalyzer()
            email_data = analyzer.fetch_email_metadata(service, max_emails=max_emails, query=query)
            
        elif acc['type'] == 'outlook':
            if "client_id" not in acc:
                return f"アカウント {acc['name']} の client_id が accounts.json に指定されていません。"
            
            try:
                auth_outlook = OutlookAuthenticator(
                    account_id=acc['id'],
                    client_id=acc['client_id'],
                    username=acc['username']
                )
                access_token = auth_outlook.get_access_token()
            except Exception as e:
                return f"Outlookの認証に失敗しました: {str(e)}"

            client = OutlookIMAPClient(
                username=acc['username'],
                access_token=access_token,
                server=acc.get('imap_server', 'outlook.office365.com'),
                port=acc.get('imap_port', 993)
            )
            try:
                email_data = client.fetch_email_metadata(max_emails=max_emails)
            finally:
                client.close()
            analyzer = GmailAnalyzer()
        else:
            return f"未サポートのアカウントタイプです: {acc['type']}"
            
        if not email_data:
            return f"アカウント '{acc['name']}' に分析可能なメールが見つかりませんでした。"
            
        rules = analyzer.generate_rules(email_data, num_categories=num_categories)
        
        if rules:
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            return f"分析完了: {len(rules)} 個のルールを生成し、{rules_file} に保存しました。"
        return "ルールの生成に失敗しました。"
        
    except Exception as e:
        logger.error(f"分析エラー: {e}")
        return f"分析中にエラーが発生しました: {str(e)}"

@mcp.tool()
def apply_classification_rules(account_id: str = "default", archive: bool = True, create_filters: bool = True) -> str:
    """rules_<account_id>.json のルールを読み込み、メールボックスに適用（分類とアーカイブ）します。"""
    try:
        acc = get_account_by_id(account_id)
        rules_file = get_rules_filename(account_id)
        
        if not os.path.exists(rules_file):
            fallback_file = 'rules.json'
            if os.path.exists(fallback_file):
                logger.warning(f"アカウント固有のルールファイル {rules_file} が見つからないため、共通の {fallback_file} をフォールバックとして使用します。")
                rules_file = fallback_file
            else:
                return f"ルールファイル {rules_file} が見つかりません。先に analyze_emails を実行してください。"
        
        with open(rules_file, 'r', encoding='utf-8') as f:
            rules = json.load(f)
            
        if acc['type'] == 'gmail':
            auth = GmailAuthenticator(account_id=acc['id'] if acc['id'] != "default" else None)
            service = auth.get_service()
            applier = GmailRuleApplier(service)
            
            results = []
            for rule in rules:
                label_id = applier.create_or_update_label(rule['name'], rule.get('color'))
                if label_id:
                    applier.apply_query_to_messages(rule['query'], label_id, rule['name'], archive=archive)
                    if create_filters:
                        applier.create_filter(rule['name'], rule['query'], label_id, archive=archive)
                    results.append(f"Applied: {rule['name']}")
            
            # 未分類メールのフォールバック
            applier.apply_unclassified_fallback([rule['name'] for rule in rules], archive=archive)
            return f"適用完了: Gmailアカウント '{acc['name']}' にルールを適用し、メールを整理しました。"
            
        elif acc['type'] == 'outlook':
            if "client_id" not in acc:
                return f"アカウント {acc['name']} の client_id が accounts.json に指定されていません。"
            
            try:
                auth_outlook = OutlookAuthenticator(
                    account_id=acc['id'],
                    client_id=acc['client_id'],
                    username=acc['username']
                )
                access_token = auth_outlook.get_access_token()
            except Exception as e:
                return f"Outlookの認証に失敗しました: {str(e)}"

            client = OutlookIMAPClient(
                username=acc['username'],
                access_token=access_token,
                server=acc.get('imap_server', 'outlook.office365.com'),
                port=acc.get('imap_port', 993)
            )
            try:
                client.apply_rules(rules, archive=archive)
                return f"適用完了: Outlookアカウント '{acc['name']}' にフォルダ移動を適用しました。"
            finally:
                client.close()
        else:
            return f"未サポートのアカウントタイプです: {acc['type']}"
            
    except Exception as e:
        logger.error(f"適用エラー: {e}")
        return f"適用中にエラーが発生しました: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
