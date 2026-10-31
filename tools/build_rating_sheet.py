#!/usr/bin/env python3
"""Build a rating sheet (index.html) for a voice-test round.

The sheet plays the round's MP3s, highlights the current voice, lets you rate
each voice bad/medium/good (keys 1/2/3), can save the audio on the device for
offline listening, and exports ratings as Markdown or CSV.

Usage:
  build_rating_sheet.py ROUND_DIR --voices voices.csv --title "Smith et al. (2024)" \
      [--previous voices/ratings-roundN.csv] [--round 7]

ROUND_DIR must contain segments.csv (written by tts_generate.py) and the MP3s.
Track labels and pages are read from the script's "### NN | stem | title | pages"
headers if --script is given; otherwise the file stems are used.
"""
import argparse, csv, json, os, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("round_dir")
ap.add_argument("--voices", required=True)
ap.add_argument("--title", required=True, help="short paper name shown on the sheet")
ap.add_argument("--script", help="listening script, for track titles and pages")
ap.add_argument("--previous", help="ratings CSV from an earlier round (column 'rating')")
ap.add_argument("--round", default="", help="round number or name")
ap.add_argument("--template", default=str(HERE.parent / "rating-sheet" / "template.html"))
a = ap.parse_args()

rd = Path(a.round_dir)
v = {r["no"]: r for r in csv.DictReader(open(a.voices))}
segs = list(csv.DictReader(open(rd / "segments.csv")))
seg = [[int(s["voice_no"]), v[s["voice_no"]]["model"].replace("en_GB-", ""), v[s["voice_no"]].get("speaker", ""),
        v[s["voice_no"]].get("sex", ""), v[s["voice_no"]].get("accent", ""), s["track"],
        float(s["start"]), float(s["end"]), s["first_words"]] for s in segs]
stems = list(dict.fromkeys(s["track"] for s in segs))
info = {}
if a.script:
    for line in open(a.script, encoding="utf-8"):
        if line.startswith("### "):
            no, stem, title, pages = [p.strip() for p in line[4:].split("|")]
            info[stem] = (f"{no} {title.split(':')[0]}", pages)
tracks = [{"stem": s, "label": info.get(s, (s, ""))[0], "pages": info.get(s, ("", ""))[1]} for s in stems]
prev = {}
if a.previous:
    prev = {int(r["no"]): r["rating"] for r in csv.DictReader(open(a.previous)) if r.get("rating") in ("good", "medium")}
mb = round(sum(f.stat().st_size for f in rd.glob("*.mp3")) / 1048576)
per = round(sum(s[7] - s[6] for s in seg) / max(1, len({s[0] for s in seg})) / 60, 1)
key = re.sub(r"[^a-z0-9]+", "-", f"{a.title}-{a.round}".lower()).strip("-")

h = open(a.template, encoding="utf-8").read()
h = re.sub(r"const SEG=\[.*?\];\nconst ROUND1=.*?;\n", lambda m: "const SEG=" + json.dumps(seg, ensure_ascii=False, separators=(",", ":"))
           + ";\nconst ROUND1=" + json.dumps(prev) + ";\n", h, count=1, flags=re.S)
h = re.sub(r"const TRACKS=\[.*?\];", lambda m: "const TRACKS=" + json.dumps(tracks, ensure_ascii=False) + ";", h, count=1, flags=re.S)
h = re.sub(r'const KEY="[^"]*";', f'const KEY="voice-ratings-{key}";', h, count=1)
h = re.sub(r'const DBN="[^"]*";', f'const DBN="voice-test-{key}-audio";', h, count=1)
name = f"Voice Shortlist Round {a.round}".strip() if a.round else "Voice Shortlist"
h = re.sub(r"<title>.*?</title>", f"<title>{name}</title>", h, count=1)
h = re.sub(r"<h1>.*?</h1>", f"<h1>{name}</h1>", h, count=1)
start = "Ratings start from your previous round's choices; change any of them as you listen. " if prev else ""
h = re.sub(r'<p class="sub">.*?</p>', f'<p class="sub">{a.title}, read by {len(v)} voices in turn, about {per} minutes each, with a pause at every voice change. {start}1.00× is your preferred pace; the slider changes it in 0.05 steps. Keys <kbd>1</kbd> bad, <kbd>2</kbd> medium, <kbd>3</kbd> good rate the voice that is playing.</p>', h, count=1, flags=re.S)
h = re.sub(r"about \d+ MB in total", f"about {mb} MB in total", h)
h = re.sub(r"<th>Round \d+</th>", "<th>Previous</th>", h)
h = re.sub(r"# Voice ratings – round [^`\"]*?\)", f"# Voice ratings – round {a.round} ({a.title})", h)
(rd / "index.html").write_text(h, encoding="utf-8")
print(f"{rd/'index.html'}: {len(tracks)} tracks, {len(v)} voices, {per} min/voice, {mb} MB")
