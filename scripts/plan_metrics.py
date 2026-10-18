#!/usr/bin/env python3
"""Estimate cycling work, kcal, NP/TSS and three-zone PI."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.metrics import estimate, estimate_week, parse_workout, polarization


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
