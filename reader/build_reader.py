#!/usr/bin/env python3
"""Build an interactive reader for one paper: the PDF, audio for one or more
voices, and per-sentence timings so the viewer can highlight the sentence being
read and jump between text and audio.

    build_reader.py paper.pdf OUTDIR --voices 37,2 [--models ~/piper-voices]

Steps:
  1. pdf_sentences.py: sentences in reading order with their boxes on the pages
     (skipped if OUTDIR/sentences.json exists, so you can edit it by hand;
     --re-extract forces it).
  2. Piper reads every sentence (same pace rules as tools/tts_generate.py) and
     the start/end time of each sentence is recorded. Audio is split into parts
     of about --part-minutes so no file is too large.
  3. Writes OUTDIR/index.html (the viewer), paper.pdf, sync.js (all data) and
     audio/<voice>/partNN.mp3. Voices that are already built for the same text
     are not generated again, so voices can be added later.

--voices takes numbers from the voice list (or `all`; column `no`, default
voices/shortlist-current.csv); their `length_scale` calibration is used.
Open OUTDIR/index.html through a web server (python3 -m http.server) or
publish the folder as a claude.ai artifact.
"""
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import pdf_sentences  # noqa: E402

GAP = {"heading": 0.7, "para": 0.8, "sentence": 0.35}


def voice_id(v):
    m = v["model"].replace("en_GB-", "").replace("-medium", "").replace("-high", "").replace("-low", "")
    return f"{m}-{v['speaker']}" if v.get("speaker") else m


def voice_label(v):
    name = v["model"].replace("en_GB-", "").replace("-medium", "")
    if v.get("speaker"):
        name += " " + v["speaker"]
    bits = [b for b in (v.get("sex"), v.get("accent")) if b and b != "unknown"]
    return f"{v['no']} · {name}" + (f" ({', '.join(bits)})" if bits else "")


def build_voice(v, sents, outdir, models, speed, bitrate, part_minutes):
    from tts_generate import BASE_PACE, RATE, Voices, silence, synth  # needs piper
    voices = Voices(models)
    vid = voice_id(v)
    vdir = outdir / "audio" / vid
    if vdir.exists():
        shutil.rmtree(vdir)
    vdir.mkdir(parents=True)
    ls = float(v.get("length_scale") or 1.0) / (speed * BASE_PACE)
    times, parts = [], []
    pcm, part_start, total = bytearray(), 0.0, 0.0

    def flush(tmp):
        nonlocal pcm, part_start
        if not pcm:
            return
        n = len(parts) + 1
        raw = Path(tmp) / "part.raw"
        raw.write_bytes(bytes(pcm))
        name = f"part{n:02d}.mp3"
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(RATE),
                        "-ac", "1", "-i", str(raw), "-b:a", bitrate, str(vdir / name)], check=True)
        dur = len(pcm) / 2 / RATE
        parts.append({"file": f"audio/{vid}/{name}", "start": round(part_start, 3), "dur": round(dur, 3)})
        part_start += dur
        pcm = bytearray()

    with tempfile.TemporaryDirectory() as tmp:
        for i, s in enumerate(sents):
            now = part_start + len(pcm) / 2 / RATE
            audio = synth(voices, v["model"], v.get("speaker", ""), s["text"], ls, tmp)
            pcm += audio
            end = part_start + len(pcm) / 2 / RATE
            times.append([round(now, 3), round(end, 3)])
            nxt = sents[i + 1] if i + 1 < len(sents) else None
            gap = GAP["heading"] if s["kind"] == "heading" or (nxt and nxt["kind"] == "heading") \
                else GAP["para"] if s.get("para_end") else GAP["sentence"]
            pcm += silence(gap)
            # cut parts only between paragraphs, once a part is long enough
            if len(pcm) / 2 / RATE >= part_minutes * 60 and (s.get("para_end") or s["kind"] == "heading"):
                flush(tmp)
            if (i + 1) % 50 == 0:
                print(f"  {vid}: {i + 1}/{len(sents)} sentences, {end / 60:.1f} min", flush=True)
        flush(tmp)
    total = part_start
    print(f"  {vid}: {total / 60:.1f} min in {len(parts)} parts")
    return {"id": vid, **voice_meta(v), "speed": speed, "duration": round(total, 3),
            "parts": parts, "times": times}


def voice_meta(v):
    return {"label": voice_label(v), "no": v["no"], "model": v["model"], "speaker": v.get("speaker", ""),
            "sex": v.get("sex", ""), "accent": v.get("accent", ""), "length_scale": v.get("length_scale", "")}


