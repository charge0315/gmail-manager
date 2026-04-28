import json
import logging
import os
from auth import GmailAuthenticator
from analyze import GmailAnalyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    if not os.path.exists('rules.json'):
        logger.error("rules.json が見つかりません。")
        return
    if not os.path.exists('unclassified_emails.json'):
        logger.error("unclassified_emails.json が見つかりません。extract_unclassified.py を実行してください。")
        return

    with open('rules.json', 'r', encoding='utf-8') as f:
        existing_rules = json.load(f)
    with open('unclassified_emails.json', 'r', encoding='utf-8') as f:
        unclassified_data = json.load(f)

    # モデルは gemini-3.1-pro-preview を使用
    analyzer = GmailAnalyzer(model_name='gemini-3.1-pro-preview')
    
    refined_rules = analyzer.refine_existing_rules(existing_rules, unclassified_data)
    
    if refined_rules:
        # バックアップを作成 (既存があれば上書き)
        import shutil
        if os.path.exists('rules.json'):
            shutil.copy('rules.json', 'rules.json.bak')
        
        with open('rules.json', 'w', encoding='utf-8') as f:
            json.dump(refined_rules, f, ensure_ascii=False, indent=2)
        logger.info("rules.json を強化版に更新しました。")
        
        print("\n更新されたルールのプレビュー:")
        for r in refined_rules:
            print(f"- {r['name']}: {r['description']}")
    else:
        logger.error("ルールの強化に失敗しました。")

if __name__ == '__main__':
    main()
