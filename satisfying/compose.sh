#!/usr/bin/env bash
# Baut aus den gerenderten Einzelbildern das fertige TikTok-Video (1080x1920)
# mit Level-Beschriftung, Hook, KI-Hinweis und Abschlusskarte.
# Aufruf: compose.sh <bilder-ordner> <ausgabe.mp4>
set -euo pipefail
IN="$1"
OUT="$2"
TMP="$(mktemp -d)"
FONT=/usr/share/fonts/opentype/inter/InterDisplay-Black.otf
FONT2=/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf
SEG=4      # Sekunden pro Level
END=2.5    # Sekunden Abschlusskarte

printf '%s' "LEVEL 1: HART"      > "$TMP/l1.txt"
printf '%s' "LEVEL 2: WEICH"     > "$TMP/l2.txt"
printf '%s' "LEVEL 3: PUDDING"   > "$TMP/l3.txt"
printf '%s' "Schafft er's durch den Ring?" > "$TMP/hook.txt"
printf '%s' "3D-Animation · mit KI erstellt" > "$TMP/ki.txt"
printf '%s' "Was soll als Nächstes"  > "$TMP/e1.txt"
printf '%s' "durch den Ring?"        > "$TMP/e2.txt"
printf '%s' "Schreib's in die Kommentare"  > "$TMP/e3.txt"
printf '%s' "Die beste Idee kommt ins nächste Video" > "$TMP/e4.txt"

label() { # $1 textdatei, $2 start, $3 ende
  echo "drawtext=fontfile=$FONT:textfile=$1:fontsize=92:fontcolor=white:borderw=9:bordercolor=0x0B1433:x=(w-text_w)/2:y=230:enable='between(t,$2,$3)'"
}

VF="scale=1080:1920:flags=lanczos"
VF+=",$(label "$TMP/l1.txt" 0 $SEG)"
VF+=",$(label "$TMP/l2.txt" $SEG $((SEG*2)))"
VF+=",$(label "$TMP/l3.txt" $((SEG*2)) $((SEG*3)))"
VF+=",drawtext=fontfile=$FONT2:textfile=$TMP/hook.txt:fontsize=58:fontcolor=0xFF6A1A:borderw=6:bordercolor=0x0B1433:x=(w-text_w)/2:y=350:enable='between(t,0,2.2)'"
VF+=",drawtext=fontfile=$FONT2:textfile=$TMP/ki.txt:fontsize=30:fontcolor=white@0.8:x=(w-text_w)/2:y=1500"

ffmpeg -v error -y -framerate 30 -i "$IN/f_%04d.png" -vf "$VF" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p "$TMP/main.mp4"

EVF="drawtext=fontfile=$FONT:textfile=$TMP/e1.txt:fontsize=84:fontcolor=white:x=(w-text_w)/2:y=720"
EVF+=",drawtext=fontfile=$FONT:textfile=$TMP/e2.txt:fontsize=84:fontcolor=0xFF6A1A:x=(w-text_w)/2:y=830"
EVF+=",drawtext=fontfile=$FONT2:textfile=$TMP/e3.txt:fontsize=52:fontcolor=white:x=(w-text_w)/2:y=1010"
EVF+=",drawtext=fontfile=$FONT2:textfile=$TMP/e4.txt:fontsize=36:fontcolor=white@0.75:x=(w-text_w)/2:y=1100"
EVF+=",drawtext=fontfile=$FONT2:textfile=$TMP/ki.txt:fontsize=30:fontcolor=white@0.8:x=(w-text_w)/2:y=1500"
ffmpeg -v error -y -f lavfi -i "color=c=0x0B1433:s=1080x1920:r=30:d=$END" -vf "$EVF" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p "$TMP/end.mp4"

printf "file '%s'\nfile '%s'\n" "$TMP/main.mp4" "$TMP/end.mp4" > "$TMP/list.txt"
ffmpeg -v error -y -f concat -safe 0 -i "$TMP/list.txt" -c copy -movflags +faststart "$OUT"
rm -rf "$TMP"
echo "$OUT"
