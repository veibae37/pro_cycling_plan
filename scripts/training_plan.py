#!/usr/bin/env python3
"""Offline validation, private revisions, feedback and ZWO/ICS export."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.exports import export_bundle
from src.planning import assess_plan
from src.state import TrainingStore


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', default='.training-state')
    commands = parser.add_subparsers(dest='command', required=True)
    validate = commands.add_parser('validate')
    validate.add_argument('--plan', required=True)
    validate.add_argument('--profile', required=True)
    export = commands.add_parser('export')
    export.add_argument('--plan', required=True)
    export.add_argument('--out', required=True)
    profile = commands.add_parser('save-profile')
    profile.add_argument('--profile', required=True)
    profile.add_argument('--reason', required=True)
    plan = commands.add_parser('save-plan')
    plan.add_argument('--plan', required=True)
    plan.add_argument('--profile-id', required=True)
    plan.add_argument('--reason', required=True)
    history = commands.add_parser('history')
    history.add_argument('--kind', choices=['profiles', 'plans', 'actuals', 'syncs'], required=True)
    history.add_argument('--id', required=True)
    feedback = commands.add_parser('feedback')
    feedback.add_argument('--plan-id', required=True)
    feedback.add_argument('--session-id', required=True)
    feedback.add_argument('--feedback', required=True, help='JSON file with observed values')
    feedback.add_argument('--plan-revision', type=int, help='Revision actually ridden; defaults to latest')
    args = parser.parse_args()
    store, exit_code = TrainingStore(args.state_dir), 0
    try:
        if args.command == 'validate':
            result = assess_plan(read(args.plan), read(args.profile))
            exit_code = 2 if result['status'] == 'blocked' else 1 if result['status'] == 'review' else 0
        elif args.command == 'export':
            result = export_bundle(read(args.plan), args.out)
        elif args.command == 'save-profile':
            result = store.save_profile(read(args.profile), args.reason)
        elif args.command == 'save-plan':
            result = store.save_plan(read(args.plan), args.reason, args.profile_id)
        elif args.command == 'history':
            result = store.history(args.kind, args.id)
        else:
            result = store.record_actual(args.plan_id, args.session_id, read(args.feedback), args.plan_revision)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
