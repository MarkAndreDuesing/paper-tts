#!/usr/bin/env python3
"""PDF -> sentences in reading order, with their positions on the pages.

Reads the PDF's own text layer with PyMuPDF (no OCR), then:
  - drops running headers/footers, page numbers, footnotes and other small
    print (smaller than the body text), front-matter boilerplate (CCS concepts,
    keywords, licence, contact details) and table/figure debris;
  - stops at References / Bibliography / Acknowledgements and resumes at a
    later Appendix heading;
  - orders text top to bottom; on two-column pages left column, then right,
    with full-width parts (title, wide figures) in between;
  - joins paragraphs that run across columns and pages, undoes hyphenation;
  - splits into sentences and makes a speech version of each (citations, URLs
    and footnote markers removed, abbreviations expanded).

Writes JSON: {"pages": [[w, h], ...], "sentences": [{"id", "text" (spoken),
"kind" (heading/body/caption), "page" (1-based), "boxes": [[page, x0, y0, x1, y1], ...]}]}
Box coordinates are PDF points from the top-left of the page.

Usage:
    pdf_sentences.py paper.pdf sentences.json [--review sentences.txt]
                     [--skip-captions] [--keep-authors] [--drop-regex REGEX ...] [--min-size-diff 1.3]
"""
import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pymupdf

# Blocks starting with these are front matter / boilerplate, not read.
DROP_BLOCKS = [
    r"CCS Concepts", r"Additional Key Words", r"Key ?words\b", r"Index Terms",
    r"ACM Reference Format", r"Authors?[’'] (Contact|address)", r"©", r"\(c\) ?\d{4}",
    r"Permission to make", r"This work is licen[sc]ed", r"Publication rights licen[sc]ed",
    r"arXiv:", r"https?://doi\.org/\S+$", r"DOI:", r"Received \d", r"Accepted \d",
    r"Corresponding author", r"ACM ISBN", r"ISBN", r"ARTICLE ?INFO", r"journal homepage", r"Article history",
    r"CRediT authorship", r"Contents lists available", r"E-?mail address", r"Editor:", r"Declaration of competing interest", r"Declaration of Generative AI",
]
STOP_HEADINGS = re.compile(r"^(\d+\.?\s*)?(references|bibliography|acknowledge?ments?|works cited)\b", re.I)
RESUME_HEADINGS = re.compile(r"^([A-Z]\.?\s+|\d+\.?\s*)?appendi(x|ces)\b|^[A-Z](\.\d+)*\.?\s+[A-Z]", re.I)
CAPTION = re.compile(r"^(Fig\.?|Figure|Table|Listing|Algorithm|Box)\s*\d+[.:]", re.I)

# words that do not end a sentence even when followed by a capital
ABBREV = {"e.g.", "i.e.", "al.", "fig.", "figs.", "sec.", "secs.", "eq.", "eqs.", "cf.", "vs.",
          "dr.", "prof.", "no.", "nos.", "vol.", "pp.", "p.", "ref.", "refs.", "approx.", "resp.",
          "ch.", "chap.", "tab.", "mr.", "mrs.", "ms.", "st.", "jr.", "sr.", "ca.", "def.", "thm.",
          "lem.", "prop.", "eds.", "ed.", "art.", "appx.", "incl.", "esp.", "viz.", "ibid."}

