# Pragmatic evaluation sandbox

This is a space for checking **new data** against the rules and results of the thesis *Agentic Evaluation of Pragmatic Competence in Multimodal Large Language Models* (Katikela Sreeharsha Kishore, University of Hyderabad, 2026) **without touching the thesis data**.

The thesis data live in their own repository, [`agentic-pragmatic-evaluation-thesis`](https://github.com/kshkishore/agentic-pragmatic-evaluation-thesis), and this repository never writes to them.
- **`reference/`:** a frozen, read-only copy of the thesis data needed for comparison, taken from commit `4e5d766` of the thesis repository.
- **`reference.sha256`:** checksums of every file in that copy. Every check first confirms that the copy is unchanged.
- **New data:** go only in `submissions/`.

## What can be checked

| Put this file in `submissions/<your-folder>/` | What the checker does |
|---|---|
| `items.json` or `items.csv`, new test items | Checks the items against the thesis's construction rules (see below), computes BLEU, chrF and ROUGE-L for A, B and C, and compares the means with the 160 thesis items |
| `replies.jsonl` or `replies.csv`, new chatbot replies to the 160 thesis prompts | Checks ids and coverage, then applies the thesis's format rule, chart-fact rule and wrong-text-type features, computes the metrics, and compares the results with the thesis generators G1 and G2 |
| `judge.jsonl` or `judge.csv`, scores from a new judge for the 480 thesis responses (A, B, C) | Computes pairwise accuracy on A–B, A–C and all contrasts (with bootstrap CI), accuracy by category and by dimension, agreement with the thesis judges J1 and J2 (α, ρ, weighted κ), and McNemar tests against J1. It compares the results with every thesis judge condition on the same items |

The construction rules for new items are:
- the item has a valid schema and a unique id that is not used in the thesis;
- its prompt is not a duplicate of a thesis prompt;
- all six specification fields are filled in;
- design rule 1: B's chrF to the reference exceeds A's by more than 10;
- design rule 2: A's chrF to the reference is below 60;
- design rule 4: A and B are of similar length;
- A meets its own format.

A folder can contain any combination of the three files. Templates are in [`templates/`](templates/), and working examples are in `submissions/example_items`, `example_replies` and `example_judge`.

### File formats

- **Items:** the same JSON format as the thesis dataset (see `templates/items_template.json`), or the flat CSV of the thesis's `data_exports/items.csv`. Chart items (category `MM`) need their image in `submissions/<your-folder>/images/`.
- **Replies:** columns `model`, `item`, `output`. `item` is a thesis item id such as `IDI-01`. A file may hold several models.
- **Judge scores:** columns `judge`, `item`, `cand` (A, B or C), and either:
  - the six rubric scores `C`, `O`, `S`, `T`, `A`, `R` (integers 1–5), which are combined exactly as in the thesis; or
  - a single `score` column on any numeric scale, where higher means better.

## How to check new data

**On GitHub (nothing to install):**
1. On the repository page, click **Add file → Upload files**.
2. Drag in your file. In the file name box, type a new folder name first, for example `submissions/my-new-items/items.json`.
3. Commit the change. The **Check submissions** workflow runs automatically.
4. Open the **Actions** tab and click the latest run. The full report appears on the run's summary page and can be downloaded as `reports`.

**On your computer:**
```bash
pip install -r requirements.txt
python checker/check.py submissions/my-new-items        # writes REPORT.md and report.json into that folder
python checker/check.py --all                           # checks every folder in submissions/
```

The checker exits with an error if any check fails. Warnings, such as incomplete coverage or an A/B length difference, do not count as failures.

## Why the results can be trusted

The checker uses the thesis's own rules, copied verbatim from the thesis code into `checker/rules.py`: the format rule, chart-fact rule, text-type features, Markdown stripping and the pairwise-accuracy definition.

`tests/test_against_thesis.py` feeds the thesis's own data through the checker and confirms that it reproduces the published numbers:
- J1 and J2 rubric accuracy on all, A–B and A–C contrasts, and their ties;
- the format-rule rates, mean lengths, text-type features and chart facts of both generators;
- design rules 1 and 2 on all 112 items written for the main study;
- BLEU and chrF for every item.

The only exception is the bootstrap intervals. They are random draws and match to within 0.01. The test runs first on every check.

## Limits

- **Measures not included:** the checker computes only the lightweight measures. BERTScore, BARTScore, the NLI scores and f_syntax need large neural models, as do the LLM judges themselves. To compute them for new data, use the scripts in the thesis repository on a local machine.
- **Prompts must be the thesis's:** replies and judge scores are compared with the thesis results only for the thesis's own items and prompts.

## Licence

The code is under the MIT licence. The copy of the thesis data in `reference/` is under CC BY 4.0, as in the thesis repository.
