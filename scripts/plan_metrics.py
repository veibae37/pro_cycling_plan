#!/usr/bin/env python3
"""Estimate cycling work, kcal, NP/TSS and three-zone PI. Standard library only.

Supports constant/range %FTP steps and flat Nx groups in Intervals.icu text.
This is a planning estimator, not an activity-file reader or training prescription.
"""

import argparse
from collections import deque
import json
import math
from pathlib import Path
import re


def _number(value, name, *, positive=False):
    value = float(value)
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return value


def parse_workout(text):
    """Expand flat groups; blank lines or new headings end a group.

    A repeat includes every listed step, including a final recovery if present.
    Unsupported step syntax fails rather than silently omitting work.
    """
    result, group, repeats = [], [], 1

    def flush():
        nonlocal group, repeats
        result.extend(group * repeats)
        group, repeats = [], 1

    pattern = re.compile(
        r"^-\s+(?P<duration>(?:\d+h)?(?:\d+m)?(?:\d+s)?)\s+"
        r"(?P<lo>\d+(?:\.\d+)?)(?:-(?P<hi>\d+(?:\.\d+)?))?%\s*$"
    )
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            flush()
        elif line.startswith('-'):
            match = pattern.fullmatch(line)
            if not match or not match['duration']:
                raise ValueError(f"Unsupported step at line {line_number}: {line}")
            seconds = sum(int(n) * {'h': 3600, 'm': 60, 's': 1}[unit]
                          for n, unit in re.findall(r'(\d+)([hms])', match['duration']))
            low = _number(match['lo'], 'power')
            high = _number(match['hi'] or match['lo'], 'power')
            if seconds <= 0 or high < low:
                raise ValueError(f"Invalid duration or range at line {line_number}")
            group.append((seconds, low, high))
        else:
            flush()
            repeat = re.search(r'\b(\d+)x$', line, re.I)
            if repeat:
                repeats = int(repeat.group(1))
                if not 1 <= repeats <= 1000:
                    raise ValueError('Repeat count must be between 1 and 1000')
    flush()
    if not result:
        raise ValueError('No supported workout steps')
    if sum(step[0] for step in result) > 172800:
        raise ValueError('A workout cannot exceed 48 hours')
    return result


def polarization(zone_minutes):
    """Treff PI uses normalized fractions, NOT percentages or raw minutes."""
    if len(zone_minutes) != 3:
        raise ValueError('Provide three zone durations')
    minutes = [_number(v, 'zone duration') for v in zone_minutes]
    total = sum(minutes)
    if total == 0:
        raise ValueError('Total zone duration must be positive')
    low, middle, high = [v / total for v in minutes]
    pi = math.log10(low / middle * high * 100) if all(v > 0 for v in minutes) else None
    if low > high > middle and pi is not None and pi > 2:
        classification = 'polarized'
    elif low > middle > high:
        classification = 'pyramidal'
    else:
        classification = 'other_or_insufficient'
    return {
        'zone_minutes': minutes,
        'zone_fractions': [round(v / total, 6) for v in minutes],
        'pi': round(pi, 4) if pi is not None else None,
        'classification': classification,
        'note': ('PI undefined with a zero zone; no artificial epsilon added'
                 if pi is None else 'Three physiological zones; not FTP seven-zone labels'),
    }


def estimate(steps, ftp, *, scenario='midpoint', lt1_pct=None, lt2_pct=None):
    ftp = _number(ftp, 'FTP', positive=True)
    if scenario not in ('low', 'midpoint', 'high'):
        raise ValueError('Unknown power-range scenario')
    if (lt1_pct is None) != (lt2_pct is None):
        raise ValueError('Both LT1 and LT2 boundaries are required')
    if lt1_pct is not None:
        lt1_pct = _number(lt1_pct, 'LT1', positive=True)
        lt2_pct = _number(lt2_pct, 'LT2', positive=True)
        if lt1_pct >= lt2_pct:
            raise ValueError('LT1 must be below LT2')
    seconds, work_j, total_watts = 0, 0.0, 0.0
    window, running, fourth, windows = deque(), 0.0, 0.0, 0
    zone_seconds = [0, 0, 0]
    for duration, low, high in steps:
        if not isinstance(duration, int) or duration <= 0:
            raise ValueError('Step duration must be a positive integer number of seconds')
        low, high = _number(low, 'power'), _number(high, 'power')
        if high < low:
            raise ValueError('Reversed power range')
        pct = {'low': low, 'midpoint': (low + high) / 2, 'high': high}[scenario]
        watts = ftp * pct / 100
        seconds += duration
        if seconds > 172800:
            raise ValueError('A workout cannot exceed 48 hours')
        work_j += watts * duration
        total_watts += watts * duration
        if lt1_pct is not None:
            index = 0 if pct <= lt1_pct else (1 if pct <= lt2_pct else 2)
            zone_seconds[index] += duration
        for _ in range(duration):
            window.append(watts)
            running += watts
            if len(window) > 30:
                running -= window.popleft()
            if len(window) == 30:
                fourth += (running / 30) ** 4
                windows += 1
    if not seconds:
        raise ValueError('No workout steps')
    np_w = (fourth / windows) ** 0.25 if windows else None
    intensity = np_w / ftp if np_w is not None else None
    tss = seconds / 3600 * intensity ** 2 * 100 if intensity is not None else None
    work_kj = work_j / 1000
    result = {
        'duration_seconds': seconds,
        'average_power_w': round(total_watts / seconds, 2),
        'work_kj': round(work_kj, 3),
        'estimated_kcal_range': [round(work_kj / (4.184 * .25)),
                                 round(work_kj / (4.184 * .20))],
        'estimated_np_w': round(np_w, 2) if np_w is not None else None,
        'estimated_if': round(intensity, 4) if intensity is not None else None,
        'estimated_tss': round(tss, 2) if tss is not None else None,
        'power_range_scenario': scenario,
        'method': '1s constant targets; full 30s rolling windows; gross efficiency 20-25%',
        'limitations': 'Planning estimate; coasting, actual sprints, ramps, heat and muscle fatigue may differ',
    }
    if lt1_pct is not None:
        result['three_zone_distribution'] = polarization([s / 60 for s in zone_seconds])
        result['zone_boundaries_pct_ftp'] = [lt1_pct, lt2_pct]
    return result