SPEECH_SUBS = [
    (r"^[•▪◦●‣]\s*", ""), (r"\S+@\S+\.\w+", ""),
    # broken quote/dash encoding in some ACM fonts
    (r"ł(?=\w)", '"'), (r"(?<=[\w.,?!])ž", '"'), (r"(?<=\d)ś(?=\d)", "–"), (r"\be\.\s?g\.", "for example"), (r"\bi\.\s?e\.", "that is"), (r"\betc\.", "and so on"),
    (r"\bet al\.('s)?", lambda m: "and colleagues" + ("'" if m.group(1) else "")),
    (r"\bcf\.", "compare"), (r"\bvs\.", "versus"), (r"\bviz\.", "namely"),
    (r"\bFigs?\.", "Figure"), (r"\bSecs?\.", "Section"), (r"\bEqs?\.", "Equation"),
    (r"\bTab\.", "Table"), (r"\bpp?\.\s?(?=\d)", "page "), (r"\bNo\.\s?(?=\d)", "number "),
    (r"\bapprox\.", "approximately"), (r"\bresp\.", "respectively"),
    (r"\bRQs\b", "research questions"), (r"\bRQ\s?(\d+)", r"research question \1"),
    (r"(\d+(?:\.\d+)?)\s?%", r"\1 per cent"), (r"(\d)\s?[–—-]\s?(\d)", r"\1 to \2"),
    (r"\s?&\s?", " and "), (r"≈\s?", "about "), (r"≤\s?", "at most "), (r"≥\s?", "at least "),
    (r"\s?<\s?", " below "), (r"\s?>\s?", " above "), (r"\s?=\s?", " equals "),
    (r"[’‘]", "'"), (r"[“”]", '"'), (r"\s+—\s+|—", ", "), (r"\s+–\s+", ", "),
    (r"(\d),(\d{3})\b", r"\1\2"),
]
# all-caps words that should be read as words, not letter by letter
CAPS_WORDS = {"I", "A", "OK", "NASA", "COVID", "UNESCO", "NATO", "AND", "OR", "NOT", "THE"}


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    return s.replace("­", "").replace("​", "")


def is_bold(span):
    return bool(span["flags"] & 16) or bool(
        re.search(r"bold|black|heavy|semibold|demi|[a-z]TB$|-B[a-zA-Z]*$|\.B$", span["font"], re.I))


