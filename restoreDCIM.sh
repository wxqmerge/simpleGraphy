#!/bin/bash
# restoreDCIM.sh - copy generated JPGs from D:\DCIM_Raw back to D:\DCIM
# Subdirectory structure is recreated as needed. Files already present
# in D:\DCIM are skipped (never overwritten). RAWs stay in D:\DCIM_Raw.
#
# Usage:
#   ~/restoreDCIM.sh             run for real
#   ~/restoreDCIM.sh --DRY_RUN   preview only, change nothing
#
# Edit COPY_EXTS below to change which extensions get copied back.

set -euo pipefail

SRC=/cygdrive/d/DCIM_Raw
DST=/cygdrive/d/DCIM

# Extensions to copy back (case-insensitive). Edit as needed.
COPY_EXTS="jpg jpeg"

usage() {
  cat <<EOF
restoreDCIM.sh - copy JPGs from D:\\DCIM_Raw back to D:\\DCIM (existing files skipped)

Usage:
  ~/restoreDCIM.sh             run for real
  ~/restoreDCIM.sh --DRY_RUN   preview only, change nothing
  ~/restoreDCIM.sh --help      this help
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

if [ ! -d "$SRC" ]; then
  echo "ERROR: $SRC not found. Aborting." >&2
  exit 1
fi
cd "$SRC" || { echo "ERROR: cannot cd to $SRC" >&2; exit 1; }
[ "$(basename "$(pwd)")" = "DCIM_Raw" ] || { echo "ERROR: cd verification failed, now in $(pwd)" >&2; exit 1; }

# Build find args: -type f ( -iname '*.jpg' -o -iname '*.jpeg' )
findargs=(-type f \( )
first=1
for ext in $COPY_EXTS; do
  if [ "$first" -eq 0 ]; then findargs+=(-o); fi
  findargs+=(-iname "*.${ext}")
  first=0
done
findargs+=(\) )

if [ "$DRY_RUN" != "1" ]; then
  mkdir -p "$DST"
fi

copied=0; skipped=0
while IFS= read -r f; do
  rel=${f#./}
  dir=$(dirname "$rel")
  dest="$DST/$rel"
  if [ -e "$dest" ]; then
    skipped=$((skipped+1))
    echo "skip (exists): $rel"
  else
    if [ "$DRY_RUN" = "1" ]; then
      echo "DRY-RUN: would copy $rel -> $dest"
    else
      mkdir -p "$DST/$dir"
      cp -- "$f" "$dest"
      echo "copied: $rel"
    fi
    copied=$((copied+1))
  fi
done < <(find . "${findargs[@]}")

echo "Done. Copied $copied, skipped $skipped (existing) -> $DST"
