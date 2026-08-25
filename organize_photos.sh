#!/bin/bash
# organize_photos.sh - Move photos into date-based folders
# Matches: 2026.07.2306.32.30DSC04323.JPG → 260723
#          PXL_20260708_195957308.JPG → 260708

shopt -s nullglob

extensions=("*.JPG" "*.jpg" "*.jpeg" "*.JPEG" "*.HEIC" "*.heic" "*.CR2" "*.cr2" "*.ARW" "*.arw" "*.NEF" "*.nef" "*.RAW" "*.raw" "*.DNG" "*.dng" "*.SRW" "*.srw" "*.ORF" "*.orf" "*.PEF" "*.pef" "*.SR2" "*.sr2" "*.SR3" "*.sr3" "*.RAF" "*.raf")

moved=0
skipped=0

for pattern in "${extensions[@]}"; do
  for f in $pattern; do
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

      for ext in caption xmp; do
        [ -f "${base}.${ext}" ] && mv -n "${base}.${ext}" "$folder/"
      done
    }
  done
done

echo "Done. Moved: $moved | Skipped: $skipped"