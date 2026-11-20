#!/usr/bin/env bash
# Baut aus den gerenderten Einzelbildern das fertige TikTok-Video (1080x1920).
# Reihenfolge von weich nach hart: Level 1 = Pudding, Level 2 = weich, Level 3 = hart.
# Einblendungen nur "LEVEL 1-3" plus kurze Abschlusskarte (englisch).
# Der KI-Hinweis steht nicht im Bild, sondern wird beim Hochladen per TikTok-Schalter gesetzt.
# Aufruf: compose.sh <bilder-ordner> <ausgabe.mp4> [tonspur.wav]
set -euo pipefail
IN="$1"
OUT="$2"
AUDIO="${3:-}"
TMP="$(mktemp -d)"
FONT=/usr/share/fonts/opentype/inter/InterDisplay-Black.otf
FONT2=/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf
SEGF=120   # Bilder pro Level im Render (Reihenfolge dort: hart, weich, pudding)
SEG=4      # Sekunden pro Level
END=2.5    # Sekunden Abschlusskarte
ORDER=(3 2 1)  # Render-Segmente in Video-Reihenfolge: pudding, weich, hart

# Bilder in neuer Reihenfolge durchnummerieren
mkdir "$TMP/seq"
n=1
for seg in "${ORDER[@]}"; do
  for ((i = 1; i <= SEGF; i++)); do
    src=$(printf "%s/f_%04d.png" "$IN" $(((seg - 1) * SEGF + i)))
    ln -s "$src" "$(printf "%s/seq/f_%04d.png" "$TMP" $n)"
    n=$((n + 1))
  done
done

for k in 1 2 3; do printf '%s' "LEVEL $k" > "$TMP/l$k.txt"; done
printf '%s' "What goes"     > "$TMP/e1.txt"
printf '%s' "through next?" > "$TMP/e2.txt"
printf '%s' "Comment below" > "$TMP/e3.txt"

label() { # $1 textdatei, $2 start, $3 ende
  echo "drawtext=fontfile=$FONT:textfile=$1:fontsize=110:fontcolor=white:borderw=10:bordercolor=0x0B1433:x=(w-text_w)/2:y=230:enable='between(t,$2,$3)'"
}

VF="scale=1080:1920:flags=lanczos"
VF+=",$(label "$TMP/l1.txt" 0 $SEG)"
VF+=",$(label "$TMP/l2.txt" $SEG $((SEG*2)))"
VF+=",$(label "$TMP/l3.txt" $((SEG*2)) $((SEG*3)))"

ffmpeg -v error -y -framerate 30 -i "$TMP/seq/f_%04d.png" -vf "$VF" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p "$TMP/main.mp4"

EVF="drawtext=fontfile=$FONT:textfile=$TMP/e1.txt:fontsize=100:fontcolor=white:x=(w-text_w)/2:y=720"
EVF+=",drawtext=fontfile=$FONT:textfile=$TMP/e2.txt:fontsize=100:fontcolor=0xFF6A1A:x=(w-text_w)/2:y=845"
EVF+=",drawtext=fontfile=$FONT2:textfile=$TMP/e3.txt:fontsize=56:fontcolor=white@0.85:x=(w-text_w)/2:y=1030"
ffmpeg -v error -y -f lavfi -i "color=c=0x0B1433:s=1080x1920:r=30:d=$END" -vf "$EVF" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p "$TMP/end.mp4"

printf "file '%s'\nfile '%s'\n" "$TMP/main.mp4" "$TMP/end.mp4" > "$TMP/list.txt"
if [ -n "$AUDIO" ]; then
  ffmpeg -v error -y -f concat -safe 0 -i "$TMP/list.txt" -i "$AUDIO" \
    -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"
else
  ffmpeg -v error -y -f concat -safe 0 -i "$TMP/list.txt" -c copy -movflags +faststart "$OUT"
fi
rm -rf "$TMP"
echo "$OUT"
