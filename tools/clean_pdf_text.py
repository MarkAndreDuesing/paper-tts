#!/usr/bin/env python3
"""First-pass clean-up of PDF text for a TTS listening script.

Input: text extracted page by page with markers, e.g.
    for p in $(seq 1 N); do echo "@@PAGE $p"; pdftotext -f $p -l $p paper.pdf -; done > raw.txt
Output: one paragraph per line, "@@PAGE n" markers kept, with running headers,
author-year citations, line-break hyphenation and common abbreviations handled.

The output still needs a manual pass: remove table/figure debris, replace each
table/figure with a spoken description plus page number, add track headers and
signposts (see docs/workflow.md and tools/examples/).

Usage: clean_pdf_text.py raw.txt clean.txt [--header-regex REGEX ...]
"""
import argparse, re

ap = argparse.ArgumentParser()
ap.add_argument("raw"); ap.add_argument("out")
ap.add_argument("--header-regex", action="append", default=[],
                help="regex for running header/footer lines to drop (repeatable)")
a = ap.parse_args()
heads = [re.compile(h) for h in a.header_regex] + [re.compile(r"^\d{1,3}$")]

out = []
for pg in open(a.raw, encoding="utf-8").read().split("@@PAGE ")[1:]:
    num, txt = pg.split("\n", 1)
    paras, cur = [], []
    for ln in txt.split("\n"):
        s = ln.strip()
        if any(h.match(s) for h in heads):
            continue
        if not s:
            if cur: paras.append(" ".join(cur)); cur = []
            continue
        cur.append(s)
        if len(s) < 60 and s.endswith((".", ":", "?")):
            paras.append(" ".join(cur)); cur = []
    if cur: paras.append(" ".join(cur))
    out.append(f"@@PAGE {num}")
    for p in paras:
        p = re.sub(r"(\w)- (\w)", lambda m: m.group(1) + m.group(2) if m.group(2).islower() else m.group(0), p)
        p = re.sub(r"\s*\((?:e\.g\.,\s*)?(?:see\s+)?(?:[A-Z][^()]*?\d{4}[a-z]?(?:;\s*|,\s*)?)+\)", "", p)
        p = re.sub(r"([A-Z][A-Za-z\-]+) et al\. \(\d{4}[a-z]?\)", r"\1 and colleagues", p)
        p = re.sub(r"([A-Z][A-Za-z\-]+) \(\d{4}[a-z]?\)", r"\1", p)
        for x, y in [("e.g.,", "for example,"), ("i.e.,", "that is,"), ("e.g.", "for example"), ("i.e.", "that is"), ("etc.", "and so on")]:
            p = p.replace(x, y)
        p = re.sub(r"(\d+(?:\.\d+)?)\s?%", r"\1 per cent", p)
        out.append(p)
open(a.out, "w", encoding="utf-8").write("\n".join(out) + "\n")
