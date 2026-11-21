# Check report: example_replies

**Result: PASSED with warnings** (0 failed, 1 warnings)
- **PASS** the frozen thesis reference data are unchanged (reference.sha256)

## New model replies

- **PASS** file has the columns `item` and `output` (and optionally `model`)
- **PASS** all item ids exist in the thesis dataset
- **PASS** one reply per model and item (0 duplicates)
- **WARN** `hand-written example`: replies to 4 of 160 prompts
- **PASS** `hand-written example`: 0 empty replies

| Model | Replies | Format rule met | Chart facts stated | Mean words | Wrong text type* | BLEU | chrF | ROUGE-L |
|---|---|---|---|---|---|---|---|---|
| hand-written example | 4 | 3 (75%) | 1 of 1 | 14.0 | 1 | 10.1 | 29.0 | 31.4 |
| G1 Qwen3-VL-2B (thesis) | 160 | 120 (75%) | 13 of 16 | 34.0 | 14 | 10.1 | 35.2 | 31.9 |
| G2 SmolVLM2-2.2B (thesis) | 160 | 60 (38%) | 8 of 16 | 67.7 | 62 | 5.4 | 30.6 | 23.6 |

*Replies with a subject line, a placeholder such as [Your Name], a meta-comment ("Here's…"), a numbered list or bullets.
Metrics compare each reply with the item's reference. In the thesis they agreed with the judge mainly through length, so read them with care.
- **PASS** the folder contains items, replies or judge files