def page_lines(page, pno):
    """Blocks of lines; a line is a list of word dicts with text, box, size, bold."""
    blocks = []
    raw = page.get_text("rawdict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP)
    for b in raw["blocks"]:
        if b["type"] != 0:
            continue
        lines = []
        for li, l in enumerate(b["lines"]):
            if abs(l["dir"][1]) > 0.1:      # rotated text (arXiv stamp, figure labels)
                continue
            sizes = Counter()
            for sp in l["spans"]:
                sizes[round(sp["size"], 1)] += len(sp["chars"])
            if not sizes:
                continue
            lsize = sizes.most_common(1)[0][0]
            base = next(sp["origin"][1] for sp in l["spans"] if round(sp["size"], 1) == lsize)
            words, cur = [], None
            for sp in l["spans"]:
                # raised small text (footnote markers, reference numbers) is not read;
                # lowered small text (subscripts as in "RO1") is kept
                small = sp["size"] < 0.8 * lsize
                if small and sp["origin"][1] < base - 0.5:
                    if cur:
                        words.append(cur); cur = None
                    continue
                for ch in sp["chars"]:
                    c = ch["c"]
                    if c.isspace():
                        if cur:
                            words.append(cur); cur = None
                        continue
                    x0, y0, x1, y1 = ch["bbox"]
                    if cur is None:
                        cur = {"text": "", "box": [x0, y0, x1, y1], "size": sp["size"],
                               "bold": is_bold(sp), "font": sp["font"]}
                    cur["text"] += c
                    bx = cur["box"]
                    bx[0], bx[1], bx[2], bx[3] = min(bx[0], x0), min(bx[1], y0), max(bx[2], x1), max(bx[3], y1)
            if cur:
                words.append(cur)
            for w in words:
                w["text"] = norm(w["text"])
                w["page"] = pno
                w["line"] = (pno, b["number"], li)
            words = [w for w in words if w["text"]]
            if words:
                bbox = [min(w["box"][0] for w in words), min(w["box"][1] for w in words),
                        max(w["box"][2] for w in words), max(w["box"][3] for w in words)]
                lines.append({"words": words, "bbox": bbox, "size": lsize,
                              "text": " ".join(w["text"] for w in words)})
        # split a block where the line style changes (a bold heading line above its paragraph)
        groups = []
        for l in lines:
            n = sum(len(w["text"]) for w in l["words"]) or 1
            l["style"] = (sum(len(w["text"]) for w in l["words"] if w["bold"]) / n > 0.6, l["size"])
            if groups:
                ps = groups[-1][-1]["style"]
                if ps[0] == l["style"][0] and abs(ps[1] - l["style"][1]) < 0.6:
                    groups[-1].append(l)
                    continue
            groups.append([l])
        for g in groups:
            blocks.append({"lines": g, "page": pno, "bbox": bbox_of(g)})
    return blocks


def bbox_of(lines):
    return [min(l["bbox"][0] for l in lines), min(l["bbox"][1] for l in lines),
            max(l["bbox"][2] for l in lines), max(l["bbox"][3] for l in lines)]


def block_stats(b):
    sizes, bold, n = Counter(), 0, 0
    for l in b["lines"]:
        for w in l["words"]:
            sizes[round(w["size"] * 2) / 2] += len(w["text"])
            bold += len(w["text"]) if w["bold"] else 0
            n += len(w["text"])
    b["size"] = sizes.most_common(1)[0][0]
    b["bold"] = bold / max(n, 1)
    b["text"] = " ".join(l["text"] for l in b["lines"])
    b["nwords"] = sum(len(l["words"]) for l in b["lines"])


def unspace(t):
    """Letter-spaced words ("A B S T R A C T") -> "ABSTRACT"."""
    return re.sub(r"\b(?:[A-Za-z] ){3,}[A-Za-z]\b", lambda m: m.group(0).replace(" ", ""), t)


def drop_key(t):
    return unspace(re.sub(r"^[^\w(©]+", "", t))


def digits_key(s):
    return re.sub(r"\d+", "#", s.strip().lower())


def order_blocks(blocks, width):
    """Reading order on one page: bands between full-width blocks; in each band
    the left column top to bottom, then the right column."""
    mid = width / 2
    def side(b):
        x0, _, x1, _ = b["bbox"]
        if x1 <= mid + 12:
            return "L"
        if x0 >= mid - 12:
            return "R"
        return "S"
    chars = Counter()
    for b in blocks:
        chars[side(b)] += len(b["text"])
    total = sum(chars.values()) or 1
    two_col = chars["L"] / total > 0.2 and chars["R"] / total > 0.2
    if not two_col:
        return sorted(blocks, key=lambda b: (round(b["bbox"][1]), b["bbox"][0]))
    spans = sorted([b for b in blocks if side(b) == "S"], key=lambda b: b["bbox"][1])
    cols = [b for b in blocks if side(b) != "S"]
    out, prev_y = [], -1
    for cut in spans + [None]:
        y = cut["bbox"][1] if cut else 1e9
        band = [b for b in cols if prev_y <= (b["bbox"][1] + b["bbox"][3]) / 2 < y]
        for s in "LR":
            out += sorted([b for b in band if side(b) == s], key=lambda b: b["bbox"][1])
        if cut:
            out.append(cut)
            prev_y = (cut["bbox"][1] + cut["bbox"][3]) / 2
    return out


def classify(b, body):
    t = b["text"]
    if CAPTION.match(t):
        return "caption"
    first = re.search(r"[A-Za-z0-9]", t)
    if first is None or first.group(0).islower():
        return "body"
    numbered = re.match(r"^(\d+(\.\d+)*\.?|[A-Z](\.\d+)+\.?|[A-Z]\.)\s+\S", t)
    if (len(b["lines"]) <= 3 and b["nwords"] <= 18 and len(re.findall(r"[A-Za-z]", t)) >= 2
            and (b["bold"] > 0.6 or b["size"] >= body + 0.9) and b["size"] >= body - 0.5
            and not re.search(r"[,;]$", t) and (not t.endswith(".") or numbered or b["nwords"] <= 6)):
        return "heading"
    return "body"


def same_heading(a, b):
    """Two heading blocks that are one heading broken over lines (a long title)."""
    if a["page"] != b["page"] or abs(a["size"] - b["size"]) > 0.3 or (a["bold"] > 0.6) != (b["bold"] > 0.6):
        return False
    gap = b["bbox"][1] - a["bbox"][3]
    overlap = min(a["bbox"][2], b["bbox"][2]) - max(a["bbox"][0], b["bbox"][0])
    return -1 <= gap < a["size"] * 0.8 and overlap > 0 and not re.search(r"[.:]$", a["text"])


def looks_like_debris(b):
    """Tables and figure labels: many short lines, lots of numbers, few sentences."""
    t = b["text"]
    letters = sum(c.isalpha() for c in t)
    digits = sum(c.isdigit() for c in t)
    if letters < 3:
        return True
    if digits > letters * 0.6 and len(t) > 8:
        return True
    n = len(b["lines"])
    if n >= 3 and b["nwords"] / n < 3.5 and not re.search(r"[.?!:]$", t):
        return True
    return False


def extract(pdf, skip_captions=False, drop_regex=(), min_size_diff=1.3, keep_authors=False):
    doc = pymupdf.open(pdf)
    pages = [[round(p.rect.width, 2), round(p.rect.height, 2)] for p in doc]
    npages = len(doc)
    all_blocks = []
    for pno, page in enumerate(doc):
        for b in page_lines(page, pno + 1):
            block_stats(b)
            all_blocks.append(b)

    # body text size: most common size in the first part of the paper (appendices
    # and reference lists in small print must not win)
    sizes = Counter()
    first = max(3, npages // 3)
    for b in all_blocks:
        if b["page"] <= first:
            sizes[b["size"]] += len(b["text"])
    body = sizes.most_common(1)[0][0]

    # running headers/footers: in the top/bottom margin and repeated, numeric or small
    repeat = Counter()
    for b in all_blocks:
        for l in b["lines"]:
            repeat[digits_key(l["text"])] += 1
    npages = len(doc)
    drops = [re.compile(r, re.I) for r in DROP_BLOCKS + list(drop_regex)]

    kept_lines_blocks = []
    for b in all_blocks:
        h = pages[b["page"] - 1][1]
        lines = []
        for l in b["lines"]:
            y0, y1 = l["bbox"][1], l["bbox"][3]
            in_margin = y1 < h * 0.1 or y0 > h * 0.9
            if in_margin and (repeat[digits_key(l["text"])] >= max(3, npages * 0.3)
                              or re.fullmatch(r"[\divxlcIVXLC\s:.\-–]+", l["text"])
                              or l["size"] < body - 0.4):
                continue
            lines.append(l)
        if lines:
            nb = dict(b, lines=lines)
            nb["bbox"] = [min(l["bbox"][0] for l in lines), min(l["bbox"][1] for l in lines),
                          max(l["bbox"][2] for l in lines), max(l["bbox"][3] for l in lines)]
            block_stats(nb)
            kept_lines_blocks.append(nb)

    ordered = []
    for pno in range(1, npages + 1):
        pb = [b for b in kept_lines_blocks if b["page"] == pno]
        ordered += order_blocks(pb, pages[pno - 1][0])

    # filter and classify
    stream, skipping, skip_section = [], False, None
    for b in ordered:
        kind = classify(b, body)
        if kind == "heading" and stream and stream[-1]["kind"] == "heading" and same_heading(stream[-1], b):
            stream[-1]["lines"] += b["lines"]
            stream[-1]["bbox"] = bbox_of(stream[-1]["lines"])
            block_stats(stream[-1])
            continue
        if kind == "heading":
            if STOP_HEADINGS.match(b["text"]):
                skipping = True
                continue
            if skipping and re.search(r"appendi(x|ces)", b["text"], re.I):
                skipping = False
            # a boilerplate heading ("CCS Concepts", "Keywords") drops everything up to the
            # next heading of the same or a larger size
            if any(r.match(drop_key(b["text"])) for r in drops):
                skip_section = b["size"]
                continue
            if skip_section is not None and b["size"] >= skip_section - 0.1:
                skip_section = None
        if skipping or skip_section is not None:
            continue
        if kind != "heading" and b["size"] < body - min_size_diff:
            continue
        if any(r.match(drop_key(b["text"])) for r in drops):
            continue
        if kind == "caption" and skip_captions:
            continue
        if kind == "body" and looks_like_debris(b):
            continue
        b["kind"] = kind
        stream.append(b)

    # front matter: keep the title (first heading), drop author names and affiliations
    # up to the abstract (a heading "Abstract"/"Introduction" or the first long paragraph)
    if not keep_authors:
        start = next((i for i, b in enumerate(stream)
                      if (b["kind"] == "heading" and re.match(r"^(\d+\.?\s*)?(abstract|introduction|summary)\b",
                                                              unspace(b["text"]), re.I))
                      or (b["kind"] == "body" and b["nwords"] >= 40)), None)
        title = next((i for i, b in enumerate(stream) if b["kind"] == "heading"), None)
        if start is not None and title is not None and title < start and stream[start]["page"] <= 2:
            big = max(stream[:start], key=lambda b: (b["size"], b["nwords"]) if b["kind"] == "heading" else (0, 0))
            stream = [big] + stream[start:]

    # vocabulary for hyphenation decisions
    vocab = Counter()
    for b in stream:
        for l in b["lines"]:
            for w in l["words"]:
                vocab[re.sub(r"^\W+|\W+$", "", w["text"]).lower()] += 1

    # paragraphs: list of tokens; a token = text + boxes (more than one if hyphenated)
    paras = []
    open_para = None
    for b in stream:
        words = [w for l in b["lines"] for w in l["words"]]
        toks = [{"text": w["text"], "parts": [w]} for w in words]
        if b["kind"] == "body" and open_para is not None and toks and toks[0]["text"][:1].islower():
            target = open_para
        else:
            target = {"kind": b["kind"], "tokens": []}
            paras.append(target)
        for t in toks:
            prev = target["tokens"][-1] if target["tokens"] else None
            if (prev and prev["text"].endswith("-") and len(prev["text"]) > 2
                    and prev["parts"][-1]["line"] != t["parts"][0]["line"] and t["text"][:1].isalpha()):
                head = prev["text"][:-1]
                tail = t["text"]
                bare = lambda s: re.sub(r"^\W+|\W+$", "", s).lower()
                joined, hyph = bare(head + tail), bare(head + "-" + tail)
                keep = vocab[hyph] > vocab[joined] or tail[:1].isupper()
                prev["text"] = head + ("-" if keep else "") + tail
                prev["parts"] += t["parts"]
                continue
            target["tokens"].append(t)
        if b["kind"] == "body":
            last = target["tokens"][-1]["text"] if target["tokens"] else ""
            open_para = None if re.search(r"[.?!:][\"”’')\]]*$", last) else target
    return pages, paras, body


CITATIONS = [
    re.compile(r"\s?\[[^\[\]]{0,300}?\d[^\[\]]{0,300}?\]"),                       # [12], [3-5], [Smith, 2020]
    re.compile(r"\s?\((?:e\.g\.,?\s*|see(?: also)?\s+|cf\.\s*)?(?:[A-Z][^()]*?(?:19|20)\d\d[a-z]?(?:;\s*|,\s*)?)+\)"),
    re.compile(r"\s?\(?(?:https?://|www\.)\S+?\)?(?=[\s,;]|\.?(?:\s|$))"),
]


def sentence_ranges(s):
    """Split points in s (start indices of sentences)."""
    starts = [0]
    for m in re.finditer(r"[.?!][\"”’')\]]*\s+(?=[\"“‘(\[]?[A-Z0-9])", s):
        end = m.start() + 1
        word = s[:end].split()[-1].lower() if s[:end].split() else ""
        word = word.lstrip("(\"“‘[")
        if word in ABBREV or re.fullmatch(r"[a-z]\.", word) or re.fullmatch(r"(\w\.){2,}", word):
            continue
        if re.fullmatch(r"\s*(Fig\.?|Figure|Table|Listing|Algorithm|Box)\s*\d+\.", s[:end]):
            continue
        starts.append(m.end())
    for m in re.finditer(r"\s(?=[•▪◦●‣]\s)", s):
        starts.append(m.end())
    return sorted(set(starts))


def speech(text, kind):
    t = unspace(text)
    if kind == "heading":
        if sum(c.isupper() for c in t) > 0.7 * sum(c.isalpha() for c in t):
            small = {"and", "or", "of", "the", "a", "an", "in", "on", "for", "to", "with", "at", "by", "from"}
            t = re.sub(r"[A-Za-z][A-Za-z']*\d*", lambda m: m.group(0) if re.search(r"\d", m.group(0))
                       else (m.group(0).lower() if m.group(0).lower() in small and m.start() > 3
                             else m.group(0).capitalize()), t)
        t = re.sub(r"^(\d+(?:\.\d+)*|[A-Z](?:\.\d+)+|[A-Z](?=\.))\.?\s+", r"\1. ", t)
    for a, b in SPEECH_SUBS:
        t = re.sub(a, b, t)
    # all-caps abbreviations are read letter by letter: "SEDs" -> "S E Ds"
    def caps(m):
        w, plural = m.group(1), m.group(2) or ""
        if w in CAPS_WORDS or len(w) > 5:
            return m.group(0)
        return " ".join(w[:-1]) + " " + w[-1] + plural if len(w) > 1 else w + plural
    letters = [c for c in t if c.isalpha()]
    if sum(c.isupper() for c in letters) < 0.5 * max(len(letters), 1):
        t = re.sub(r"\b([A-Z]{2,})(s)?(?=\b|\d)", caps, t)
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s+([,.;:?!)])", r"\1", t)
    t = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = re.sub(r"^[,;:.\s]+", "", t)
    if kind == "heading" and t and t[-1] not in ".?!:":
        t += "."
    return t


def sentences(paras, pad=1.0):
    out = []
    for p in paras:
        toks = p["tokens"]
        if not toks:
            continue
        raw, pos = "", []
        for t in toks:
            if raw:
                raw += " "
            pos.append(len(raw))
            raw += t["text"]
        keep = [True] * len(raw)
        for rx in CITATIONS:
            for m in rx.finditer(raw):
                for i in range(m.start(), m.end()):
                    keep[i] = False
        # split on the cleaned text, map back to raw indices
        idx = [i for i in range(len(raw)) if keep[i]]
        clean = "".join(raw[i] for i in idx)
        if p["kind"] == "heading":
            cstarts = [0]
        else:
            cstarts = sentence_ranges(clean)
        rstarts = [idx[c] if c < len(idx) else len(raw) for c in cstarts] if idx else [0]
        rstarts[0] = 0
        bounds = rstarts + [len(raw)]
        cb = cstarts + [len(clean)]
        groups = []
        for k in range(len(rstarts)):
            members = [t for t, s in zip(toks, pos) if bounds[k] <= s < bounds[k + 1]]
            text = speech(clean[cb[k]:cb[k + 1]].strip(), p["kind"])
            if not re.search(r"[A-Za-z]{2}", text) and groups:
                groups[-1][0].extend(members)
                continue
            groups.append([members, text])
        for k, (members, text) in enumerate(groups):
            if not members or not re.search(r"[A-Za-z]", text):
                continue
            # one box per text line
            lines = {}
            for t in members:
                for w in t["parts"]:
                    bx = lines.setdefault(w["line"], [w["page"], *w["box"]])
                    bx[1], bx[2] = min(bx[1], w["box"][0]), min(bx[2], w["box"][1])
                    bx[3], bx[4] = max(bx[3], w["box"][2]), max(bx[4], w["box"][3])
            boxes = [[b[0], round(b[1] - pad, 1), round(b[2] - pad, 1), round(b[3] + pad, 1), round(b[4] + pad, 1)]
                     for b in lines.values()]
            out.append({"id": len(out), "kind": p["kind"], "text": text,
                        "page": boxes[0][0], "boxes": boxes,
                        "para_end": k == len(groups) - 1})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("out")
    ap.add_argument("--review", help="also write a plain-text list (page | kind | text) for checking")
    ap.add_argument("--skip-captions", action="store_true", help="do not read figure/table captions")
    ap.add_argument("--drop-regex", action="append", default=[],
                    help="extra regex: drop blocks whose text starts with it (repeatable)")
    ap.add_argument("--min-size-diff", type=float, default=1.3,
                    help="drop text this many points smaller than the body text (footnotes, tables)")
    ap.add_argument("--keep-authors", action="store_true",
                    help="also read author names and affiliations (default: title, then abstract)")
    a = ap.parse_args()
    pages, paras, body = extract(a.pdf, a.skip_captions, a.drop_regex, a.min_size_diff, a.keep_authors)
    sents = sentences(paras)
    Path(a.out).write_text(json.dumps({"pages": pages, "body_size": body, "sentences": sents},
                                      ensure_ascii=False), encoding="utf-8")
    if a.review:
        with open(a.review, "w", encoding="utf-8") as f:
            for s in sents:
                f.write(f"{s['page']:>3} | {s['kind'][:4]} | {s['text']}\n")
    words = sum(len(s["text"].split()) for s in sents)
    print(f"{len(sents)} sentences, {words} words, body text {body} pt")


if __name__ == "__main__":
    main()
