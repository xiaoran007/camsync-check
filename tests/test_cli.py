"""Complete dual-B0267 image-to-report checks; no cameras or firmware required."""

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fixtures import capture


class CliTests(unittest.TestCase):
    def run_cli(self, root: Path):
        return subprocess.run([sys.executable, '-m', 'camsync_check', '--config', str(root / 'run.json')],
                              capture_output=True, text=True, timeout=60)

    def test_dual_board_full_pipeline_and_output_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            capture(root)
            result = self.run_cli(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((root / 'result/summary.json').read_text())
            self.assertEqual(summary['protocol'], 'r4-rowmajor96-v2')
            self.assertEqual(summary['representative_pair']['valid_pairs'], 4, summary)
            self.assertEqual(summary['representative_pair']['median_offset_us'], 1000)
            self.assertEqual(summary['representative_pair']['observed_jitter_std_us'], 0)
            self.assertEqual(len(summary['camera_pairs']), 28)
            with (root / 'result/pairs.csv').open() as stream: pairs = list(csv.DictReader(stream))
            self.assertEqual(len(pairs), 4 * (16 + 6 + 6))
            self.assertTrue(all(row['status'] == 'valid' for row in pairs))
            cross = [r for r in pairs if r['reference_camera'] == 'a_camera_1' and r['other_camera'] == 'b_camera_3']
            self.assertEqual({float(r['offset_us']) for r in cross}, {500})
            with (root / 'result/frames.csv').open() as stream: frames = list(csv.DictReader(stream))
            self.assertEqual(len(frames), 32)
            self.assertEqual(float(frames[0]['phase_start_us']), 22500)
            localization = json.loads((root / 'result/localization.json').read_text())
            self.assertTrue(all(v['status'] == 'valid' for v in localization['cameras'].values()))
            report = (root / 'result/report.html').read_text()
            self.assertIn('Cross-board median offsets', report)
            self.assertIn('a_camera_0', report)
            self.assertIn('localization.json', report)
            self.assertIn('SIFT', result.stderr)
            self.assertEqual(result.stdout.strip(), str(root / 'result/report.html'))
            again = self.run_cli(root)
            self.assertEqual(again.returncode, 2)
            self.assertIn('already exist', again.stderr)

    def test_missing_view_is_not_replaced_and_unmatched_frames_remain_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            data = capture(root, invalid_camera=True)
            data['sources'][1]['node_id'] = 'node_1'
            data['comparison']['other_camera'] = 'b_camera_3'
            data['comparison']['frame_pairs'] = [[0, 0], [2, 2]]
            (root / 'run.json').write_text(json.dumps(data))
            result = self.run_cli(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((root / 'result/summary.json').read_text())
            self.assertEqual(summary['representative_pair']['valid_pairs'], 0)
            self.assertIsNone(summary['representative_pair']['median_offset_us'])
            self.assertEqual(summary['unmatched_source_frames']['source_a'], [1, 3])
            self.assertEqual(summary['sources'][1]['node_id'], 'node_1')
            self.assertEqual(summary['representatives']['other'], 'b_camera_3')
            with (root / 'result/pairs.csv').open() as stream: pairs = list(csv.DictReader(stream))
            affected = [r for r in pairs if r['other_camera'] == 'b_camera_3']
            self.assertTrue(all(r['status'] == 'invalid' and r['offset_us'] == '' for r in affected))

    def test_invalid_config_has_nonzero_exit_and_no_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'run.json').write_text('{"schema_version": 1}')
            result = self.run_cli(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn('missing', result.stderr)
            self.assertFalse((root / 'result').exists())
