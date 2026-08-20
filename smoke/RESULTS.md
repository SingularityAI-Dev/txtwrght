# Smoke suite results

Run 2026-08-17 21:35 UTC. **10 of 10 passed** (gate is 8 of 10).

| Task | Kind | Result | Steps | Tokens | Seconds | Checked against |
|---|---|---|---|---|---|---|
| form-fill | fixture | pass | 3 | 13321 | 11.9 | page state |
| login-flow | fixture | pass | 4 | 17751 | 16.9 | page state |
| dropdown-select | fixture | pass | 2 | 8910 | 8.0 | page state |
| scroll-and-read | fixture | pass | 14 | 71388 | 61.4 | agent answer |
| shadow-dom-click | fixture | pass | 2 | 8421 | 8.5 | page state |
| iframe-input | fixture | pass | 3 | 13260 | 15.3 | frame state |
| spa-navigation | fixture | pass | 2 | 8493 | 9.2 | agent answer |
| popup-tab | fixture | pass | 3 | 13113 | 13.6 | final url http://127.0.0.1:60280/popup-child.html |
| real-login | live | pass | 4 | 18248 | 21.6 | final url https://the-internet.herokuapp.com/secure |
| real-extract | live | pass | 1 | 8946 | 6.6 | agent answer |

## Traces

- `form-fill`: `traces/run-20260817-213248.jsonl`
- `login-flow`: `traces/run-20260817-213300.jsonl`
- `dropdown-select`: `traces/run-20260817-213317.jsonl`
- `scroll-and-read`: `traces/run-20260817-213325.jsonl`
- `shadow-dom-click`: `traces/run-20260817-213427.jsonl`
- `iframe-input`: `traces/run-20260817-213435.jsonl`
- `spa-navigation`: `traces/run-20260817-213450.jsonl`
- `popup-tab`: `traces/run-20260817-213500.jsonl`
- `real-login`: `traces/run-20260817-213513.jsonl`
- `real-extract`: `traces/run-20260817-213535.jsonl`
