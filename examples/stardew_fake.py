"""Sends what the Stardew Valley mod would send, so the game panel can be checked without the game.

    python examples/stardew_fake.py

The map has no image, the tile falls back to the grid. One real second is ten game minutes.
"""
import argparse
import json
import math
import socket
import time

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEATHER = ["sunny", "rain", "storm", "snow", "wind", "greenrain"]


def time_text(t):
    h, m = divmod(t % 2400, 100)
    return f"{h % 12 or 12}:{m:02d} {'am' if h < 12 else 'pm'}"


ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8766)
args = ap.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
t0 = time.time()
while True:
    t = time.time() - t0
    mins = int(t) * 10                      # game minutes since 6:00 on day 12
    day = 12 + mins // 1200                 # a day runs 6:00 to 2:00
    mins %= 1200
    clock = 600 + mins // 60 * 100 + mins % 60
    day = (day - 1) % 28 + 1
    msg = {
        "game": "stardew",
        "source": "fake",
        "map": {"id": "stardew/Farm", "name": "Farm", "image": None, "origin_px": [0, 0], "px_per_unit": [16, 16]},
        "entities": [
            {"id": "player", "kind": "player", "x": 40 + 12 * math.cos(t / 6), "y": 30 + 12 * math.sin(t / 6),
             "heading": int((t * 30) % 360) // 90 * 90, "label": "Farmer"},
            {"id": "npc:Abigail", "kind": "ally", "x": 40 + 8 * math.cos(t / 4 + 1), "y": 30 + 8 * math.sin(t / 4 + 1), "label": "Abigail"},
            {"id": "npc:Pierre", "kind": "ally", "x": 52, "y": 24 + 3 * math.sin(t / 3), "label": "Pierre"},
            {"id": "monster:0", "kind": "other", "x": 40 + 15 * math.cos(t / 9 + 2), "y": 30 + 10 * math.sin(t / 9 + 2), "label": "Green Slime"},
        ],
        "stats": {
            "day": day, "season": "spring", "year": 1, "weekday": WEEKDAYS[(day - 1) % 7],
            "time": clock, "timeText": time_text(clock),
            "weather": WEATHER[day % len(WEATHER)],
            "money": 12345 + int(t) * 7,
            "energy": max(0, round(270 - mins * 0.2)), "maxEnergy": 270,
            "health": round(60 + 40 * math.sin(t / 20)), "maxHealth": 100,
            "location": "Farm", "luck": round(math.sin(day) * 0.1, 3),
            "skills": {"farming": 3, "mining": 1, "foraging": 2, "fishing": 4, "combat": 0},
            "birthday": "Abigail" if day == 13 else None,
            "festival": "Egg Festival" if day == 13 else None,
        },
    }
    sock.sendto(json.dumps(msg).encode(), ("127.0.0.1", args.port))
    time.sleep(0.1)
