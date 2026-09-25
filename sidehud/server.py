import json
import mimetypes
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from .maps.defs import MapDefs, image_url
from .maps.state import MapState
from .maps.udp import UdpListener
from .sampler import Sampler

STATIC = Path(__file__).resolve().parent / "static"


class App:
    def __init__(self, cfg):
        self.cfg = cfg
        self.sampler = Sampler(cfg)
        self.state = MapState()
        self.maps = MapDefs(cfg["maps_dir"])
        self.udp = UdpListener(self.state, cfg["map_port"])

    def start(self):
        Path(self.cfg["mangohud_dir"]).expanduser().mkdir(parents=True, exist_ok=True)
        self.sampler.start()
        self.udp.start()

    def map_snapshot(self):
        snap = self.state.snapshot()
        if isinstance(snap["map"], str):
            snap["map"] = self.maps.get(snap["map"])
        elif isinstance(snap["map"], dict):
            snap["map"] = dict(snap["map"], image=image_url(snap["map"].get("image")))
        return snap


class Handler(SimpleHTTPRequestHandler):
    app = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self):
        path = unquote(self.path.split("?", 1)[0])
        if path == "/api/stats":
            self.send_json(self.app.sampler.get())
        elif path == "/api/map":
            self.send_json(self.app.map_snapshot())
        elif path == "/api/games":
            self.send_json(sorted(f.stem for f in (STATIC / "games").glob("*.js")))
        elif path.startswith("/maps/"):
            self.send_map_file(path[len("/maps/"):])
        else:
            super().do_GET()

    def send_json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_map_file(self, name):
        root = Path(self.app.cfg["maps_dir"]).expanduser().resolve()
        target = (root / name).resolve()
        if root not in target.parents or not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path.endswith((".html", ".js", ".css")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        if self.app.cfg.get("verbose"):
            super().log_message(fmt, *args)


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 80))  # no packet is sent, this only picks the outgoing interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def serve(cfg):
    app = App(cfg)
    app.start()
    Handler.app = app
    Handler.extensions_map[".webmanifest"] = "application/manifest+json"
    server = ThreadingHTTPServer((cfg["bind"], cfg["port"]), Handler)
    print(f"sidehud: http://{lan_ip()}:{cfg['port']}   map data: udp 127.0.0.1:{cfg['map_port']}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
