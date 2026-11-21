"""Check new data against the thesis's rules and results, without touching the thesis data.

Usage:
    python checker/check.py submissions/<folder>         # check one submission folder
    python checker/check.py --all                         # check every folder in submissions/

A submission folder may contain any of these files (see templates/ and README.md):
    items.json  or items.csv       new test items       -> design checks, metrics, overlap with the thesis items
    replies.jsonl or replies.csv   new model replies    -> format rule, chart facts, text-type features, metrics,
                                                           comparison with the thesis generators G1 and G2
    judge.jsonl  or judge.csv      new judge scores     -> pairwise accuracy (A-B, A-C), by category, agreement with
                                                           J1 and J2, McNemar tests, comparison with the thesis judges
The report is written to <folder>/REPORT.md and <folder>/report.json. The exit code is 1 if any check fails.
"""
import sys, os, json, csv, re, hashlib, argparse, warnings
warnings.filterwarnings("ignore", message="This pattern is interpreted as a regular expression")
import numpy as np, pandas as pd
from scipy.stats import binomtest, spearmanr
import krippendorff, sacrebleu
from rouge_score import rouge_scorer
from sklearn.metrics import cohen_kappa_score
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules import fmt_ok, facts_ok, strip_markdown, FEAT, FACTS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "reference")
DIMS = list("COSTAR")
CATS = ["IDI", "ISA", "IMP", "IRO", "REF", "REG", "FTA", "EMP", "CUL", "MM"]
FIELDS = ["context", "objective", "style", "tone", "audience", "response_format"]
SEED = 20261109
_rs = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
r3 = lambda x: None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 3)


# ------------------------------------------------------------------ reference data (read-only)
def verify_reference():
    """Confirm that the frozen copy of the thesis data is unchanged (reference.sha256)."""
    bad = []
    for line in open(os.path.join(ROOT, "reference.sha256")):
        h, f = line.split(maxsplit=1); f = f.strip()
        p = os.path.join(REF, f)
        if not os.path.exists(p) or hashlib.sha256(open(p, "rb").read()).hexdigest() != h: bad.append(f)
    return bad

DATA = json.load(open(os.path.join(REF, "golden_dataset_v2.json"))); BYID = {it["id"]: it for it in DATA}
SUMMARY = json.load(open(os.path.join(REF, "summary_v2.json")))
def jl(p): return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


# ------------------------------------------------------------------ helpers
class Report:
    def __init__(self, title):
        self.title, self.lines, self.json, self.fails, self.warns = title, [], {}, 0, 0
    def h(self, t): self.lines += ["", "## " + t, ""]
    def p(self, t=""): self.lines.append(t)
    def check(self, ok, text, level="fail"):
        mark = "PASS" if ok else ("FAIL" if level == "fail" else "WARN")
        if not ok: self.fails += level == "fail"; self.warns += level != "fail"
        self.lines.append(f"- **{mark}** {text}"); return ok
    def table(self, header, rows):
        self.lines.append("| " + " | ".join(header) + " |"); self.lines.append("|" + "---|" * len(header))
        for r in rows: self.lines.append("| " + " | ".join("–" if v is None else str(v) for v in r) + " |")
        self.lines.append("")
    def text(self):
        status = "FAILED" if self.fails else ("PASSED with warnings" if self.warns else "PASSED")
        return "\n".join([f"# {self.title}", "", f"**Result: {status}** ({self.fails} failed, {self.warns} warnings)"] + self.lines) + "\n"

def read_table(folder, stem):
    """Read <stem>.jsonl, <stem>.json or <stem>.csv from a folder; return a list of dicts or None."""
    for ext in (".jsonl", ".json", ".csv"):
        p = os.path.join(folder, stem + ext)
        if not os.path.exists(p): continue
        if ext == ".jsonl": return jl(p), p
        if ext == ".json":
            d = json.load(open(p, encoding="utf-8")); return (d if isinstance(d, list) else d.get("items", [])), p
        return list(csv.DictReader(open(p, encoding="utf-8-sig"))), p
    return None, None

def overlap(c, r):
    return dict(bleu=sacrebleu.sentence_bleu(c, [r]).score, chrf=sacrebleu.sentence_chrf(c, [r]).score, rougeL=_rs.score(r, c)["rougeL"].fmeasure * 100)

