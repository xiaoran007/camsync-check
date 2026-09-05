"""Timing assertions use known exposure windows rather than decoder-generated labels."""

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

import numpy as np

from camsync_check.analysis import compare, statistics
from camsync_check.config import Camera, Settings, load_config
from camsync_check.vision import decode, make_sampling, sample
from fixtures import CORNERS, HEIGHT, WIDTH, config, exposure, reference


SETTINGS = Settings(20, 5, 0.25, 1, 10000, 1000, None)


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.image = reference(root)
        config(root)
        self.run = load_config(root / "run.json")
        self.geometry = make_sampling(CORNERS, Camera("view", (0, 0, WIDTH, HEIGHT)))

    def observe(self, start, duration):
        signals, saturated = sample(exposure(self.image, start, duration), self.geometry)
        return decode(signals, saturated, SETTINGS, 250)

    def test_start_bounds_with_unknown_and_varying_exposure(self):
        for start in (0, 130, 249, 23750, 23900):
            for duration in (900, 2000, 4250):
                with self.subTest(start=start, duration=duration):
                    observation = self.observe(start, duration)
                    if (start, duration) == (130, 900):
                        # The last pulse overlaps for 30 us: 160 * 30 / 250 is near threshold 20.
                        self.assertEqual(observation['reason'], 'threshold_ambiguous')
                        continue
                    self.assertEqual(observation['status'], 'valid', observation)
                    phase_error = (observation['phase_start_us'] - start + 12000) % 24000 - 12000
                    self.assertLessEqual(abs(phase_error), 250)
                    self.assertLessEqual(observation['exposure_min_us'], duration)
                    self.assertGreaterEqual(observation['exposure_max_us'], duration)

    def test_wraparound_and_signed_offset(self):
        left, right = self.observe(23500, 2000), self.observe(24500, 3500)
        result = compare(left, right, self.run)
        self.assertEqual(result['status'], 'valid')
        self.assertEqual(result['offset_us'], 1000)
        self.assertEqual((result['lower_us'], result['upper_us']), (500, 1500))
        self.assertEqual(compare(right, left, self.run)['offset_us'], -1000)

    def test_invalid_binary_patterns(self):
        cases = []
        cases.append((np.zeros(96), np.zeros(96), 'no_lit_leds'))
        cases.append((np.full(96, 100), np.zeros(96), 'full_or_near_full_cycle'))
        signals = np.zeros(96); signals[[0, 2]] = 100
        cases.append((signals, np.zeros(96), 'disconnected_lit_intervals'))
        signals = np.zeros(96); signals[0] = 20
        cases.append((signals, np.zeros(96), 'threshold_ambiguous'))
        signals = np.zeros(96); signals[0] = 100
        saturation = np.zeros(96); saturation[0] = 0.5
        cases.append((signals, saturation, 'saturated'))
        for signals, saturation, reason in cases:
            with self.subTest(reason=reason):
                result = decode(signals, saturation, SETTINGS, 250)
                self.assertEqual(result['reason'], reason)
                self.assertIsNone(result['phase_start_us'])

    def test_cycle_prior_and_invalid_observations(self):
        left = {'status': 'valid', 'reason': '', 'phase_start_us': 0}
        for offset, reason in ((11000, 'offset_prior_not_satisfied'), (9750, 'offset_prior_boundary')):
            result = compare(left, left | {'phase_start_us': offset}, self.run)
            self.assertEqual(result['reason'], reason)
            self.assertEqual(result['status'], 'invalid')
        ambiguous_run = replace(self.run, settings=replace(SETTINGS, max_offset_us=11999))
        self.assertEqual(compare(left, left | {'phase_start_us': 12000}, ambiguous_run)['reason'], 'ambiguous_cycle')
        invalid = compare(left, {'status': 'invalid', 'reason': 'saturated'}, self.run)
        self.assertIsNone(invalid['offset_us'])
        self.assertEqual(invalid['decision'], 'inconclusive')

    def test_tolerance_decisions_use_entire_interval(self):
        run = replace(self.run, settings=replace(SETTINGS, pass_tolerance_us=1000))
        left = {'status': 'valid', 'reason': '', 'phase_start_us': 0}
        for offset, decision in ((0, 'pass'), (1000, 'inconclusive'), (2000, 'fail')):
            with self.subTest(offset=offset):
                self.assertEqual(compare(left, left | {'phase_start_us': offset}, run)['decision'], decision)

    def test_statistics_and_insufficient_coverage(self):
        rows = [{'status': 'valid', 'reason': '', 'offset_us': value, 'reference_frame': i}
                for i, value in enumerate((0, 250, 500))]
        rows.append({'status': 'invalid', 'reason': 'missing', 'reference_frame': 3})
        result = statistics(rows, 20000)
        self.assertEqual(result['median_offset_us'], 250)
        self.assertEqual(result['observed_jitter_std_us'], 250)
        self.assertEqual(result['drift_us_per_reference_frame'], 250)
        self.assertEqual(result['drift_us_per_second'], 12500)
        self.assertEqual(result['valid_fraction'], 0.75)
        self.assertEqual(result['rejection_counts'], {'missing': 1})
        self.assertIsNone(statistics(rows[:1])['observed_jitter_std_us'])
        self.assertIsNone(statistics(rows[:2])['drift_us_per_reference_frame'])
        self.assertIsNone(statistics([])['median_offset_us'])
