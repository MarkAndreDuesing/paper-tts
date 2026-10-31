# Paper TTS

Turn research papers into structured MP3 listening tracks with British-English
voices, to reduce reading load: tracks follow a reading plan, skips are
announced, and tables and figures are described with their page numbers so you
can look them up. Includes a voice-testing process with rating sheets to find
the voices you like.

Runs locally with free, offline tools ([Piper](https://github.com/OHF-Voice/piper1-gpl)
TTS, ffmpeg, pdftotext).

## Quick start

```bash
pip install -r tools/requirements.txt          # plus ffmpeg and poppler-utils
python3 -m piper.download_voices --data-dir ~/piper-voices en_GB-alba-medium
tools/extract_pdf.sh paper.pdf raw.txt --two-column
python3 tools/clean_pdf_text.py raw.txt clean.txt
# edit clean.txt into script.txt (format in docs/workflow.md)
python3 tools/tts_generate.py script.txt out --voice en_GB-alba-medium --models ~/piper-voices
```

## Contents

| Path | What |
|---|---|
| `docs/workflow.md` | **Start here.** Output rules, setup, script format, track order, generation, voice tests, rating sheets |
| `docs/voice-selection.md` | Preferences learned and the result of every voice-test round |
| `docs/reading-guide-template.md` | Time-boxed method for reading a paper (three passes, claim → evidence → doubt); can define the track order |
| `tools/` | `extract_pdf.sh`, `clean_pdf_text.py`, `tts_generate.py`, `calibrate_voices.py`, `refine_calibration.py`, `build_rating_sheet.py`, `requirements.txt` |
| `tools/examples/` | Scripts that built the listening scripts of earlier rounds |
| `rating-sheet/template.html` | Rating sheet page used by `build_rating_sheet.py` |
| `voices/` | All candidate voices with calibration, ratings per round, current shortlist |
| `rounds/round-N/` | Each voice-test round: paper, script, voice list, timestamps, MP3s, rating sheet |

The papers in `rounds/` are kept only as test material for the voice tests.
