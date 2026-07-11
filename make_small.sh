#find . \( -iname "*.JPG" -o -iname "*.HEIC" \) -exec convert {} -resize 30% ../$DIRNAME/{} \;

#DIRNAME=$(basename $(pwd))
DIRNAME="small"
mkdir -p "$DIRNAME"
find . -maxdepth 1 \( -iname "*.JPG" -o -iname "*.HEIC" \) | while read f; do
  base=$(basename "$f")
  out="./$DIRNAME/${base%.*}.jpg"
  convert "$f" -resize 3060x3060 -quality 90 "$out"
done
