import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from sidehud import config, server


class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = config.load(Path(cls.tmp.name) / "none.toml")
        cfg["maps_dir"] = cls.tmp.name
        cfg["map_port"] = 0
        cls.cfg = cfg
        (Path(cls.tmp.name) / "demo.png").write_bytes(b"\x89PNG fake")
        app = server.App(cfg)
        app.state.update({"map": "demo", "x": 1, "y": 1})
        (Path(cls.tmp.name) / "demo.toml").write_text('image = "demo.png"\n')
        server.Handler.app = app
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()

    def test_index(self):
        status, ctype, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"sidehud", body)

    def test_stats_before_sampler_started(self):
        status, ctype, body = self.get("/api/stats")
        self.assertEqual(status, 200)
        self.assertIn(b'"ready": false', body)

    def test_map_resolves_definition(self):
        status, ctype, body = self.get("/api/map")
        self.assertIn(b'"image": "/maps/demo.png"', body)

    def test_inline_map_image(self):
        app = server.App(self.cfg)
        for image, want in [("stardew/Farm.png", "/maps/stardew/Farm.png"), ("/x.png", "/x.png"),
                            ("http://h/x.png", "http://h/x.png"), (None, None)]:
            app.state.update({"map": {"id": "stardew/Farm", "image": image, "px_per_unit": [16, 16]},
                              "game": "stardew", "stats": {"day": 1}, "x": 1, "y": 1})
            snap = app.map_snapshot()
            self.assertEqual(snap["map"]["image"], want)
            self.assertEqual(snap["map"]["px_per_unit"], [16, 16])
            self.assertEqual(snap["game"], "stardew")
            self.assertEqual(snap["stats"], {"day": 1})
        app.state.update({"map": None, "x": 1, "y": 1})
        self.assertIsNone(app.map_snapshot()["map"])
        app.udp.sock.close()

    def test_inline_map_bad_image(self):
        app = server.Handler.app
        try:
            app.state.update({"map": {"image": 5}, "x": 1, "y": 1})
            self.assertIsNone(app.map_snapshot()["map"]["image"])
            status, ctype, body = self.get("/api/map")
            self.assertEqual(status, 200)
            self.assertIn(b'"image": null', body)
            app.state.update({"map": 5, "x": 1, "y": 1})
            self.assertEqual(app.map_snapshot()["map"], {"image": None})
        finally:
            app.state.update({"map": "demo", "x": 1, "y": 1})

    def test_map_file(self):
        status, ctype, body = self.get("/maps/demo.png")
        self.assertEqual(ctype, "image/png")
        self.assertEqual(body, b"\x89PNG fake")

    def test_games_list(self):
        status, ctype, body = self.get("/api/games")
        self.assertEqual(status, 200)
        self.assertIn(b'"stardew"', body)

    def test_no_path_traversal(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/maps/../pyproject.toml")
        self.assertEqual(cm.exception.code, 404)
        cm.exception.close()
