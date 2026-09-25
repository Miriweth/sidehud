import tomllib
from pathlib import Path


def image_url(image):
    """Relative image names live in the maps dir and are served under /maps/."""
    if isinstance(image, str) and image and "://" not in image and not image.startswith("/"):
        return "/maps/" + image
    return image if isinstance(image, str) else None


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
        d["image"] = image_url(d.get("image"))
        self._cache[map_id] = (mtime, d)
        return d
