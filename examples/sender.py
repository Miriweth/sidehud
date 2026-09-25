"""Moves three markers around so you can see the map tile without a game.

    python examples/sender.py            # grid only
    python examples/sender.py --map demo # with examples/maps/demo.* copied to ~/.config/sidehud/maps/
"""
import argparse
import json
import math
import socket
import time

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8766)
ap.add_argument("--map", default=None)
args = ap.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
t0 = time.time()
try:
    while True:
        t = time.time() - t0
        msg = {
            "source": "example",
            "entities": [
                {"id": "me", "kind": "player", "x": 200 * math.cos(t / 6), "y": 200 * math.sin(t / 6),
                 "heading": (t * 30) % 360, "label": "me"},
                {"id": "a1", "kind": "ally", "x": 150 * math.cos(t / 4 + 1), "y": 150 * math.sin(t / 4 + 1), "label": "ally"},
                {"id": "x1", "kind": "other", "x": 250 * math.cos(t / 9 + 2), "y": 120 * math.sin(t / 9 + 2)},
            ],
        }
        if args.map:
            msg["map"] = args.map
        sock.sendto(json.dumps(msg).encode(), ("127.0.0.1", args.port))
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
