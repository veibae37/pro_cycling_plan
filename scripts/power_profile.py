"""Offline progressive intake or a real read-only MCP stdio trial. No account writes."""
import argparse
import json
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.power_profile import prepare_intake, GROUP_FACTORS


def load_env(path):
    """Read only the two Intervals keys; never display their values or execute shell text."""
    env = dict(os.environ)
    if path:
        for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                if key.strip() in ('INTERVALS_ATHLETE_ID', 'INTERVALS_API_KEY'):
                    env[key.strip()] = value.strip().strip('\"\'')
    return env


def profile_context(profile):
    # API account settings are user settings, not a validated test or lab evidence.
    weight, ftp = profile.get('weight_kg'), None
    for setting in profile.get('sportSettings') or []:
        types = setting.get('types') or []
        if any(t in types for t in ('Ride', 'VirtualRide')):
            candidate = setting.get('ftp')
            if type(candidate) in (int, float) and candidate > 0:
                ftp = candidate
                break
    return weight, ftp


async def live_trial(args):
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    env = load_env(args.env_file)
    if not env.get('INTERVALS_API_KEY'):
        raise ValueError('INTERVALS_API_KEY is missing; configure environment or --env-file')
    env.setdefault('INTERVALS_ATHLETE_ID', '0')
    calls = []
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT/'mcp/intervals_mcp_server.py')], env=env)
    context = json.loads(args.context_file.read_text(encoding='utf-8')) if args.context_file else {}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            with anyio.fail_after(30):
                await session.initialize()
            async def call(name, arguments):
                with anyio.fail_after(90):
                    result = await session.call_tool(name, arguments)
                calls.append(name)
                if result.isError:
                    raise RuntimeError('MCP ' + name + ' failed; check permissions and input (details suppressed)')
                return json.loads(next(c.text for c in result.content if c.type == 'text'))
            profile = await call('get_athlete_profile', {})
            weight, ftp = profile_context(profile)
            report = await call('get_power_curve_evidence', dict(newest_date=args.as_of,
                windows_days=args.windows, primary_window=args.primary_window,
                weight_kg=args.weight if args.weight is not None else weight,
                working_ftp_w=args.ftp if args.ftp is not None else ftp,
                performance_group=args.performance_group, group_basis=args.group_basis,
                effort_status=context.get('effort_status', 'unknown'),
                working_ftp_note=context.get('working_ftp_note')))
            report['working_ftp_provenance'] = 'CLI user input' if args.ftp is not None else 'account setting; test protocol/date not verified'
            report['steady_windows'] = []
            if args.steady:
                primary = next(c for c in report['curves'] if c['window'] == args.primary_window)
                ids = list(dict.fromkeys(p['activity_id'] for p in reversed(primary['points'])
                                          if p['duration_seconds'] >= 2400 and p['activity_id']))[:2]
                for aid in ids:
                    try:
                        report['steady_windows'].append(await call('get_steady_ride_evidence',
                            dict(activity_id=aid, start_seconds=900, duration_seconds=2400)))
                    except RuntimeError:
                        report['steady_windows'].append(dict(status='read_failed', lt1_w=None))
            report['mcp_calls'] = calls
            report['transport'] = 'real MCP stdio ClientSession'
            report['user_context'] = context
            return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--as-of', help='Required for live read; athlete-local YYYY-MM-DD')
    parser.add_argument('--windows', type=int, nargs='+', default=[42, 90, 365])
    parser.add_argument('--primary-window', default='90d')
    parser.add_argument('--cp20', type=float)
    parser.add_argument('--weight', type=float)
    parser.add_argument('--ftp', type=float)
    parser.add_argument('--performance-group', choices=list(GROUP_FACTORS))
    parser.add_argument('--group-basis', choices=['vo2max_report', 'self_report', 'wkg_heuristic'])
    parser.add_argument('--steady', action='store_true', help='Read up to 2 source activity windows without GPS')
    parser.add_argument('--context-file', type=Path, help='Optional local user feedback: effort_status and working_ftp_note')
    parser.add_argument('--out', type=Path, help='Private local JSON; live output must be inside .training-state')
    args = parser.parse_args()
    if args.live and not args.as_of:
        parser.error('--live requires --as-of in the athlete timezone')
    if args.live and args.out and not args.out.resolve().is_relative_to((ROOT/'.training-state').resolve()):
        parser.error('Keep live athlete reports inside the git-ignored .training-state directory')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    try:
        if args.live:
            import anyio
            report = anyio.run(live_trial, args)
        else:
            report = prepare_intake(args.cp20, args.weight, working_ftp_w=args.ftp,
                                     performance_group=args.performance_group, group_basis=args.group_basis)
        text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text + '\n', encoding='utf-8')
            print(json.dumps(dict(status='saved', file=str(args.out.resolve()),
                                  account_writes=0, mcp_calls=report.get('mcp_calls', [])), ensure_ascii=False))
        else:
            print(text)
    except (ValueError, RuntimeError, OSError) as exc:
        # These messages are controlled; remote response bodies and credentials are not printed.
        parser.exit(1, type(exc).__name__ + ': ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
