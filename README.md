# Nimbus

Pick a wallpaper and your whole desktop takes its colours.

![Clicking wallpapers in Nimbus: the desktop, the app and Calculator recolour to match each one](docs/demo.gif)

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
curl -fsSL https://raw.githubusercontent.com/yuxev/nimbus/main/get.sh | bash
```

Run the same line again to update. Later, open **Nimbus** from your apps (press Super and
type *wallpaper*) or run `nimbus`.

Or from a clone:

```sh
git clone https://github.com/yuxev/nimbus.git
cd nimbus
./install.sh
```

## How to use it

<img src="docs/window.png" alt="The Nimbus window" width="560">

1. **Pick a folder.** The app comes with 16 wallpapers to start with;
   *Change folder…* points it at your own pictures and videos instead.
2. **Click a wallpaper.** The desktop changes and every open app takes its colours within a second.
   You can also drop a picture onto the window, or use *Open a file…*.
3. **Choose light, dark or auto** under *Colours*. Auto follows your system's style (Settings → Appearance).
4. **Optional:** a new random wallpaper every few hours, see-through windows, and *Keep screen awake*
   while you read or watch something.

To undo everything, open the menu (⋮) and choose *Restore original look*.

## Your own style

Write your own style in `~/.config/gtk-3.0/gtk.css` and `gtk-4.0/gtk.css`. Nimbus only adds one
line at the top of the GTK 4 file and keeps everything else. Use these colours there and your style follows
every wallpaper:

| Name | What it is |
|---|---|
| `@nimbus_paper`, `@nimbus_paper2`, `@nimbus_sheet` | backgrounds: window, header bars, content |
| `@nimbus_ink`, `@nimbus_muted` | text, secondary text |
| `@nimbus_accent`, `@nimbus_accent_text`, `@nimbus_on_accent` | the accent, accent-coloured text, text on the accent |
| `@nimbus_shadow` | a hard shadow colour (ink by day, black at night) |

For example, sharp corners with an accent shadow under every window:

```css
* { border-radius: 0; }
window.csd { box-shadow: 0 0 0 2px @nimbus_ink, 5px 5px 0 1px @nimbus_accent; }
```

## Recolour other tools (hooks)

After every recolour, Nimbus runs each executable file in `~/.config/nimbus/hooks/`
(in the background, in name order). The colours for the current mode are in environment variables:

| Variable | Value |
|---|---|
| `NIMBUS_MODE` | `light` or `dark` |
| `NIMBUS_PAPER`, `NIMBUS_PAPER2`, `NIMBUS_SHEET`, `NIMBUS_INK`, `NIMBUS_MUTED` | backgrounds and text, as `#RRGGBB` |
| `NIMBUS_ACCENT`, `NIMBUS_ACCENT_TEXT`, `NIMBUS_ON_ACCENT` | the accent colours |
| `NIMBUS_ANSI_0` … `NIMBUS_ANSI_15` | a 16-colour terminal palette |
| `NIMBUS_STATE` | path to `state.json`, with both the light and dark palettes |

For example, `~/.config/nimbus/hooks/kitty` (made executable with `chmod +x`):

```sh
#!/bin/sh
printf 'background %s\nforeground %s\ncursor %s\n' "$NIMBUS_PAPER" "$NIMBUS_INK" "$NIMBUS_ACCENT" > ~/.config/kitty/wallpaper.conf
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
leave it. Hide it with `nimbus logtime off`.

## Command line

```
nimbus                  open the window
nimbus set FILE         use a picture or video
nimbus next             a random different one from your folder
nimbus light|dark|auto  colour mode
nimbus logtime          today's and this month's logtime as 1337 counts it, in the terminal
nimbus logtime on|off    show or hide the desktop card
nimbus logtime login LOGIN   follow another login than the one you're signed in with
nimbus awake [MINUTES|on|off]   keep your session active so it doesn't lock (default 60 minutes)
nimbus guard [off]               lock the screen on the first key or mouse move (3 s to let go first)
nimbus stop             stop everything (stays off after logging in again); nothing is uninstalled
nimbus start            start it again (opening the app does too)
nimbus restore          undo everything
```

The installer adds a `nimbus` alias to bash, zsh and fish, so the command works in every new
terminal. In the terminal you installed from, run `source ~/.bashrc` (or `~/.zshrc`) first.

## Uninstall

```sh
./uninstall.sh
```

It restores your original look first, then removes the app.

## How it works

| Part | What it does |
|---|---|
| `nimbus/palette.py` | Reads the picture at a tiny size and picks an accent colour (the picture's most vivid colour that stands out) plus neutrals tinted with its overall colour, in a light and a dark set. |
| `nimbus/core.py` | Applies them: a small GTK theme ("Nimbus A"/"B" in `~/.local/share/themes`, adw-gtk3 underneath plus your colours), the light/dark setting and a GNOME Terminal profile. Saves your original settings first. GTK only re-reads a theme when its name changes, so each recolour flips between the two identical copies and open apps restyle live. |
| `nimbus/desktop.py` | A small helper started at login. GNOME's own wallpaper is locked at 42, so it draws the wallpaper in a desktop window behind everything. Pictures cost almost nothing once drawn. Videos play through VLC and pause when a window is maximised or the screen is locked. It also handles the rotation timer, follows the system's light/dark switch in auto mode, and keeps the session active while *Keep screen awake* is on (GNOME's idle inhibitor, plus a 1-pixel pointer nudge every 50 s, since some locks only count real input). |
| `nimbus/app.py` | The window (GTK 4 + libadwaita). |
| `nimbus/logtime.py` | Your logtime: reads 1337's hours every 5 minutes, adds the session you're in, and draws the desktop card (GTK 3), above the desktop icons, taking the pointer only on the card. |

Everything it writes lives in `~/.config/nimbus`, `~/.cache/nimbus` and
`~/.local/share/nimbus`.

Older GTK 3 apps (Files, Terminal…) take the colours through the
[adw-gtk3](https://github.com/lassekongo83/adw-gtk3) theme, which `install.sh` downloads into
`~/.local/share/themes` if you don't have it.

## Limits

- Open GTK 3 apps (Files, Terminal, Calculator…) and the Nimbus window recolour instantly.
  Other libadwaita apps (Settings, Text Editor…) only read their colours when they start, so they change
  the next time you open them.

- X11 sessions only (the default at 42).
- Videos need VLC and use more memory than pictures (about 75–130 MB while playing).
