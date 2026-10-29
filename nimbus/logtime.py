"""Logtime: your hours at 1337, counted the way 1337 counts them for the scholarship.

The numbers come from 1337's own logtime service (logtime-med.1337.ma, the one its staff check),
which needs no key: it counts a session once you log out, all of it on the day it began, and gives
whole hours. The session you're in now isn't in there yet, so the card shows it apart, ticking live,
from when this desktop session began.

The desktop helper shows it on the desktop as a small card: this session, the scholarship month
(the 28th to the 27th of the next month) as a calendar with each day shaded by its hours, and how
far you are from the 120h goal.
"""
import concurrent.futures
import datetime
import getpass
import json
import os
import socket
import threading
import urllib.error
import urllib.request

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GdkX11, Gio, GLib, Gtk, Pango, PangoCairo  # noqa: E402

from . import core, palette  # noqa: E402

API = "https://logtime-med.1337.ma/api/get_log"
PLACE = os.path.join(core.CONFIG_DIR, "logtime-place.json")    # where the card was dragged to
RETRY = 60               # seconds before asking 1337 again when it couldn't be reached
FULL_DAY = 10 * 3600     # a day with this much time or more gets the strongest shade
GOAL = 120               # hours to log in a period to keep the scholarship
USER_AGENT = "nimbus (+https://github.com/yuxev/nimbus)"


class ApiError(Exception):
    pass


def source():
    """1337's logtime for the login you're signed in with (at 1337 it's your 42 login)."""
    return Campus(core.load_config().get("logtime_login") or getpass.getuser())