def contrasts(scores, kinds=("B", "C"), items=None):
    """scores: {(item, cand): value}. Same credit rule as the thesis: 1 if A higher, 0.5 if tied, 0 otherwise."""
    rows = []
    for it in (items or sorted({i for i, _ in scores})):
        a = scores.get((it, "A"))
        if a is None or (isinstance(a, float) and np.isnan(a)): continue
        for k in kinds:
            x = scores.get((it, k))
            if x is None or (isinstance(x, float) and np.isnan(x)): continue
            rows.append(dict(item=it, kind=k, cat=BYID[it]["category"] if it in BYID else it.split("-")[0],
                             credit=1.0 if a > x else (0.5 if a == x else 0.0), strict=int(a > x), tie=int(a == x)))
    return pd.DataFrame(rows)

def boot(d, B=10000):
    rng = np.random.default_rng(SEED)
    items = d.item.unique(); g = {i: d[d.item == i].credit.values for i in items}
    v = [np.concatenate([g[i] for i in rng.choice(items, len(items))]).mean() for _ in range(B)]
    return [round(float(x), 3) for x in np.percentile(v, [2.5, 97.5])]

def accuracy(scores, items=None, ci=True):
    out = {}
    for lab, kinds in [("all", ("B", "C")), ("AB", ("B",)), ("AC", ("C",))]:
        d = contrasts(scores, kinds, items)
        if d.empty: continue
        out[lab] = dict(n=len(d), acc=r3(d.credit.mean()), ties=r3(d.tie.mean()), ci=boot(d) if ci else None)
    return out

def fmt_acc(a, lab):
    if lab not in a: return None
    x = a[lab]; return f"{x['acc']:.2f}" + (f" [{x['ci'][0]:.2f}, {x['ci'][1]:.2f}]" if x.get("ci") else "")

def mcnemar(s1, s2, items):
    m = contrasts(s1, items=items).merge(contrasts(s2, items=items), on=["item", "kind"], suffixes=("_1", "_2"))
    b = int(((m.strict_1 == 1) & (m.strict_2 == 0)).sum()); c = int(((m.strict_1 == 0) & (m.strict_2 == 1)).sum())
    return dict(n=len(m), only_new=b, only_thesis=c, p=r3(binomtest(b, b + c, 0.5).pvalue) if b + c else 1.0)


# ------------------------------------------------------------------ thesis judges, as {(item, cand): score}
VT = pd.read_csv(os.path.join(REF, "variant_table_v2.csv"))
def vt_scores(col): return {(r.item, r.cand): getattr(r, col) for r in VT.itertuples() if not pd.isna(getattr(r, col))}
THESIS_JUDGES = {"J1 CO-STAR rubric": "J1_costar", "J1 holistic + specification": "J1_spec_holistic", "J1 plain": "J1_plain",
                 "J2 CO-STAR rubric": "J2_costar", "J2 holistic + specification": "J2_spec_holistic", "J2 plain": "J2_plain"}


