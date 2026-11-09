# Reader (prototype)

Listen to a paper while it is highlighted in the PDF itself, sentence by sentence.

- The sentence being read is marked on the page and kept in view.
- Click or drag on the timeline: the sentence at that point is shown and reading goes on from there.
- Click a sentence in the PDF: reading jumps there and goes on.
- Reads the paper in page order, top to bottom (left column, then right column).
  Skips running headers and footers, page numbers, footnotes, small print,
  author block, front-matter boilerplate (CCS concepts, keywords, licence) and the references.
  Figure and table captions are read; tables themselves are not.
- Voice menu (all voices built for the paper), speed 0.8–2×, zoom, keyboard
  (space, ← →). The position is remembered in the browser.

This is separate from the listening tracks in `docs/workflow.md`: no reading
plan, no spoken descriptions of tables or figures, no manual script.

## Build

```bash
pip install -r tools/requirements.txt
python3 -m piper.download_voices --data-dir ~/piper-voices en_GB-vctk-medium en_GB-alba-medium

# 1. check the text first (optional): sentences.txt lists page | kind | text
python3 reader/pdf_sentences.py paper.pdf out/sentences.json --review out/sentences.txt

# 2. audio for one or more voices (numbers from voices/shortlist-current.csv)
python3 reader/build_reader.py paper.pdf out --voices 37,2

# 3. open it
cd out && python3 -m http.server 8000     # then http://localhost:8000
```

- `build_reader.py` reuses `out/sentences.json` if it exists, so you can fix a
  sentence's `text` (what is spoken) by hand and build again; `--re-extract`
  starts over. Voices already built for the same text are kept, so you can add
  a voice later with `--voices 37,2,65`.
- `--speed` as in `tools/tts_generate.py` (1.0 = preferred pace). The speed menu
  in the page changes playback speed on top of that.
- Options for the text: `--skip-captions`, `--keep-authors`, `--drop-regex
  '^Some boilerplate'` (repeatable).
- About 1 MB of audio per 4 minutes (32 kbps mono), split into parts of
  about 10 minutes (`--part-minutes`). Building takes about 1 minute per 20 minutes
  of speech per voice.

## Files

| File | What |
|---|---|
| `pdf_sentences.py` | PDF → sentences in reading order with their line boxes (PyMuPDF), plus the spoken version of each |
| `build_reader.py` | Runs the extraction, synthesises every sentence with Piper (records start/end per sentence), writes the output folder |
| `viewer.html` | The page (pdf.js 3.11 from cdnjs). `build_reader.py` copies it as `index.html` |

Output folder: `index.html`, `paper.pdf`, `sync.js` (and the same data as
`sync.json`: sentences with page, boxes and spoken text; per voice the audio
parts and each sentence's start and end), `audio/<voice>/partNN.mp3`,
`sentences.json`, `sentences.txt`.

Built examples: `rounds/round-7/reader/` (single column) and
`rounds/round-6/reader/` (two columns), voices 37 (vctk p240) and 2 (alba).

## Opening it

- **Local web server** (recommended): `python3 -m http.server` in the output folder.
- **Double-click `index.html`**: works, but most browsers block reading the PDF
  from disk; the page then asks you to pick `paper.pdf`.
- **claude.ai artifact**: publish `viewer.html` with `paper.pdf`, `sync.js` and
  the `audio/` files as supporting files.

## Known limits

- Highlighting is per sentence; there is no word-level timing.
- The text comes from the PDF's text layer: scanned PDFs do not work, and
  formulas, tables printed at body size and unusual layouts can produce odd
  sentences. Check `sentences.txt`.
- Abbreviations are spelled out by a simple rule (all-caps words of up to five
  letters: "SED" → "S E D"); a few may sound wrong.
- No offline saving yet (the rating sheet has it; it could be added).
