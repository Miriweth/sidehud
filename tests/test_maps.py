import json
import socket
import tempfile
import time
import unittest
from pathlib import Path

from sidehud.maps.defs import MapDefs
from sidehud.maps.state import MapState
from sidehud.maps.udp import UdpListener


class State(unittest.TestCase):
    def test_short_form_and_entities(self):
        s = MapState()
        s.update({"map": "castle", "x": 1, "y": 2, "heading": 90})
        snap = s.snapshot()
        self.assertTrue(snap["live"])
        self.assertEqual(snap["map"], "castle")
        self.assertEqual(snap["entities"][0]["id"], "player")
        s.update({"entities": [{"id": "bob", "kind": "ally", "x": 5, "y": 5}, {"id": "bad"}]})
        ids = sorted(e["id"] for e in s.snapshot()["entities"])
        self.assertEqual(ids, ["bob"])
        s.update({"stats": {"money": 1}})
        self.assertEqual(len(s.snapshot()["entities"]), 1)

    def test_game_and_stats(self):
        s = MapState()
        s.update({"x": 0, "y": 0})
        snap = s.snapshot()
        self.assertIsNone(snap["game"])
        self.assertIsNone(snap["stats"])
        s.update({"game": "stardew", "stats": {"day": 12, "money": 500}, "x": 0, "y": 0})
        snap = s.snapshot()
        self.assertEqual(snap["game"], "stardew")
        self.assertEqual(snap["stats"]["money"], 500)
        s.update({"game": 7, "stats": "no", "x": 1, "y": 1})
        snap = s.snapshot()
        self.assertIsNone(snap["game"])
        self.assertIsNone(snap["stats"])
        s.update({"game": "stardew", "stats": {"day": 12}, "x": 0, "y": 0})
        s.update({"x": 1, "y": 1})
        snap = s.snapshot()
        self.assertIsNone(snap["game"])
        self.assertIsNone(snap["stats"])

    def test_goes_stale(self):
        s = MapState(ttl=0.05)
        s.update({"x": 0, "y": 0})
        time.sleep(0.2)
        snap = s.snapshot()
        self.assertFalse(snap["live"])
        self.assertEqual(snap["entities"], [])

    def test_nothing_yet(self):
        snap = MapState().snapshot()
        self.assertFalse(snap["live"])
        self.assertIsNone(snap["age"])


class Udp(unittest.TestCase):
    def test_datagram_updates_state(self):
        state = MapState()
        listener = UdpListener(state, 0)
        listener.start()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"not json", ("127.0.0.1", listener.port))
        sock.sendto(json.dumps({"map": "m", "x": 3, "y": 4}).encode(), ("127.0.0.1", listener.port))
        for _ in range(50):
            if state.snapshot()["live"]:
                break
            time.sleep(0.02)
        sock.close()
        snap = state.snapshot()
        self.assertTrue(snap["live"])
        self.assertEqual(snap["source"], "udp")
        self.assertEqual(snap["entities"][0]["x"], 3)


class Defs(unittest.TestCase):
    def test_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "castle.toml").write_text('name = "Castle"\nimage = "castle.png"\norigin_px = [1, 2]\n')
            defs = MapDefs(tmp)
            d = defs.get("castle")
            self.assertEqual(d["image"], "/maps/castle.png")
            self.assertEqual(d["id"], "castle")
            self.assertIs(defs.get("castle"), d)  # cached
            self.assertIsNone(defs.get("missing"))
            self.assertIsNone(defs.get("../castle"))
            self.assertIsNone(defs.get(None))
