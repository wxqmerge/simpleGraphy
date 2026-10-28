#!/bin/bash
# organize_photos.sh - Move photos into date-based folders
# Matches: 2026.07.2306.32.30DSC04323.JPG → 260723
#          PXL_20260708_195957308.JPG → 260708

shopt -s nullglob

extensions=("*.JPG" "*.jpg" "*.jpeg" "*.JPEG" "*.HEIC" "*.heic" "*.CR2" "*.cr2" "*.ARW" "*.arw" "*.NEF" "*.nef" "*.RAW" "*.raw" "*.DNG" "*.dng" "*.SRW" "*.srw" "*.ORF" "*.orf" "*.PEF" "*.pef" "*.SR2" "*.sr2" "*.SR3" "*.sr3" "*.RAF" "*.raf")

moved=0
skipped=0

# Build find args: \( -name '*.JPG' -o -name '*.jpg' -o ... \)
# Iterating find -print0 avoids word-splitting on filenames with spaces.
findargs=()
first=1
for pattern in "${extensions[@]}"; do
  [ "$first" -eq 0 ] && findargs+=(-o)
  findargs+=(-name "$pattern")
  first=0
done

while IFS= read -r -d '' f; do
  f="${f#./}"
  [ -f "$f" ] || continue
  base="${f%.*}"
  folder=""

  # Pattern 1: YYYY.MM.DD...
  if [[ "$base" =~ ^[0-9]{4}\.[0-9]{2}\.[0-9]{2} ]]; then
    date_raw="${base:0:10}"
    date_clean="${date_raw//./}"
    folder="${date_clean:2:2}${date_clean:4:4}"

  # Pattern 2: PXL_YYYYMMDD...
  elif [[ "$base" =~ ^PXL_[0-9]{8} ]]; then
    folder="${base:6:2}${base:8:4}"
  fi

  [ -z "$folder" ] && continue

  [ ! -d "$folder" ] && { mkdir -p "$folder"; echo "Created: $folder"; }

  if [ -e "$folder/$f" ]; then
    echo "SKIP: $f"
    ((skipped++))
    continue
  fi

  mv -n "$f" "$folder/" && {
    echo "Moved: $f → $folder/"
    ((moved++))

    # Sidecars are named after the full filename: IMG_5848.jpg.caption
    for ext in caption xmp; do
      [ -f "$f.$ext" ] && mv -n "$f.$ext" "$folder/"
    done
  }
done < <(find . -maxdepth 1 \( "${findargs[@]}" \) -print0)

echo "Done. Moved: $moved | Skipped: $skipped"