#!/usr/bin/env python3
"""Measure each voice's speaking rate and add a `length_scale` column to voices.csv.

Every voice reads the same passage; voiced time (20 ms frames above an energy
threshold) is measured, and length_scale = median time / voice time. Feeding that
into Piper makes all voices speak at about the median rate.

Usage: calibrate_voices.py voices.csv --models /tmp/piper-voices
"""
import argparse, csv, io, json, statistics, wave
import numpy as np
from piper import PiperVoice, SynthesisConfig

TEXT = ("Reading research papers aloud makes long texts easier to follow on the go. "
        "This passage contains ordinary sentences, a few numbers such as six hundred and one, "
        "and some longer clauses, so that every voice can be timed on the same material. "
        "The measured duration is compared with the median of all voices.")

ap = argparse.ArgumentParser()
ap.add_argument("voices")
ap.add_argument("--models", default="/tmp/piper-voices")
a = ap.parse_args()

rows = list(csv.DictReader(open(a.voices)))
cache = {}
for r in rows:
    m = r["model"]
    if m not in cache:
        cache[m] = (PiperVoice.load(f"{a.models}/{m}.onnx"), json.load(open(f"{a.models}/{m}.onnx.json")))
    voice, meta = cache[m]
    sid = meta["speaker_id_map"][r["speaker"]] if r.get("speaker") else None
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        voice.synthesize_wav(TEXT, w, syn_config=SynthesisConfig(speaker_id=sid, length_scale=1.0))
    buf.seek(0)
    with wave.open(buf) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)
    f = int(sr * 0.02)
    e = np.sqrt((x[: len(x) // f * f].reshape(-1, f) ** 2).mean(1))
    r["speech_s"] = round((e > 0.05 * e.max()).sum() * 0.02, 2)

med = statistics.median(float(r["speech_s"]) for r in rows)
for r in rows:
    r["length_scale"] = round(med / float(r["speech_s"]), 3)
with open(a.voices, "w", newline="") as fo:
    w = csv.DictWriter(fo, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"median voiced time {med} s; length_scale range "
      f"{min(float(r['length_scale']) for r in rows)}–{max(float(r['length_scale']) for r in rows)}")
