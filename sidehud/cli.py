import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, config

SERVE_OPTS = ("port", "bind", "mangohud_dir", "maps_dir", "verbose")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog="sidehud", description="Your phone as a second screen for your gaming PC.")
    ap.add_argument("--version", action="version", version=f"sidehud {__version__}")
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("serve", help="start the web server (default)")
    s.add_argument("--port", type=int)
    s.add_argument("--bind", help="0.0.0.0 for the whole LAN, 127.0.0.1 for this machine only")
    s.add_argument("--mangohud-dir", help="folder MangoHud writes its csv logs to")
    s.add_argument("--maps-dir", help="folder with map images and their .toml files")
    s.add_argument("--verbose", action="store_true", help="log every request")
    s.add_argument("--config")

    m = sub.add_parser("mangohud-setup", help="make MangoHud write the fps log that sidehud reads")
    m.add_argument("--conf", help="path to MangoHud.conf")
    m.add_argument("--config")

    c = sub.add_parser("check", help="show what sidehud can see on this machine")
    c.add_argument("--config")

    if argv and argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version"):
        argv = ["serve"] + argv
    args = ap.parse_args(argv)
    cfg = config.load(getattr(args, "config", None))
    cmd = args.cmd or "serve"

    if cmd == "serve":
        for key in SERVE_OPTS:
            value = getattr(args, key, None)
            if value:
                cfg[key] = value
        from .server import serve
        serve(cfg)
    elif cmd == "mangohud-setup":
        from .sensors import mangohud
        conf = args.conf or mangohud.CONF
        changed = mangohud.setup(cfg["mangohud_dir"], conf)
        if changed:
            print(f"{conf}:\n  " + "\n  ".join(changed))
            print("MangoHud reads this at game start, so restart the game once.")
        else:
            print(f"{conf} already logs to {cfg['mangohud_dir']}, nothing changed.")
    elif cmd == "check":
        check(cfg)


def check(cfg):
    from .sensors import gpu, mangohud, system
    from .server import lan_ip

    g = gpu.query()
    print("gpu:       " + (f"{g['name']} ({gpu.backend_name()})" if g else "none found (needs nvidia-smi or an amdgpu card)"))
    temp = system.cpu_temp()
    print(f"cpu:       {system.cpu_model()}" + (f", {temp:.0f} °C" if temp is not None else ", no temperature sensor"))
    folder = mangohud.current_output_folder()
    if folder:
        print(f"mangohud:  logs to {folder}")
        if Path(folder).expanduser() != Path(cfg["mangohud_dir"]).expanduser():
            print(f"           sidehud reads {cfg['mangohud_dir']} though. Set mangohud_dir in config.toml.")
    else:
        print("mangohud:  not logging. Run: sidehud mangohud-setup")
    print(f"maps:      {cfg['maps_dir']}")
    print(f"url:       http://{lan_ip()}:{cfg['port']}")
    if shutil.which("ufw"):
        state = subprocess.run(["systemctl", "is-active", "ufw"], capture_output=True, text=True).stdout.strip()
        if state == "active":
            print(f"firewall:  ufw is active. Allow the port for your LAN, e.g.\n"
                  f"           sudo ufw allow from 192.168.0.0/16 to any port {cfg['port']} proto tcp")
