import tempfile
import unittest
from pathlib import Path

from sidehud.sensors import amd


def fake_sysfs(root):
    dev = root / "card1" / "device"
    hw = dev / "hwmon" / "hwmon3"
    hw.mkdir(parents=True)
    (root / "card1-DP-1" / "device").mkdir(parents=True)  # a connector, must be skipped
    values = {
        dev / "vendor": "0x1002", dev / "gpu_busy_percent": "42",
        dev / "mem_info_vram_used": str(3 * 2 ** 30), dev / "mem_info_vram_total": str(16 * 2 ** 30),
        hw / "temp1_input": "61000", hw / "temp2_input": "75000",
        hw / "power1_average": "180000000", hw / "power1_cap": "263000000",
        hw / "freq1_input": "2100000000", hw / "freq2_input": "1000000000",
        hw / "pwm1": "128", hw / "pwm1_max": "255",
    }
    for path, value in values.items():
        path.write_text(value + "\n")


class AmdSysfs(unittest.TestCase):
    def test_reads_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_sysfs(root)
            g = amd.query(drm=root)
        self.assertEqual(g["vendor"], "amd")
        self.assertEqual(g["load"], 42)
        self.assertEqual(g["temp"], 75)          # junction wins over edge
        self.assertEqual(g["power"], 180)
        self.assertEqual(g["power_limit"], 263)
        self.assertEqual(g["vram_used"], 3072)
        self.assertEqual(g["vram_total"], 16384)
        self.assertEqual(g["clock"], 2100)
        self.assertEqual(g["mem_clock"], 1000)
        self.assertEqual(g["fan"], 50)

    def test_no_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(amd.query(drm=Path(tmp)))
