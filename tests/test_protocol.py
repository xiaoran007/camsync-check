"""Check the generated firmware protocol against a literal row-major specification."""

import json
from pathlib import Path
import re
import runpy
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Environment:
    def __init__(self, root):
        self.root = root
        self.includes = []

    def subst(self, variable):
        return str(self.root / ('firmware' if variable == '$PROJECT_DIR' else 'build'))

    def Append(self, CPPPATH):
        self.includes.extend(CPPPATH)


class ProtocolTests(unittest.TestCase):
    def generate(self, root, profile):
        path = root / 'src/camsync_check/profiles/uno_r4_wifi.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile))
        env = Environment(root)
        runpy.run_path(str(ROOT / 'firmware/generate_protocol.py'), init_globals={'Import': lambda _: None, 'env': env})
        return root / 'build/generated/optical_protocol.h'

    def test_exact_row_major_protocol_and_repeatable_generation(self):
        profile = json.loads((ROOT / 'src/camsync_check/profiles/uno_r4_wifi.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            header = self.generate(root, profile)
            text = header.read_text()
            order = [int(x) for x in re.search(r'scan_order\[96\] = \{([^}]+)\}', text)[1].split(',')]
            self.assertEqual(order, [row * 12 + column for row in range(8) for column in range(12)])
            self.assertIn('r4-rowmajor96-v2', text)
            self.assertIn('slot_us = 250', text)
            modified = header.stat().st_mtime_ns
            self.generate(root, profile)
            self.assertEqual(header.stat().st_mtime_ns, modified)

    def test_old_or_inconsistent_protocol_is_rejected(self):
        original = json.loads((ROOT / 'src/camsync_check/profiles/uno_r4_wifi.json').read_text())
        for change in ({'protocol': 'r4-permuted96-v1'}, {'scan_order': list(reversed(range(96)))}, {'slot_us': 100}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                self.generate(Path(directory), original | change)