# ================================================================== 1. new items
def check_items(rep, rows, folder):
    rep.h("New test items")
    REQ = {"id", "category", "prompt", "reference"}
    items = []
    for r in rows:   # accept the thesis JSON format or the flat CSV format of data_exports/items.csv
        if "costar" not in r: r = dict(r, costar={k: r.get(k, "") for k in FIELDS})
        if "candidates" not in r: r = dict(r, candidates={k: r.get(k, "") for k in "ABC"})
        items.append(r)
    rep.p(f"{len(items)} items submitted.")
    ids, prompts, res = set(), set(), []
    thesis_prompts = {it["prompt"]: it["id"] for it in DATA}
    for it in items:
        iid = str(it.get("id", "?")); errs, warns = [], []
        miss = REQ - {k for k in it if it[k]}
        if miss: errs.append("missing " + ", ".join(sorted(miss)))
        if iid in ids: errs.append("duplicate id")
        if iid in BYID: errs.append("id already used in the thesis dataset")
        if it.get("category") not in CATS: errs.append(f"unknown category {it.get('category')!r} (use one of {', '.join(CATS)})")
        p = it.get("prompt", "")
        if p in prompts: errs.append("duplicate prompt")
        if p in thesis_prompts: errs.append(f"prompt identical to thesis item {thesis_prompts[p]}")
        ids.add(iid); prompts.add(p)
        cs = it.get("costar", {})
        empty = [k for k in FIELDS if not str(cs.get(k, "")).strip()]
        if empty: errs.append("empty specification field(s): " + ", ".join(empty))
        cand = it.get("candidates", {})
        if set(k for k in "ABC" if str(cand.get(k, "")).strip()) != {"A", "B", "C"}: errs.append("needs non-empty A, B and C responses")
        if it.get("category") == "MM":
            img = it.get("image")
            if not it.get("answer_key"): errs.append("chart item needs an answer_key")
            if not img or not os.path.exists(os.path.join(folder, "images", img)): errs.append("chart image not found in images/")
        for s in [p, it.get("reference", ""), *map(str, cand.values()), *map(str, cs.values())]:
            if s != s.strip() or "  " in s: warns.append("extra spaces"); break
        for s in [p, it.get("reference", ""), *map(str, cand.values()), *map(str, cs.values())]:
            if any(ch in s for ch in " ‘’“”–—"): warns.append("typographic quotes or dashes (the thesis uses plain ASCII)"); break
        rec = dict(id=iid, category=it.get("category"))
        if not errs or all(not e.startswith("needs") and not e.startswith("missing") for e in errs):
            A, B, C, R = str(cand.get("A", "")), str(cand.get("B", "")), str(cand.get("C", "")), str(it.get("reference", ""))
            if A and B and C and R:
                m = {k: overlap(v, R) for k, v in (("A", A), ("B", B), ("C", C))}
                ca, cb = m["A"]["chrf"], m["B"]["chrf"]
                if not cb > ca + 10: errs.append(f"design rule 1: B's chrF to the reference ({cb:.1f}) must exceed A's ({ca:.1f}) by more than 10")
                if not ca < 60: errs.append(f"design rule 2: A is too close to the reference (chrF {ca:.1f}, must be below 60)")
                la, lb, lc = len(A.split()), len(B.split()), len(C.split())
                if abs(la - lb) > max(6, 0.4 * max(la, lb)): warns.append(f"design rule 4: A and B differ in length ({la} vs {lb} words)")
                fa = fmt_ok(A, cs.get("response_format", ""))
                if not fa: warns.append("A does not meet its own response format according to the format rule")
                best = max(DATA, key=lambda t: sacrebleu.sentence_chrf(p, [t["prompt"]]).score)
                sim = sacrebleu.sentence_chrf(p, [best["prompt"]]).score
                if sim > 60: warns.append(f"prompt is very similar to thesis item {best['id']} (chrF {sim:.0f})")
                rec.update(words_A=la, words_B=lb, words_C=lc, A_fmt_ok=fa,
                           **{f"{k}_{x}": round(m[k][x], 1) for k in "ABC" for x in ("bleu", "chrf", "rougeL")})
        rec["errors"], rec["warnings"] = errs, warns; res.append(rec)
    rows_out = []
    for r in res:
        rep.check(not r["errors"], f"`{r['id']}`: " + ("; ".join(r["errors"]) if r["errors"] else "valid; design rules 1 and 2 met"))
        for w in r["warnings"]: rep.check(False, f"`{r['id']}`: {w}", "warn")
        if "A_bleu" in r: rows_out.append([r["id"], r["category"], r["A_bleu"], r["B_bleu"], r["C_bleu"], r["A_chrf"], r["B_chrf"], r["C_chrf"], r["words_A"], r["words_B"], r["words_C"]])
    if rows_out:
        rep.p(""); rep.p("Similarity of each response to the reference (B should be much closer than A):"); rep.p("")
        rep.table(["Item", "Cat.", "BLEU A", "BLEU B", "BLEU C", "chrF A", "chrF B", "chrF C", "Words A", "Words B", "Words C"], rows_out)
        dc = SUMMARY.get("design_check", {})
        df = pd.DataFrame([r for r in res if "A_bleu" in r])
        rep.p("Means compared with the 160 thesis items:"); rep.p("")
        th = lambda v, k: round(dc[v][k], 1) if isinstance(dc.get(v), dict) and k in dc[v] else None
        rep.table(["", "A", "B", "C", "Thesis A", "Thesis B", "Thesis C"],
                  [["BLEU", *[round(df[f"{v}_bleu"].mean(), 1) for v in "ABC"], th("A", "bleu"), th("B", "bleu"), th("C", "bleu")],
                   ["chrF", *[round(df[f"{v}_chrf"].mean(), 1) for v in "ABC"], th("A", "chrf"), th("B", "chrf"), th("C", "chrf")],
                   ["Words", *[round(df[f"words_{v}"].mean(), 1) for v in "ABC"], th("A", "n_words"), th("B", "n_words"), th("C", "n_words")]])
    rep.json["items"] = res


