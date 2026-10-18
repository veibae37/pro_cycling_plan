"""Offline ZWO and RFC 5545 calendar export from the same expanded steps."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from .planning import normalize_plan, iso_date
from .state import fingerprint
from .workout import Workout


def zwo(workout, name, scenario='midpoint'):
    root = ET.Element('workout_file')
    for tag, value in [('author', 'Pro Cycling Workouts'), ('name', name), ('sportType', 'bike'),
                       ('description', f'Power ranges resolved using {scenario} targets. FTP-relative planning workout.')]:
        ET.SubElement(root, tag).text = value
    body = ET.SubElement(root, 'workout')
    for step in workout.steps:
        ET.SubElement(body, 'SteadyState', Duration=str(step.duration_seconds),
                      Power=f'{step.target(scenario)/100:.8g}')
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n'


def _escape(value):
    return str(value).replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def _fold(line):
    """Fold at 75 UTF-8 octets without splitting a Unicode character."""
    pieces, current = [], ''
    for char in line:
        if len((current + char).encode('utf-8')) > 75:
            pieces.append(current)
            current = ' '
        current += char
    return '\r\n'.join(pieces + [current])


def ics(plan, *, generated_at=None):
    """All-day sessions preserve the rider's local date without timezone ambiguity.

    ICS is a schedule preview. ZWO carries executable intervals. Reimport/update
    behavior depends on the calendar application even though UIDs are stable.
    """
    plan = normalize_plan(plan)
    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        raise ValueError('generated_at must be timezone-aware')
    dtstamp = generated_at.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Pro Cycling Workouts//Training Plan//EN',
             'CALSCALE:GREGORIAN']
    for session in plan['sessions']:
        workout = Workout.from_dict(session['workout'])
        description = (f"{workout.duration_seconds} seconds; FTP {plan['ftp']:g} W; "
                       f"{plan['power_range_scenario']} power targets. "
                       + (f"Suggested local start {session['start_time']}. " if session.get('start_time') else '')
                       + '\n' + workout.to_text(plan['power_range_scenario']))
        day = iso_date(session['date'])
        lines.extend(['BEGIN:VEVENT', f"UID:{plan['plan_id']}.{session['session_id']}@pro-cycling-workouts",
                      'DTSTAMP:' + dtstamp, 'SEQUENCE:' + str(int(plan.get('revision', 0))),
                      'DTSTART;VALUE=DATE:' + day.strftime('%Y%m%d'),
                      'DTEND;VALUE=DATE:' + (day + timedelta(days=1)).strftime('%Y%m%d'),
                      'SUMMARY:' + _escape(session['name']), 'DESCRIPTION:' + _escape(description),
                      'TRANSP:TRANSPARENT', 'END:VEVENT'])
    return '\r\n'.join(_fold(line) for line in lines + ['END:VCALENDAR']) + '\r\n'


def export_bundle(plan, directory):
    plan = normalize_plan(plan)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = dict(plan_id=plan['plan_id'], plan_hash=fingerprint(plan),
                    power_range_scenario=plan['power_range_scenario'], files=[])
    # Refuse to replace a previous export, avoiding partial overwrites of user files.
    outputs = {'plan.ics': ics(plan)}
    for s in plan['sessions']:
        outputs[s['session_id'] + '.zwo'] = zwo(Workout.from_dict(s['workout']), s['name'], plan['power_range_scenario'])
    outputs['manifest.json'] = json.dumps({**manifest, 'files': sorted(outputs)}, indent=2) + '\n'
    if any((directory / name).exists() for name in outputs):
        raise ValueError('Export destination contains a matching file; choose a new directory')
    for name, content in outputs.items():
        with (directory / name).open('x', encoding='utf-8', newline='') as f:
            f.write(content)
    return dict(directory=str(directory.resolve()), files=sorted(outputs), plan_hash=manifest['plan_hash'])
