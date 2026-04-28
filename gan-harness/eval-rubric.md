# Evaluation Rubric: ZenMail Automator

This rubric is used to evaluate the implementation of the ZenMail Automator project.

| Criteria | Weight | Excellent (4) | Good (3) | Satisfactory (2) | Poor (1) |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **Design Quality** | 0.3 | Labels use intuitive emojis/colors; UI/Console output is clean and highly readable. | Labels are clear; output is structured but basic. | Some labels are confusing; output is cluttered. | No visual hierarchy; labels are plain text. |
| **Originality** | 0.2 | AI generates deep semantic rules beyond simple keywords; unique features like "Dry Run" are fully realized. | Rules are mostly keyword-based but well-categorized by AI. | Basic AI categorization that mimics simple manual filters. | Minimal AI involvement; rules are hardcoded or trivial. |
| **Craft** | 0.3 | Robust error handling; uses batch operations correctly; clean, modularized code with logs. | Handles common errors; uses basic API calls correctly; code is readable. | Occasional crashes; inefficient API usage (e.g., no batching). | Frequent errors; spaghetti code; ignores rate limits. |
| **Functionality** | 0.2 | All features (Analysis, Apply, Filter, Reset) work seamlessly; covers 90%+ of inbox. | Main flows work; most emails are categorized correctly. | Some scripts fail or produce incorrect Gmail queries. | Core functionality is broken or severely limited. |

## Specific Test Scenarios
1. **Initial Setup**: Run `auth.py` and verify token generation.
2. **Analysis**: Run `analyze.py` and check if `rules.json` contains meaningful, diverse categories with valid Gmail queries.
3. **Safety**: Execute a "Dry Run" and verify that no changes are made to Gmail yet.
4. **Application**: Run `apply_rules.py` and verify that labels are created with correct colors/emojis and messages are tagged.
5. **Automation**: Verify that a Gmail filter is created for at least one rule.
6. **Reset**: Run `delete_old_rules.py` and verify that all custom labels and filters are removed.