class Campus:
    def __init__(self, login):
        self.login = login
        self.key = ("1337", login)

    def hours(self, first, last):
        """The whole hours 1337 counts from day `first` to day `last`, both included."""
        body = json.dumps({"login": self.login, "startDate": f"{first}T00:00:00.000Z",
                           "endDate": f"{last}T00:00:00.000Z"}).encode()
        req = urllib.request.Request(API, body, {"Content-Type": "application/json", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=20) as reply:
                members = json.load(reply).get("hydra:member") or []
        except urllib.error.HTTPError as e:
            raise ApiError(f"1337 logtime answered {e.code}") from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise ApiError("can't reach logtime-med.1337.ma") from e
        return int(members[0].get("totalHours") or 0) if members else 0

    def month(self, today):
        """(the period's total, {day: hours}) up to today. 1337 rounds the total once, so it's read
        as one figure, not added up from the days."""
        first, end = period(today)
        days = [first + datetime.timedelta(days=i) for i in range((today - first).days + 1)]
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            total = pool.submit(self.hours, first, end - datetime.timedelta(days=1))
            return total.result(), dict(zip(days, pool.map(lambda d: self.hours(d, d), days)))


def logged_in_since():
    """When this desktop session began: the session that's counting now (None if unknown)."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)

        def get(path, iface, name):
            return bus.call_sync("org.freedesktop.login1", path, "org.freedesktop.DBus.Properties", "Get",
                                 GLib.Variant("(ss)", (iface, name)), None, 0, 2000, None).unpack()[0]

        user = bus.call_sync("org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
                             "GetUser", GLib.Variant("(u)", (os.getuid(),)), None, 0, 2000, None).unpack()[0]
        _id, session = get(user, "org.freedesktop.login1.User", "Display")
        stamp = get(session, "org.freedesktop.login1.Session", "Timestamp")
    except GLib.Error:
        return None
    return datetime.datetime.fromtimestamp(stamp / 1e6).astimezone() if stamp else None


# --- the maths -----------------------------------------------------------------------

def period(today):
    """The scholarship month a date falls in: (the 28th, the 28th of the next month), so it runs
    from the 28th to the 27th."""
    if today.day >= 28:
        first = today.replace(day=28)
    else:
        first = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=28)
    return first, (first.replace(day=1) + datetime.timedelta(days=32)).replace(day=28)


def midnight(day):
    return datetime.datetime.combine(day, datetime.time()).astimezone()


def hours(seconds):
    m = int(seconds) // 60
    return f"{m // 60}h {m % 60:02d}m"


def span(today):
    first, end = period(today)
    return f"{first.day} {first:%b} – {(end - datetime.timedelta(days=1)).day} {end:%b}"


def summary(total, days, today):
    """One line for the terminal."""
    first, end = period(today)
    left = max(GOAL - total, 0)
    goal = f"{left}h left, {hours(left * 3600 / (end - today).days)}/day" if left else "goal reached"
    return f"Today {days.get(today, 0)}h · {span(today)}: {total}h of {GOAL}h ({goal}) · as 1337 counts it"


# --- the card on the desktop --------------------------------------------------------

PAD, CELL, ROW, MARGIN = 16, 38, 30, 24
EDGE = 4                # the hard shadow under the right and bottom edges, like the app's windows
TITLE = 30              # the title strip
WIDTH = 7 * CELL + 2 * PAD
METER = 40, 3           # the goal as hour cells: 40 a row (in tens), 3 rows = 120h
FROST = 20              # the glass blurs the wallpaper by drawing it this many times smaller, then stretched
FALLBACK = {"paper": "#EEEEEE", "paper2": "#DDDDDD", "sheet": "#F7F7F7", "ink": "#1A1A1A",
            "muted": "#5A5A5A", "accent": "#14B8B0", "accent_text": "#0E8C86", "on_accent": "#FFFFFF"}


class Card(Gtk.Window):
    """This session, the scholarship month's calendar and how far you are from the goal, as 1337
    counts them, drawn on the desktop above the wallpaper.

    It's a window of its own, below all the others; drag it anywhere (the window manager moves it,
    like a window by its title bar). Hover a day for its hours; double-click for the details. It
    never takes the focus, and stays out of the window switcher."""

    def __init__(self, api, on_shown):
        super().__init__(type=Gtk.WindowType.TOPLEVEL, title="nimbus logtime")
        self.api = api                 # a Campus: 1337's logtime
        self.on_shown = on_shown
        self.total, self.days = None, {}          # 1337's hours: the period's, and each day's
        self.error, self.loaded = None, None      # loaded: the period's first day
        self.since = logged_in_since()            # this session: 1337 adds it once you log out
        self.host = socket.gethostname().split(".")[0]
        self.fetching = False
        self.colours, self.glass = None, False
        self.backdrop, self.shown = None, None    # the wallpaper, tiny, for the frosted glass; from which file
        self.marks = None                         # while drawing: the rows that hold text (top, bottom)
        self.height = 560                         # the card's, worked out again on every draw
        self.pos, self.size = (0, 0), (0, 0)      # the card's place on the screen, shadow included
        self.press = None                         # where a click began, until it turns into a drag
        self.saving = 0
        self.placed = False                       # back where it was left (the window manager places it first)
        self.hover, self.cells = None, []         # the day under the pointer; the drawn day cells
        saved = core._read_json(PLACE, None)
        self.expanded = bool(saved.get("expanded")) if isinstance(saved, dict) else False   # double-click
        self.cursor = None
        mono = Gio.Settings.new("org.gnome.desktop.interface").get_string("monospace-font-name")
        self.font = (mono or "Monospace 11").rsplit(" ", 1)[0]

        # an ordinary window kept below all others: the window manager moves those smoothly
        # (desktop windows it barely moves), and it stays on top of the desktop and its icons
        self.set_keep_below(True)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.stick()
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self.draw)
        self.connect("map-event", self.mapped)
        self.connect("configure-event", self.moved)
        self.connect("button-press-event", self.pressed)
        self.connect("motion-notify-event", self.pointer)
        self.connect("button-release-event", self.released)
        self.connect("leave-notify-event", self.left)
        self.get_screen().connect("monitors-changed", lambda *_: self.place())

        self.recolour()
        self.place()
        self.move(*self.pos)
        self.show()
        self.shape()
        self.fetch()
        self.timers = [GLib.timeout_add_seconds(1, self.tick)]

    def mapped(self, *_):
        self.on_shown()
        GLib.timeout_add(200, self.restore)
        return False

    def restore(self):
        """Back where it was left, once the window manager has placed the new window its own way."""
        self.placed = True
        self.put(*self.pos)
        return False

    def moved(self, *_):
        """Moved, by a drag or the window manager: draw the glass for its new place, and remember it."""
        where = tuple(self.get_window().get_origin()[1:])      # on the screen (the event's is in its frame)
        if self.placed and where != self.pos:
            self.pos = where
            if self.saving:
                GLib.source_remove(self.saving)
            self.saving = GLib.timeout_add(500, self.save)
        self.shape()
        self.queue_draw()
        return False

    def xid(self):
        window = self.get_window()
        return GdkX11.X11Window.get_xid(window) if window is not None else None

    def close(self):
        for t in self.timers:
            GLib.source_remove(t)
        self.destroy()

    def recolour(self):
        """The wallpaper's colours, in the current light/dark mode, and frosted glass over the
        wallpaper when glass is on."""
        state = core.load_state()
        self.colours = state.get("palette", {}).get(state.get("mode") or core.effective_mode())
        self.glass = core.load_config()["glass"]
        picture = state.get("still") or state.get("wallpaper")      # a video's still frame
        if not self.glass or not picture or not os.path.exists(picture):
            self.backdrop, self.shown = None, None
        elif picture != self.shown:
            from .desktop import render_cover
            sw, sh = screen_size()
            try:
                self.backdrop = render_cover(picture, max(sw // FROST, 1), max(sh // FROST, 1))
            except GLib.Error:
                self.backdrop = None
            self.shown = picture
        self.redraw()

    def frost(self, cr, width, height):
        """The wallpaper under the card, blurred: a copy a twentieth of the size, stretched back
        smoothly, so only its colours and light come through and the text stays easy to read."""
        sw, sh = screen_size()
        cr.save()
        cr.rectangle(0, 0, width, height)
        cr.clip()
        cr.translate(-self.pos[0], -self.pos[1])
        cr.scale(sw / self.backdrop.get_width(), sh / self.backdrop.get_height())
        cr.set_source_surface(self.backdrop, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_GOOD)
        cr.get_source().set_extend(cairo.EXTEND_PAD)
        cr.paint()
        cr.restore()

    def weeks(self, today):
        """The calendar's rows: whole weeks, Sunday first, from the period's first day to its last."""
        first, end = period(today)
        day = first - datetime.timedelta(days=(first.weekday() + 1) % 7)
        rows = []
        while day < end:
            rows.append([day + datetime.timedelta(days=i) for i in range(7)])
            day += datetime.timedelta(days=7)
        return rows

    def place(self):
        """Put the card where it was dragged to, kept on screen; at first top right, under the top
        bar (the desktop icons start top left)."""
        saved = core._read_json(PLACE, None)
        if isinstance(saved, dict) and "x" in saved and "y" in saved:
            x, y = saved["x"], saved["y"]
        else:
            display = Gdk.Display.get_default()
            area = (display.get_primary_monitor() or display.get_monitor(0)).get_workarea()
            x, y = area.x + area.width - WIDTH - EDGE - MARGIN, area.y + MARGIN
        self.size = (WIDTH + EDGE, self.height + EDGE)
        self.set_size_request(*self.size)
        self.resize(*self.size)
        self.put(x, y)

    def put(self, x, y):
        """Move the card to (x, y) on the screen, keeping all of it on screen."""
        sw, sh = screen_size()
        w, h = self.size
        self.pos = (max(0, min(int(x), sw - w)), max(0, min(int(y), sh - h)))
        if self.get_window() is not None:
            self.get_window().move(*self.pos)

    def local(self, x, y):
        """A point on the screen, in the window (which the window manager keeps where it likes)."""
        window = self.get_window()
        ox, oy = window.get_origin()[1:] if window is not None else (0, 0)
        return x - ox, y - oy

    def shape(self):
        """Take the pointer on the card only; everywhere else it falls through."""
        x, y = self.local(*self.pos)
        self.input_shape_combine_region(cairo.Region(cairo.RectangleInt(x, y, WIDTH, self.height)))

    # --- the pointer ---------------------------------------------------------------

    def point(self, name):
        if name != self.cursor and self.get_window() is not None:
            self.cursor = name
            self.get_window().set_cursor(Gdk.Cursor.new_from_name(self.get_display(), name))

    def pressed(self, _widget, event):
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:     # open or close the details
            self.press = None
            self.expanded = not self.expanded
            self.hover, self.cells = None, []
            self.save()
            self.redraw()
        elif event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS:
            self.press = (event.x_root, event.y_root)
        return True

    def pointer(self, _widget, event):
        if self.press is not None and event.state & Gdk.ModifierType.BUTTON1_MASK:
            if abs(event.x_root - self.press[0]) + abs(event.y_root - self.press[1]) > 4:   # a drag, not a click
                self.press = None
                self.hover = None
                self.redraw()
                self.begin_move_drag(1, int(event.x_root), int(event.y_root), event.time)
            return True
        x, y = event.x_root - self.pos[0], event.y_root - self.pos[1]
        hover = next((day for cx, cy, day in self.cells if cx <= x < cx + CELL and cy <= y < cy + ROW), None)
        if hover != self.hover:
            self.hover = hover
            self.redraw()
        self.point("default" if hover else "grab")
        return True

    def released(self, _widget, event):
        if event.button == 1:
            self.press = None
        return True

    def save(self):
        self.saving = 0
        core._write(PLACE, json.dumps({"x": self.pos[0], "y": self.pos[1], "expanded": self.expanded}) + "\n")
        return False

    def left(self, *_):
        if self.hover is not None:
            self.hover = None
            self.redraw()
        return False

    # --- data ----------------------------------------------------------------------

    def fetch(self):
        """Read 1337's hours. Once a login is enough: 1337 adds nothing while you're logged in here
        (it counts a session when it ends), and the card counts this one itself. The helper starts
        at each login and keeps running while the screen is locked."""
        if self.fetching:
            return False
        self.fetching = True
        today = datetime.date.today()
        start = period(today)[0]

        def work():
            try:
                result, error = self.api.month(today), None
            except ApiError as e:
                result, error = None, str(e)
            except Exception as e:           # never take the helper down over a bad reply
                result, error = None, f"logtime: {e}"
            GLib.idle_add(self.received, start, result, error)

        threading.Thread(target=work, daemon=True).start()
        return False

    def received(self, start, result, error):
        self.fetching = False
        if result is not None:
            (self.total, self.days), self.loaded = result, start
        else:                                 # no network yet at login, say: try again shortly
            self.timers.append(GLib.timeout_add_seconds(RETRY, self.fetch))
        self.error = error
        self.redraw()
        return False

    def tick(self):
        if self.loaded and self.loaded != period(datetime.date.today())[0]:    # a new period began
            self.loaded = None
            self.fetch()
        self.redraw()
        return True

    def redraw(self):
        self.queue_draw()

    def resized(self, height):
        """The card grew or shrank (a six-week month, an error line): follow it."""
        self.height, self.size = height, (WIDTH + EDGE, height + EDGE)
        self.set_size_request(*self.size)
        self.resize(*self.size)
        self.shape()
        self.put(*self.pos)
        return False

    # --- drawing -------------------------------------------------------------------

    def layout(self, cr, s, size, bold=False, spacing=0):
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription.from_string(self.font)
        font.set_absolute_size(size * Pango.SCALE)
        font.set_weight(Pango.Weight.BOLD if bold else Pango.Weight.NORMAL)
        layout.set_font_description(font)
        if spacing:
            attrs = Pango.AttrList()
            attrs.insert(Pango.attr_letter_spacing_new(int(spacing * Pango.SCALE)))
            layout.set_attributes(attrs)
        layout.set_text(s, -1)
        return layout

    def text(self, cr, s, x, y, size, colour, bold=False, align=0.0, alpha=1.0, spacing=0):
        """Draw s with its middle at y; returns its width."""
        layout = self.layout(cr, s, size, bold, spacing)
        w, h = layout.get_pixel_size()
        cr.set_source_rgba(*palette.hex_to_rgb(colour), alpha)
        cr.move_to(x - w * align, y - h / 2)
        PangoCairo.show_layout(cr, layout)
        if self.marks is not None:
            self.marks.append((y - h / 2, y + h / 2))
        return w

    def label(self, cr, s, x, y, c, align=0.0):
        """A small capitals heading, like the ones in a terminal's system summary."""
        return self.text(cr, s, x, y, 10, c["accent_text"], bold=True, align=align, spacing=1.5)

    def rule(self, cr, y, c):
        """A dotted line across the card; on glass, the gap between panes does that instead."""
        if self.glass and self.backdrop is not None:
            return
        cr.set_source_rgba(*palette.hex_to_rgb(c["ink"]), 0.35)
        x = PAD
        while x < WIDTH - PAD:
            cr.rectangle(x, y, 2, 1)
            x += 5
        cr.fill()

    def draw(self, _widget, cr):
        c = {**FALLBACK, **(self.colours or {})}
        ink, accent = palette.hex_to_rgb(c["ink"]), palette.hex_to_rgb(c["accent"])
        now = datetime.datetime.now().astimezone()
        today = now.date()
        first, end = period(today)
        # 1337 counts a session once it ends, all of it on the day it began: count this one the same
        # way now, so every figure is what 1337 will show, live
        live = (now - self.since).total_seconds() if self.since else 0
        start = self.since.date() if self.since else None
        total = self.total or 0
        month = total * 3600 + (live if start and first <= start < end else 0)     # seconds
        blink = now.second % 2 == 0

        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.translate(*self.local(*self.pos))
        width, height = WIDTH, self.height

        def content(cr):
            """Everything on the card, the title's words included; returns its height and the
            hovered day."""
            cr.set_source_rgba(*accent, 1)
            cr.rectangle(PAD, TITLE / 2 - 4, 8, 8)
            cr.fill()
            self.text(cr, "logtime", PAD + 16, TITLE / 2, 12, c["ink"], bold=True)
            self.text(cr, "less ▴" if self.expanded else "more ▾", width - PAD, TITLE / 2, 11, c["muted"], align=1)
            self.marks = []

            # always shown: today, the month and this session, live, as 1337 will count them
            span_seconds = (midnight(end) - midnight(first)).total_seconds()
            elapsed = (now - midnight(first)).total_seconds()
            expected = GOAL * 3600 * elapsed / span_seconds  # where logging the goal evenly would be now
            y = TITLE + 22
            self.label(cr, "TODAY", PAD, y, c)
            if self.since:
                w = self.text(cr, "LIVE", width - PAD, y, 10, c["accent_text"], bold=True, align=1, spacing=1.5)
                cr.set_source_rgba(*accent, 1 if blink else 0.25)
                cr.rectangle(width - PAD - w - 13, y - 3.5, 7, 7)
                cr.fill()
            y += 30
            counted = self.days.get(today, 0)
            t = int(counted * 3600 + (live if start == today else 0))
            w = self.text(cr, f"{t // 3600}:{t % 3600 // 60:02d}", PAD - 2, y, 40, c["ink"], bold=True)
            self.text(cr, f":{t % 60:02d}", PAD - 2 + w, y + 6, 20, c["accent_text"], bold=True)

            y += 42
            self.marks.append(None)          # a new pane of glass from here
            self.label(cr, "THIS MONTH", PAD, y, c)
            self.text(cr, span(today), width - PAD, y, 10, c["muted"], bold=True, align=1)
            y += 26
            if self.total is None:
                self.text(cr, "loading…", PAD, y, 16, c["muted"], bold=True)
            else:
                m = int(month)
                w = self.text(cr, f"{m // 3600}h {m % 3600 // 60:02d}m", PAD - 1, y, 30, c["ink"], bold=True)
                self.text(cr, f"/ {GOAL}h", PAD + w + 6, y + 4, 14, c["muted"], bold=True)
                self.text(cr, f"{min(month / 3600 / GOAL, 1):.0%}", width - PAD, y + 2, 18, c["accent_text"],
                          bold=True, align=1)
            y += 22
            y += self.meter(cr, y, total * 3600, month, expected, blink, c)
            y += 18
            if self.since:
                line = f"session {hours(live)} · {self.host} since {self.since:%H:%M}"
                if self.total is not None:   # 1337's site rounds to whole hours
                    self.text(cr, f"1337 site now {total}h · after logout {int(month / 3600 + 0.5)}h", PAD, y, 11,
                              c["ink"], bold=True)
                    y += 18
            else:
                line = self.host
            self.text(cr, line, PAD, y, 11, c["muted"])
            if self.error:
                y += 18
                self.text(cr, self.error, PAD, y, 11, c["ink"])
            hovered = None
            if not self.expanded:
                self.cells = []
                return y + 4 + PAD, None
            y += 18
            self.rule(cr, y, c)
            self.marks.append(None)

            # the period's calendar
            y += 20
            for i, name in enumerate("SMTWTFS"):
                self.text(cr, name, PAD + i * CELL + CELL / 2, y, 10, c["muted"], bold=True, align=0.5)
            y += 10
            sheet = palette.hex_to_rgb(c["sheet"])
            self.cells = []
            for week in self.weeks(today):
                for i, day in enumerate(week):
                    if not first <= day < end:
                        continue
                    x = PAD + i * CELL
                    self.cells.append((x, y, day))
                    seconds = self.days.get(day, 0) * 3600 + (live if day == start else 0)
                    shade = 0.15 + 0.85 * min(seconds / FULL_DAY, 1) if seconds else 0
                    cr.rectangle(x + 2, y + 2, CELL - 4, ROW - 4)
                    if seconds:
                        cr.set_source_rgba(*accent, shade)
                    else:
                        cr.set_source_rgba(*ink, 0.05)
                    cr.fill()
                    if day == today or day == self.hover:
                        cr.rectangle(x + 2, y + 2, CELL - 4, ROW - 4)
                        cr.set_source_rgba(*ink, 1)
                        cr.set_line_width(2 if day == today else 1)
                        cr.stroke()
                    if day == self.hover:
                        hovered = (x, y, day, seconds)
                    # light digits on the darker shades (bold, so 3:1 reads well), dark ones elsewhere
                    fill = palette.rgb_to_hex([a * shade + b * (1 - shade) for a, b in zip(accent, sheet)])
                    light = palette.contrast(c["sheet"], fill) >= 3
                    colour = c["sheet"] if light else c["ink"]
                    self.text(cr, str(day.day), x + CELL / 2, y + ROW / 2, 12, colour, bold=light or day.day == 1,
                              align=0.5, alpha=0.4 if day > today else 1)
                y += ROW
            y += 8
            self.rule(cr, y, c)
            self.marks.append(None)

            # the goal: one cell an hour, in rows of forty
            y += 20
            left, days_left = max(GOAL * 3600 - month, 0), (end - today).days
            y += 4

            # the numbers that matter
            ahead = month - expected
            stats = [("LEFT", hours(left) if left else "done"),
                     ("PER DAY", hours(left / days_left) if left else "—"),
                     ("PACE", ("+" if ahead >= 0 else "−") + hours(abs(ahead)))]
            third = (width - 2 * PAD) / 3
            for i, (name, value) in enumerate(stats):
                x = PAD + i * third
                self.text(cr, name, x, y, 9, c["muted"], bold=True, spacing=1.5)
                colour = c["accent_text"] if name == "PACE" and ahead >= 0 else c["ink"]
                self.text(cr, value, x, y + 18, 15, colour, bold=True)
            y += 40

            # where this pace lands you
            rate = month / elapsed if elapsed > 0 else 0         # logged seconds per second gone
            if not left:
                line = "goal reached ✓"
            elif rate:
                eta = now + datetime.timedelta(seconds=left / rate)
                if eta < midnight(end):
                    line = f"→ {GOAL}h on {eta:%a %d %b} at this pace"
                else:
                    last = end - datetime.timedelta(days=1)
                    projected = (month + rate * (midnight(end) - now).total_seconds()) / 3600
                    line = f"→ {projected:.0f}h by {last:%d %b} at this pace"
            else:
                line = "→ nothing logged yet this month"
            self.text(cr, line, PAD, y, 11, c["muted"])
            y += PAD + 4
            return y, hovered

        # a first pass on a scrap surface finds the rows with text, so the glass goes under them;
        # then the frame, and the content again for real
        frosted = self.glass and self.backdrop is not None
        content(cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)))
        marks, self.marks = self.marks, None
        self.frame(cr, c, width, height, frosted, marks)
        y, hovered = content(cr)
        self.marks = None
        if hovered:
            self.tooltip(cr, c, *hovered, today, live if hovered[2] == start else 0)
        if y != self.height:
            GLib.idle_add(self.resized, y)
        return True

    def frame(self, cr, c, width, height, frosted, marks):
        """The card itself: square with a hard shadow, like the app's windows. As glass, a clear pane
        with a bevelled rim and frosted panes only under its rows of text; otherwise a tinted sheet."""
        ink = palette.hex_to_rgb(c["ink"])
        cr.set_source_rgba(*ink, 1)
        cr.rectangle(width, EDGE, EDGE, height)
        cr.rectangle(EDGE, height, width - EDGE, EDGE)
        cr.fill()
        if not frosted:
            cr.rectangle(0, 0, width, height)
            cr.set_source_rgba(*palette.hex_to_rgb(c["paper"]), 0.8 if self.glass else 1)
            cr.fill()
            cr.rectangle(0, 0, width, TITLE)
            cr.set_source_rgba(*palette.hex_to_rgb(c["paper2"]), 0.85 if self.glass else 1)
            cr.fill()
            cr.set_source_rgba(*ink, 1)
            cr.rectangle(0, TITLE, width, 1)
            cr.fill()
            cr.rectangle(0.5, 0.5, width - 1, height - 1)
            cr.set_line_width(1)
            cr.stroke()
            return

        # the clear pane: barely tinted, with light running down it
        cr.rectangle(0, 0, width, height)
        cr.set_source_rgba(*palette.hex_to_rgb(c["paper"]), 0.06)
        cr.fill()
        sheen = cairo.LinearGradient(0, 0, width * 0.4, height)
        sheen.add_color_stop_rgba(0, 1, 1, 1, 0.16)
        sheen.add_color_stop_rgba(0.5, 1, 1, 1, 0.02)
        sheen.add_color_stop_rgba(1, 1, 1, 1, 0.08)
        cr.rectangle(0, 0, width, height)
        cr.set_source(sheen)
        cr.fill()

        # frosted panes: the title strip, and one under each run of rows with text
        panes = [(0, 0, width, TITLE, c["paper2"])]
        bands, split = [], True
        for mark in marks:                               # in drawing order; None starts a new pane
            if mark is None:
                split = True
            elif split or not bands:
                bands.append(list(mark))
                split = False
            else:
                bands[-1] = [min(bands[-1][0], mark[0]), max(bands[-1][1], mark[1])]
        panes += [(PAD - 8, top - 6, width - 2 * PAD + 16, bottom - top + 12, c["paper"]) for top, bottom in bands]
        for x, y, w, h, colour in panes:
            cr.save()
            cr.rectangle(x, y, w, h)
            cr.clip()
            self.frost(cr, width, height)
            cr.rectangle(x, y, w, h)
            cr.set_source_rgba(*palette.hex_to_rgb(colour), 0.5)
            cr.fill()
            cr.restore()
            cr.set_source_rgba(1, 1, 1, 0.45)            # each pane's edge: lit on top, shaded below
            cr.rectangle(x, y, w, 1)
            cr.fill()
            cr.set_source_rgba(*ink, 0.18)
            cr.rectangle(x, y + h - 1, w, 1)
            cr.fill()

        # the bevelled rim, like embossed glass: bright where the light falls, dark on the far side
        rim = cairo.LinearGradient(0, 0, width, height)
        rim.add_color_stop_rgba(0, 1, 1, 1, 0.95)
        rim.add_color_stop_rgba(0.45, 1, 1, 1, 0.35)
        rim.add_color_stop_rgba(1, *ink, 0.55)
        cr.rectangle(1.5, 1.5, width - 3, height - 3)
        cr.set_source(rim)
        cr.set_line_width(3)
        cr.stroke()
        cr.rectangle(3.5, 3.5, width - 7, height - 7)
        cr.set_source_rgba(1, 1, 1, 0.3)
        cr.set_line_width(1)
        cr.stroke()
        cr.rectangle(0.5, 0.5, width - 1, height - 1)
        cr.set_source_rgba(*ink, 0.7)
        cr.stroke()

    def meter(self, cr, y, done, month, expected, blink, c):
        """The goal as one cell an hour, in rows of forty split in tens: what 1337 has counted, solid;
        this session, blinking; the hours an even pace would have by now, outlined. Returns its height."""
        ink, accent = palette.hex_to_rgb(c["ink"]), palette.hex_to_rgb(c["accent"])
        cols, rows = METER
        gap, high, step = 5, 10, 14
        pitch = (WIDTH - 2 * PAD - gap * (cols // 10 - 1)) / cols
        for i in range(cols * rows):
            row, col = divmod(i, cols)
            x = PAD + col * pitch + col // 10 * gap
            cy = y + row * step
            hour = i * 3600
            cr.rectangle(x, cy, pitch - 1.5, high)
            cr.set_source_rgba(*ink, 0.08)
            cr.fill()
            counted = min(max((done - hour) / 3600, 0), 1)
            pending = min(max((month - hour) / 3600, 0), 1)
            if pending > counted:
                cr.rectangle(x, cy, (pitch - 1.5) * pending, high)
                cr.set_source_rgba(*accent, 0.55 if blink else 0.3)
                cr.fill()
            if counted:
                cr.rectangle(x, cy, (pitch - 1.5) * counted, high)
                cr.set_source_rgba(*accent, 1)
                cr.fill()
            elif not pending and hour < expected:         # hours you're behind on
                cr.rectangle(x + 0.5, cy + 0.5, pitch - 2.5, high - 1)
                cr.set_source_rgba(*ink, 0.55)
                cr.set_line_width(1)
                cr.stroke()
        if self.marks is not None:
            self.marks.append((y, y + rows * step - (step - high)))
        return rows * step - (step - high)

    def tooltip(self, cr, c, x, y, day, seconds, today, live):
        """A day's hours as 1337 counts them, above its cell (below it on the first row)."""
        ink = palette.hex_to_rgb(c["ink"])
        lines = [(day.strftime("%a %d %b").upper(), 9, c["muted"], True, 1.5)]
        if day > today:
            lines.append(("upcoming", 13, c["muted"], True, 0))
        else:
            lines.append((hours(seconds), 15, c["ink"], True, 0))
            if live:
                lines.append((f"{(seconds - live) / 3600:.0f}h done + {hours(live)} now", 11, c["muted"], False, 0))
        sizes = [self.layout(cr, s, size, bold, sp).get_pixel_size() for s, size, _c, bold, sp in lines]
        bw = max(w for w, _h in sizes) + 20
        bh = sum(h for _w, h in sizes) + 4 * (len(lines) - 1) + 16
        bx = min(max(x + CELL / 2 - bw / 2, 4), WIDTH - bw - 4)
        by = y - bh - 4 if y - bh - 4 > TITLE + 4 else y + ROW + 4
        cr.set_source_rgba(*ink, 1)
        cr.rectangle(bx + 3, by + 3, bw, bh)
        cr.fill()
        cr.rectangle(bx, by, bw, bh)
        cr.set_source_rgba(*palette.hex_to_rgb(c["sheet"]), 1)
        cr.fill_preserve()
        cr.set_source_rgba(*ink, 1)
        cr.set_line_width(1)
        cr.stroke()
        ty = by + 8
        for (s, size, colour, bold, sp), (_w, h) in zip(lines, sizes):
            self.text(cr, s, bx + 10, ty + h / 2, size, colour, bold=bold, spacing=sp)
            ty += h + 4


def screen_size():
    """All the monitors together, in GTK's (scaled) pixels."""
    display = Gdk.Display.get_default()
    width = height = 1
    for i in range(display.get_n_monitors()):
        g = display.get_monitor(i).get_geometry()
        width, height = max(width, g.x + g.width), max(height, g.y + g.height)
    return width, height
