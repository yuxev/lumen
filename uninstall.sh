#!/usr/bin/env bash
# Remove Nimbus and put your desktop back the way it was.
set -uo pipefail
APP=io.github.yuxev.Nimbus
DEST="$HOME/.local/share/nimbus"

[ -x "$DEST/bin/nimbus" ] && "$DEST/bin/nimbus" restore
pkill -f "^[^ ]+ $DEST/bin/nimbus desktop\$|^[^ ]*python3[^ ]* -m nimbus desktop\$" 2>/dev/null
rm -rf "$DEST" "$HOME/.config/nimbus" "$HOME/.cache/nimbus"
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
	[ -f "$rc" ] && sed -i '/^# >>> nimbus >>>$/,/^# <<< nimbus <<<$/d' "$rc"
done
rm -f "$HOME/.config/fish/conf.d/nimbus.fish"
rm -f "$HOME/.local/bin/nimbus" "$HOME/.local/share/applications/$APP.desktop" \
	"$HOME/.local/share/icons/hicolor/scalable/apps/$APP.svg" "$HOME/.config/autostart/nimbus-desktop.desktop"
echo "Nimbus removed. (The adw-gtk3 theme in ~/.local/share/themes was left in place.)"
