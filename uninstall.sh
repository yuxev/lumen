#!/usr/bin/env bash
# Remove Lumen and put your desktop back the way it was.
set -uo pipefail
APP=io.github.yuxev.Lumen
DEST="$HOME/.local/share/lumen"

[ -x "$DEST/bin/lumen" ] && "$DEST/bin/lumen" restore
pkill -f "^[^ ]+ $DEST/bin/lumen desktop\$|^[^ ]*python3[^ ]* -m lumen desktop\$" 2>/dev/null
rm -rf "$DEST" "$HOME/.config/lumen" "$HOME/.cache/lumen"
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
	[ -f "$rc" ] && sed -i '/^# >>> lumen >>>$/,/^# <<< lumen <<<$/d' "$rc"
done
rm -f "$HOME/.config/fish/conf.d/lumen.fish"
rm -f "$HOME/.local/bin/lumen" "$HOME/.local/share/applications/$APP.desktop" \
	"$HOME/.local/share/icons/hicolor/scalable/apps/$APP.svg" "$HOME/.config/autostart/lumen-desktop.desktop"
echo "Lumen removed. (The adw-gtk3 theme in ~/.local/share/themes was left in place.)"
