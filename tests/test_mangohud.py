import os
import tempfile
import time
import unittest
from pathlib import Path

from sidehud.sensors import mangohud

CSV = """os,cpu,gpu,ram,kernel,driver,cpuscheduler
Linux,AMD,NVIDIA,32,6.0,570,
--------------------DATA---------------------
fps,frametime,cpu_load,gpu_load,cpu_temp,gpu_temp,elapsed
59.9,16.7,12,45,62,53,1000000
143.2,7.0,20,98,70,66,1500000
"""


class MangoHudLog(unittest.TestCase):
    def test_reads_last_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Game.exe_2026-09-25_21-00-00.csv").write_text(CSV)
            (Path(tmp) / "Game.exe_2026-09-25_21-00-00_summary.csv").write_text("ignored")
            got = mangohud.MangoHudLog(tmp).read()
        self.assertEqual(got, {"fps": 143.2, "frametime": 7.0, "game": "Game.exe"})

    def test_stale_log_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Game.exe_2026-09-25_21-00-00.csv"
            path.write_text(CSV)
            old = time.time() - 60
            os.utime(path, (old, old))
            self.assertIsNone(mangohud.MangoHudLog(tmp).read())

    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(mangohud.MangoHudLog(tmp).read())


class MangoHudSetup(unittest.TestCase):
    def test_adds_missing_lines_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / "MangoHud.conf"
            conf.write_text("fps_limit=144\nlog_interval=100\n")
            added = mangohud.setup("/tmp/logs", conf)
            self.assertEqual(added, ["output_folder=/tmp/logs", "autostart_log=1"])
            self.assertTrue(conf.with_suffix(".conf.bak").exists())
            self.assertEqual(mangohud.setup("/tmp/logs", conf), [])
            self.assertEqual(mangohud.current_output_folder(conf), "/tmp/logs")
            self.assertIn("fps_limit=144", conf.read_text())

    def test_fixes_existing_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / "MangoHud.conf"
            conf.write_text("autostart_log=0\nlog_duration=30\noutput_folder=/elsewhere\n# autostart_log=0\n")
            changed = mangohud.setup("/tmp/logs", conf)
            self.assertEqual(changed, ["output_folder=/tmp/logs", "autostart_log=1", "log_duration=0", "log_interval=500"])
            text = conf.read_text()
            self.assertNotIn("\nautostart_log=0", "\n" + text)
            self.assertIn("# autostart_log=0", text)
            self.assertEqual(mangohud.setup("/tmp/logs", conf), [])

    def test_creates_conf(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / "sub" / "MangoHud.conf"
            self.assertEqual(len(mangohud.setup("/tmp/logs", conf)), 3)
            self.assertTrue(conf.exists())
