"""Calendar contract tests: idempotency, stale previews and ambiguous writes."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.intervals import ApiError, CalendarSync, IntervalsClient, event_payloads, parsed_steps
from src.state import TrainingStore
from src.workout import Workout
from test_training_workflow import ROOT, fixtures


class FakeCalendar:
    """An API boundary fake: global upsert, date-filtered reads and parsed structure."""
    def __init__(self, *, ftp=200):
        self.events, self.writes, self.ftp = {}, 0, ftp
        self.timeout_after_write = False
        self.partial = False
        self.empty_steps = False
        self.read_error = False

    def request(self, path, method='GET', payload=None):
        if method == 'GET':
            if self.read_error:
                raise ApiError('read unavailable')
            q = parse_qs(urlparse(path).query)
            return copy.deepcopy([e for e in self.events.values()
                                  if q['oldest'][0] <= e['start_date_local'][:10] <= q['newest'][0]])
        if path != '/events/bulk?upsert=true' or method != 'POST':
            raise AssertionError('Unexpected endpoint or write method')
        self.writes += 1
        for p in payload[:1] if self.partial else payload:
            steps = Workout.from_text(p['description']).steps
            existing = self.events.get(p['external_id'])
            e = dict(copy.deepcopy(p), id=existing['id'] if existing else len(self.events)+1,
                     workout_doc=dict(steps=[] if self.empty_steps else [
                         dict(duration=s.duration_seconds, power={'units': '%ftp', 'value': s.low_pct},
                              _power={'value': self.ftp*s.low_pct/100}) for s in steps]))
            self.events[p['external_id']] = e
        if self.timeout_after_write:
            raise ApiError('write response timed out')
        return list(self.events.values())


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.profile = fixtures()
        self.api = FakeCalendar()
        self.syncer = CalendarSync(self.api.request)

    def sync(self):
        preview = self.syncer.preview(self.plan)
        return self.syncer.sync(self.plan, preview['preview_hash'])

    def test_preview_no_write_and_repeat_is_noop(self):
        self.syncer.preview(self.plan)
        self.assertEqual(self.api.writes, 0)
        self.assertEqual(self.sync()['status'], 'verified')
        self.assertEqual(self.sync()['status'], 'verified')
        self.assertEqual(self.api.writes, 1)
        self.assertEqual(len(self.api.events), 1)

    def test_changed_workout_updates_and_moved_date_keeps_id(self):
        self.sync()
        initial_id = next(iter(self.api.events.values()))['id']
        self.plan['sessions'][0]['workout'] = '- 45m 55-65%'
        self.sync()
        self.assertEqual(next(iter(self.api.events.values()))['moving_time'], 2700)
        self.plan['sessions'][0]['date'] = '2026-11-05'
        self.assertEqual(self.sync()['status'], 'verified')
        self.assertEqual(len(self.api.events), 1)
        self.assertEqual(next(iter(self.api.events.values()))['id'], initial_id)

    def test_partial_write_is_reported_and_retry_only_upserts_missing(self):
        second = copy.deepcopy(self.plan['sessions'][0])
        second.update(session_id='climb-02', date='2026-11-05')
        self.plan['sessions'].append(second)
        self.api.partial = True
        result = self.sync()
        self.assertEqual(result['status'], 'unverified')
        self.assertTrue(result['sessions'][0]['verified'])
        self.assertFalse(result['sessions'][1]['verified'])
        self.assertEqual(self.api.writes, 1)
        self.api.partial = False
        self.assertEqual(self.sync()['status'], 'verified')
        self.assertEqual(len(self.api.events), 2)

    def test_timeout_after_success_resolves_by_readback_without_retry(self):
        self.api.timeout_after_write = True
        result = self.sync()
        self.assertEqual(result['status'], 'verified')
        self.assertIsNotNone(result['write_error'])
        self.assertEqual(self.api.writes, 1)

    def test_readback_failure_remains_unverified_and_no_retry(self):
        base_request = self.api.request
        def request(path, method='GET', payload=None):
            response = base_request(path, method, payload)
            if method == 'POST':
                self.api.read_error = True
            return response
        syncer = CalendarSync(request)
        preview = syncer.preview(self.plan)
        result = syncer.sync(self.plan, preview['preview_hash'])
        self.assertEqual(result['status'], 'unverified')
        self.assertTrue(result['write_attempted'])
        self.assertEqual(self.api.writes, 1)

    def test_empty_platform_steps_and_wrong_ftp_fail_verification(self):
        self.api.empty_steps = True
        self.assertEqual(self.sync()['status'], 'unverified')
        self.api.empty_steps = False
        self.api.ftp = 250
        result = self.sync()
        self.assertEqual(result['status'], 'unverified')
        self.assertIn('resolved_watts_or_ftp_mismatch', result['sessions'][0]['errors'])

    def test_changed_plan_or_calendar_invalidates_preview(self):
        self.sync()
        preview = self.syncer.preview(self.plan)
        next(iter(self.api.events.values()))['name'] = 'Edited manually'
        result = self.syncer.sync(self.plan, preview['preview_hash'])
        self.assertEqual(result['status'], 'stale_preview')
        self.assertEqual(self.api.writes, 1)
        preview = self.syncer.preview(self.plan)
        self.plan['ftp'] = 210
        self.assertEqual(self.syncer.sync(self.plan, preview['preview_hash'])['status'], 'stale_preview')

    def test_other_events_retained_and_namespace_collision_blocked(self):
        self.sync()
        e = next(iter(self.api.events.values()))
        e['external_id'] = 'someone-elses-event'
        self.api.events = {e['external_id']: e}
        self.sync()
        self.assertEqual(len(self.api.events), 2)
        own = self.api.events[event_payloads(self.plan)[0]['external_id']]
        own['description'] = '- 60m 50%'
        with self.assertRaises(ValueError):
            self.syncer.preview(self.plan)

    def test_nested_platform_repeat_counts(self):
        step = dict(duration=60, power=dict(units='%ftp', value=100), _power=dict(value=200))
        e = dict(workout_doc=dict(steps=[dict(reps=3, duration=360, steps=[step, step])]))
        self.assertEqual(parsed_steps(e), [(60, 100, 200)]*6)

    def test_http_errors_are_sanitized_and_post_is_not_retried(self):
        import httpx
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(403, text='private server response and fake-secret')
        client = IntervalsClient('0', 'fake-secret', transport=httpx.MockTransport(handler))
        with self.assertRaises(ApiError) as context:
            client.request('/events/bulk?upsert=true', 'POST', [])
        self.assertNotIn('fake-secret', str(context.exception))
        self.assertNotIn('private', str(context.exception))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].headers['User-Agent'], 'cyclingworkouts-mcp/1.0 (personal training planner)')


class McpToolBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('cycling_mcp_for_test', ROOT/'mcp'/'intervals_mcp_server.py')
        cls.server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.server)

    def setUp(self):
        self.plan, self.profile = fixtures()
        # Current date only changes wellness/FTP-age warnings, acknowledged below.
        self.api = FakeCalendar()
        self.original_request = self.server._request
        self.original_store = self.server.STORE
        self.server._request = self.api.request
        root = ROOT/'.training-state'/'test-temp'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.server.STORE = TrainingStore(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(setattr, self.server, '_request', self.original_request)
        self.addCleanup(setattr, self.server, 'STORE', self.original_store)

    def test_public_preview_sync_and_reload_tools(self):
        self.server.save_athlete_profile(self.profile, 'Synthetic fixture')
        self.server.save_training_plan(self.plan, 'demo-rider', 'Initial synthetic fixture')
        preview = json.loads(self.server.preview_training_plan(self.plan, self.profile))
        result = json.loads(self.server.sync_training_plan(self.plan, self.profile, preview['preview_hash'], 'Synthetic acceptance only'))
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(self.api.writes, 1)
        history = json.loads(self.server.read_training_state('plans', self.plan['plan_id']))
        self.assertEqual(history[0]['profile_revision'], 1)
        audits = json.loads(self.server.read_training_state('syncs', self.plan['plan_id']))
        self.assertEqual(audits[0]['result']['status'], 'verified')
        self.assertEqual(audits[0]['review_note'], 'Synthetic acceptance only')

    def test_removed_sessions_reported_without_deletion(self):
        self.server.save_athlete_profile(self.profile, 'Synthetic fixture')
        first = copy.deepcopy(self.plan['sessions'][0])
        first.update(session_id='removed-later', date='2026-11-04')
        self.plan['sessions'].append(first)
        self.server.save_training_plan(self.plan, 'demo-rider', 'Both sessions')
        preview = json.loads(self.server.preview_training_plan(self.plan, self.profile))
        self.server.sync_training_plan(self.plan, self.profile, preview['preview_hash'], 'Synthetic acceptance')
        self.plan['sessions'].pop()
        self.server.save_training_plan(self.plan, 'demo-rider', 'Retain calendar event, revise plan only')
        preview = json.loads(self.server.preview_training_plan(self.plan, self.profile))
        self.assertEqual(len(preview['retained_events']), 1)
        result = json.loads(self.server.sync_training_plan(self.plan, self.profile, preview['preview_hash'], 'Synthetic acceptance'))
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(len(self.api.events), 2)

    def test_hard_constraints_block_all_writes(self):
        self.profile['availability']['weekly_hours'] = .1
        preview = json.loads(self.server.preview_training_plan(self.plan, self.profile))
        result = json.loads(self.server.sync_training_plan(self.plan, self.profile, preview['preview_hash'], 'Cannot override a hard cap'))
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.api.writes, 0)

    def test_missing_recovery_requires_reason_and_profile_change_invalidates(self):
        self.profile.pop('wellness')
        preview = json.loads(self.server.preview_training_plan(self.plan, self.profile))
        result = json.loads(self.server.sync_training_plan(self.plan, self.profile, preview['preview_hash']))
        self.assertEqual(result['status'], 'needs_review_note')
        self.profile['language'] = 'zh'
        result = json.loads(self.server.sync_training_plan(self.plan, self.profile, preview['preview_hash'], 'Reviewed'))
        self.assertEqual(result['status'], 'stale_preview')
        self.assertEqual(self.api.writes, 0)

    def test_legacy_writer_uses_exact_seconds_and_requires_explicit_ftp(self):
        with self.assertRaises(ValueError):
            self.server.create_intervals_workout('2026-11-03', 'Test', '- 61s 50%')
        with self.assertRaises(ValueError):
            self.server.create_intervals_workout('2026-11-03', 'Test', '- 61s 50%', 60, 200)
        result = json.loads(self.server.create_intervals_workout('2026-11-03', 'Test', '- 61s 50%', 61, 200))
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(next(iter(self.api.events.values()))['moving_time'], 61)


if __name__ == '__main__':
    unittest.main()
