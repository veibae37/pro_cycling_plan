"""Intervals.icu transport and read-before-write, verified, idempotent plan sync."""
import re
from urllib.parse import urlencode
from .planning import normalize_plan, iso_date
from .state import fingerprint
from .workout import Workout


class ApiError(RuntimeError):
    """Sanitized error: no credentials, response bodies or private URLs."""


class IntervalsClient:
    def __init__(self, athlete_id, api_key, *, transport=None):
        if not re.fullmatch(r'i?\d+', athlete_id):
            raise ValueError('Invalid Intervals athlete ID')
        if not api_key:
            raise ValueError('Missing INTERVALS_API_KEY environment variable')
        self.base = f'https://intervals.icu/api/v1/athlete/{athlete_id}'
        self.api_key, self.transport = api_key, transport

    def request(self, path, method='GET', payload=None):
        if not path.startswith(('/', '?')) and path != '':
            raise ValueError('Only athlete-relative API paths are supported')
        return self._request_url(self.base + path, method, payload)

    def _request_url(self, url, method='GET', payload=None):
        import httpx
        try:
            with httpx.Client(transport=self.transport, timeout=30,
                              auth=('API_KEY', self.api_key),
                              headers={'User-Agent': 'cyclingworkouts-mcp/1.0 (personal training planner)',
                                       'Accept': 'application/json'}) as client:
                response = client.request(method, url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise ApiError(f'Intervals HTTP {exc.response.status_code}; inspect permissions or retry after checking the calendar.') from None
        except (httpx.RequestError, ValueError):
            raise ApiError('Intervals request failed or returned invalid JSON; write outcome may be unknown.') from None

    def power_curves(self, newest_date, windows_days=None):
        """Read watts curves. Keep API-reported bounds: Nd may span N+1 calendar dates."""
        newest_date = iso_date(newest_date).isoformat()
        windows = [42, 90, 365] if windows_days is None else windows_days
        if (not isinstance(windows, list) or not 1 <= len(windows) <= 6 or
                any(type(d) is not int or not 1 <= d <= 3650 for d in windows) or
                len(set(windows)) != len(windows)):
            raise ValueError('Use 1-6 unique integer lookback windows, each 1-3650 days')
        query = urlencode(dict(type='Ride', curves=','.join(f'{d}d' for d in windows),
                               newest=newest_date, now=newest_date, includeRanks='false'))
        return self.request('/power-curves?' + query)

    def activity_streams(self, activity_id):
        """Read only time/power/HR/cadence, without location streams or account writes."""
        if not isinstance(activity_id, str) or not re.fullmatch(r'i?\d+', activity_id):
            raise ValueError('Invalid activity ID')
        base = self.base.split('/athlete/', 1)[0]
        return self._request_url(base + '/activity/' + activity_id + '/streams?' +
                                 urlencode(dict(types='time,watts,heartrate,cadence', includeDefaults='false')))

    def power_activity_metadata(self, oldest_date, newest_date):
        oldest_date, newest_date = iso_date(oldest_date), iso_date(newest_date)
        if oldest_date > newest_date:
            raise ValueError('Activity range reversed')
        fields = 'id,type,start_date_local,moving_time,icu_average_watts,icu_weight,source,device_watts,icu_ignore_power'
        return self.request('/activities?' + urlencode(dict(oldest=oldest_date.isoformat(),
                            newest=newest_date.isoformat()+'T23:59:59', fields=fields, limit=1000)))


def list_calendar(request, oldest, newest):
    if iso_date(oldest) > iso_date(newest):
        raise ValueError('Calendar date range is reversed')
    data = request('/events?' + urlencode(dict(oldest=oldest, newest=newest, resolve='true', powerRange=0)))
    if not isinstance(data, list):
        raise ApiError('Calendar response must be an array')
    return data


def _marker(plan_id, session_id):
    return f'PCW v1 plan={plan_id} session={session_id}'


def event_payloads(plan):
    plan = normalize_plan(plan)
    events = []
    for s in plan['sessions']:
        w = Workout.from_dict(s['workout'])
        # Resolve ranges to the same scenario used for estimates and ZWO export.
        # Never send workout_doc={}: the platform must parse native text itself.
        events.append(dict(external_id=f"pcw-v1:{plan['plan_id']}:{s['session_id']}", category='WORKOUT',
                           start_date_local=s['date'] + 'T' + s.get('start_time', '00:00') + ':00',
                           type=s['sport'], name=s['name'], moving_time=w.duration_seconds,
                           description=_marker(plan['plan_id'], s['session_id']) + '\n\n' + w.to_text(plan['power_range_scenario'])))
    return events


def parsed_steps(event):
    """Flatten platform repeats without counting parent and child durations twice."""
    output = []

    def walk(steps):
        for s in steps:
            if s.get('steps'):
                reps = s.get('reps', 1)
                if type(reps) is not int or not 1 <= reps <= 1000:
                    raise ValueError('Invalid platform repeat count')
                for _ in range(reps):
                    walk(s['steps'])
            else:
                duration, power = s.get('duration'), s.get('power', {})
                if not isinstance(duration, (int, float)) or duration <= 0 or int(duration) != duration:
                    raise ValueError('Missing/invalid platform step duration')
                if power.get('units') != '%ftp' or power.get('value') is None:
                    raise ValueError('Platform step is not a constant %FTP target')
                resolved = s.get('_power', {})
                output.append((int(duration), float(power['value']), resolved.get('value')))
                if len(output) > 100000:
                    raise ValueError('Too many platform steps')
    walk((event.get('workout_doc') or {}).get('steps', []))
    if not output:
        raise ValueError('Platform returned no parsed steps')
    return output


def verify_event(event, payload, workout, ftp, scenario):
    errors = []
    for field in ('external_id', 'category', 'start_date_local', 'type', 'name', 'moving_time', 'description'):
        if event.get(field) != payload.get(field):
            errors.append(field + '_mismatch')
    if event.get('push_errors'):
        errors.append('platform_push_errors')
    try:
        actual = parsed_steps(event)
        expected = [(s.duration_seconds, s.target(scenario)) for s in workout.steps]
        if [(s, p) for s, p, _ in actual] != expected:
            errors.append('parsed_steps_mismatch')
        # Requiring resolved watts catches account FTP differing from planned FTP.
        if any(w is None or abs(float(w) - ftp*p/100) > 1.01 for _, p, w in actual):
            errors.append('resolved_watts_or_ftp_mismatch')
    except (ValueError, TypeError, KeyError):
        errors.append('parsed_steps_unverified')
    return errors


class CalendarSync:
    def __init__(self, request):
        self.request = request

    def preview(self, plan, *, scan_oldest=None, scan_newest=None):
        plan = normalize_plan(plan)
        dates = [s['date'] for s in plan['sessions']]
        # Include previous dates when moving sessions; callers may supply a wider
        # range from stored revisions. Global external-ID upsert also preserves ID.
        oldest = scan_oldest or min(dates)
        newest = scan_newest or max(dates)
        if oldest > min(dates) or newest < max(dates):
            raise ValueError('Lookup range must cover all planned dates')
        existing = list_calendar(self.request, oldest, newest)
        wanted = event_payloads(plan)
        ids = {p['external_id'] for p in wanted}
        matches = {}
        for event in existing:
            eid = event.get('external_id')
            if eid in ids:
                if eid in matches:
                    raise ValueError('Duplicate calendar external_id; resolve before syncing')
                matches[eid] = event
        changes = []
        for payload, session in zip(wanted, plan['sessions']):
            current = matches.get(payload['external_id'])
            if current:
                marker = _marker(plan['plan_id'], session['session_id'])
                if not (current.get('description') or '').startswith(marker + '\n\n'):
                    raise ValueError('External-ID collision with an event lacking this plan ownership marker')
                errors = verify_event(current, payload, Workout.from_dict(session['workout']), plan['ftp'], plan['power_range_scenario'])
                action = 'update' if errors else 'unchanged'
            else:
                action = 'upsert'  # May already exist outside the lookup range.
            changes.append(dict(session_id=session['session_id'], external_id=payload['external_id'], action=action))
        prefix = f"pcw-v1:{plan['plan_id']}:"
        leftovers = [e['external_id'] for e in existing if str(e.get('external_id', '')).startswith(prefix) and e['external_id'] not in ids]
        token = fingerprint(dict(plan=plan, existing=matches, scan=[oldest, newest]))
        return dict(preview_hash=token, changes=changes, retained_events=leftovers,
                    scan_oldest=oldest, scan_newest=newest,
                    note='Removed sessions are retained. No deletion or automatic write retry is performed.')

    def sync(self, plan, expected_preview_hash, *, scan_oldest=None, scan_newest=None):
        plan = normalize_plan(plan)
        preview = self.preview(plan, scan_oldest=scan_oldest, scan_newest=scan_newest)
        if preview['preview_hash'] != expected_preview_hash:
            return dict(status='stale_preview', preview=preview, write_attempted=False)
        wanted = event_payloads(plan)
        pending = [p for p, c in zip(wanted, preview['changes']) if c['action'] != 'unchanged']
        write_error = None
        if pending:
            try:
                self.request('/events/bulk?upsert=true', method='POST', payload=pending)
            except ApiError as exc:
                write_error = str(exc)
        # Always read back, including after a timeout/partial application. Never
        # blindly retry a POST or treat its HTTP 200 as proof of parsed workouts.
        try:
            events = list_calendar(self.request, preview['scan_oldest'], preview['scan_newest'])
        except ApiError as exc:
            return dict(status='unverified', write_attempted=bool(pending), error=str(exc), write_error=write_error)
        results = []
        for payload, session in zip(wanted, plan['sessions']):
            matches = [e for e in events if e.get('external_id') == payload['external_id']]
            errors = (verify_event(matches[0], payload, Workout.from_dict(session['workout']), plan['ftp'], plan['power_range_scenario'])
                      if len(matches) == 1 else ['missing_or_duplicate_event'])
            results.append(dict(session_id=session['session_id'], verified=not errors, errors=errors))
        return dict(status='verified' if all(r['verified'] for r in results) else 'unverified',
                    write_attempted=bool(pending), write_error=write_error, sessions=results,
                    retained_events=preview['retained_events'])
