"""Validate portable profiles/plans and report concrete scheduling conflicts."""
from datetime import date, datetime, timedelta
import copy
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .metrics import _number, polarization
from .workout import Workout


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', value):
        raise ValueError('IDs must contain 1-64 letters, numbers, underscores or hyphens')
    return value


def iso_date(value):
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError('Dates must use YYYY-MM-DD')
    return result


def validate_profile(profile):
    profile = copy.deepcopy(profile)
    if profile.get('schema_version') != 1:
        raise ValueError('Unsupported profile schema_version')
    identifier(profile['profile_id'])
    profile['weight_kg'] = _number(profile['weight_kg'], 'weight', positive=True)
    profile['ftp']['watts'] = _number(profile['ftp']['watts'], 'FTP', positive=True)
    if not isinstance(profile['ftp']['source'], str) or not profile['ftp']['source'].strip():
        raise ValueError('FTP source is required')
    iso_date(profile['ftp']['date'])
    if profile.get('language', 'en') not in ('en', 'zh'):
        raise ValueError('Language must be en or zh')
    if profile.get('units', 'metric') not in ('metric', 'imperial'):
        raise ValueError('Units must be metric or imperial (stored power is W, weight is kg)')
    try:
        ZoneInfo(profile['timezone'])
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError('Unknown timezone; install tzdata on Windows if needed') from exc
    availability = profile['availability']
    for name in ('weekly_hours', 'max_session_hours'):
        availability[name] = _number(availability[name], name, positive=True)
    if any(type(d) is not int or d not in range(7) for d in availability['rest_days']):
        raise ValueError('rest_days uses Monday=0 through Sunday=6')
    for d, hours in availability.get('daily_hours', {}).items():
        if d not in tuple(str(n) for n in range(7)):
            raise ValueError('daily_hours keys use Monday=0 through Sunday=6')
        availability['daily_hours'][d] = _number(hours, 'daily hours')
    for week in profile.get('recent_weeks', []):
        if iso_date(week['week_start']).weekday() != 0:
            raise ValueError('History week_start must be Monday')
        for field in ('hours', 'tss'):
            if week.get(field) is not None:
                week[field] = _number(week[field], field)
    starts = [w['week_start'] for w in profile.get('recent_weeks', [])]
    if len(starts) != len(set(starts)):
        raise ValueError('Duplicate history week')
    thresholds = profile.get('thresholds')
    if thresholds:
        if not isinstance(thresholds.get('source'), str) or not thresholds['source'].strip():
            raise ValueError('Thresholds require a measured or explicitly assumed source')
        low = _number(thresholds['lt1_pct'], 'LT1', positive=True)
        high = _number(thresholds['lt2_pct'], 'LT2', positive=True)
        if low >= high:
            raise ValueError('LT1 must be below LT2')
        thresholds.update(lt1_pct=low, lt2_pct=high)
    wellness = profile.get('wellness')
    if wellness:
        iso_date(wellness['date'])
        if wellness.get('fatigue') not in ('normal', 'high', 'unknown'):
            raise ValueError('fatigue must be normal, high or unknown')
    return profile


def normalize_plan(plan):
    plan = dict(plan)
    if plan.get('schema_version') != 1:
        raise ValueError('Unsupported plan schema_version')
    identifier(plan['plan_id'])
    if 'revision' in plan and (type(plan['revision']) is not int or plan['revision'] < 0):
        raise ValueError('Plan revision must be a nonnegative integer')
    ftp = _number(plan['ftp'], 'FTP', positive=True)
    scenario = plan.get('power_range_scenario', 'midpoint')
    if scenario not in ('low', 'midpoint', 'high'):
        raise ValueError('Unknown power-range scenario')
    if plan.get('distribution') not in (None, 'polarized', 'pyramidal'):
        raise ValueError('Distribution must be polarized or pyramidal')
    if plan.get('pi_min') is not None:
        plan['pi_min'] = _number(plan['pi_min'], 'PI minimum')
    if plan.get('weekly_tss_range') is not None:
        target = plan['weekly_tss_range']
        if len(target) != 2 or _number(target[0], 'TSS') > _number(target[1], 'TSS'):
            raise ValueError('Invalid weekly_tss_range')
        plan['weekly_tss_range'] = [_number(v, 'TSS') for v in target]
    sessions = plan.get('sessions', [])
    if not 1 <= len(sessions) <= 1000:
        raise ValueError('A plan requires 1-1000 sessions')
    seen, result = set(), []
    for session in sessions:
        sid = identifier(session['session_id'])
        if sid in seen:
            raise ValueError('Duplicate session_id')
        seen.add(sid)
        iso_date(session['date'])
        name = session['name']
        if not isinstance(name, str) or not name.strip() or '\n' in name or '\r' in name:
            raise ValueError('Session name must be one nonempty line')
        sport = session.get('sport', 'Ride')
        if sport not in ('Ride', 'VirtualRide'):
            raise ValueError('Supported sports: Ride, VirtualRide')
        if 'start_time' in session:
            datetime.strptime(session['start_time'], '%H:%M')
            if not re.fullmatch(r'\d{2}:\d{2}', session['start_time']):
                raise ValueError('start_time must use HH:MM')
        raw = session['workout']
        workout = Workout.from_text(raw) if isinstance(raw, str) else Workout.from_dict(raw)
        result.append({**session, 'sport': sport, 'workout': workout.to_dict()})
    return {**plan, 'ftp': ftp, 'power_range_scenario': scenario,
            'sessions': sorted(result, key=lambda s: (s['date'], s.get('start_time', ''), s['session_id']))}


