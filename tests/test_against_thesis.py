"""Self-test: feed the thesis's own data through the checker and confirm that it reproduces the
published thesis numbers. Run with:  python tests/test_against_thesis.py
Uses a temporary folder; nothing in reference/ or submissions/ is changed."""
import os, sys, json, csv, tempfile, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "checker"))
import check

REF = os.path.join(ROOT, "reference")
S = check.SUMMARY
jl = check.jl
ok = True
def expect(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(("ok   " if good else "FAIL ") + f"{label}: got {got}, thesis {want}")

tmp = tempfile.mkdtemp()
try:
    # 1. judge scores: the thesis's J1 and J2 rubric logs, resubmitted as a new judge
    for jf, key, expect_key in [("contrast_j1.jsonl", "J1", ("exp2", "J1_costar")), ("contrast_j2.jsonl", "J2", ("exp4", "J2_costar"))]:
        d = os.path.join(tmp, "judge_" + key); os.makedirs(d)
        with open(os.path.join(d, "judge.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["judge", "item", "cand", *"COSTAR"])
            for r in jl(os.path.join(REF, jf)):
                if r["condition"] == "costar": w.writerow([key, r["item"], r["cand"], *[r["scores"][k] for k in "COSTAR"]])
        rep = check.check_folder(d); res = rep.json["judges"][key]["accuracy"]
        th = S[expect_key[0]][expect_key[1]]["acc"]
        for lab in ("all", "AB", "AC"):
            expect(f"{key} rubric accuracy {lab}", res[lab]["acc"], th[lab]["acc"])
        # bootstrap intervals are random draws; the thesis drew all its intervals from one shared random stream,
        # so the bounds are compared to within 0.01 rather than exactly
        close = all(abs(a - b) <= 0.01 for a, b in zip(res["all"]["ci"], th["all"]["ci"]))
        expect(f"{key} rubric 95% CI (all) within 0.01", close, True)
        expect(f"{key} rubric ties (all)", res["all"]["ties"], th["all"]["ties"])

    # 2. model replies: the thesis's two generators, resubmitted
    d = os.path.join(tmp, "replies"); os.makedirs(d)
    with open(os.path.join(d, "replies.jsonl"), "w") as f:
        for g in ("qwen3vl-2b", "smolvlm2-2.2b"):
            for r in jl(os.path.join(REF, f"gen_{g}.jsonl")): f.write(json.dumps(dict(model=g, item=r["item"], output=r["output"])) + "\n")
    rep = check.check_folder(d); R = rep.json["replies"]
    rate = S["exp5"]["fmt_rate"]
    for g in ("qwen3vl-2b", "smolvlm2-2.2b"):
        expect(f"{g} format rule rate", round(R[g]["fmt_ok"] / R[g]["n"], 3), rate[g])
        expect(f"{g} mean words", round(R[g]["words"], 3), round(S["exp5"]["means"][g]["n_words"], 3))
        expect(f"{g} replies with a wrong-text-type feature", R[g]["any_feature"], S["exp5"]["features"][g]["any"])
    expect("chart facts stated, G1 and G2", (R["qwen3vl-2b"]["facts_ok"], R["smolvlm2-2.2b"]["facts_ok"]), (13, 8))

    # 3. items: the thesis items, resubmitted under new ids, must pass design rules 1 and 2
    d = os.path.join(tmp, "items"); os.makedirs(os.path.join(d, "images"))
    items = []
    for it in check.DATA:
        if it["origin"] != "new": continue
        it = dict(it, id="X" + it["id"], prompt=it["prompt"] + " ")   # avoid the duplicate-prompt and duplicate-id checks
        if it.get("image"): shutil.copy(os.path.join(REF, "images", it["image"]), os.path.join(d, "images", it["image"]))
        items.append(it)
    json.dump(items, open(os.path.join(d, "items.json"), "w"))
    rep = check.check_folder(d)
    rule_fails = [r["id"] for r in rep.json["items"] if any(e.startswith("design rule") for e in r["errors"])]
    expect("thesis items failing design rule 1 or 2", rule_fails, [])
    vt = json.load(open(os.path.join(REF, "metrics_contrast.json")))
    th = {(r["item"], r["cand"]): r for r in vt}
    diffs = [r["id"] for r in rep.json["items"] for k in "ABC"
             if abs(r[f"{k}_bleu"] - round(th[(r["id"][1:], k)]["bleu"], 1)) > 0.051 or abs(r[f"{k}_chrf"] - round(th[(r["id"][1:], k)]["chrf"], 1)) > 0.051]
    expect("items whose BLEU/chrF differ from the thesis metric files", diffs, [])
finally:
    shutil.rmtree(tmp)
print("\nALL CHECKS REPRODUCE THE THESIS" if ok else "\nSOME CHECKS DIFFER FROM THE THESIS")
sys.exit(0 if ok else 1)
