import json
import logging
import os
import argparse
import sys
import shutil
from auth import GmailAuthenticator
from analyze import GmailAnalyzer
from utils import load_accounts

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='未分類メールデータを元に分類ルールを洗練します。')
    parser.add_argument('--account', help='処理対象とするアカウントID。指定しない場合はすべて処理。')
    args = parser.parse_args()

    accounts = load_accounts()
    
    # 対象アカウントの特定
    if args.account:
        target_accounts = [a for a in accounts if a['id'] == args.account]
        if not target_accounts:
            logger.error(f"アカウント ID '{args.account}' が見つかりません。")
            sys.exit(1)
    else:
        target_accounts = accounts

    for acc in target_accounts:
        logger.info(f"\nルール洗練を開始: {acc['name']} ({acc['type']})")
        
        rules_file = 'rules.json' if acc['id'] == 'default' else f'rules_{acc["id"]}.json'
        unclassified_file = 'unclassified_emails.json' if acc['id'] == 'default' else f'unclassified_emails_{acc["id"]}.json'
        
        if not os.path.exists(rules_file):
            if os.path.exists('rules.json'):
                logger.warning(f"アカウント固有のルールファイル {rules_file} が存在しないため、共通の rules.json をフォールバックとして使用します。")
                rules_file = 'rules.json'
            else:
                logger.warning(f"ルールファイル {rules_file} が見つかりません。スキップします。")
                continue
        if not os.path.exists(unclassified_file):
            if os.path.exists('unclassified_emails.json'):
                logger.warning(f"アカウント固有の未分類メールファイル {unclassified_file} が存在しないため、共通の unclassified_emails.json をフォールバックとして使用します。")
                unclassified_file = 'unclassified_emails.json'
            else:
                logger.warning(f"未分類メールファイル {unclassified_file} が見つかりません。先に extract_unclassified.py を実行してください。スキップします。")
                continue

        with open(rules_file, 'r', encoding='utf-8') as f:
            existing_rules = json.load(f)
        with open(unclassified_file, 'r', encoding='utf-8') as f:
            unclassified_data = json.load(f)

        # モデルは gemini-3.1-pro を使用 (RULE: 2026年4月時点最新モデル/ベストプラクティスを考慮するが、今回は gemini-3.1-pro)
        analyzer = GmailAnalyzer(model_name='gemini-3.1-pro')
        
        refined_rules = analyzer.refine_existing_rules(existing_rules, unclassified_data)
        
        if refined_rules:
            # バックアップを作成
            shutil.copy(rules_file, f"{rules_file}.bak")
            
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(refined_rules, f, ensure_ascii=False, indent=2)
            logger.info(f"アカウント '{acc['name']}' の {rules_file} を強化版に更新しました。")
            
            print(f"\n更新されたルール ({acc['name']}) のプレビュー:")
            for r in refined_rules:
                print(f"- {r['name']}: {r['description']}")
        else:
            logger.error(f"アカウント '{acc['name']}' のルールの強化に失敗しました。")

if __name__ == '__main__':
    main()
