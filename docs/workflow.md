# Workflow: From Paper PDF to Listening Tracks

How a paper becomes a set of MP3s you can listen to instead of (or alongside)
reading, and how voices are tested and chosen. Everything runs locally with
free tools; no Claude or cloud service is required.

## Requirements for the output

- **Language/accent:** British English (`en_GB` voices). German voices exist for
  German texts (e.g. `de_DE-thorsten-high`).
- **Format:** MP3, one file per track.
- **Order:** follow a reading plan, not necessarily the paper's page order. The
  default plan is in "Track order" below; a custom reading guide (see
  `reading-guide-template.md`) can replace it.
- **Every skip is announced** ("Skipping ahead to section eight, on page 12.").
- **Non-audio content** (tables, figures, formulas, code, long number lists) is
  not read raw: it gets a one- or two-sentence description and always its page
  number, so it can be looked up in the PDF.
- **Pace:** `--speed 1.0` is the preferred listening pace (0.9× Piper's normal
  rate, `BASE_PACE` in `tools/tts_generate.py`).

## 1. Set up (once)

```bash
sudo apt install ffmpeg poppler-utils        # macOS: brew install ffmpeg poppler
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt
mkdir -p ~/piper-voices
python3 -m piper.download_voices --data-dir ~/piper-voices \
  en_GB-alba-medium en_GB-jenny_dioco-medium en_GB-semaine-medium en_GB-vctk-medium
```

Voice models (60–115 MB each) come from Hugging Face (`rhasspy/piper-voices`)
and are not stored in git. `voices/all-voices.csv` names the model (and, for
multi-speaker models, the speaker) of every voice.

## 2. Make the listening script

1. **Extract text** page by page:
   `tools/extract_pdf.sh paper.pdf raw.txt` (add `--two-column` for two-column
   layouts, `--first-page-number 469` if the printed page numbers differ).
2. **First-pass clean-up:**
   `python3 tools/clean_pdf_text.py raw.txt clean.txt --header-regex '^Running header'`
   (removes running headers, author-year citations, hyphenation; expands
   "e.g.", "%"...).
3. **Manual pass** into the script format:

   ```
   ### 01 | smith-01-survey | Survey: abstract, introduction, conclusion | pp. 1–2, 12
   Smith, Jones and Lee, twenty twenty-four. Title. Track one: survey. ...
   Abstract. ...
   ```

   - one `###` header per track: number, file stem, title, pages;
   - one paragraph per line;
   - signpost at the start and end of each track ("End of track two. Next: ...");
   - announce every skip and jump;
   - replace each table/figure/formula with a description plus page;
   - drop numeric citations, footnote markers, URLs; read important footnotes
     inline ("A footnote adds that ...");
   - spell out abbreviations letter by letter where Piper would mangle them
     ("I C S E"), numbers in parentheses as words ("45, of which 39 ...");
   - state page-number type (printed vs PDF) in the first track if it matters.

   `tools/examples/` shows how this was scripted for several papers (column
   joins, substitutions in `common_sub.py`). Copy the structure, not the line numbers.

### Track order (default)

| Track | Content |
|---|---|
| 01 Survey | Abstract, introduction, **jump to the conclusion**, then a spoken list of all figures and tables with pages (or the paper's boxed findings) |
| 02 Background | Background / related concepts |
| 03 Method | Methodology; threats to validity can be pulled in here |
| 04+ Results | Results, one track per large section or research question |
| … | Discussion, recommendations, limitations |
| last | Related work; announce that the conclusion was heard in track 01; skip references, appendices, acknowledgements, licence text |

Long sections (over about 25 minutes) can be split into two tracks.

## 3. Generate MP3s

```bash
# one voice (final listening version)
python3 tools/tts_generate.py script.txt out --voice en_GB-alba-medium --models ~/piper-voices --album "Course – Paper"
# a speaker of a multi-speaker model, with its calibration factor from the voice list
python3 tools/tts_generate.py script.txt out --voice en_GB-vctk-medium --speaker p240 --voice-scale 1.07 --models ~/piper-voices
# voice test: spread the paper over a voice list (writes out/segments.csv)
python3 tools/tts_generate.py script.txt out --voices voices/shortlist-current.csv --models ~/piper-voices
```

- `--speed` changes the pace in any step (e.g. `1.05` = 5 % faster than preferred).
- Merge tracks into one file:
  `ls out/*.mp3 | sed "s/^/file '/;s/$/'/" > list.txt && ffmpeg -f concat -safe 0 -i list.txt -c copy full.mp3`

## 4. Voice tests

Used to pick voices by listening to them on real papers, round by round.

- **Voice list:** CSV with `no,model,speaker,sex,accent,length_scale` (see
  `voices/`). `no` stays the same across rounds so ratings can be compared.
- **Even speed:** `tools/calibrate_voices.py voices.csv` measures every voice on
  a fixed passage and writes `length_scale`. After a run on a real paper,
  `tools/refine_calibration.py voices.csv out/segments.csv` corrects it from
  actual speaking rates; generate again.
- **Balanced snippets:** each voice reads whole sentences, about the same
  speaking time each (share recomputed after every voice).
- **Mixed order** (default): voices from less common models are spread evenly,
  neighbours differ in sex and accent, so similar voices don't blend together
  (`--no-mix` keeps the CSV order).
- **3-second pause** at every voice change (`--switch-gap`). No spoken voice
  labels: the rating sheet shows who is speaking, with timestamps.
- **Rating sheet:**
  `python3 tools/build_rating_sheet.py out --voices voices.csv --title "Smith et al. (2024)" --script script.txt --previous voices/ratings-roundN.csv --round N+1`
  writes `out/index.html`: player with track tabs, speed slider, current voice
  highlighted, bad/medium/good per voice (keys 1/2/3), filters, export as
  Markdown/CSV, and "save all tracks on this device" for offline listening.
- **After rating:** save the export as `voices/ratings-roundN.csv`; keep good and
  medium voices as the next `voices/shortlist-current.csv`.

The sheet is a self-contained page: open `index.html` locally next to its MP3s,
serve the folder with any static host (`python3 -m http.server`, GitHub Pages),
or publish it as a claude.ai artifact. Ratings live in the browser; export them.

## 5. Store a round

`rounds/round-N/`: `paper.pdf`, `script.txt`, `voices.csv` (as used, with
calibration), `segments.csv`, the MP3s and `index.html`. Add a line to
`docs/voice-selection.md`.

## Limitations

- Synthetic voices: clear, not audiobook quality.
- Multi-column PDFs, tables and figure debris need a manual check.
- Formulas and statistics are simplified in speech; the PDF stays the reference.
