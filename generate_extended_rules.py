import os
import json
import logging
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("環境変数 GEMINI_API_KEY が設定されていません。")
        return

    # 1. データの読み込み
    with open('rules.json', 'r', encoding='utf-8') as f:
        existing_rules = json.load(f)
    with open('unclassified_emails.json', 'r', encoding='utf-8') as f:
        unclassified_data = json.load(f)

    num_existing = len(existing_rules)
    num_min_target = num_existing + 5
    num_max_target = num_existing + 10

    # 送信者ごとの頻度と件名を分析
    summary = {}
    for data in unclassified_data:
        s = data['sender']
        if s not in summary:
            summary[s] = {"count": 0, "subjects": []}
        summary[s]["count"] += 1
        if len(summary[s]["subjects"]) < 3:
            summary[s]["subjects"].append(data['subject'])
    
    sorted_summary = sorted(summary.items(), key=lambda x: x[1]['count'], reverse=True)[:200]
    unclassified_text = json.dumps({k: v for k, v in sorted_summary}, ensure_ascii=False, indent=2)
    rules_text = json.dumps(existing_rules, ensure_ascii=False, indent=2)

    prompt = f"""
あなたはGmail整理の専門家です。現在{num_existing}個のカテゴリでGmailを自動整理していますが、まだ多くのメールが「その他」に分類されてしまっています。
ユーザーからのフィードバックに基づき、**「できるだけその他に偏らず、カテゴリ数を{num_min_target}〜{num_max_target}個程度に増やして、より美しく詳細に分類する」**ための新しい整理ルールを作成してください。

提供された「既存の{num_existing}カテゴリの定義」と「未分類メールのデータ」を徹底的に分析し、以下のタスクを実行してください。

1. **既存の{num_existing}カテゴリのクエリを強化**し、関連する未分類メールを適切に吸収できるようにしてください。
2. **新規カテゴリを5〜10個追加**してください。未分類メール（送信頻度の高いもの）から、意味のあるテーマを持つ新カテゴリを抽出してください。
   （例：ホンダ等の「🚗 マイカー・車」、東横インやBooking.com等の「🏨 旅行・ホテル予約」、Garmin等の「🏃 スポーツ・スマートウォッチ」、重要通知やセキュリティ等の「🔔 重要なお知らせ」など）
3. 新しいルールセットは、**合計{num_min_target}個から最大{num_max_target}個のカテゴリ**で構成してください。
4. 各カテゴリの「backgroundColor」は、以下の Gmail API で許可されたカラーリストから選んでください（重複可）：
   #000000, #434343, #666666, #999999, #cccccc, #efefef, #f3f3f3, #ffffff,
   #fb4c2f, #ffad47, #fad165, #16a766, #43d692, #4a86e8, #a479e2, #f691b3,
   #f6c5be, #ffe6c7, #fef1d1, #b9e4d0, #c6f3de, #c9daf8, #e4d7f5, #fcdee8,
   #efa093, #ffd6a2, #fce8b3, #89d3b2, #a0eac9, #a4c2f4, #d0bcf1, #fbc8d9,
   #e66550, #ffbc6b, #fcda83, #44b984, #68dfa9, #6d9eeb, #b694e8, #f7a7c0,
   #cc3a21, #eaa041, #f2c960, #149e60, #3dc789, #3c78d8, #8e63ce, #e07798,
   #ac2b16, #cf8933, #d5ae49, #0b804b, #2a9c68, #285bac, #653e9b, #b65775,
   #822111, #a46a21, #aa8831, #076239, #1a764d, #1c4587, #41236d, #83334c

   textColor は常に "#ffffff" にしてください。
5. 出力は、カテゴリ定義のJSON配列のみを返してください。

【既存の{num_existing}カテゴリの定義】
{rules_text}

【未分類メールのデータ（送信頻度順抜粋）】
{unclassified_text[:30000]}
"""

    logger.info(f"Gemini 3.1 Pro でカテゴリを拡張し、新しいルールセットを生成しています (目標: {num_min_target}〜{num_max_target})...")
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model='gemini-3.1-pro',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
            )
        )
        extended_rules = json.loads(response.text)
        
        # バックアップを作成
        import shutil
        shutil.copy('rules.json', 'rules.json.bak2')
        
        with open('rules.json', 'w', encoding='utf-8') as f:
            json.dump(extended_rules, f, ensure_ascii=False, indent=2)
            
        logger.info(f"rules.json を拡張版に更新しました（カテゴリ数: {len(extended_rules)}）。")
        print("\n拡張されたルールのプレビュー:")
        for r in extended_rules:
            print(f"- {r['name']}: {r['description']}")
            
    except Exception as e:
        logger.error(f"ルールの拡張中にエラーが発生しました: {e}")

if __name__ == '__main__':
    main()
