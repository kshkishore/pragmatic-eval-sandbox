# Check report: example_judge

**Result: PASSED with warnings** (0 failed, 1 warnings)
- **PASS** the frozen thesis reference data are unchanged (reference.sha256)

## New judge scores

- **PASS** file has the columns `item` and `cand` (A, B or C)
- **PASS** file has either a `score` column or the six rubric columns C, O, S, T, A, R
- **PASS** all item ids exist in the thesis dataset
- **PASS** `example-judge (copy of thesis J2 holistic scores)`: all scores are numbers
- **WARN** `example-judge (copy of thesis J2 holistic scores)`: 18 of 480 variants scored
### `example-judge (copy of thesis J2 holistic scores)`

Pairwise accuracy: the share of contrasts in which A scores higher than the failed response (ties count ½; chance = 0.5).

| Judge | A–B | A–C | All [95% CI] | Ties |
|---|---|---|---|---|
| **example-judge (copy of thesis J2 holistic scores)** (submitted) | 0.83 [0.67, 1.00] | 1.00 [1.00, 1.00] | 0.92 [0.83, 1.00] | 17% |
| J1 CO-STAR rubric (thesis, same items) | 0.67 | 0.75 | 0.71 | 8% |
| J1 holistic + specification (thesis, same items) | 0.92 | 1.00 | 0.96 | 8% |
| J1 plain (thesis, same items) | 0.83 | 0.92 | 0.88 | 25% |
| J2 CO-STAR rubric (thesis, same items) | 0.83 | 1.00 | 0.92 | 17% |
| J2 holistic + specification (thesis, same items) | 0.83 | 1.00 | 0.92 | 17% |
| J2 plain (thesis, same items) | 0.92 | 1.00 | 0.96 | 8% |

By category:

|  | EMP | IDI | ISA | REF |
|---|---|---|---|---|
| Accuracy | 0.75 | 1.00 | 0.88 | 1.00 |

Agreement with the thesis judges on the same variants (interval α is shown only for rubric scores on the same 0–1 scale):

| Thesis judge | Variants | Krippendorff's α | Spearman ρ |
|---|---|---|---|
| J1 CO-STAR rubric | 18 | – | 0.546 |
| J2 CO-STAR rubric | 18 | – | 0.903 |

Paired comparison with the thesis's main judge (exact McNemar test; ties count as errors):

| Compared with | Contrasts | Only submitted judge correct | Only thesis judge correct | p |
|---|---|---|---|---|
| J1 CO-STAR rubric | 12 | 4 | 2 | 0.688 |
| J1 holistic + specification | 12 | 0 | 1 | 1.0 |

- **PASS** the folder contains items, replies or judge files
