"""Explicit input identities, protocol versioning, and profile validation."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from camsync_check.config import ConfigError, load_config
from camsync_check.vision import read_frame
from fixtures import config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = config(self.root)
        self.path = self.root / 'run.json'

    def load(self, data):
        self.path.write_text(json.dumps(data))
        return load_config(self.path)

    def test_relative_paths_and_shared_node_identity(self):
        run = self.load(self.data)
        self.assertEqual(run.output, self.root / 'result')
        self.assertEqual(run.sources[0].node_id, run.sources[1].node_id)
        self.assertNotEqual(run.sources[0].board_id, run.sources[1].board_id)
        self.assertEqual(len(run.sources[0].cameras), 4)
        self.assertEqual(run.scan_order, tuple(range(96)))

    def test_custom_camera_profile(self):
        profile = {'schema_version': 1, 'kind': 'camera', 'model': 'custom',
                   'image': {'width': 640, 'height': 480, 'dtype': 'uint8', 'channels': 1},
                   'shutter': 'global', 'views': [{'id': 'full', 'crop_xywh': [0, 0, 640, 480]}]}
        (self.root / 'camera.json').write_text(json.dumps(profile))
        data = copy.deepcopy(self.data)
        data.pop('comparison')
        data['sources'] = [data['sources'][0]]
        data['sources'][0].update(profile='camera.json', camera_ids={'full': 'camera'})
        self.assertEqual(self.load(data).sources[0].cameras[0].crop, (0, 0, 640, 480))

    def test_old_protocol_and_localization_options_are_rejected(self):
        for change in ('protocol', 'localization'):
            data = copy.deepcopy(self.data)
            if change == 'protocol': data['target']['protocol'] = 'r4-permuted96-v1'
            else: data['localization']['orientation_margin'] = 2
            with self.subTest(change=change), self.assertRaises(ConfigError): self.load(data)

    def test_duplicate_identities_bad_pairs_and_unknown_fields(self):
        for change in ('camera', 'board', 'pairs', 'unknown', 'exposure', 'reference'):
            data = copy.deepcopy(self.data)
            if change == 'camera': data['sources'][1]['camera_ids']['view_0'] = 'a_camera_0'
            elif change == 'board': data['sources'][1]['sync_board_id'] = data['sources'][0]['sync_board_id']
            elif change == 'pairs': data['comparison']['frame_pairs'] = [[1, 1], [0, 0]]
            elif change == 'unknown': data['guess_size'] = True
            elif change == 'exposure': data['sources'][0]['exposure'] = {'value_us': 4000, 'provenance': 'unknown'}
            else: data['localization']['reference'] = None
            with self.subTest(change=change), self.assertRaises(ConfigError): self.load(data)

    def test_unreadable_wrong_size_color_and_uint16_frames(self):
        source = self.load(self.data).sources[0]
        with self.assertRaises(ConfigError): read_frame(self.root / 'absent.png', source)
        for image in (np.zeros((20, 20), np.uint8), np.zeros((800, 5120, 3), np.uint8),
                      np.zeros((800, 5120), np.uint16)):
            path = self.root / 'bad.png'; cv2.imwrite(str(path), image)
            with self.subTest(shape=image.shape, dtype=str(image.dtype)), self.assertRaises(ConfigError):
                read_frame(path, source)
