#!/usr/bin/env python3
"""Refine per-voice length_scale from a real run (segments.csv with chars column).

Each voice's measured seconds per character is compared with the median; its
length_scale is scaled so it matches. Run the generator again afterwards.

Usage: refine_calibration.py voices.csv segments.csv
"""
import csv, statistics, sys
from collections import defaultdict

voices_path, seg_path = sys.argv[1], sys.argv[2]
sec, chars = defaultdict(float), defaultdict(int)
for s in csv.DictReader(open(seg_path)):
    sec[s["voice_no"]] += float(s["end"]) - float(s["start"])
    chars[s["voice_no"]] += int(s["chars"])
rate = {v: sec[v] / chars[v] for v in sec if chars[v]}
med = statistics.median(rate.values())
rows = list(csv.DictReader(open(voices_path)))
for r in rows:
    if r["no"] in rate:
        r["length_scale"] = round(float(r["length_scale"]) * med / rate[r["no"]], 3)
with open(voices_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print("rate spread before refinement:", round(min(rate.values()) / med, 2), "to", round(max(rate.values()) / med, 2))
