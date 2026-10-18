#!/usr/bin/env python3
"""Local stdio MCP: planning, private revisions and verified Intervals.icu sync."""
import json
import logging
import os
from pathlib import Path
import sys
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp.server.fastmcp import FastMCP
from src.intervals import CalendarSync, IntervalsClient, list_calendar
from src.planning import assess_plan, iso_date
from src.state import TrainingStore, fingerprint
from src.tier_calculator import RiderProfile, generate_workout
from src.workout import Workout

mcp = FastMCP('intervals-icu')
# FastMCP configures INFO logging; HTTP URLs contain private athlete IDs.
logging.getLogger('httpx').setLevel(logging.WARNING)
ATHLETE_ID = os.environ.get('INTERVALS_ATHLETE_ID', '0')
API_KEY = os.environ.get('INTERVALS_API_KEY', '')
# Resolve relative to the repository, independent of the host client's cwd.
STORE = TrainingStore(os.environ.get('CYCLING_STATE_DIR', str(Path(__file__).resolve().parents[1] / '.training-state')))


def _request(path, method='GET', payload=None):
    return IntervalsClient(ATHLETE_ID, API_KEY).request(path, method, payload)


def _json(data):
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)


def _scan_dates(plan):
    dates = [s['date'] for s in plan['sessions']]
    for revision in STORE.history('plans', plan['plan_id']):
        dates.extend(s['date'] for s in revision['data']['sessions'])
    return dict(scan_oldest=min(dates), scan_newest=max(dates))


@mcp.tool()
def get_athlete_profile() -> str:
    """Read athlete identity, weight and sport settings (FTP fields depend on API response)."""
    data = _request('')
    return _json(dict(id=data.get('id'), name=data.get('name'), weight_kg=data.get('icu_weight'),
                      sportSettings=data.get('sportSettings', [])))


@mcp.tool()
def get_recent_wellness_and_activities(oldest_date: str, newest_date: str) -> str:
    """Read actual history and wellness. Missing records do not imply normal recovery."""
    if iso_date(oldest_date) > iso_date(newest_date):
        raise ValueError('Date range reversed')
    query = '?' + urlencode(dict(oldest=oldest_date, newest=newest_date))
    return _json(dict(activities=_request('/activities' + query), wellness=_request('/wellness' + query)))


@mcp.tool()
def get_calendar_events(oldest_date: str, newest_date: str) -> str:
    """Read planned events, including platform-parsed steps and resolved watt targets."""
    return _json(list_calendar(_request, oldest_date, newest_date))


@mcp.tool()
def preview_training_plan(plan: dict, profile: dict) -> str:
    """Read-only preview: assess constraints and compare stable session IDs with calendar events.

    Use schemas in docs/IMPLEMENTATION.md. Preserve plan_id/session_id when moving
    or revising sessions. Save revisions to include old dates in calendar lookup.
    """
    assessment = assess_plan(plan, profile)
    preview = CalendarSync(_request).preview(plan, **_scan_dates(plan))
    token = fingerprint(dict(calendar=preview['preview_hash'], profile=profile, assessment=assessment))
    preview['preview_hash'] = token
    return _json(dict(**preview, assessment=assessment))


@mcp.tool()
def sync_training_plan(plan: dict, profile: dict, expected_preview_hash: str, review_note: str = '') -> str:
    """Write an authorized plan after preview, then verify every event by reading it back.

    Hard constraint errors block writes. Warnings require a reason in review_note.
    A changed profile/calendar/plan requires a fresh preview. No automatic
    deletions, blind write retries or writes to completed activities.
    """
    current = json.loads(preview_training_plan(plan, profile))
    if current['preview_hash'] != expected_preview_hash:
        return _json(dict(status='stale_preview', write_attempted=False, preview=current))
    if current['assessment']['status'] == 'blocked':
        return _json(dict(status='blocked', write_attempted=False, assessment=current['assessment']))
    if current['assessment']['status'] == 'review' and not review_note.strip():
        return _json(dict(status='needs_review_note', write_attempted=False, assessment=current['assessment']))
    syncer = CalendarSync(_request)
    preview = syncer.preview(plan, **_scan_dates(plan))
    if fingerprint(dict(calendar=preview['preview_hash'], profile=profile, assessment=current['assessment'])) != expected_preview_hash:
        return _json(dict(status='stale_preview', write_attempted=False))
    result = syncer.sync(plan, preview['preview_hash'], **_scan_dates(plan))
    result['review_note'] = review_note
    try:
        STORE.record_sync(plan, result, review_note)
    except OSError:
        result['state_warning'] = 'Calendar result returned, but private sync audit could not be saved.'
    return _json(result)


