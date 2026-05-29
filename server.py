import os
import json
import logging
from mcp.server.fastmcp import FastMCP
from auth import GmailAuthenticator
from reset import GmailResetter
from analyze import GmailAnalyzer
from apply_rules import GmailRuleApplier

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MCPサーバの初期化
mcp = FastMCP("Gmail-Manager")

@mcp.tool()
def reset_gmail() -> str:
    """Gmailの全てのカスタムラベルとフィルタを削除し、全てのメールを受信トレイに戻します（初期化）。"""
    try:
        auth = GmailAuthenticator()
        service = auth.get_service()
        resetter = GmailResetter(service)
        
        resetter.reset_to_inbox()
        resetter.delete_all_filters_and_labels()
        return "Gmailの初期化（リセット）が完了しました。全てのメールが受信トレイに戻り、カスタムラベルとフィルタが削除されました。"
    except Exception as e:
        logger.error(f"リセットエラー: {e}")
        return f"リセット中にエラーが発生しました: {str(e)}"

@mcp.tool()
def analyze_emails(query: str = "newer_than:1y", max_emails: int = 500) -> str:
    """Gmailのメールを分析し、最適な分類ルール（rules.json）をAIで生成します。"""
    try:
        auth = GmailAuthenticator()
        service = auth.get_service()
        
        # モデル名はデフォルトを使用 (gemini-3.5-flash)
        analyzer = GmailAnalyzer()
        data = analyzer.fetch_email_metadata(service, max_emails=max_emails, query=query)
        rules = analyzer.generate_rules(data)
        
        if rules:
            with open('rules.json', 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            return f"分析完了: {len(rules)} 個のルールを生成し、rules.json に保存しました。"
        return "ルールの生成に失敗しました。AIからの応答が空でした。"
    except Exception as e:
        logger.error(f"分析エラー: {e}")
        return f"分析中にエラーが発生しました: {str(e)}"

@mcp.tool()
def apply_classification_rules(archive: bool = True, create_filters: bool = True) -> str:
    """rules.json のルールをGmailに適用し、ラベル作成、過去メールの整理、今後の自動振り分けフィルタ設定を行います。"""
    try:
        if not os.path.exists('rules.json'):
            return "rules.json が見つかりません。先に analyze_emails を実行してください。"
        
        with open('rules.json', 'r', encoding='utf-8') as f:
            rules = json.load(f)
            
        auth = GmailAuthenticator()
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
                    
        return f"適用完了: {len(results)} 個のルールを適用し、メールを整理しました。"
    except Exception as e:
        logger.error(f"適用エラー: {e}")
        return f"適用中にエラーが発生しました: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
