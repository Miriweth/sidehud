import re

import psutil

TEMP_SOURCES = (("k10temp", "Tctl"), ("k10temp", "Tdie"), ("zenpower", "Tdie"), ("coretemp", "Package id 0"))


def cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    name = line.split(":", 1)[1]
                    name = re.sub(r"\s*\d+-Core Processor|\(R\)|\(TM\)|\bCPU\b|@.*", "", name)
                    return " ".join(name.split())
    except OSError:
        pass
    return "CPU"


def cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None
    for chip, label in TEMP_SOURCES:
        for sensor in temps.get(chip, []):
            if sensor.label == label:
                return sensor.current
    for chip, _ in TEMP_SOURCES:
        if temps.get(chip):
            return temps[chip][0].current
    return None


def net_totals():
    rx = tx = 0
    for name, c in psutil.net_io_counters(pernic=True).items():
        if name != "lo":
            rx += c.bytes_recv
            tx += c.bytes_sent
    return rx, tx


def top_processes(limit=4):
    """cpu_percent() needs a previous call per process; psutil keeps that state per pid."""
    rows = []
    for proc in psutil.process_iter(["name"]):
        try:
            cpu = proc.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        if cpu > 0.5:
            rows.append((cpu, proc))
    rows.sort(key=lambda r: r[0], reverse=True)
    out = []
    for cpu, proc in rows[:limit]:
        try:
            out.append({"name": proc.info.get("name") or proc.name(), "cpu": round(cpu, 1),
                        "mem": proc.memory_info().rss})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return out
