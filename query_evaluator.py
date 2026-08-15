import re
import logging

logger = logging.getLogger(__name__)

def evaluate_gmail_query(query: str, sender: str, subject: str) -> bool:
    """
    Gmail風クエリの文字列をPythonで評価し、senderとsubjectがマッチするか判定する。
    
    サポートするシンタックス:
    - from:(a.com OR b.com) / from:a.com
    - subject:("word1" OR "word2") / subject:word1
    - -from:... / -subject:... (否定)
    - OR による論理和
    - スペース区切りによる論理積(AND)
    - label:INBOX など (常にTrueとして評価)
    """
    sender = sender.lower()
    subject = subject.lower()
    query = query.strip()

    if not query:
        return False

    # 1. 括弧内の OR 条件をパースするための簡易ヘルパー
    def parse_or_terms(term_str):
        # (a OR b OR c) のような文字列から要素を取り出す
        term_str = term_str.strip('()')
        # 大文字の OR で分割
        parts = []
        # 単純な分割だとクォーテーション内の OR と混同するため、クォーテーションを考慮
        current = []
        in_q = False
        i = 0
        while i < len(term_str):
            c = term_str[i]
            if c == '"' or c == "'":
                in_q = not in_q
                current.append(c)
            elif term_str[i:i+4] == ' OR ' and not in_q:
                parts.append(''.join(current).strip())
                current = []
                i += 3
            else:
                current.append(c)
            i += 1
        if current:
            parts.append(''.join(current).strip())
        
        return [p.strip('"\'').lower() for p in parts if p.strip()]

    # 2. 括弧の外にある " OR " で分割する (論理和)
    # 括弧のネストとクォーテーションを考慮する
    tokens = []
    current = []
    paren_depth = 0
    in_quotes = False
    
    i = 0
    while i < len(query):
        char = query[i]
        if char == '"' or char == "'":
            in_quotes = not in_quotes
            current.append(char)
        elif char == '(' and not in_quotes:
            paren_depth += 1
            current.append(char)
        elif char == ')' and not in_quotes:
            paren_depth -= 1
            current.append(char)
        elif query[i:i+4] == ' OR ' and paren_depth == 0 and not in_quotes:
            tokens.append(''.join(current).strip())
            current = []
            i += 3  # " OR" をスキップ
        else:
            current.append(char)
        i += 1
    if current:
        tokens.append(''.join(current).strip())

    # tokens のいずれか1つの AND 条件グループが満たされればマッチ (OR)
    for token in tokens:
        if not token:
            continue
        
        # 3. スペースで分割する (論理積: AND)
        # ただし括弧内やダブルクォーテーション内のスペースは無視する
        and_terms = []
        curr_term = []
        p_depth = 0
        in_q = False
        
        j = 0
        while j < len(token):
            c = token[j]
            if c == '"' or c == "'":
                in_q = not in_q
                curr_term.append(c)
            elif c == '(' and not in_q:
                p_depth += 1
                curr_term.append(c)
            elif c == ')' and not in_q:
                p_depth -= 1
                curr_term.append(c)
            elif c == ' ' and p_depth == 0 and not in_q:
                if curr_term:
                    and_terms.append(''.join(curr_term).strip())
                    curr_term = []
            else:
                curr_term.append(c)
            j += 1
        if curr_term:
            and_terms.append(''.join(curr_term).strip())

        # すべての AND 条件を満たしているかチェック
        match_and = True
        for term in and_terms:
            if not term:
                continue
            
            is_negated = term.startswith('-')
            actual_term = term[1:] if is_negated else term
            
            term_matched = False
            if actual_term.startswith('from:'):
                val = actual_term[5:]
                if val.startswith('(') and val.endswith(')'):
                    domains = parse_or_terms(val)
                    term_matched = any(domain in sender for domain in domains)
                else:
                    domain = val.strip('"\'').lower()
                    term_matched = domain in sender
            elif actual_term.startswith('subject:'):
                val = actual_term[8:]
                if val.startswith('(') and val.endswith(')'):
                    words = parse_or_terms(val)
                    term_matched = any(word in subject for word in words)
                else:
                    word = val.strip('"\'').lower()
                    term_matched = word in subject
            elif actual_term.startswith('label:'):
                # label:INBOX などの指定は、IMAP側では常にINBOXを対象とするためTrueとする
                term_matched = True
            else:
                # プレーンテキスト検索（FromまたはSubjectに含まれるか）
                keyword = actual_term.strip('"\'').lower()
                term_matched = (keyword in sender) or (keyword in subject)
            
            if is_negated:
                term_matched = not term_matched
            
            if not term_matched:
                match_and = False
                break
        
        if match_and:
            return True
            
    return False
