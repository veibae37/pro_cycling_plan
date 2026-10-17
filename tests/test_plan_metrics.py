"""Arithmetic and boundary checks for planned-load estimates, without API calls."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from plan_metrics import estimate, estimate_week, parse_workout, polarization


class MetricsTests(unittest.TestCase):
    def test_one_hour_at_ftp(self):
        result = estimate([(3600, 100, 100)], 250)
        self.assertEqual(result['work_kj'], 900)
        self.assertEqual(result['estimated_np_w'], 250)
        self.assertEqual(result['estimated_tss'], 100)

    def test_repeat_duration_and_final_recovery(self):
        steps = parse_workout('Warmup\n- 10m 50%\n\nMain 9x\n- 45s 125-130%\n- 30s 50%\n\nCooldown\n- 5m 50%')
        self.assertEqual(sum(s for s, _, _ in steps), 1575)
        self.assertEqual(len(steps), 20)
        self.assertLess(estimate(steps, 250, scenario='low')['work_kj'],
                        estimate(steps, 250, scenario='high')['work_kj'])

    def test_variable_load_uses_rolling_power(self):
        result = estimate([(1800, 50, 50), (1800, 100, 100)], 250)
        self.assertEqual(result['work_kj'], 675)
        # Long constant halves approach ((0.5**4 + 1**4)/2)**0.25 FTP.
        self.assertAlmostEqual(result['estimated_np_w'] / 250,
                               ((.5**4 + 1) / 2)**.25, delta=.003)
        self.assertGreater(result['estimated_tss'], 56.25)

    def test_pi_is_normalized_and_scale_invariant(self):
        result = polarization([648, 24, 48])
        self.assertAlmostEqual(result['pi'], math.log10(180), places=4)
        self.assertEqual(result['classification'], 'polarized')
        self.assertEqual(result['pi'], polarization([.9, 1/30, 1/15])['pi'])
        self.assertEqual(polarization([480, 90, 30])['classification'], 'pyramidal')

    def test_zero_zones_are_not_faked(self):
        self.assertIsNone(polarization([600, 0, 60])['pi'])
        self.assertIsNone(polarization([600, 60, 0])['pi'])
        with self.assertRaises(ValueError):
            polarization([0, 0, 0])
        with self.assertRaises(ValueError):
            polarization([-1, 2, 3])

    def test_zone_boundaries_and_short_record(self):
        result = estimate([(60, 70, 70), (60, 100, 100), (60, 110, 110)],
                          250, lt1_pct=70, lt2_pct=100)
        self.assertEqual(result['three_zone_distribution']['zone_minutes'], [1, 1, 1])
        self.assertNotIn('three_zone_distribution', estimate([(60, 60, 60)], 250))
        self.assertIsNone(estimate([(15, 150, 150)], 250)['estimated_tss'])

    def test_invalid_inputs_fail(self):
        for text in ('- 10m sprint', '- 10m 130-120%', '- 0s 50%', '- 10m ramp 50-80%'):
            with self.assertRaises(ValueError):
                parse_workout(text)
        with self.assertRaises(ValueError):
            estimate([(60, 60, 60)], 0)
        with self.assertRaises(ValueError):
            estimate([(60, 60, 60)], 250, lt1_pct=100, lt2_pct=70)
        with self.assertRaises(ValueError):
            polarization([math.nan, 2, 3])

    def test_week_adds_sessions_instead_of_concatenating_power(self):
        result = estimate_week({'ftp': 250, 'weekly_tss_range': [120, 130], 'sessions': [
            {'day': 'Tue', 'workout': '- 60m 100%'},
            {'day': 'Thu', 'workout': '- 60m 50%'},
        ]})
        self.assertEqual(result['estimated_week_tss'], 125)
        self.assertEqual(result['total_hours'], 2)
        self.assertTrue(result['within_tss_range'])

    def test_example_workout_and_week_match_published_numbers(self):
        import json
        root = Path(__file__).resolve().parents[1]
        week = estimate_week(json.loads((root/'examples/polarized-week.json').read_text(encoding='utf-8')))
        self.assertEqual(week['total_hours'], 12)
        self.assertAlmostEqual(week['estimated_week_tss'], 544.61)
        self.assertEqual(week['three_zone_distribution']['zone_minutes'], [648, 24, 48])
        climb = estimate(parse_workout((root/'examples/z2-climbing.txt').read_text(encoding='utf-8')), 250)
        self.assertEqual(climb['duration_seconds'], 5400)
        self.assertEqual(climb['work_kj'], 806.25)
        self.assertEqual(climb['estimated_kcal_range'], [771, 963])


if __name__ == '__main__':
    unittest.main()