# ================================================================== 2. new model replies
def check_replies(rep, rows):
    rep.h("New model replies")
    df = pd.DataFrame(rows)
    if "model" not in df: df["model"] = df.get("generator", "submitted model")
    need = {"item", "output"}
    if not rep.check(need <= set(df.columns), "file has the columns `item` and `output` (and optionally `model`)"): return
    df["output"] = df["output"].fillna("").astype(str)
    unknown = sorted(set(df.item) - set(BYID))
    rep.check(not unknown, "all item ids exist in the thesis dataset" + (f" (unknown: {', '.join(unknown[:10])})" if unknown else ""))
    df = df[df.item.isin(BYID)]
    dup = df.duplicated(["model", "item"]).sum()
    rep.check(dup == 0, f"one reply per model and item ({dup} duplicates)")
    out = {}
    for model, d in df.groupby("model"):
        d = d.drop_duplicates("item").copy()
        cover = len(d); rep.check(cover == len(DATA), f"`{model}`: replies to {cover} of {len(DATA)} prompts", "warn")
        empty = int((d.output.str.strip() == "").sum()); rep.check(empty == 0, f"`{model}`: {empty} empty replies", "warn")
        d["category"] = d.item.map(lambda i: BYID[i]["category"])
        d["n_words"] = d.output.map(lambda o: len(o.split()))
        d["fmt_ok"] = [fmt_ok(o, BYID[i]["costar"]["response_format"]) for i, o in zip(d.item, d.output)]
        d["facts_ok"] = [facts_ok(i, o) if i in FACTS else None for i, o in zip(d.item, d.output)]
        for k, pat in FEAT.items(): d[k] = d.output.str.contains(pat, regex=True)
        d["any_feature"] = d.output.apply(lambda o: any(re.search(p, o) for p in FEAT.values()))
        m = pd.DataFrame([overlap(strip_markdown(o) if o.strip() else "(empty)", BYID[i]["reference"]) for i, o in zip(d.item, d.output)], index=d.index)
        d = pd.concat([d, m], axis=1)
        mm = d[d.category == "MM"]
        out[model] = dict(n=cover, fmt_ok=int(d.fmt_ok.sum()), facts_ok=int(mm.facts_ok.sum()) if len(mm) else None, n_mm=len(mm),
                          words=r3(d.n_words.mean()), **{k: int(d[k].sum()) for k in list(FEAT) + ["any_feature"]},
                          bleu=r3(d.bleu.mean()), chrf=r3(d.chrf.mean()), rougeL=r3(d.rougeL.mean()),
                          by_cat={c: dict(n=len(g), fmt_ok=int(g.fmt_ok.sum()), words=r3(g.n_words.mean())) for c, g in d.groupby("category")},
                          per_reply=d.drop(columns=["output"]).to_dict("records"))
    # thesis generators, computed with the same code from the frozen logs
    th = {}
    for g, lab in [("qwen3vl-2b", "G1 Qwen3-VL-2B (thesis)"), ("smolvlm2-2.2b", "G2 SmolVLM2-2.2B (thesis)")]:
        rs = jl(os.path.join(REF, f"gen_{g}.jsonl"))
        t = pd.DataFrame(rs); t["model"] = lab
        th[lab] = t
    rows_t = []
    for lab, t in th.items():
        fo = [fmt_ok(o, BYID[i]["costar"]["response_format"]) for i, o in zip(t.item, t.output)]
        fa = [facts_ok(i, o) for i, o in zip(t.item, t.output) if i in FACTS]
        feats = sum(t.output.apply(lambda o: any(re.search(p, o) for p in FEAT.values())))
        mg = pd.read_csv(os.path.join(REF, "gen_table_v2.csv")); mg = mg[mg.generator == t.generator.iloc[0]]
        rows_t.append([lab, len(t), f"{sum(fo)} ({sum(fo) / len(t):.0%})", f"{sum(fa)} of {len(fa)}", round(t.output.map(lambda o: len(o.split())).mean(), 1), feats,
                       round(mg.bleu.mean(), 1), round(mg.chrf.mean(), 1), round(mg.rougeL.mean(), 1)])
    rows_n = [[m, o["n"], f"{o['fmt_ok']} ({o['fmt_ok'] / o['n']:.0%})", f"{o['facts_ok']} of {o['n_mm']}" if o["n_mm"] else "–", o["words"], o["any_feature"],
               round(o["bleu"], 1), round(o["chrf"], 1), round(o["rougeL"], 1)] for m, o in out.items()]
    rep.p(""); rep.table(["Model", "Replies", "Format rule met", "Chart facts stated", "Mean words", "Wrong text type*", "BLEU", "chrF", "ROUGE-L"], rows_n + rows_t)
    rep.p("*Replies with a subject line, a placeholder such as [Your Name], a meta-comment (\"Here's…\"), a numbered list or bullets.")
    rep.p("Metrics compare each reply with the item's reference. In the thesis they agreed with the judge mainly through length, so read them with care.")
    rep.json["replies"] = {m: {k: v for k, v in o.items() if k != "per_reply"} for m, o in out.items()}
    rep.json["replies_per_reply"] = {m: o["per_reply"] for m, o in out.items()}


