"""lumen — change your wallpaper and recolour your desktop from it.

    lumen                          open the window
    lumen set FILE                 use a picture or video as the wallpaper
    lumen next                     a random different wallpaper from your folder
    lumen light|dark|auto          light or dark colours, or follow the system
    lumen logtime [on|off|login LOGIN]
                                   your logtime as 1337 counts it, also shown live on the desktop:
                                   this session and the scholarship month (no setup needed)
    lumen stop                     stop everything (the wallpaper, rotation, the window)
                                   until you start it again; nothing is uninstalled
    lumen start                    start it again
    lumen restore                  put your desktop back the way it was
    lumen uninstall                put your desktop back the way it was and remove Lumen
    lumen desktop                  the background helper (started at login)
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
            print(f"lumen: {e}", file=sys.stderr)
            return 1
        print(logtime.summary(total, days, today))
    else:
        print("usage: lumen logtime [on|off|login LOGIN]", file=sys.stderr)
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
                print("lumen: no other pictures in", core.load_config()["folder"], file=sys.stderr)
                return 1
            core.start()
        elif command in ("light", "dark", "auto"):
            core.save_config(mode=command)
            core.apply_theme()
        elif command == "apply":
            core.apply_theme()
        elif command == "logtime":
            return logtime_command(argv[2:])
        elif command == "stop":
            core.stop()
            print("Lumen stopped. Your colours stay as they are; nothing was uninstalled.\n"
                  "It stays off after logging in again. Run 'lumen start' (or open the app) to bring it back.")
        elif command == "start":
            core.start()
            print("Lumen started.")
        elif command == "uninstall":
            # the copy install.sh keeps next to the app, so it works without the download or a clone
            script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uninstall.sh")
            if not os.path.exists(script):
                print("lumen: uninstall.sh isn't here; run it from the Lumen folder you installed from",
                      file=sys.stderr)
                return 1
            os.execvp("bash", ["bash", script])
        elif command == "restore":
            core.restore()
        else:
            print(__doc__.strip())
            return 1
    except ValueError as e:
        print(f"lumen: {e}", file=sys.stderr)
        return 1
    return 0


sys.exit(main(sys.argv))
