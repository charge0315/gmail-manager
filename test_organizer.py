import unittest
from query_evaluator import evaluate_gmail_query
from outlook_client import encode_imap_utf7, decode_imap_utf7

class TestQueryEvaluator(unittest.TestCase):
    def test_basic_from(self):
        self.assertTrue(evaluate_gmail_query("from:example.com", "sender@example.com", "Hello"))
        self.assertFalse(evaluate_gmail_query("from:example.com", "sender@other.com", "Hello"))

    def test_or_from(self):
        query = "from:(example.com OR other.com)"
        self.assertTrue(evaluate_gmail_query(query, "sender@example.com", "Hello"))
        self.assertTrue(evaluate_gmail_query(query, "sender@other.com", "Hello"))
        self.assertFalse(evaluate_gmail_query(query, "sender@third.com", "Hello"))

    def test_subject(self):
        self.assertTrue(evaluate_gmail_query("subject:urgent", "sender@example.com", "This is an urgent matter"))
        self.assertFalse(evaluate_gmail_query("subject:urgent", "sender@example.com", "Normal email"))

    def test_negation(self):
        query = "from:example.com -from:spam.example.com"
        self.assertTrue(evaluate_gmail_query(query, "sender@example.com", "Hello"))
        self.assertFalse(evaluate_gmail_query(query, "sender@spam.example.com", "Hello"))

    def test_complex_query(self):
        query = 'from:(1password.com) OR subject:("セキュリティ通知" OR "パスワード")'
        self.assertTrue(evaluate_gmail_query(query, "no-reply@1password.com", "Your invoice"))
        self.assertTrue(evaluate_gmail_query(query, "admin@mycompany.com", "セキュリティ通知のご案内"))
        self.assertFalse(evaluate_gmail_query(query, "friend@gmail.com", "ランチのお誘い"))

class TestIMAPUTF7(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(encode_imap_utf7("INBOX"), b"INBOX")
        self.assertEqual(decode_imap_utf7(b"INBOX"), "INBOX")

    def test_non_ascii(self):
        orig = "🎮 配信・コミュニティ"
        encoded = encode_imap_utf7(orig)
        decoded = decode_imap_utf7(encoded)
        self.assertEqual(decoded, orig)

    def test_ampersand(self):
        self.assertEqual(encode_imap_utf7("A & B"), b"A &- B")
        self.assertEqual(decode_imap_utf7(b"A &- B"), "A & B")

if __name__ == '__main__':
    unittest.main()
