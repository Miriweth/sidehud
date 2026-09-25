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

    def test_map_file(self):
        status, ctype, body = self.get("/maps/demo.png")
        self.assertEqual(ctype, "image/png")
        self.assertEqual(body, b"\x89PNG fake")

    def test_no_path_traversal(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/maps/../pyproject.toml")
        self.assertEqual(cm.exception.code, 404)
        cm.exception.close()
