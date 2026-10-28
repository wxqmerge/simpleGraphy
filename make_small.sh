#find . \( -iname "*.JPG" -o -iname "*.HEIC" \) -exec convert {} -resize 30% ../$DIRNAME/{} \;

#DIRNAME=$(basename $(pwd))
DIRNAME="small"
mkdir -p "$DIRNAME"
find . -maxdepth 1 \( -iname "*.JPG" -o -iname "*.HEIC" \) | while IFS= read -r f; do
  base=$(basename "$f")
  out="./$DIRNAME/${base%.*}.jpg"
  # IMG.JPG and IMG.HEIC both map to small/IMG.jpg; never overwrite.
  if [ -e "$out" ]; then
    echo "SKIP: $f -> $out (exists)"
    continue
  fi
  convert "$f" -resize 3060x3060 -quality 90 "$out"
done
