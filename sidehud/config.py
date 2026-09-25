import copy
import os
import tomllib
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "sidehud"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser() / "sidehud"

DEFAULTS = {
    "port": 8765,
    "bind": "0.0.0.0",
    "map_port": 8766,
    "history": 120,
    "mangohud_dir": str(DATA_DIR / "mangohud"),
    "maps_dir": str(CONFIG_DIR / "maps"),
    "games_dir": str(CONFIG_DIR / "games"),
    # [warn, critical]
    "thresholds": {"gpu_temp": [83, 90], "cpu_temp": [85, 93], "vram": [90, 97], "ram": [90, 97]},
}


def load(path=None):
    cfg = copy.deepcopy(DEFAULTS)
    path = Path(path).expanduser() if path else CONFIG_DIR / "config.toml"
    if path.exists():
        with open(path, "rb") as f:
            user = tomllib.load(f)
        for key, value in user.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
    return cfg
