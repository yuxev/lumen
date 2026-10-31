# Lumen

Pick a wallpaper and your whole desktop takes its colours.

![Clicking wallpapers in Lumen: the desktop, the app and Calculator recolour to match each one](docs/demo.gif)

*Picking a wallpaper recolours the desktop and every open app on the spot. [Full-quality video](docs/demo.webm).*

- **Wallpapers:** pictures or looping videos, chosen from a folder of yours, with an optional new one every few hours.
- **Colours:** apps and GNOME Terminal are recoloured to match, in light, dark, or auto (follows your system's light/dark style).
- **One click back:** *Restore original look* puts every setting back the way it was.

Made for the 42 iMacs (Ubuntu 22.04, GNOME, X11), where the normal desktop picture setting is locked.
No sudo needed.

![The same wallpaper in light mode (left) and dark mode (right)](docs/light-dark.png)

*One wallpaper, two looks: light and dark.*

## Install

Paste this in a terminal. It downloads, installs and opens the app (no sudo needed):

```sh
curl -fsSL https://raw.githubusercontent.com/yuxev/lumen/main/get.sh | bash
```

Run the same line again to update. Later, open **Lumen** from your apps (press Super and
type *wallpaper*) or run `lumen`.

Or from a clone:

```sh
git clone https://github.com/yuxev/lumen.git
cd lumen
./install.sh
```

## How to use it

<img src="docs/window.png" alt="The Lumen window" width="560">

1. **Pick a folder.** The app comes with 16 wallpapers to start with;
   *Change folder…* points it at your own pictures and videos instead.
2. **Click a wallpaper.** The desktop changes and every open app takes its colours within a second.
   You can also drop a picture onto the window, or use *Open a file…*.
3. **Choose light, dark or auto** under *Colours*. Auto follows your system's style (Settings → Appearance).
4. **Optional:** a new random wallpaper every few hours, and see-through windows.

To undo everything, open the menu (⋮) and choose *Restore original look*.

## Your own style

Write your own style in `~/.config/gtk-3.0/gtk.css` and `gtk-4.0/gtk.css`. Lumen only adds one
line at the top of the GTK 4 file and keeps everything else. Use these colours there and your style follows
every wallpaper:

| Name | What it is |
|---|---|
| `@lumen_paper`, `@lumen_paper2`, `@lumen_sheet` | backgrounds: window, header bars, content |
| `@lumen_ink`, `@lumen_muted` | text, secondary text |
| `@lumen_accent`, `@lumen_accent_text`, `@lumen_on_accent` | the accent, accent-coloured text, text on the accent |
| `@lumen_shadow` | a hard shadow colour (ink by day, black at night) |

For example, sharp corners with an accent shadow under every window:

```css
* { border-radius: 0; }
window.csd { box-shadow: 0 0 0 2px @lumen_ink, 5px 5px 0 1px @lumen_accent; }
```

## Recolour other tools (hooks)

After every recolour, Lumen runs each executable file in `~/.config/lumen/hooks/`
(in the background, in name order). The colours for the current mode are in environment variables:

| Variable | Value |
|---|---|
| `LUMEN_MODE` | `light` or `dark` |
| `LUMEN_PAPER`, `LUMEN_PAPER2`, `LUMEN_SHEET`, `LUMEN_INK`, `LUMEN_MUTED` | backgrounds and text, as `#RRGGBB` |
| `LUMEN_ACCENT`, `LUMEN_ACCENT_TEXT`, `LUMEN_ON_ACCENT` | the accent colours |
| `LUMEN_ANSI_0` … `LUMEN_ANSI_15` | a 16-colour terminal palette |
| `LUMEN_STATE` | path to `state.json`, with both the light and dark palettes |

For example, `~/.config/lumen/hooks/kitty` (made executable with `chmod +x`):

```sh
#!/bin/sh
printf 'background %s\nforeground %s\ncursor %s\n' "$LUMEN_PAPER" "$LUMEN_INK" "$LUMEN_ACCENT" > ~/.config/kitty/wallpaper.conf
pkill -USR1 kitty
```

## Logtime on the desktop

Shows your logtime on the desktop, counted the way 1337 counts it for the scholarship: the hours come
from 1337's own logtime service ([logtime-med.1337.ma](https://logtime-med.1337.ma)), so there's no
key and no setup. It uses the login you're signed in with.

The card is small: **today** and **this month** (the 28th to the 27th of the next month, out of 120h),
both ticking live, and the month as one cell per hour. 1337 only counts a session once you log out,
all of it on the day it began; the card adds the session you're in now the same way, so it always
shows what 1337 will. Double-click it for the calendar (hover a day for its hours), what's left, the
hours per day you need, your pace and when you'll reach 120h. Drag it anywhere; it stays where you
leave it. Hide it with `lumen logtime off`.

## Command line

```
lumen                         open the window
lumen set FILE                use a picture or video
lumen next                    a random different one from your folder
lumen light|dark|auto         colour mode
lumen logtime                 today's and this month's logtime as 1337 counts it, in the terminal
lumen logtime on|off          show or hide the desktop card
lumen logtime login LOGIN     follow another login than the one you're signed in with
lumen stop                    stop everything (stays off after logging in again); nothing is uninstalled
lumen start                   start it again (opening the app does too)
lumen restore                 undo everything
lumen uninstall               restore your original look, then remove Lumen
```

The installer adds a `lumen` alias to bash, zsh and fish, so the command works in every new
terminal. In the terminal you installed from, run `source ~/.bashrc` (or `~/.zshrc`) first.

## Uninstall

```sh
lumen uninstall
```

It restores your original look first, then removes the app. (From a clone, `./uninstall.sh` does the same.)

## How it works

| Part | What it does |
|---|---|
| `lumen/palette.py` | Reads the picture at a tiny size and picks an accent colour (the picture's most vivid colour that stands out) plus neutrals tinted with its overall colour, in a light and a dark set. |
| `lumen/core.py` | Applies them: a small GTK theme ("Lumen A"/"B" in `~/.local/share/themes`, adw-gtk3 underneath plus your colours), the light/dark setting and a GNOME Terminal profile. Saves your original settings first. GTK only re-reads a theme when its name changes, so each recolour flips between the two identical copies and open apps restyle live. |
| `lumen/desktop.py` | A small helper started at login. GNOME's own wallpaper is locked at 42, so it draws the wallpaper in a desktop window behind everything. Pictures cost almost nothing once drawn. Videos play through VLC and pause when a window is maximised or the screen is locked. It also handles the rotation timer and follows the system's light/dark switch in auto mode. |
| `lumen/app.py` | The window (GTK 4 + libadwaita). |
| `lumen/logtime.py` | Your logtime: reads 1337's hours every 5 minutes, adds the session you're in, and draws the desktop card (GTK 3), above the desktop icons, taking the pointer only on the card. |

Everything it writes lives in `~/.config/lumen`, `~/.cache/lumen` and
`~/.local/share/lumen`.

Older GTK 3 apps (Files, Terminal…) take the colours through the
[adw-gtk3](https://github.com/lassekongo83/adw-gtk3) theme, which `install.sh` downloads into
`~/.local/share/themes` if you don't have it.

## Limits

- Open GTK 3 apps (Files, Terminal, Calculator…) and the Lumen window recolour instantly.
  Other libadwaita apps (Settings, Text Editor…) only read their colours when they start, so they change
  the next time you open them.

- X11 sessions only (the default at 42).
- Videos need VLC and use more memory than pictures (about 75–130 MB while playing).
