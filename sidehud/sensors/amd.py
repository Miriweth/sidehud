import re
from pathlib import Path

DRM = Path("/sys/class/drm")


def _read(path, scale=1.0):
    try:
        return int(path.read_text().strip()) / scale
    except (OSError, ValueError):
        return None


def find_device(drm=DRM):
    for dev in sorted(drm.glob("card*/device")):
        if not re.fullmatch(r"card\d+", dev.parent.name):
            continue
        try:
            vendor = (dev / "vendor").read_text().strip()
        except OSError:
            continue
        if vendor == "0x1002" and (dev / "gpu_busy_percent").exists():
            return dev
    return None


def query(drm=DRM):
    dev = find_device(drm)
    if dev is None:
        return None
    hw = next(iter((dev / "hwmon").glob("hwmon*")), dev)
    fan = None
    pwm, pwm_max = _read(hw / "pwm1"), _read(hw / "pwm1_max")
    if pwm is not None and pwm_max:
        fan = round(pwm / pwm_max * 100)
    name = "AMD GPU"
    try:
        name = (dev / "product_name").read_text().strip() or name
    except OSError:
        pass
    return {
        "vendor": "amd",
        "name": name,
        "load": _read(dev / "gpu_busy_percent"),
        # junction (temp2) is what throttles, fall back to edge
        "temp": _read(hw / "temp2_input", 1000) or _read(hw / "temp1_input", 1000),
        "power": _read(hw / "power1_average", 1e6) or _read(hw / "power1_input", 1e6),
        "power_limit": _read(hw / "power1_cap", 1e6),
        "vram_used": _read(dev / "mem_info_vram_used", 2 ** 20),
        "vram_total": _read(dev / "mem_info_vram_total", 2 ** 20),
        "clock": _read(hw / "freq1_input", 1e6),
        "mem_clock": _read(hw / "freq2_input", 1e6),
        "fan": fan,
    }