@mcp.tool()
def save_athlete_profile(profile: dict, reason: str) -> str:
    """Save a private profile revision with FTP provenance/date, constraints and preferences."""
    return _json(STORE.save_profile(profile, reason))


@mcp.tool()
def save_training_plan(plan: dict, profile_id: str, reason: str) -> str:
    """Save an immutable plan revision, linked profile version, reason and session diff."""
    return _json(STORE.save_plan(plan, reason, profile_id))


@mcp.tool()
def read_training_state(kind: str, record_id: str) -> str:
    """Read private revision history. kind is profiles, plans, actuals or syncs."""
    return _json(STORE.history(kind, record_id))


@mcp.tool()
def record_training_feedback(plan_id: str, session_id: str, feedback: dict, plan_revision: int | None = None) -> str:
    """Append completed-session feedback; compare supplied actual load with the saved prescription.

    rpe is 0-10, completion is 0-1; optional actual duration_seconds, work_kj, tss,
    carbs_g, sleep_hours and notes. Does not automatically alter future sessions.
    """
    return _json(STORE.record_actual(plan_id, session_id, feedback, plan_revision))


@mcp.tool()
def create_intervals_workout(target_date: str, name: str, description_code: str,
                             moving_time_sec: int | None = None, ftp_watts: float | None = None,
                             plan_id: str = 'single-workouts', session_id: str = '') -> str:
    """Compatibility single-session writer with stable IDs and read-back verification.

    Explicit FTP is required. Use preview_training_plan/sync_training_plan for
    full history/constraints assessment. Supplied duration must equal parsed steps.
    """
    if ftp_watts is None:
        raise ValueError('ftp_watts is required to verify resolved power targets')
    workout = Workout.from_text(description_code)
    if moving_time_sec is not None and moving_time_sec != workout.duration_seconds:
        raise ValueError('moving_time_sec differs from the expanded workout')
    sid = session_id or fingerprint(dict(date=target_date, name=name))[:24]
    plan = dict(schema_version=1, plan_id=plan_id, ftp=ftp_watts,
                sessions=[dict(session_id=sid, date=target_date, name=name, workout=workout.to_dict())])
    syncer = CalendarSync(_request)
    preview = syncer.preview(plan)
    return _json(syncer.sync(plan, preview['preview_hash']))


@mcp.tool()
def generate_and_push_pro_workout(target_date: str, weight_kg: float, cp60_or_cp20_watts: float,
                                  is_cp20: bool = True, cp1_watts: float = 0.0,
                                  weekly_hours: str = '5-10', leg_strength: str = 'none',
                                  age_group: str = '<30', indoor: bool = True, model: str = 'lt2') -> str:
    """Compatibility generator/writer. Use the plan preview tools for constraint-aware scheduling.

    Requires authorization to write. is_cp20=false uses supplied FTP/CP60 directly.
    """
    rider = RiderProfile(weight_kg=weight_kg, cp60_watts=None if is_cp20 else cp60_or_cp20_watts,
                         cp20_watts=cp60_or_cp20_watts if is_cp20 else None, cp1_watts=cp1_watts or None,
                         weekly_hours=weekly_hours, leg_strength=leg_strength, age_group=age_group, indoor=indoor)
    analysis = rider.analyze()
    w = generate_workout(analysis, model)
    plan = dict(schema_version=1, plan_id='generated-workouts', ftp=analysis['effective_ftp_w'],
                sessions=[dict(session_id=target_date + '-' + model, date=target_date,
                               name=w['workout_name'], sport='VirtualRide' if indoor else 'Ride', workout=w['workout'])])
    syncer = CalendarSync(_request)
    preview = syncer.preview(plan)
    return _json(dict(analysis=analysis, workout=w, sync=syncer.sync(plan, preview['preview_hash'])))


if __name__ == '__main__':
    mcp.run()
