#!/usr/bin/env bash
# Extract PDF text page by page with "@@PAGE n" markers, for clean_pdf_text.py.
# Usage: extract_pdf.sh paper.pdf out.txt [--two-column] [--first-page-number N]
# --two-column reads the left half of each page, then the right half, which keeps
# the reading order of two-column layouts (e.g. ACM/IEEE). Assumes US Letter/A4 width.
set -euo pipefail
pdf=$1; out=$2; shift 2; cols=1; off=0
while [ $# -gt 0 ]; do case $1 in --two-column) cols=2;; --first-page-number) off=$(( $2 - 1 )); shift;; esac; shift; done
n=$(pdfinfo "$pdf" | awk '/^Pages:/{print $2}')
w=$(pdfinfo "$pdf" | awk '/^Page size:/{printf "%d", $3}'); h=$(pdfinfo "$pdf" | awk '/^Page size:/{printf "%d", $5}')
: > "$out"
for p in $(seq 1 "$n"); do
  echo "@@PAGE $((p + off))" >> "$out"
  if [ "$cols" = 2 ]; then
    pdftotext -f "$p" -l "$p" -x 0 -y 0 -W $((w / 2)) -H "$h" "$pdf" - >> "$out"
    pdftotext -f "$p" -l "$p" -x $((w / 2)) -y 0 -W $((w / 2)) -H "$h" "$pdf" - >> "$out"
  else
    pdftotext -f "$p" -l "$p" "$pdf" - >> "$out"
  fi
done
