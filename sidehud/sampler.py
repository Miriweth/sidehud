import socket
import threading
import time
from collections import deque

import psutil

from .sensors import gpu, system
from .sensors.mangohud import MangoHudLog


class Sampler(threading.Thread):
    """Reads everything once a second and keeps the latest snapshot plus a short history."""

    def __init__(self, cfg):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.lock = threading.Lock()
        self.snapshot = {"ready": False}
        n = cfg["history"]
        self.history = {k: deque([None] * n, maxlen=n) for k in ("gpu", "cpu", "down", "up", "fps")}
        self.mango = MangoHudLog(cfg["mangohud_dir"])
        self.cpu_name = system.cpu_model()
        self.host = socket.gethostname()
        self._procs = []
        self._procs_at = 0.0

    def run(self):
        psutil.cpu_percent(percpu=True)
        rx, tx = system.net_totals()
        t_prev = time.time()
        while True:
            t0 = time.time()
            g = gpu.query()
            per_core = psutil.cpu_percent(percpu=True)
            cpu_load = sum(per_core) / len(per_core) if per_core else 0.0
            freq = psutil.cpu_freq()
            mem = psutil.virtual_memory()
            rx2, tx2 = system.net_totals()
            dt = max(t0 - t_prev, 0.001)
            down, up = (rx2 - rx) * 8 / dt / 1e6, (tx2 - tx) * 8 / dt / 1e6
            rx, tx, t_prev = rx2, tx2, t0
            fps = self.mango.read()
            if t0 - self._procs_at >= 2:
                self._procs, self._procs_at = system.top_processes(), t0

            self.history["gpu"].append(g["load"] if g else None)
            self.history["cpu"].append(round(cpu_load, 1))
            self.history["down"].append(round(down, 2))
            self.history["up"].append(round(up, 2))
            self.history["fps"].append(fps["fps"] if fps else None)

            snap = {
                "ready": True,
                "time": t0,
                "host": self.host,
                "uptime": t0 - psutil.boot_time(),
                "gpu": g,
                "cpu": {"name": self.cpu_name, "load": round(cpu_load, 1), "per_core": per_core,
                        "temp": system.cpu_temp(), "freq": freq.current if freq else None},
                "mem": {"used": mem.total - mem.available, "total": mem.total, "percent": mem.percent},
                "net": {"down": round(down, 2), "up": round(up, 2)},
                "fps": fps,
                "procs": self._procs,
                "thresholds": self.cfg["thresholds"],
                "history": {k: list(v) for k, v in self.history.items()},
            }
            with self.lock:
                self.snapshot = snap
            time.sleep(max(0.0, 1.0 - (time.time() - t0)))

    def get(self):
        with self.lock:
            return self.snapshot
