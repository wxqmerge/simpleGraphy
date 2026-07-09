#find . \( -iname "*.JPG" -o -iname "*.HEIC" \) -exec convert {} -resize 30% ../$DIRNAME/{} \;

DIRNAME=$(basename $(pwd))
mkdir -p "$DIRNAME"
find . -maxdepth 1 \( -iname "*.JPG" -o -iname "*.HEIC" \) | while read f; do
  out="./$DIRNAME/$(basename "${f%.HEIC}.jpg")"
  convert "$f" -resize 3060x3060 -quality 90 "$out"
done
