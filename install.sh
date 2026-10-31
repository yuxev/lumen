#!/usr/bin/env bash
# Install Lumen for the current user (no sudo needed). Run it again to update.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

APP=io.github.yuxev.Lumen
DEST="$HOME/.local/share/lumen"
ADW_GTK3=v6.5   # GTK 3 theme that lets older apps (Files, Terminal…) take the new colours

say() { printf '\033[1m%s\033[0m\n' "$*"; }

# --- what the app needs -------------------------------------------------------------
# A Python that can load GTK 4 and libadwaita. Ubuntu's own /usr/bin/python3 can; a python3 from
# Homebrew, conda, pyenv or a virtualenv usually can't, even when it comes first in PATH.
has_gtk() {
	# the window (GTK 4) and the desktop helper (GDK 3 + cairo) run as separate processes: check each
	"$1" - 2>/dev/null <<'PY' && "$1" - 2>/dev/null <<'PY2'
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw
PY
import gi, cairo
gi.require_version("Gdk", "3.0"); gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf
PY2
}
PYTHON=
tried=()
for candidate in /usr/bin/python3 "$(command -v python3 || true)" /usr/local/bin/python3; do
	[ -n "$candidate" ] && [ -x "$candidate" ] || continue
	tried+=("$candidate")
	if has_gtk "$candidate"; then PYTHON=$candidate; break; fi
done
if [ -z "$PYTHON" ]; then
	echo "Lumen needs a Python with GTK 4 and libadwaita, and none was found." >&2
	echo "Tried: ${tried[*]:-no python3 at all}" >&2
	echo "On Ubuntu these come from the packages python3-gi, python3-gi-cairo, gir1.2-gtk-4.0 and gir1.2-adw-1." >&2
	exit 1
fi
if [ "${XDG_SESSION_TYPE:-x11}" != x11 ]; then
	echo "Note: you're on $XDG_SESSION_TYPE; the wallpaper is only drawn in X11 (Xorg) sessions." >&2
fi
command -v cvlc >/dev/null || echo "Note: VLC isn't installed, so video wallpapers won't play (pictures work)." >&2

# an older home-made setup also draws the desktop and writes gtk.css; two would fight
if [ -f "$HOME/.config/autostart/studio-wallpaper.desktop" ]; then
	echo "Found the older 'studio' setup. Run 'studio reset' first so the two don't fight over the desktop." >&2
	exit 1
fi

# --- the app ------------------------------------------------------------------------
say "Installing to $DEST"
# stop this install's background helper (and one started by an older version) before replacing it
HELPER="^[^ ]+ $DEST/bin/lumen desktop\$|^[^ ]*python3[^ ]* -m lumen desktop\$"
pkill -f "$HELPER" 2>/dev/null || true
for _ in $(seq 50); do pgrep -f "$HELPER" >/dev/null || break; sleep 0.1; done   # let it let go first
rm -rf "$DEST"
mkdir -p "$DEST" "$HOME/.local/bin" "$HOME/.local/share/applications" \
	"$HOME/.local/share/icons/hicolor/scalable/apps" "$HOME/.config/autostart"
cp -r lumen bin wallpapers uninstall.sh "$DEST/"   # uninstall.sh: for `lumen uninstall`
find "$DEST" -name __pycache__ -prune -exec rm -rf {} +
# always run with the Python that has GTK, whatever python3 comes first in PATH later
sed -i "1s|^#!.*|#!$PYTHON|" "$DEST/bin/lumen"
ln -sf "$DEST/bin/lumen" "$HOME/.local/bin/lumen"
cp data/$APP.svg "$HOME/.local/share/icons/hicolor/scalable/apps/$APP.svg"

cat >"$HOME/.local/share/applications/$APP.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Lumen
Comment=Change your wallpaper and recolour your desktop to match
Exec=$DEST/bin/lumen
Icon=$APP
Categories=Settings;DesktopSettings;GTK;
Keywords=wallpaper;background;theme;colour;color;
StartupNotify=true
DESKTOP

# the helper that draws the wallpaper, every time you log in
cat >"$HOME/.config/autostart/lumen-desktop.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Lumen (desktop)
Comment=Draws your Lumen wallpaper behind every window
Exec=$DEST/bin/lumen desktop
NoDisplay=true
X-GNOME-Autostart-enabled=true
DESKTOP

# the lumen command in every new terminal, even where ~/.local/bin isn't on PATH
# (zsh never adds it, and bash only does at login if the folder already existed)
MARK_BEGIN="# >>> lumen >>>"
MARK_END="# <<< lumen <<<"
add_alias() {
	local rc=$1
	[ -f "$rc" ] && sed -i "/^$MARK_BEGIN\$/,/^$MARK_END\$/d" "$rc"
	[ -s "$rc" ] && [ -n "$(tail -c1 "$rc")" ] && echo >>"$rc"   # don't glue onto a last line without a newline
	printf '%s\nalias lumen="%s"\n%s\n' "$MARK_BEGIN" "$DEST/bin/lumen" "$MARK_END" >>"$rc"
}
add_alias "$HOME/.bashrc"
if [ -f "$HOME/.zshrc" ] || command -v zsh >/dev/null; then add_alias "$HOME/.zshrc"; fi
if command -v fish >/dev/null; then
	mkdir -p "$HOME/.config/fish/conf.d"
	printf 'alias lumen "%s"\n' "$DEST/bin/lumen" >"$HOME/.config/fish/conf.d/lumen.fish"
fi

# --- GTK 3 theme --------------------------------------------------------------------
if [ ! -d "$HOME/.local/share/themes/adw-gtk3" ] && [ ! -d /usr/share/themes/adw-gtk3 ]; then
	say "Downloading the adw-gtk3 theme ($ADW_GTK3)"
	mkdir -p "$HOME/.local/share/themes"
	if curl -fsSL "https://github.com/lassekongo83/adw-gtk3/releases/download/$ADW_GTK3/adw-gtk3${ADW_GTK3}.tar.xz" |
		tar -xJ -C "$HOME/.local/share/themes"; then
		:
	else
		echo "Couldn't download adw-gtk3; newer apps will still be recoloured, older ones won't." >&2
	fi
fi

update-desktop-database -q "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# start the helper now, so you don't have to log out
(setsid "$DEST/bin/lumen" desktop >/dev/null 2>&1 &)

say "Done (using $PYTHON). Open “Lumen” from your apps, or run: lumen"
echo "The lumen command works in new terminals (in this one, run: source ~/.bashrc, or ~/.zshrc)."
