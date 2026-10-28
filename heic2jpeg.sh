#!/bin/bash
# heic2jpeg.sh - Convert HEIC files to JPEG in-place (same resolution, no resize)
# Run from the directory containing your HEIC files.

# Safety: skip if no HEIC files found
shopt -s nullglob
files=(*.HEIC *.heic)
shopt -u nullglob

if [ ${#files[@]} -eq 0 ]; then
  echo "No HEIC files found in $(pwd)"
  exit 0
fi

for f in "${files[@]}"; do
  out="${f%.*}.jpg"
  # Never overwrite an existing .jpg (heic+jpg same-stem pairs; also guards
  # *.HEIC/*.heic double-match on case-insensitive filesystems).
  if [ -e "$out" ]; then
    echo "SKIP: $f -> $out (exists)"
    continue
  fi
  echo "Converting: $f -> $out"
  convert "$f" -quality 90 "$out"
done

echo "Done. Converted ${#files[@]} file(s)."
