#!/bin/bash
# updateDCIM.sh - move RAW files from D:\DCIM to D:\DCIM_Raw, movies to D:\DCIM_Movie
# Subdirectory structure is preserved. JPGs stay in D:\DCIM.
# Subdirs left empty are removed from D:\DCIM.
#
# Usage:
#   ~/updateDCIM.sh             run for real
#   ~/updateDCIM.sh --DRY_RUN   preview only, change nothing
#
# Edit RAW_EXTS / MOV_EXTS below to match your cameras.

set -euo pipefail

SRC=/cygdrive/d/DCIM
RAW=/cygdrive/d/DCIM_Raw
MOV=/cygdrive/d/DCIM_Movie

# RAW + movie extensions to move (case variants). Edit to match your cameras.
RAW_EXTS="DNG dng NEF nef PEF pef ARW arw CR2 cr2"
MOV_EXTS="MOV mov MP4 mp4"

usage() {
  cat <<EOF
updateDCIM.sh - move RAWs from D:\\DCIM to D:\\DCIM_Raw, movies to D:\\DCIM_Movie

Usage:
  ~/updateDCIM.sh             run for real
  ~/updateDCIM.sh --DRY_RUN   preview only, change nothing
  ~/updateDCIM.sh --help      this help
EOF
}

DRY_RUN=${DRY_RUN:-0}
for arg in "$@"; do
  case "$arg" in
    --DRY_RUN|--dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $arg" >&2; usage; exit 1 ;;
  esac
done

run() {
  if [ "$DRY_RUN" = "1" ]; then
    echo "DRY-RUN: $*"
  else
    "$@"
  fi
}

if [ ! -d "$SRC" ]; then
  echo "ERROR: $SRC not found. Aborting." >&2
  exit 1
fi
cd "$SRC" || { echo "ERROR: cannot cd to $SRC" >&2; exit 1; }
[ "$(basename "$(pwd)")" = "DCIM" ] || { echo "ERROR: cd verification failed, now in $(pwd)" >&2; exit 1; }

run mkdir -p "$RAW" "$MOV"

# Capture the dir list up front (stable while we move files out of them)
dirs=$(find . -type d)

moved=0
while IFS= read -r directory; do
  if [ "$directory" = "." ]; then
    raw_target="$RAW";  mov_target="$MOV"
  else
    rel=${directory#./}
    raw_target="$RAW/$rel";  mov_target="$MOV/$rel"
  fi
  run mkdir -p "$raw_target" "$mov_target"

  for ext in $RAW_EXTS; do
    for f in "$directory"/*."$ext"; do
      if [ -e "$f" ]; then
        run mv -- "$f" "$raw_target/"
        moved=$((moved+1))
      fi
    done
  done
  for ext in $MOV_EXTS; do
    for f in "$directory"/*."$ext"; do
      if [ -e "$f" ]; then
        run mv -- "$f" "$mov_target/"
        moved=$((moved+1))
      fi
    done
  done
done <<< "$dirs"

if [ "$DRY_RUN" = "1" ]; then
  echo "DRY-RUN: would remove empty source subdirs"
else
  # -depth removes children before parents; non-empty dirs (leftover files) are left alone
  find . -mindepth 1 -depth -type d -exec rmdir {} \; 2>/dev/null || true
fi

echo "Done. Moved $moved file(s). RAWs -> $RAW, movies -> $MOV."
