"""Synthetic fixtures only. No live credentials, athlete IDs or network calls."""
import copy
import json
import unittest
from urllib.parse import parse_qs, urlparse
import httpx
from src.intervals import IntervalsClient
from src.power_profile import (DURATIONS, GROUP_FACTORS, prepare_intake, normalize_curves,
                               fit_cp_candidate, assess_power_curves, summarize_steady_streams, history_coverage)
from src.tier_calculator import RiderProfile


def fixture():
    powers = [1000, 650, 500, 350, 310, 275, 265, 250, 245]
    ids = ['i1', 'i1', 'i1', 'i1', 'i2', 'i3', 'i4', 'i4', 'i4']
    return {'list': [{'id': '90d', 'days': 91, 'start_date_local': '2026-07-22T00:00:00',
                      'end_date_local': '2026-10-20T00:00:00', 'secs': list(DURATIONS),
                      'watts': powers, 'activity_id': ids}],
            'activities': {f'i{i}': {'icu_weight': 70, 'start_date_local': f'2026-10-{10+i:02}T08:00:00'}
                           for i in range(1, 5)}}


class IntakeTests(unittest.TestCase):
    def test_cp20_only_asks_optional_points_without_reasking_20m(self):
        r = prepare_intake(250, 70)
        self.assertEqual(len(r['optional_missing']), 8)
        self.assertNotIn('20m', r['optional_missing'])
        self.assertIsNone(r['working_ftp_w'])
        self.assertFalse(any(c['selected'] for c in r['group_candidates']))
        self.assertEqual([c['predicted_p60_w'] for c in r['group_candidates']], [220, 230, 237.5, 240])
        self.assertFalse(r['scaling']['research_group_inferred'])

    def test_declared_group_requires_a_basis_and_does_not_adopt_ftp(self):
        with self.assertRaises(ValueError):
            prepare_intake(250, 70, performance_group='trained')
        r = prepare_intake(250, 70, performance_group='trained', group_basis='self_report')
        self.assertEqual(r['selected_candidate']['coefficient'], .92)
        self.assertIsNone(r['working_ftp_w'])

    def test_invalid_values_and_conflicting_p20(self):
        for x in [True, 0, -1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                prepare_intake(cp20_watts=x)
        with self.assertRaises(ValueError):
            prepare_intake(250, known_points={'1200': 200})

    def test_generator_stops_before_blind_conversion_and_cp1_does_not_choose_factor(self):
        with self.assertRaises(ValueError):
            RiderProfile(70, cp20_watts=250).analyze()
        for cp1 in (200, 800):
            r = RiderProfile(70, cp20_watts=250, cp1_watts=cp1,
                             performance_group='trained', group_basis='vo2max_report', cp20_is_maximal=True).analyze()
            self.assertEqual(r['effective_ftp_w'], 230)
        r = RiderProfile(70, cp60_watts=240, cp20_watts=250).analyze()
        self.assertEqual(r['effective_ftp_w'], 240)

    def test_nonmaximal_training_does_not_calibrate_or_predict_ftp(self):
        r = assess_power_curves(fixture(), '2026-10-20', working_ftp_w=200,
                                effort_status='training_not_maximal', working_ftp_note='Old test, date unknown')
        self.assertEqual(r['cp']['status'], 'submaximal_only_no_ftp_inference')
        self.assertEqual(r['cp']['models'], [])
        self.assertFalse(r['intake']['prediction_eligible'])
        self.assertTrue(all(c['status'] == 'illustrative_only_submaximal_p20' for c in r['intake']['group_candidates']))
        with self.assertRaises(ValueError):
            RiderProfile(70, cp20_watts=250, performance_group='trained', group_basis='self_report').analyze()


class CurveTests(unittest.TestCase):
    def test_missing_six_seconds_not_substituted_with_five(self):
        f = fixture()
        f['list'][0]['secs'][0] = 5
        r = normalize_curves(f, '2026-10-20')[0]
        self.assertIsNone(r['points'][0]['watts'])
        self.assertEqual(r['api_reported_days'], 91)
        self.assertEqual(r['points'][3]['date'], '2026-10-11')

    def test_activity_weight_not_different_platform_wkg_max(self):
        f = fixture()
        f['list'][0]['watts_per_kg'] = [99]*9
        r = normalize_curves(f, '2026-10-20')[0]
        self.assertAlmostEqual(r['points'][0]['watts_per_kg'], 14.286)
        f['activities']['i1'].pop('icu_weight')
        self.assertIsNone(normalize_curves(f, '2026-10-20')[0]['points'][0]['watts_per_kg'])

    def test_model_math_sensitivity_and_no_false_thresholds(self):
        r = assess_power_curves(fixture(), '2026-10-20', working_ftp_w=240, weight_kg=70)
        for m in r['cp']['models']:
            self.assertEqual(m['cp_w'], 250)
            self.assertEqual(m['w_prime_j'], 18000)
        self.assertEqual(r['intake']['working_ftp_w'], 240)
        self.assertEqual(r['thresholds']['lt1']['status'], 'not_measured')
        self.assertEqual(r['thresholds']['lt2']['status'], 'not_measured')
        self.assertFalse(r['cp']['adopted_as_ftp'])
        self.assertIn('maximal_efforts_not_confirmed', r['cp']['quality_reasons'])
        self.assertEqual(r['account_writes'], 0)

    def test_malformed_alignment_fails_and_inversion_preserved(self):
        f = fixture()
        f['list'][0]['watts'].pop()
        with self.assertRaises(ValueError):
            normalize_curves(f, '2026-10-20')
        f = fixture()
        f['list'][0]['watts'][6] = 280
        r = normalize_curves(f, '2026-10-20')[0]
        self.assertEqual(r['points'][6]['watts'], 280)
        self.assertTrue(r['inversions'])

    def test_insufficient_and_nonphysical_fits(self):
        self.assertEqual(fit_cp_candidate([])['status'], 'insufficient_anchors')
        points = normalize_curves(fixture(), '2026-10-20')[0]['points']
        for p in points:
            p['watts'] = 250
        self.assertEqual(fit_cp_candidate(points)['status'], 'invalid_model')


class TransportTests(unittest.TestCase):
    def test_read_paths_and_bounds_never_write(self):
        calls = []
        def handler(request):
            self.assertEqual(request.method, 'GET')
            calls.append(request.url)
            return httpx.Response(200, json=fixture())
        client = IntervalsClient('0', 'test-key', transport=httpx.MockTransport(handler))
        client.power_curves('2026-10-20')
        q = parse_qs(calls[0].query.decode())
        self.assertEqual(q['curves'], ['42d,90d,365d'])
        self.assertEqual(q['newest'], ['2026-10-20'])
        client.activity_streams('i123')
        self.assertEqual(calls[1].path, '/api/v1/activity/i123/streams')
        self.assertNotIn('latlng', str(calls[1]))
        for window in [[], [90, 90], [True], [-1], [float('inf')]]:
            with self.assertRaises(ValueError):
                client.power_curves('2026-10-20', window)
        with self.assertRaises(ValueError):
            client.activity_streams('../events')
        self.assertEqual(len(calls), 2)

    def test_coverage_is_not_number_of_best_effort_sources_and_stubs_are_unknown(self):
        metadata = [{'id': 'i1', 'type': 'Ride', 'start_date_local': '2026-10-11T08:00:00', 'icu_average_watts': 140},
                    {'id': 'i2', 'type': 'Run', 'start_date_local': '2026-10-12T08:00:00'},
                    {'id': 'i3'}]
        curves = normalize_curves(fixture(), '2026-10-20')
        r = history_coverage(metadata, curves)
        self.assertEqual(r['windows'][0]['rides'], 1)
        self.assertEqual(r['windows'][0]['rides_with_power_metadata'], 1)
        self.assertEqual(r['type_missing_count'], 1)
        self.assertEqual(r['date_missing_count'], 1)
        self.assertEqual(r['windows'][0]['unclassified_in_window'], 0)


class SteadyTests(unittest.TestCase):
    def streams(self):
        return [dict(type='time', data=list(range(4000))), dict(type='watts', data=[150]*4000),
                dict(type='heartrate', data=[120]*2100+[126]*1900)]

    def test_descriptive_decoupling_not_lt1(self):
        r = summarize_steady_streams(self.streams())
        self.assertEqual(r['mean_power_w'], 150)
        self.assertAlmostEqual(r['power_hr_decoupling_pct'], 4.76, places=2)
        self.assertIsNone(r['lt1_w'])

    def test_null_gap_and_coasting_preserved(self):
        s = self.streams()
        s[0]['data'][1000] += .5
        self.assertIn('not_continuous', summarize_steady_streams(s)['status'])
        s = self.streams()
        s[1]['data'][1000] = None
        self.assertIn('invalid_samples', summarize_steady_streams(s)['status'])
        s = self.streams()
        s[1]['data'][1000] = 0
        r = summarize_steady_streams(s)
        self.assertLess(r['mean_power_w'], 150)
        self.assertGreater(r['power_cv'], 0)


if __name__ == '__main__':
    unittest.main()