def assess_plan(plan, profile, *, today=None):
    """Rules flag conflicts; no claim of medical clearance or automatic optimization."""
    profile = validate_profile(profile)
    plan = normalize_plan(plan)
    today = today or date.today()
    issues, weeks, day_seconds, hard_days = [], {}, {}, set()

    def issue(code, message, suggestion, severity='warning'):
        issues.append(dict(code=code, severity=severity, message=message, suggestion=suggestion))

    if abs(plan['ftp'] - profile['ftp']['watts']) > .01:
        issue('ftp_mismatch', 'Plan FTP differs from the saved profile.',
              'Retest or explicitly revise the FTP source before recalculating.', 'error')
    if iso_date(profile['ftp']['date']) > today:
        issue('future_ftp', 'FTP date is in the future.', 'Use an observed measurement or label a current estimate with its actual date.', 'error')
    if (today - iso_date(profile['ftp']['date'])).days > 90:
        issue('ftp_age', 'FTP measurement is over 90 days old.', 'Confirm whether this FTP still represents current ability.')
    boundaries = profile.get('thresholds')
    availability = profile['availability']
    for s in plan['sessions']:
        d = iso_date(s['date'])
        monday = (d - timedelta(days=d.weekday())).isoformat()
        workout = Workout.from_dict(s['workout'])
        m = workout.metrics(plan['ftp'], scenario=plan['power_range_scenario'],
                            lt1_pct=boundaries['lt1_pct'] if boundaries else None,
                            lt2_pct=boundaries['lt2_pct'] if boundaries else None)
        w = weeks.setdefault(monday, dict(seconds=0, tss=0, zones=[0, 0, 0]))
        w['seconds'] += m['duration_seconds']
        if m['estimated_tss'] is None:
            issue('unknown_tss', f'{s["session_id"]}: fewer than 30 seconds; TSS is undefined.',
                  'Use a full workout before assessing weekly load.', 'error')
        else:
            w['tss'] += m['estimated_tss']
        if boundaries:
            w['zones'] = [a+b for a, b in zip(w['zones'], m['three_zone_distribution']['zone_minutes'])]
        day_seconds[d] = day_seconds.get(d, 0) + workout.duration_seconds
        if d.weekday() in availability['rest_days']:
            issue('rest_day', f'{s["session_id"]} is on a fixed rest day.', 'Move this session to an available day.', 'error')
        if workout.duration_seconds > availability['max_session_hours'] * 3600:
            issue('session_cap', f'{s["session_id"]} exceeds the ride duration cap.', 'Shorten endurance volume or split on separate available days.', 'error')
        # A scheduling heuristic, independent of a physiological zone classification.
        intense = sum(st.duration_seconds for st in workout.steps if st.target(plan['power_range_scenario']) >= 105)
        threshold = sum(st.duration_seconds for st in workout.steps if st.target(plan['power_range_scenario']) >= 90)
        if intense >= 120 or threshold >= 600:
            hard_days.add(d)
    for d, seconds in day_seconds.items():
        cap = availability.get('daily_hours', {}).get(str(d.weekday()), availability['max_session_hours'])
        if seconds > cap * 3600:
            issue('daily_cap', f'{d}: combined sessions exceed the daily cap.', 'Reduce or move one of the sessions.', 'error')
    for d in sorted(hard_days):
        if d - timedelta(days=1) in hard_days:
            issue('adjacent_quality', f'{d}: consecutive quality days.', 'Insert an easy or rest day between quality sessions.')
    target = plan.get('weekly_tss_range')
    if target is not None:
        if len(target) != 2 or _number(target[0], 'TSS') > _number(target[1], 'TSS'):
            raise ValueError('Invalid weekly_tss_range')
    history = sorted([w for w in profile.get('recent_weeks', [])
                      if iso_date(w['week_start']) < iso_date(min(weeks))], key=lambda w: w['week_start'])[-6:]
    recent_hours = [w['hours'] for w in history if w.get('hours') is not None]
    recent_tss = [w['tss'] for w in history if w.get('tss') is not None]
    if not recent_hours or not recent_tss:
        issue('history_unknown', 'Recent tolerated hours or TSS are missing.', 'Review actual training history; available time is not a load baseline.')
    if history and (iso_date(min(weeks)) - iso_date(history[-1]['week_start'])).days > 21:
        issue('history_stale', 'Training history ends over three weeks before the plan.', 'Refresh recent completed training before starting.')
    # Configurable review trigger, not an evidence-based universal safe progression rate.
    factor = _number(profile.get('load_review_factor', 1.25), 'load_review_factor', positive=True)
    if factor < 1:
        raise ValueError('load_review_factor must be at least 1')
    previous_hours = sum(recent_hours)/len(recent_hours) if recent_hours else None
    previous_tss = sum(recent_tss)/len(recent_tss) if recent_tss else None
    summaries = []
    for monday, w in sorted(weeks.items()):
        hours, tss = w['seconds']/3600, w['tss']
        if hours > availability['weekly_hours'] + 1e-9:
            issue('weekly_cap', f'{monday}: {hours:.2f} h exceeds available time.', 'Reduce total duration.', 'error')
        if target and not target[0] <= tss <= target[1]:
            issue('tss_target', f'{monday}: estimated TSS {tss:.1f} is outside the requested range.',
                  'Adjust load or explicitly revise the range for a recovery week.', 'error' if tss > target[1] else 'warning')
        for value, baseline, label in ((hours, previous_hours, 'hours'), (tss, previous_tss, 'tss')):
            if baseline is not None and value > baseline * factor + 1e-9:
                issue('load_jump_' + label, f'{monday}: {label} increases from {baseline:.1f} to {value:.1f}.',
                      'Start from tolerated load and stage progression, or record the reason for accepting this increase.')
        previous_hours, previous_tss = hours, tss
        summary = dict(week_start=monday, hours=round(hours, 3), estimated_tss=round(tss, 2))
        if boundaries:
            distribution = polarization(w['zones'])
            summary['distribution'] = distribution
            minimum = plan.get('pi_min')
            if minimum is not None and (distribution['pi'] is None or distribution['pi'] < _number(minimum, 'PI minimum')):
                issue('pi_target', f'{monday}: PI does not meet the requested minimum or is undefined.',
                      'Review the three-zone split; do not add artificial middle-zone time to manufacture PI.')
            wanted_distribution = plan.get('distribution')
            if wanted_distribution and distribution['classification'] != wanted_distribution:
                issue('distribution_target', f'{monday}: estimated split is not classified as {wanted_distribution}.',
                      'Review low, middle and high time against the declared thresholds.')
        summaries.append(summary)
    if not boundaries and (plan.get('pi_min') is not None or plan.get('distribution')):
        issue('thresholds_unknown', 'Distribution target cannot be checked without LT1/LT2.',
              'Supply measured boundaries or explicitly label proxy boundaries.')
    wellness = profile.get('wellness')
    if not wellness or wellness.get('fatigue') == 'unknown' or not 0 <= (today - iso_date(wellness['date'])).days <= 7:
        issue('wellness_unknown', 'Current fatigue/recovery status is unknown or stale.', 'Check recovery before starting; missing data does not mean normal recovery.')
    elif wellness['fatigue'] == 'high' and hard_days:
        issue('fatigue_quality', 'High fatigue conflicts with scheduled quality work.',
              'Replace upcoming intensity with rest/easy riding and reassess.', 'error')
    return dict(status='blocked' if any(i['severity'] == 'error' for i in issues) else 'review' if issues else 'ready',
                issues=issues, weeks=summaries, thresholds=boundaries,
                load_review_factor=factor,
                note='1.25 default is a configurable review trigger, not a guarantee of safe progression.')
