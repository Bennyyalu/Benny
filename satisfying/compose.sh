#!/usr/bin/env bash
# Baut aus den gerenderten Einzelbildern das fertige TikTok-Video (1080x1920)
# mit kurzen englischen Einblendungen und Abschlusskarte.
# Der KI-Hinweis steht nicht im Bild, sondern wird beim Hochladen per TikTok-Schalter gesetzt.
# Aufruf: compose.sh <bilder-ordner> <ausgabe.mp4>
set -euo pipefail
IN="$1"
OUT="$2"
TMP="$(mktemp -d)"
FONT=/usr/share/fonts/opentype/inter/InterDisplay-Black.otf
FONT2=/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf
SEG=4      # Sekunden pro Level
END=2.5    # Sekunden Abschlusskarte

printf '%s' "HARD"          > "$TMP/l1.txt"
printf '%s' "SOFT"          > "$TMP/l2.txt"
printf '%s' "JELLY"         > "$TMP/l3.txt"
printf '%s' "Will it fit?"  > "$TMP/hook.txt"
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
VF+=",drawtext=fontfile=$FONT2:textfile=$TMP/hook.txt:fontsize=64:fontcolor=0xFF6A1A:borderw=6:bordercolor=0x0B1433:x=(w-text_w)/2:y=370:enable='between(t,0,2.2)'"

ffmpeg -v error -y -framerate 30 -i "$IN/f_%04d.png" -vf "$VF" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p "$TMP/main.mp4"

EVF="drawtext=fontfile=$FONT:textfile=$TMP/e1.txt:fontsize=100:fontcolor=white:x=(w-text_w)/2:y=720"
EVF+=",drawtext=fontfile=$FONT:textfile=$TMP/e2.txt:fontsize=100:fontcolor=0xFF6A1A:x=(w-text_w)/2:y=845"
EVF+=",drawtext=fontfile=$FONT2:textfile=$TMP/e3.txt:fontsize=56:fontcolor=white@0.85:x=(w-text_w)/2:y=1030"
ffmpeg -v error -y -f lavfi -i "color=c=0x0B1433:s=1080x1920:r=30:d=$END" -vf "$EVF" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p "$TMP/end.mp4"

printf "file '%s'\nfile '%s'\n" "$TMP/main.mp4" "$TMP/end.mp4" > "$TMP/list.txt"
ffmpeg -v error -y -f concat -safe 0 -i "$TMP/list.txt" -c copy -movflags +faststart "$OUT"
rm -rf "$TMP"
echo "$OUT"
