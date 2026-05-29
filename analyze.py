import os
import json
import logging
import argparse
import socket
from google import genai
from google.genai import types
from auth import GmailAuthenticator
from utils import execute_with_retry

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# タイムアウト設定を延長 (秒)
socket.setdefaulttimeout(60)

class GmailAnalyzer:
    """Gmailのデータを抽出し、Geminiでルールを生成するクラス"""

    def __init__(self, model_name='gemini-3.5-flash'): 
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("環境変数 GEMINI_API_KEY が設定されていません。")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        logger.info(f"Analyzer を初期化しました (使用モデル: {model_name})")

    def fetch_email_metadata(self, service, max_emails=None, query='newer_than:1y'):
        """メールの送信元と件名を収集する (全量取得対応)"""
        logger.info(f"メールデータを収集しています (クエリ: {query}, 制限: {max_emails if max_emails else '無制限'})...")
        
        messages = []
        try:
            results = execute_with_retry(lambda: service.users().messages().list(
                userId='me', q=query, maxResults=500))
            if results and 'messages' in results:
                messages.extend(results['messages'])
                
            while results and 'nextPageToken' in results:
                if max_emails and len(messages) >= max_emails:
                    break
                page_token = results['nextPageToken']
                results = execute_with_retry(lambda: service.users().messages().list(
                    userId='me', q=query, pageToken=page_token, maxResults=500))
                if results and 'messages' in results:
                    messages.extend(results['messages'])
                    logger.info(f"現在 {len(messages)} 件のメッセージを特定...")
        except Exception as e:
            logger.error(f"メール一覧の取得中に致命的なエラーが発生しました: {e}")
            return []

        email_data = []
        target_count = len(messages) if not max_emails else min(len(messages), max_emails)
        logger.info(f"メッセージ詳細を取得中 (対象: {target_count} 件)...")
        
        for msg in messages[:target_count]:
            try:
                detail = execute_with_retry(lambda: service.users().messages().get(
                    userId='me', id=msg['id'], format='metadata', 
                    metadataHeaders=['From', 'Subject', 'Date']
                ))
                
                if not detail:
                    continue

                headers = detail.get('payload', {}).get('headers', [])
                entry = {h['name'].lower(): h['value'] for h in headers}
                
                if 'from' in entry or 'subject' in entry:
                    email_data.append({
                        "sender": entry.get('from', ''),
                        "subject": entry.get('subject', ''),
                        "date": entry.get('date', '')
                    })
                
                if len(email_data) % 100 == 0:
                    logger.info(f"  -> {len(email_data)} 件の詳細を取得完了")
                    
            except Exception:
                continue
                
        logger.info(f"合計 {len(email_data)} 件のメールメタデータを抽出しました。")
        return email_data

    def refine_existing_rules(self, existing_rules, unclassified_data):
        """既存のルールを未分類メールデータに基づいて強化する"""
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
あなたはGmail整理の専門家です。現在、15個のカテゴリで運用していますが、一部のメールがまだ分類されていません。
提供された「未分類メールのデータ」を分析し、以下の対応を行ってください。

1. 既存の15個のカテゴリのクエリを強化し、可能な限り多くの未分類メールを既存カテゴリに振り分けてください。
2. それでも分類しきれないメールのために、16番目のカテゴリとして 「📁 その他・未分類」 を新たに追加してください。
3. 出力は合計16個の要素を持つJSON配列としてください。

【制約事項】
- 既存の15個のカテゴリ名（name）は変更しないでください。
- 16番目の名前は 「📁 その他・未分類」 としてください。
- 16番目のクエリ（query）は、今回の未分類メールを確実にキャッチできるよう、主要な送信元ドメインやキーワードを列挙してください。
- 各カテゴリの backgroundColor は、Gmail APIで許可されたリストから選んでください。16番目は #999999 (グレー) にしてください。

【既存のルール】
{rules_text}