# ================================================================== 3. new judge scores
def check_judge(rep, rows):
    rep.h("New judge scores")
    df = pd.DataFrame(rows)
    if "judge" not in df: df["judge"] = "submitted judge"
    if not rep.check({"item", "cand"} <= set(df.columns), "file has the columns `item` and `cand` (A, B or C)"): return
    rubric = set(DIMS) <= set(df.columns)
    if not rep.check(rubric or "score" in df.columns, "file has either a `score` column or the six rubric columns C, O, S, T, A, R"): return
    unknown = sorted(set(df.item) - set(BYID)); rep.check(not unknown, "all item ids exist in the thesis dataset" + (f" (unknown: {', '.join(unknown[:10])})" if unknown else ""))
    df = df[df.item.isin(BYID) & df.cand.isin(list("ABC"))].copy()
    res = {}
    for judge, d in df.groupby("judge"):
        d = d.drop_duplicates(["item", "cand"]).copy()
        if rubric:
            for k in DIMS: d[k] = pd.to_numeric(d[k], errors="coerce")
            bad = int((~d[DIMS].isin([1, 2, 3, 4, 5])).any(axis=1).sum())
            rep.check(bad == 0, f"`{judge}`: rubric scores are integers from 1 to 5 ({bad} rows outside)")
            d["value"] = sum((d[k] - 1) / 4 for k in DIMS) / 6
        else:
            d["value"] = pd.to_numeric(d["score"], errors="coerce")
            rep.check(d.value.notna().all(), f"`{judge}`: all scores are numbers")
        rep.check(len(d) == 480, f"`{judge}`: {len(d)} of 480 variants scored", "warn")
        S = {(r.item, r.cand): r.value for r in d.itertuples() if not pd.isna(r.value)}
        items = sorted({i for i, _ in S})
        a = accuracy(S, items)
        rec = dict(n_variants=len(d), accuracy=a)
        rep.p(f"### `{judge}`"); rep.p("")
        rows_t = [[f"**{judge}** (submitted)", fmt_acc(a, "AB"), fmt_acc(a, "AC"), fmt_acc(a, "all"), f"{a['all']['ties']:.0%}" if "all" in a else None]]
        for lab, col in THESIS_JUDGES.items():
            t = accuracy(vt_scores(col), items, ci=False)
            if "all" in t: rows_t.append([lab + " (thesis, same items)", fmt_acc(t, "AB"), fmt_acc(t, "AC"), fmt_acc(t, "all"), f"{t['all']['ties']:.0%}"])
        rep.p("Pairwise accuracy: the share of contrasts in which A scores higher than the failed response (ties count ½; chance = 0.5)."); rep.p("")
        rep.table(["Judge", "A–B", "A–C", "All [95% CI]", "Ties"], rows_t)
        if rubric:
            rows_d = []
            for k in DIMS:
                ak = accuracy({(r.item, r.cand): r[k] for _, r in d.iterrows() if not pd.isna(r[k])}, items, ci=False)
                rows_d.append([k, fmt_acc(ak, "AB"), fmt_acc(ak, "AC"), fmt_acc(ak, "all")])
            rep.p("Each rubric dimension used alone:"); rep.p(""); rep.table(["Dimension", "A–B", "A–C", "All"], rows_d)
        cats = contrasts(S, items=items).groupby("cat").credit.mean()
        rep.p("By category:"); rep.p(""); rep.table(["", *cats.index], [["Accuracy", *[f"{v:.2f}" for v in cats.values]]])
        rec["by_cat"] = {k: r3(v) for k, v in cats.items()}
        ag, mc = [], []
        for lab, col in [("J1 CO-STAR rubric", "J1_costar"), ("J2 CO-STAR rubric", "J2_costar")]:
            ref = vt_scores(col); keys = [k for k in S if k in ref]
            if len(keys) < 10: continue
            x, y = np.array([S[k] for k in keys]), np.array([ref[k] for k in keys])
            alpha = krippendorff.alpha(reliability_data=np.vstack([x, y]).astype(float), level_of_measurement="interval") if rubric else None
            ag.append([lab, len(keys), r3(alpha) if rubric else "–", r3(spearmanr(x, y)[0])])
        if rubric:
            rows_q = []
            for lab, pre in [("J1", "J1_costar"), ("J2", "J2_costar")]:
                vals = []
                for k in DIMS:
                    ref = vt_scores(f"{pre}_{k}"); keys = [kk for kk in ref if kk in set(zip(d.item, d.cand))]
                    if len(keys) < 10: vals.append(None); continue
                    sub = d.set_index(["item", "cand"])[k]
                    vals.append(r3(cohen_kappa_score([int(sub[kk]) for kk in keys], [int(ref[kk]) for kk in keys], weights="quadratic")))
                if any(v is not None for v in vals): rows_q.append([lab, *vals])
        rep.p("Agreement with the thesis judges on the same variants (interval α is shown only for rubric scores on the same 0–1 scale):"); rep.p("")
        rep.table(["Thesis judge", "Variants", "Krippendorff's α", "Spearman ρ"], ag)
        if rubric and rows_q:
            rep.p("Quadratically weighted κ with each thesis judge, per dimension:"); rep.p(""); rep.table(["", *DIMS], rows_q)
        for lab, col in [("J1 CO-STAR rubric", "J1_costar"), ("J1 holistic + specification", "J1_spec_holistic")]:
            m = mcnemar(S, vt_scores(col), items); mc.append([lab, m["n"], m["only_new"], m["only_thesis"], m["p"]])
        rep.p("Paired comparison with the thesis's main judge (exact McNemar test; ties count as errors):"); rep.p("")
        rep.table(["Compared with", "Contrasts", "Only submitted judge correct", "Only thesis judge correct", "p"], mc)
        rec.update(agreement=ag, mcnemar=mc); res[judge] = rec
    rep.json["judges"] = res