def text_hash(sents):
    return hashlib.sha1("\n".join(s["text"] for s in sents).encode()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("outdir")
    ap.add_argument("--voices", default="37", help="comma-separated voice numbers from the voice list")
    ap.add_argument("--voice-list", default=str(ROOT / "voices" / "shortlist-current.csv"))
    ap.add_argument("--models", default=str(Path.home() / "piper-voices"))
    ap.add_argument("--speed", type=float, default=1.0, help="1.0 = preferred pace (see tts_generate.py)")
    ap.add_argument("--bitrate", default="32k")
    ap.add_argument("--part-minutes", type=float, default=10)
    ap.add_argument("--title", default="")
    ap.add_argument("--jobs", type=int, default=1, help="voices generated in parallel")
    ap.add_argument("--re-extract", action="store_true", help="extract sentences again even if sentences.json exists")
    ap.add_argument("--rebuild", action="store_true", help="generate audio again even if it is up to date")
    ap.add_argument("--skip-captions", action="store_true")
    ap.add_argument("--keep-authors", action="store_true")
    ap.add_argument("--drop-regex", action="append", default=[])
    a = ap.parse_args()

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    sj = out / "sentences.json"
    if a.re_extract or not sj.exists():
        pages, paras, body = pdf_sentences.extract(a.pdf, a.skip_captions, a.drop_regex, keep_authors=a.keep_authors)
        sents = pdf_sentences.sentences(paras)
        sj.write_text(json.dumps({"pages": pages, "body_size": body, "sentences": sents}, ensure_ascii=False),
                      encoding="utf-8")
        with open(out / "sentences.txt", "w", encoding="utf-8") as f:
            for s in sents:
                f.write(f"{s['page']:>3} | {s['kind'][:4]} | {s['text']}\n")
        print(f"{len(sents)} sentences -> {sj} (review: {out / 'sentences.txt'})")
    data = json.loads(sj.read_text(encoding="utf-8"))
    sents = data["sentences"]
    h = text_hash(sents)

    if Path(a.pdf).resolve() != (out / "paper.pdf").resolve():
        shutil.copyfile(a.pdf, out / "paper.pdf")

    old = {}
    sync_json = out / "sync.json"
    if sync_json.exists():
        prev = json.loads(sync_json.read_text(encoding="utf-8"))
        if prev.get("text_hash") == h:
            old = {v["id"]: v for v in prev["voices"]}

    with open(a.voice_list, newline="") as f:
        vlist = {r["no"]: r for r in csv.DictReader(f)}
    nos = [x.strip() for x in a.voices.split(",") if x.strip()]
    if nos == ["all"]:
        nos = list(vlist)
    built, todo = {}, []
    for no in nos:
        v = vlist[no]
        vid = voice_id(v)
        if vid in old and not a.rebuild and old[vid].get("speed") == a.speed \
                and all((out / p["file"]).exists() for p in old[vid]["parts"]):
            print(f"  {vid}: up to date")
            built[no] = {**old[vid], **voice_meta(v)}
        else:
            todo.append(v)
    args = [(v, sents, out, a.models, a.speed, a.bitrate, a.part_minutes) for v in todo]
    if a.jobs > 1 and len(todo) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(a.jobs) as ex:
            for v, r in zip(todo, ex.map(build_voice, *zip(*args))):
                built[v["no"]] = r
    else:
        for v, x in zip(todo, args):
            print(f"Generating {voice_id(v)} ...")
            built[v["no"]] = build_voice(*x)
    built = [built[no] for no in nos]

    title = a.title or next((s["text"].rstrip(".") for s in sents if s["kind"] == "heading"), Path(a.pdf).stem)
    sync = {"title": title, "pdf": "paper.pdf", "text_hash": h, "pages": data["pages"],
            "sentences": [{"id": s["id"], "kind": s["kind"], "text": s["text"], "page": s["page"],
                           "boxes": s["boxes"]} for s in sents],
            "voices": built}
    sync_json.write_text(json.dumps(sync, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # sync.js works without a server (file://), where fetch() of local files is blocked
    (out / "sync.js").write_text("window.READER_DATA = " + json.dumps(sync, ensure_ascii=False, separators=(",", ":"))
                                 + ";\n", encoding="utf-8")
    # the viewer template is page content only (that is what a claude.ai artifact wants);
    # for local use it gets a normal document head
    page = (HERE / "viewer.html").read_text(encoding="utf-8")
    (out / "index.html").write_text('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                                    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                                    '<style>body{margin:0}[hidden]{display:none!important}</style>\n</head>\n<body>\n'
                                    + page + "\n</body>\n</html>\n", encoding="utf-8")
    print(f"Wrote {out / 'index.html'}")


if __name__ == "__main__":
    main()