def estimate_week(plan):
    """Aggregate per-session estimates; never compute NP across rest days."""
    sessions = plan.get('sessions', [])
    if not sessions:
        raise ValueError('Week must contain sessions')
    boundaries = plan.get('zone_boundaries_pct_ftp')
    if boundaries is not None and len(boundaries) != 2:
        raise ValueError('Provide two zone boundaries')
    results, zones, tss, work, seconds = [], [0.0, 0.0, 0.0], 0.0, 0.0, 0
    all_tss_known = True
    for session in sessions:
        result = estimate(parse_workout(session['workout']), plan['ftp'],
                          lt1_pct=boundaries[0] if boundaries else None,
                          lt2_pct=boundaries[1] if boundaries else None)
        results.append({'day': session['day'], 'label': session.get('label', ''), **result})
        seconds += result['duration_seconds']
        work += result['work_kj']
        if result['estimated_tss'] is None:
            all_tss_known = False
        else:
            tss += result['estimated_tss']
        if boundaries:
            zones = [a+b for a, b in zip(zones, result['three_zone_distribution']['zone_minutes'])]
    output = {
        'sessions': results,
        'total_hours': round(seconds / 3600, 3),
        'estimated_week_tss': round(tss, 2) if all_tss_known else None,
        'total_work_kj': round(work, 3),
        'estimated_week_kcal_range': [round(work / (4.184 * .25)), round(work / (4.184 * .20))],
    }
    if boundaries:
        output['three_zone_distribution'] = polarization(zones)
        output['zone_boundaries_pct_ftp'] = boundaries
    target = plan.get('weekly_tss_range')
    if target is not None:
        if len(target) != 2:
            raise ValueError('Weekly TSS range needs two bounds')
        lower, upper = [_number(v, 'weekly TSS') for v in target]
        if lower > upper:
            raise ValueError('Reversed weekly TSS range')
        output['requested_tss_range'] = [lower, upper]
        output['within_tss_range'] = lower <= tss <= upper if all_tss_known else None
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workout', type=Path, help='UTF-8 Intervals.icu text file')
    parser.add_argument('--week', type=Path, help='JSON containing FTP and per-session workout text')
    parser.add_argument('--ftp', type=float)
    parser.add_argument('--lt1-pct', type=float, help='User-specific or explicitly assumed boundary')
    parser.add_argument('--lt2-pct', type=float)
    parser.add_argument('--zone-minutes', nargs=3, type=float, metavar=('LOW', 'MID', 'HIGH'))
    parser.add_argument('--range-scenarios', action='store_true', help='Also estimate all-low and all-high targets')
    args = parser.parse_args()
    try:
        if not args.workout and not args.week and args.zone_minutes is None:
            raise ValueError('Provide --workout, --week or --zone-minutes')
        if args.week and (args.workout or args.zone_minutes is not None or
                          any(v is not None for v in (args.ftp, args.lt1_pct, args.lt2_pct)) or
                          args.range_scenarios):
            raise ValueError('--week uses the FTP and boundaries in its JSON; do not combine modes')
        if args.workout is None and any(v is not None for v in (args.ftp, args.lt1_pct, args.lt2_pct)):
            raise ValueError('FTP and thresholds require --workout')
        if args.range_scenarios and not args.workout:
            raise ValueError('--range-scenarios requires --workout')
        output = {}
        if args.week:
            output['week'] = estimate_week(json.loads(args.week.read_text(encoding='utf-8-sig')))
        if args.workout:
            if args.ftp is None:
                raise ValueError('--ftp is required with --workout')
            steps = parse_workout(args.workout.read_text(encoding='utf-8-sig'))
            output['workout'] = estimate(steps, args.ftp, lt1_pct=args.lt1_pct, lt2_pct=args.lt2_pct)
            if args.range_scenarios:
                output['range_scenarios'] = {
                    s: estimate(steps, args.ftp, scenario=s, lt1_pct=args.lt1_pct, lt2_pct=args.lt2_pct)
                    for s in ('low', 'high')
                }
        if args.zone_minutes is not None:
            output['supplied_distribution'] = polarization(args.zone_minutes)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