# ================================================================== main
def check_folder(folder):
    name = os.path.basename(os.path.normpath(folder))
    rep = Report(f"Check report: {name}")
    bad = verify_reference()
    rep.check(not bad, "the frozen thesis reference data are unchanged (reference.sha256)" + (f"; modified: {bad}" if bad else ""))
    found = False
    items, p = read_table(folder, "items")
    if items is not None: found = True; check_items(rep, items, folder)
    replies, p = read_table(folder, "replies")
    if replies is not None: found = True; check_replies(rep, replies)
    judge, p = read_table(folder, "judge")
    if judge is not None: found = True; check_judge(rep, judge)
    rep.check(found, "the folder contains items, replies or judge files")
    open(os.path.join(folder, "REPORT.md"), "w").write(rep.text())
    json.dump(rep.json, open(os.path.join(folder, "report.json"), "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    return rep

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("folders", nargs="*"); ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    folders = a.folders or []
    if a.all: folders = sorted(os.path.join(ROOT, "submissions", f) for f in os.listdir(os.path.join(ROOT, "submissions")) if os.path.isdir(os.path.join(ROOT, "submissions", f)))
    if not folders: ap.error("give a submission folder or --all")
    failed = 0
    for f in folders:
        r = check_folder(f); failed += r.fails > 0
        print(f"{f}: {'FAILED' if r.fails else 'passed'} ({r.fails} failed, {r.warns} warnings) -> {os.path.join(f, 'REPORT.md')}")
    sys.exit(1 if failed else 0)
