# Voice Selection Log

Running record of the voice tests: preferences learned, and the result of each
round. Ratings files are in `voices/`, the rounds themselves in `rounds/`.

## Preferences learned so far

- British English only; American-accent VCTK speakers are excluded.
- Preferred pace: 0.9× Piper's normal rate, now the default 1.0×.
- All voices are speed-calibrated so they speak at the same rate.
- Snippets of equal speaking time per voice, split at sentence boundaries.
- No spoken voice labels (distracting while reading); timestamps in the sheet instead.
- Voices must not be grouped by voice pack: similar voices blend together.
  Mixed order plus a 3-second pause at each voice change.
- Offline playback matters (listening on the go).

## Candidate voices

All British-English Piper voices: 6 single-speaker models (alan, alba, cori,
jenny_dioco, northern_english_male, southern_english_female), aru (12 speakers),
semaine (4) and vctk (109 speakers, of which 21 American are excluded): 110
voices, listed with sex, approximate accent and calibration in
`voices/all-voices.csv`. Accent labels for vctk/aru speakers are approximate.

## Rounds

| Round | Paper (in `rounds/round-N/paper.pdf`) | Voices | Per voice | Result |
|---|---|---|---|---|
| 1 | Collberg & Proebsting 2016, 8 pp. | 110, CSV order, no pause | ~14 s (uneven) | 6 good, 55 medium, 49 bad → 61 kept (`ratings-round1.csv`) |
| 2 | Heumüller et al. 2020, 32 pp. | 61 | ~68 s | 5 good, 23 medium, 33 bad → 28 kept (`ratings-round2.csv`) |
| 3 | Timperley et al. 2021, 41 pp. | 28, pace 0.9 | ~3.5 min | 2 good, 20 medium, 6 bad → 22 kept (`ratings-round3.csv`) |
| 4 | Hermann et al. 2020, 12 pp. | 28 | ~2.4 min | skipped, no ratings |
| 5 | Olszewski et al. 2023, 27 pp. | 22, mixed order, 3 s pauses | ~2.7 min | 0 good, 15 medium, 7 bad → 15 kept (`ratings-round5.csv`) |
| 6 | Winter et al. 2022, 12 pp. | 15 (regenerated after round 5), mixed order, 3 s pauses | ~3.9 min | 0 good, 14 medium, 1 bad (vctk p284) → 14 kept (`ratings-round6.csv`) |
| 7 | Broneske et al. 2024, 24 pp. | 14, mixed order, 3 s pauses | ~4.5 min | open |
| 8 | Guevara-Vega et al. 2024, 16 pp. | 14, mixed order, 3 s pauses | ~4.2 min | open |

Rounds can also be rated in the reader (`reader/`): `rounds/round-7/reader/`
has the whole paper in each of the 14 shortlist voices, with Bad / Medium /
Good per voice and a CSV export in the same format.

Round 1 used the first, word-count based split (some voices got only a few
seconds); from round 2 snippets are balanced by speaking time.

## Current shortlist (14 voices, `voices/shortlist-current.csv`)

Rated medium in rounds 5 and 6: alba, jenny_dioco, and vctk p240, p247, p252,
p255, p256, p260, p269, p276, p280, p298, p313, p347.
No voice has been rated good since round 3; the field has converged on a set of
acceptable voices rather than a clear favourite.
