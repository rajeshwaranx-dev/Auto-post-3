#!/usr/bin/env bash
# scripts/setup_fonts.sh
# Downloads free DejaVu fonts → assets/fonts/
set -e

DEST="assets/fonts"
mkdir -p "$DEST"

URL="https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2"

echo "Downloading DejaVu fonts..."
wget -qO /tmp/dejavu.tar.bz2 "$URL"
tar -xjf /tmp/dejavu.tar.bz2 -C /tmp/

cp /tmp/dejavu-fonts-ttf-2.37/ttf/DejaVuSans-Bold.ttf "$DEST/bold.ttf"
cp /tmp/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf      "$DEST/regular.ttf"

rm -rf /tmp/dejavu*
echo "✅ Fonts installed to $DEST/"
