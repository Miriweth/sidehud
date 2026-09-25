"""FPS from MangoHud's CSV log. MangoHud writes one line per log_interval while a game runs."""
import os
import shutil
import time
from pathlib import Path

CONF = Path("~/.config/MangoHud/MangoHud.conf").expanduser()


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


class MangoHudLog:
    def __init__(self, folder, max_age=5.0):
        self.folder = Path(folder).expanduser()
        self.max_age = max_age
        self._path = None
        self._cols = None

    def newest(self):
        try:
            files = [p for p in self.folder.glob("*.csv") if not p.name.endswith("_summary.csv")]
        except OSError:
            return None
        return max(files, key=lambda p: p.stat().st_mtime) if files else None

    def _columns(self, path):
        if path == self._path and self._cols:
            return self._cols
        cols = None
        try:
            with open(path, errors="ignore") as f:
                for _ in range(8):
                    line = f.readline()
                    if not line:
                        break
                    if line.startswith("fps,"):
                        cols = line.strip().split(",")
                        break
        except OSError:
            return None
        self._path, self._cols = path, cols
        return cols

    def read(self):
        path = self.newest()
        if path is None:
            return None
        try:
            if time.time() - path.stat().st_mtime > self.max_age:
                return None
            cols = self._columns(path)
            if not cols:
                return None
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - 2048))
                lines = [l for l in f.read().decode(errors="ignore").splitlines() if l.strip()]
        except OSError:
            return None
        if not lines:
            return None
        row = dict(zip(cols, lines[-1].split(",")))
        fps = _num(row.get("fps"))
        if fps is None:
            return None
        return {"fps": fps, "frametime": _num(row.get("frametime")), "game": path.name.rsplit("_", 2)[0]}


def setup(output_dir, conf=CONF):
    """Make MangoHud log where sidehud reads, for as long as the game runs. Returns the lines set."""
    conf = Path(conf).expanduser()
    lines = conf.read_text().splitlines() if conf.exists() else []
    at = {}
    for i, line in enumerate(lines):
        key, sep, _ = line.partition("=")
        if sep and not key.lstrip().startswith("#"):
            at[key.strip()] = i
    must = {"output_folder": str(output_dir), "autostart_log": "1"}
    done = []
    for key, value in {**must, "log_duration": "0"}.items():
        if key in at and lines[at[key]].partition("=")[2].strip() != value:
            lines[at[key]] = f"{key}={value}"
            done.append(lines[at[key]])
    add = [f"{k}={v}" for k, v in {**must, "log_interval": "500"}.items() if k not in at]
    if not done and not add:
        return []
    if conf.exists():
        shutil.copy(conf, conf.with_suffix(".conf.bak"))
    conf.parent.mkdir(parents=True, exist_ok=True)
    if add:
        lines += ["", "# sidehud: fps log for the phone"] + add
    conf.write_text("\n".join(lines) + "\n")
    return done + add


def current_output_folder(conf=CONF):
    conf = Path(conf).expanduser()
    if not conf.exists():
        return None
    for line in conf.read_text().splitlines():
        if line.strip().startswith("output_folder="):
            return line.split("=", 1)[1].strip()
    return None
