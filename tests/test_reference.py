"""Reference geometry is checked against independent synthetic correspondences."""

import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

import cv2
import numpy as np

from camsync_check.config import Camera, ConfigError, load_config
from camsync_check.localize import localize, refine_grid
from camsync_check.reference import ReferenceMatcher, load_reference
from camsync_check.vision import make_sampling
from fixtures import CENTERS, CORNERS, HEIGHT, WIDTH, config, exposure, reference


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.image = reference(self.root)
        config(self.root)
        self.run = load_config(self.root / "run.json")
        self.reference = load_reference(self.run)
        self.matcher = ReferenceMatcher(self.reference)

    def test_reference_masks_changing_leds(self):
        self.assertEqual(self.reference.mask[160, 210], 0)
        self.assertGreater(np.count_nonzero(self.reference.mask), 100)
        self.assertEqual(len(self.reference.metadata["image_sha256"]), 64)

    def test_original_rotated_reflected_and_perspective_views(self):
        transforms = [np.eye(3), np.array([[0, -1, 400], [1, 0, 20], [0, 0, 1.0]]),
                      np.array([[-1, 0, 470], [0, 1, 30], [0, 0, 1.0]]),
                      np.array([[0.95, 0.08, 30], [-0.03, 1.03, 30], [0.0002, -0.0001, 1]])]
        for transform in transforms:
            with self.subTest(transform=transform.tolist()):
                frame = cv2.warpPerspective(exposure(self.image, 2000, 2000), transform, (520, 500))
                geometry, evidence = self.matcher.locate(frame, Camera("view", (0, 0, 520, 500)))
                expected = cv2.perspectiveTransform(CENTERS.reshape(1, -1, 2), transform)[0]
                self.assertLess(np.linalg.norm(geometry.centers - expected, axis=1).max(), 0.8)
                self.assertGreaterEqual(evidence["inliers"], 12)

    def test_blank_and_unrelated_images_are_rejected(self):
        rng = np.random.default_rng(41)
        for view in (np.zeros_like(self.image), rng.integers(0, 255, self.image.shape, dtype=np.uint8)):
            with self.subTest(blank=bool(view.max() == 0)), self.assertRaisesRegex(ConfigError, "reference_not_found"):
                self.matcher.locate(view, Camera("view", (0, 0, WIDTH, HEIGHT)))

    def test_noise_and_brightness_changes(self):
        noise = np.random.default_rng(18).normal(0, 2, self.image.shape)
        frame = np.clip(self.image.astype(float) * 0.8 + 12 + noise, 0, 255).astype(np.uint8)
        geometry, _ = self.matcher.locate(frame, Camera("view", (0, 0, WIDTH, HEIGHT)))
        self.assertLess(np.linalg.norm(geometry.centers - CENTERS, axis=1).max(), 0.8)

    def test_refinement_does_not_require_all_96_leds(self):
        projection = np.zeros_like(self.image)
        for index in list(range(16, 28)) + list(range(50, 62)):
            x, y = CENTERS[index]
            cv2.circle(projection, (int(x), int(y)), 3, 180, -1)
        camera = Camera("view", (0, 0, WIDTH, HEIGHT))
        initial = make_sampling(np.array(CORNERS) + 0.8, camera)
        refined, evidence = refine_grid(projection, camera, initial, 20)
        self.assertEqual(evidence["observed_leds"], 24)
        self.assertLess(np.linalg.norm(refined.centers - CENTERS, axis=1).max(), 0.4)

    def test_no_changing_leds_and_single_row_are_rejected(self):
        camera = Camera("view", (0, 0, WIDTH, HEIGHT))
        initial = make_sampling(CORNERS, camera)
        projection = np.zeros_like(self.image)
        for state in ("blank", "single_row"):
            if state == "single_row":
                for x, y in CENTERS[:12]:
                    cv2.circle(projection, (int(x), int(y)), 3, 180, -1)
            with self.subTest(state=state), self.assertRaisesRegex(ConfigError, "insufficient_led_evidence"):
                refine_grid(projection, camera, initial, 20)

    def test_invalid_reference_dimensions_and_polygons(self):
        path = self.root / "reference.json"
        original = json.loads(path.read_text())
        for key, value in (("image_size", [1, 2]), ("feature_polygon_xy", [[-1, 0], [20, 0], [20, 30]])):
            path.write_text(json.dumps(original | {key: value}))
            with self.subTest(key=key), self.assertRaises(ConfigError):
                load_reference(self.run)

    def test_builtin_reference_is_usable_and_oriented(self):
        run = replace(self.run, localization=replace(self.run.localization, reference="builtin:uno_r4_wifi"))
        built_in = load_reference(run)
        matcher = ReferenceMatcher(built_in)
        geometry, _ = matcher.locate(built_in.image, Camera("view", (0, 0, 1920, 1080)))
        np.testing.assert_allclose(geometry.centers[[0, 11, 95, 84]], [[971, 553], [1267, 553], [1267, 743], [971, 743]], atol=0.1)

    def test_moving_and_conflicting_reference_frames_invalidate_the_view(self):
        camera = Camera("view", (0, 0, WIDTH, HEIGHT))
        paths = (self.root / "frame0.png", self.root / "frame1.png")
        for path in paths:
            cv2.imwrite(str(path), self.image)
        source = replace(self.run.sources[0], width=WIDTH, height=HEIGHT, cameras=(camera,), frames=paths)
        run = replace(self.run, sources=(source,))
        original = make_sampling(CORNERS, camera)
        moved = make_sampling(np.array(CORNERS) + [10, 0], camera)
        reversed_grid = make_sampling(np.array(CORNERS)[[2, 3, 0, 1]], camera)
        for second in (moved, reversed_grid):
            with self.subTest(reversed=second is reversed_grid), patch(
                    "camsync_check.localize.ReferenceMatcher.locate",
                    side_effect=[(original, {}), (second, {})]):
                result, sampling = localize(run)
                self.assertEqual(result["cameras"]["view"]["reason"], "moving_or_inconsistent_reference")
                self.assertIsNone(sampling["view"])
