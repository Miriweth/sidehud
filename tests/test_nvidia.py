import unittest

from sidehud.sensors import nvidia


class NvidiaParse(unittest.TestCase):
    def test_parse_line(self):
        g = nvidia.parse("NVIDIA GeForce RTX 4080, 35, 52, 58.69, 320.00, 2377, 16376, 720, 5001, 0")
        self.assertEqual(g["name"], "GeForce RTX 4080")
        self.assertEqual(g["vendor"], "nvidia")
        self.assertEqual(g["load"], 35.0)
        self.assertEqual(g["vram_total"], 16376.0)
        self.assertEqual(g["fan"], 0.0)

    def test_na_fields_become_none(self):
        g = nvidia.parse("GPU, 10, 40, [N/A], [N/A], 100, 1000, 500, 1000, [N/A]")
        self.assertIsNone(g["power"])
        self.assertIsNone(g["fan"])
        self.assertEqual(g["load"], 10.0)

    def test_garbage(self):
        self.assertIsNone(nvidia.parse("no gpu here"))
