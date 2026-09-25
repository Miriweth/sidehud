import subprocess

FIELDS = ["name", "utilization.gpu", "temperature.gpu", "power.draw", "power.limit",
          "memory.used", "memory.total", "clocks.sm", "clocks.mem", "fan.speed"]
KEYS = ["name", "load", "temp", "power", "power_limit", "vram_used", "vram_total", "clock", "mem_clock", "fan"]


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse(line):
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < len(KEYS):
        return None
    out = {"vendor": "nvidia", "name": parts[0].replace("NVIDIA ", "")}
    for key, value in zip(KEYS[1:], parts[1:]):
        out[key] = _num(value)
    return out


def query():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=" + ",".join(FIELDS), "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return parse(r.stdout.strip().splitlines()[0])