【未分類メールのデータ（送信頻度順）】
{unclassified_text[:30000]}
"""
        logger.info(f"Gemini API ({self.model_name}) で既存ルールを強化しています...")
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                )
            )
            refined_rules = json.loads(response.text)
            return refined_rules
        except Exception as e:
            logger.error(f"ルールの強化中にエラーが発生しました: {e}")
            return None

    def generate_rules(self, email_data, custom_instructions=None):
        """最新の google-genai SDK を使用して15個のルールを生成する"""
        # 送信者ごとの頻度と件名を分析
        summary = {}
        for data in email_data:
            s = data['sender']
            if s not in summary:
                summary[s] = {"count": 0, "subjects": []}
            summary[s]["count"] += 1
            if len(summary[s]["subjects"]) < 3:
                summary[s]["subjects"].append(data['subject'])
        
        # 上位 200 送信者程度に絞る（要約用）
        sorted_summary = sorted(summary.items(), key=lambda x: x[1]['count'], reverse=True)[:200]
        summary_text = json.dumps({k: v for k, v in sorted_summary}, ensure_ascii=False, indent=2)
        
        prompt = f"""
あなたはGmail整理の専門家です。提供された「1年分のメール送信統計データ」に基づき、
受信トレイを整理するための最適な「最大15個」のカテゴリと検索クエリを生成してください。

【出力形式】
JSON配列形式で、各要素は以下のフィールドを持つこと：
- name: ラベル名 (絵文字を1つ含む)
- color: {{ textColor: "#ffffff", backgroundColor: "#カラーコード" }}
- query: Gmail検索クエリ (from:, subject:, などを組み合わせ、そのカテゴリに属するメールを網羅すること)
- description: 分類の説明

【重要：カラー設定】
Gmail APIでは以下の背景色（backgroundColor）のみが許可されています。
必ずこのリストの中からラベルのイメージに合うものを選んでください（重複可）：
#000000, #434343, #666666, #999999, #cccccc, #efefef, #f3f3f3, #ffffff,
#fb4c2f, #ffad47, #fad165, #16a766, #43d692, #4a86e8, #a479e2, #f691b3,
#f6c5be, #ffe6c7, #fef1d1, #b9e4d0, #c6f3de, #c9daf8, #e4d7f5, #fcdee8,
#efa093, #ffd6a2, #fce8b3, #89d3b2, #a0eac9, #a4c2f4, #d0bcf1, #fbc8d9,
#e66550, #ffbc6b, #fcda83, #44b984, #68dfa9, #6d9eeb, #b694e8, #f7a7c0,
#cc3a21, #eaa041, #f2c960, #149e60, #3dc789, #3c78d8, #8e63ce, #e07798,
#ac2b16, #cf8933, #d5ae49, #0b804b, #2a9c68, #285bac, #653e9b, #b65775,
#822111, #a46a21, #aa8831, #076239, #1a764d, #1c4587, #41236d, #83334c

textColor は常に "#ffffff" にしてください。

【戦略指示】
- 単なる「送信者ごと」ではなく、「ショッピング」「金融」「開発」などの意味のある大きなカテゴリを優先してください。
- 15個をフルに使って、漏れがないように分類してください。
- クエリは、将来のメールにも適用可能な汎用性の高いものにしてください。

【データ（送信頻度順抜粋）】
{summary_text[:30000]}
"""
        if custom_instructions:
            prompt += f"\n【追加指示】\n{custom_instructions}"

        logger.info(f"Gemini API ({self.model_name}) でルールを生成しています...")
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                )
            )
            rules = json.loads(response.text)
            return rules
        except Exception as e:
            logger.error(f"ルールの生成中にエラーが発生しました: {e}")
            return None

def main():
    # zenmail.py から呼び出されることを想定していますが、単体動作も維持
    parser = argparse.ArgumentParser()
    parser.add_argument('--max', type=int, default=500)
    parser.add_argument('--model', type=str, default='gemini-3.1-flash')
    parser.add_argument('--prompt', type=str)
    args = parser.parse_args()

    from auth import GmailAuthenticator
    auth = GmailAuthenticator()
    service = auth.get_service()
    
    analyzer = GmailAnalyzer(model_name=args.model)
    data = analyzer.fetch_email_metadata(service, max_emails=args.max)
    rules = analyzer.generate_rules(data, custom_instructions=args.prompt)
    if rules:
        with open('rules.json', 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        print("Done.")

if __name__ == '__main__':
    main()
