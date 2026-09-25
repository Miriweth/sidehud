import tomllib
from pathlib import Path


class MapDefs:
    """<maps_dir>/<id>.toml describes a map image and how world units map to pixels."""

    def __init__(self, folder):
        self.folder = Path(folder).expanduser()
        self._cache = {}

    def get(self, map_id):
        if not isinstance(map_id, str) or not map_id or "/" in map_id or map_id.startswith("."):
            return None
        path = self.folder / f"{map_id}.toml"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
        cached = self._cache.get(map_id)
        if cached and cached[0] == mtime:
            return cached[1]
        with open(path, "rb") as f:
            d = tomllib.load(f)
        d["id"] = map_id
        if d.get("image") and "://" not in d["image"] and not d["image"].startswith("/"):
            d["image"] = "/maps/" + d["image"]
        self._cache[map_id] = (mtime, d)
        return d
