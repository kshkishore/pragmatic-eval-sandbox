# Check report: example_items

**Result: PASSED** (0 failed, 0 warnings)
- **PASS** the frozen thesis reference data are unchanged (reference.sha256)

## New test items

2 items submitted.
- **PASS** `IDI-101`: valid; design rules 1 and 2 met
- **PASS** `REG-101`: valid; design rules 1 and 2 met

Similarity of each response to the reference (B should be much closer than A):

| Item | Cat. | BLEU A | BLEU B | BLEU C | chrF A | chrF B | chrF C | Words A | Words B | Words C |
|---|---|---|---|---|---|---|---|---|---|---|
| IDI-101 | IDI | 2.8 | 23.8 | 1.9 | 24.3 | 45.6 | 13.7 | 18 | 26 | 11 |
| REG-101 | REG | 27.6 | 93.0 | 0.1 | 50.7 | 96.8 | 7.2 | 37 | 34 | 4 |

Means compared with the 160 thesis items:

|  | A | B | C | Thesis A | Thesis B | Thesis C |
|---|---|---|---|---|---|---|
| BLEU | 15.2 | 58.4 | 1.0 | 6.2 | 54.9 | 3.0 |
| chrF | 37.5 | 71.2 | 10.4 | 30.2 | 71.6 | 18.4 |
| Words | 27.5 | 30.0 | 7.5 | 24.2 | 26.1 | 14.9 |

- **PASS** the folder contains items, replies or judge files
