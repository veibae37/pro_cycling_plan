"""Behavioral acceptance: one prescription, constraints, revisions and exports."""
import copy
from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.exports import export_bundle, ics, zwo
from src.planning import assess_plan, normalize_plan, validate_profile
from src.state import TrainingStore
from src.tier_calculator import RiderProfile, generate_workout
from src.workout import Step, Workout

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    return tuple(json.loads((ROOT/'examples'/p).read_text(encoding='utf-8'))
                 for p in ('portable-plan.json', 'athlete-profile.json'))


class WorkoutTests(unittest.TestCase):
    def test_all_models_and_modifiers_use_exact_expanded_metrics(self):
        models = ('lt1', 'fast_vo2', 'lt2', 'z3_z4_spikes', 'vo2_over_under', 'short_30_30', 'recovery')
        for age in ('<30', '30-44', '45-54', '55+'):
            for indoor in (True, False):
                for model in models:
                    with self.subTest(age=age, indoor=indoor, model=model):
                        analysis = RiderProfile(70, cp60_watts=250, age_group=age, indoor=indoor).analyze()
                        generated = generate_workout(analysis, model)
                        workout = Workout.from_dict(generated['workout'])
                        self.assertEqual(workout, Workout.from_text(generated['intervals_icu_code']))
                        self.assertEqual(workout.duration_seconds, generated['duration_seconds'])
                        metrics = workout.metrics(250)
                        self.assertEqual(generated['estimated_tss'], metrics['estimated_tss'])
                        self.assertEqual(generated['estimated_work_kj'], metrics['work_kj'])
                        self.assertAlmostEqual(generated['total_duration_min']*60, workout.duration_seconds, delta=.031)

    def test_tiers_strength_and_recovery(self):
        for ftp in (200, 260, 350):
            for strength in ('none', 'moderate', 'heavy'):
                analysis = RiderProfile(70, cp60_watts=ftp, leg_strength=strength).analyze()
                for model in ('lt2', 'short_30_30', 'recovery'):
                    w = generate_workout(analysis, model)
                    self.assertEqual(w['metrics'], Workout.from_dict(w['workout']).metrics(ftp))
                    if model == 'recovery':
                        self.assertTrue(all(s.high_pct <= 63 for s in Workout.from_dict(w['workout']).steps))
        with self.assertRaises(ValueError):
            generate_workout(analysis, 'typo')
        for profile in (RiderProfile(0, cp60_watts=200), RiderProfile(70, cp60_watts=-2), RiderProfile(70, cp60_watts=200, age_group='unknown')):
            with self.assertRaises(ValueError):
                profile.analyze()

    def test_canonical_roundtrip_and_range_scenarios(self):
        workout = Workout.from_text('Main 2x\n- 17s 110-120%\n- 43s 50%')
        self.assertEqual(workout, Workout.from_dict(workout.to_dict()))
        self.assertEqual(workout, Workout.from_text(workout.to_text()))
        self.assertEqual(workout.duration_seconds, 120)
        for invalid in ((True, 50, 50), (0, 50, 50), (1, 80, 60), (1, float('nan'), 90)):
            with self.assertRaises(ValueError):
                Step(*invalid)


class FeasibilityTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.profile = fixtures()

    def assess(self):
        return assess_plan(self.plan, self.profile, today=date(2026, 10, 18))

    def codes(self):
        return {i['code'] for i in self.assess()['issues']}

    def test_ready_fixture_and_known_numbers(self):
        result = self.assess()
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['weeks'][0]['hours'], 1)
        self.assertEqual(result['weeks'][0]['estimated_tss'], 50.77)

    def test_availability_is_not_tolerated_load(self):
        self.plan['sessions'][0]['workout'] = '- 180m 100%'
        self.profile['recent_weeks'][0].update(hours=1, tss=40)
        self.profile['recent_weeks'][1].update(hours=1, tss=40)
        self.assertTrue({'load_jump_hours', 'load_jump_tss'} <= self.codes())

    def test_rest_day_daily_and_weekly_caps(self):
        self.plan['sessions'][0]['date'] = '2026-11-02'
        self.profile['availability'].update(weekly_hours=.5, max_session_hours=.5)
        self.assertTrue({'rest_day', 'session_cap', 'daily_cap', 'weekly_cap'} <= self.codes())
        self.assertEqual(self.assess()['status'], 'blocked')

    def test_missing_history_wellness_and_thresholds_are_unknown(self):
        self.profile.pop('recent_weeks')
        self.profile.pop('wellness')
        self.profile.pop('thresholds')
        self.plan['pi_min'] = 1.5
        self.assertTrue({'history_unknown', 'wellness_unknown', 'thresholds_unknown'} <= self.codes())
        self.assertEqual(self.assess()['status'], 'review')

    def test_high_fatigue_and_quality(self):
        self.profile['wellness']['fatigue'] = 'high'
        self.assertIn('fatigue_quality', self.codes())
        self.assertEqual(self.assess()['status'], 'blocked')

    def test_target_conflicts_undefined_pi_and_ftp_mismatch(self):
        self.plan.update(weekly_tss_range=[10, 20], pi_min=1.5, distribution='polarized', ftp=210)
        self.plan['sessions'][0]['workout'] = '- 60m 50%'
        self.assertTrue({'ftp_mismatch', 'tss_target', 'pi_target', 'distribution_target'} <= self.codes())

    def test_profile_validation_and_duplicate_ids(self):
        self.profile['ftp']['date'] = 'yesterday'
        with self.assertRaises(ValueError):
            validate_profile(self.profile)
        self.plan['sessions'] *= 2
        with self.assertRaises(ValueError):
            normalize_plan(self.plan)

    def test_pyramidal_target_is_actually_checked(self):
        self.plan['distribution'] = 'pyramidal'
        self.assertIn('distribution_target', self.codes())
        self.plan['distribution'] = 'typo'
        with self.assertRaises(ValueError):
            self.assess()

    def test_combined_daily_cap_and_stale_recovery(self):
        second = copy.deepcopy(self.plan['sessions'][0])
        second['session_id'] = 'second-ride'
        self.plan['sessions'].append(second)
        self.profile['availability']['daily_hours'] = {'1': 1.5}
        self.profile['wellness']['date'] = '2026-10-01'
        self.assertTrue({'daily_cap', 'wellness_unknown'} <= self.codes())

    def test_invalid_pi_and_sequence_fail_even_when_no_thresholds(self):
        self.profile.pop('thresholds')
        self.plan['pi_min'] = float('nan')
        with self.assertRaises(ValueError):
            self.assess()
        self.plan.pop('pi_min')
        self.plan['revision'] = -1
        with self.assertRaises(ValueError):
            normalize_plan(self.plan)


class StateAndExportTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.profile = fixtures()
        temporary_root = ROOT/'.training-state'/'test-temp'
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.store = TrainingStore(Path(self.temporary.name)/'state')

    def test_revisions_survive_reload_and_actuals_keep_original_prescription(self):
        self.store.save_profile(self.profile, 'Initial measured settings')
        first = self.store.save_plan(self.plan, 'Initial plan', 'demo-rider')
        actual = self.store.record_actual(self.plan['plan_id'], 'climb-01', dict(rpe=8, completion=.8, duration_seconds=3000, tss=40))
        original = copy.deepcopy(actual)
        self.plan['sessions'][0]['date'] = '2026-11-04'
        self.plan['sessions'][0]['workout'] = '- 45m 50%'
        second = self.store.save_plan(self.plan, 'Reduce after difficult ride', 'demo-rider')
        reloaded = TrainingStore(self.store.root)
        self.assertEqual(len(reloaded.history('plans', self.plan['plan_id'])), 2)
        self.assertEqual(second['diff']['changed'], ['climb-01'])
        self.assertEqual(second['previous_hash'], first['hash'])
        self.assertEqual(reloaded.history('actuals', self.plan['plan_id'])[0], original)
        self.assertEqual(actual['plan_revision'], 1)
        self.assertEqual(actual['comparison']['duration_seconds']['difference'], -600)
        late_feedback = self.store.record_actual(self.plan['plan_id'], 'climb-01', dict(tss=40), plan_revision=1)
        self.assertEqual(late_feedback['plan_revision'], 1)
        self.assertAlmostEqual(late_feedback['comparison']['tss']['planned'], 50.77)
        with self.assertRaises(ValueError):
            self.store.save_profile(self.profile, '')
        with self.assertRaises(ValueError):
            self.store.history('plans', '../escape')
        with self.assertRaises(ValueError):
            self.store.record_actual(self.plan['plan_id'], 'climb-01', dict(rpe=11))

    def test_zwo_matches_duration_work_and_scenario(self):
        workout = Workout.from_text('- 30m 50-60%\n- 30m 100%')
        for scenario in ('low', 'midpoint', 'high'):
            xml = ET.fromstring(zwo(workout, 'Climb & <surge>', scenario))
            blocks = list(xml.find('workout'))
            self.assertEqual(sum(int(b.attrib['Duration']) for b in blocks), 3600)
            kj = sum(int(b.attrib['Duration'])*float(b.attrib['Power'])*200/1000 for b in blocks)
            self.assertAlmostEqual(kj, workout.metrics(200, scenario=scenario)['work_kj'])
            self.assertEqual(xml.findtext('name'), 'Climb & <surge>')

    def test_ics_escaping_unicode_folding_stable_uid_and_dates(self):
        self.plan['sessions'][0]['name'] = '爬坡;冲刺,耐力\\' * 30
        generated_at = datetime(2026, 10, 18, tzinfo=timezone.utc)
        text = ics(self.plan, generated_at=generated_at)
        self.assertTrue(text.endswith('\r\n'))
        self.assertTrue(all(len(line.encode('utf-8')) <= 75 for line in text.split('\r\n')))
        unfolded = text.replace('\r\n ', '')
        self.assertIn('SUMMARY:爬坡\\;冲刺\\,耐力\\\\', unfolded)
        self.assertIn('DTSTART;VALUE=DATE:20261103', unfolded)
        self.assertIn('DTEND;VALUE=DATE:20261104', unfolded)
        uid = next(l for l in text.split('\r\n') if l.startswith('UID:'))
        self.plan['sessions'][0]['date'] = '2026-11-04'
        self.assertIn(uid, ics(self.plan, generated_at=generated_at))

    def test_export_bundle_and_no_overwrite(self):
        out = Path(self.temporary.name)/'export'
        result = export_bundle(self.plan, out)
        self.assertEqual(set(result['files']), {'plan.ics', 'climb-01.zwo', 'manifest.json'})
        with self.assertRaises(ValueError):
            export_bundle(self.plan, out)


if __name__ == '__main__':
    unittest.main()
