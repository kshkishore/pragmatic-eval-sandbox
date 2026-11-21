"""Rules copied verbatim from the thesis repository (agentic-pragmatic-evaluation-thesis,
study/analyze_v2.py and study/metrics.py), so that new data are checked exactly as the thesis data were.
Do not edit these functions; if the thesis code changes, copy them again and re-run tests/test_against_thesis.py."""
import re

def strip_markdown(text):
    """Remove Markdown emphasis, heading and list markers so that metrics see plain prose."""
    t = re.sub(r"\*\*|__|`", "", text)
    t = re.sub(r"(?m)^\s*#+\s*", "", t)
    t = re.sub(r"(?m)^\s*(?:[-*\u2022]|\d+[.)])\s+", "", t)
    t = re.sub(r"\s*\n+\s*", " ", t)
    return t.strip()

def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]

def clean_lines(text):
    t = re.sub(r"\*\*|__|`", "", text); t = re.sub(r"(?m)^\s*#+\s*", "", t); t = re.sub(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+", "", t)
    return [l.strip() for l in t.split("\n") if l.strip()]
SAL = re.compile(r"^(dear|hi|hello|hey|good (morning|afternoon|evening))\b[^.!?]*,?$", re.I)
OFF = re.compile(r"^(?:(best|kind|warm|warmest)?\s*(regards|wishes|thanks|thank you|sincerely|cheers)|best|yours(?: (?:sincerely|truly|faithfully))?)\b[^.!?]*,?$", re.I)
ABBR = re.compile(r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|e\.g|i\.e)\.", re.I)
LEAD = re.compile(r"^(?:(?:dear|hi|hello|hey)\b[^.!?,]{0,40}[,!]|good (?:morning|afternoon|evening)\b[^.!?,]{0,40}[,!])\s*", re.I)
def n_sent(text):
    body = [l for l in clean_lines(text) if not SAL.match(l) and not OFF.match(l) and not re.match(r"^\[?[A-Z][a-z]+( [A-Z][a-z]+)?\]?$", l)]
    if not body: return 0
    t = ABBR.sub(lambda m: m.group(1), " ".join(body)); t = LEAD.sub("", ABBR.sub(lambda m: m.group(1), body[0])) + t[len(ABBR.sub(lambda m: m.group(1), body[0])):]
    return len(sentences(t)) if t.strip() else 0
def fmt_ok(text, spec):
    s = spec.lower(); n = n_sent(text); w = len(" ".join(clean_lines(text)).split())
    if "at most 60 words" in s: ok = w <= 60
    elif "followed by" in s: ok = 2 <= n <= 3
    elif "exactly two" in s or s.startswith("two sentences") or "of exactly two" in s: ok = n == 2
    elif "two or three" in s: ok = 2 <= n <= 3
    elif "three sentences or fewer" in s: ok = 1 <= n <= 3
    elif s.startswith("three sentences"): ok = n == 3
    elif "one or two" in s: ok = 1 <= n <= 2
    elif "short direct answer" in s: ok = n <= 2 and w <= 40
    elif s.startswith("the rewritten sentence") or s.startswith("the shortened sentence"): ok = 1 <= n <= 2
    elif "sentence" in s and s.split()[0] in ("one",): ok = n == 1
    else: ok = True
    if "salutation" in s: ok = ok and bool(clean_lines(text)) and bool(re.match(r"^(dear|hi|hello)\b", clean_lines(text)[0], re.I))
    return bool(ok)
FACTS = {"MM-01": [r"\bapril|\bapr\b", r"\b31\b|31,000|31 ?k"], "MM-02": [r"\brent\b", r"\b40\s?%|40 per ?cent"], "MM-03": [r"telugu", r"\b9\b|nine"],
         "MM-04": [r"saturday|\bsat\b", r"\b55\b"], "MM-05": [r"\b30\s?%", r"\b55\s?%", r"online"], "MM-06": [r"\b95\b", r"\b2 hours|\(2,|two hours|\b2\b"],
         "MM-07": [r"august|\baug\b", r"\b185\b"], "MM-08": [r"\b60\b", r"week 4|\bw4\b|fourth week"],
         "MM-09": [r"\bapril|\bapr\b", r"2,?150"], "MM-10": [r"class 9\b|class nine|\b9\b", r"\b60\b"], "MM-11": [r"cycl", r"\b12\s?(%|per ?cent)"],
         "MM-12": [r"plastic", r"cloth", r"\b150\b", r"\b380\b"], "MM-13": [r"temperat|hott|warm", r"ris|increas|go(es)? up|climb|higher|more"],
         "MM-14": [r"dinosaur", r"\b850\b"], "MM-15": [r"\b8\s?(am|a\.m\.|o'?clock)|8:00|\beight\b", r"\b210\b"], "MM-16": [r"\b92\b", r"\b65\b", r"\b27\b"]}
def facts_ok(item, text): return all(re.search(p, " ".join(clean_lines(text)).lower()) for p in FACTS[item])

FEAT = {"subject_line": r"(?im)^\s*\**subject:", "placeholder": r"(?i)\[[^\]]*(name|recipient|colleague|manager|friend)[^\]]*\]", "meta_framing": r"(?i)^\s*(sure[!,.]|here('s| is| are)|certainly)",
                "numbered_list": r"(?m)^\s*\d+\.\s", "bullets": r"(?m)^\s*[-*\u2022]\s"}
