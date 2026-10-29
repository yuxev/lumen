"""nimbus — change your wallpaper and recolour your desktop from it.

    nimbus                 open the window
    nimbus set FILE        use a picture or video as the wallpaper
    nimbus next            a random different wallpaper from your folder
    nimbus light|dark|auto light or dark colours, or follow the clock
    nimbus awake [MINUTES|on|off]
                                     keep the screen from locking while you read or watch
                                     (default 60 minutes; "on" lasts until you turn it off or log out)
    nimbus guard [off]               lock the screen on the first key or mouse move, from 3 s after
                                     you run it (walking away from the computer)
    nimbus logtime [on|off|login LOGIN]
                                     your logtime as 1337 counts it, also shown live on the desktop:
                                     this session and the scholarship month (no setup needed)
    nimbus stop            stop everything (the wallpaper, rotation, keep-awake, the window)
                                     until you start it again; nothing is uninstalled
    nimbus start           start it again
    nimbus restore         put your desktop back the way it was
    nimbus desktop         the background helper (started at login)
"""
import os
import sys

# Ghostty's AppImage exports GSETTINGS_BACKEND=keyfile to everything it starts, which sends
# settings to a private file GNOME never reads; always talk to the real settings store
if os.environ.get("GSETTINGS_BACKEND") == "keyfile":
    os.environ["GSETTINGS_BACKEND"] = "dconf"


def logtime_command(args):
    from . import core, logtime
    arg = args[0] if args else ""
    if arg in ("on", "off"):
        core.save_config(logtime=arg == "on")
        if arg == "on":
            core.start()
    elif arg == "login" and len(args) == 2:
        core.save_config(logtime_login=args[1])
        print(f"Logtime now follows {args[1]}.")
    elif arg == "":
        today = now().date()
        try:
            total, days = logtime.source().month(today)
        except logtime.ApiError as e:
            print(f"nimbus: {e}", file=sys.stderr)
            return 1
        print(logtime.summary(total, days, today))
    else:
        print("usage: nimbus logtime [on|off|login LOGIN]", file=sys.stderr)
        return 1
    return 0


def now():
    import datetime
    return datetime.datetime.now().astimezone()


def main(argv):
    command = argv[1] if len(argv) > 1 else "open"
    if command == "open":
        from . import app
        return app.main()
    if command == "desktop":
        from . import desktop
        return desktop.main()

    from . import core
    try:
        if command == "set" and len(argv) > 2:
            core.set_wallpaper(argv[2])
            core.start()
        elif command == "next":
            if core.next_wallpaper() is None:
                print("nimbus: no other pictures in", core.load_config()["folder"], file=sys.stderr)
                return 1
            core.start()
        elif command in ("light", "dark", "auto"):
            core.save_config(mode=command)
            core.apply_theme()
        elif command == "apply":
            core.apply_theme()
        elif command == "awake":
            arg = argv[2] if len(argv) > 2 else "60"
            if arg == "off":
                core.keep_awake(None)
                print("Screen locks normally again.")
            elif arg == "on":
                core.keep_awake(core.FOREVER)
                print("Screen stays awake until you run 'nimbus awake off' or log out.")
            elif arg.isdigit() and int(arg) > 0:
                core.keep_awake(int(arg))
                print(f"Screen stays awake for {arg} minutes.")
            else:
                print("usage: nimbus awake [MINUTES|on|off]", file=sys.stderr)
                return 1
        elif command == "guard":
            if len(argv) > 2 and argv[2] == "off":
                core.guard(False)
                print("Disarmed.")
            else:
                core.guard(True)
                print(f"Hands off the keyboard and mouse: in {core.GUARD_GRACE} s the first touch locks the screen.")
        elif command == "logtime":
            return logtime_command(argv[2:])
        elif command == "stop":
            core.stop()
            print("Nimbus stopped. Your colours stay as they are; nothing was uninstalled.\n"
                  "It stays off after logging in again. Run 'nimbus start' (or open the app) to bring it back.")
        elif command == "start":
            core.start()
            print("Nimbus started.")
        elif command == "restore":
            core.restore()
        else:
            print(__doc__.strip())
            return 1
    except ValueError as e:
        print(f"nimbus: {e}", file=sys.stderr)
        return 1
    return 0


sys.exit(main(sys.argv))
