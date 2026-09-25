import threading
import time


class MapState:
    """Latest packet from whatever feeds the UDP port, see docs/plugin-spec.md."""

    def __init__(self, ttl=3.0):
        self._lock = threading.Lock()
        self._ttl = ttl
        self._map = None
        self._game = None
        self._stats = None
        self._entities = {}
        self._source = None
        self._updated = 0.0

    def update(self, msg, source=None):
        if not isinstance(msg, dict):
            return
        now = time.time()
        entities = msg.get("entities")
        if entities is None and "x" in msg:
            entities = [{k: msg[k] for k in ("id", "kind", "x", "y", "z", "heading", "label") if k in msg}]
        with self._lock:
            if "map" in msg and isinstance(msg["map"], (str, dict, type(None))):
                self._map = msg["map"]
            game = msg.get("game")
            self._game = game if isinstance(game, str) else None
            stats = msg.get("stats")
            self._stats = stats if isinstance(stats, dict) else None
            if entities is not None:
                self._entities = {}  # every packet carries the full list; markers from the last location must go
            for e in entities or []:
                if not isinstance(e, dict) or "x" not in e or "y" not in e:
                    continue
                e = dict(e)
                e.setdefault("id", "player")
                e.setdefault("kind", "player")
                e["seen"] = now
                self._entities[str(e["id"])] = e
            self._source = msg.get("source", source)
            self._updated = now

    def snapshot(self):
        now = time.time()
        with self._lock:
            keep = {k: e for k, e in self._entities.items() if now - e["seen"] <= self._ttl * 3}
            self._entities = keep
            age = now - self._updated if self._updated else None
            return {
                "live": age is not None and age <= self._ttl,
                "age": None if age is None else round(age, 1),
                "map": self._map,
                "game": self._game,
                "stats": self._stats,
                "source": self._source,
                "entities": [dict(e) for e in keep.values()],
            }
