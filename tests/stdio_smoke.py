"""Run separately: real MCP stdio handshake and private-state roundtrip, no account writes."""
import json
import os
from pathlib import Path
import sys
import tempfile
import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def result_json(result):
    if result.isError:
        raise AssertionError('MCP tool returned an error')
    return json.loads(next(c.text for c in result.content if c.type == 'text'))


async def main():
    temporary_root = ROOT/'.training-state'/'test-temp'
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temporary_root) as temporary:
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT/'mcp'/'intervals_mcp_server.py')],
                                       env={**os.environ, 'INTERVALS_API_KEY': '', 'CYCLING_STATE_DIR': temporary})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                expected = {'preview_training_plan', 'sync_training_plan', 'get_calendar_events',
                            'save_athlete_profile', 'save_training_plan', 'record_training_feedback', 'read_training_state'}
                assert expected <= {t.name for t in listed.tools}
                profile = json.loads((ROOT/'examples'/'athlete-profile.json').read_text(encoding='utf-8'))
                plan = json.loads((ROOT/'examples'/'portable-plan.json').read_text(encoding='utf-8'))
                saved = result_json(await session.call_tool('save_athlete_profile', dict(profile=profile, reason='stdio acceptance fixture')))
                assert saved['revision'] == 1
                saved = result_json(await session.call_tool('save_training_plan', dict(plan=plan, profile_id='demo-rider', reason='stdio acceptance fixture')))
                assert saved['profile_revision'] == 1
                feedback = result_json(await session.call_tool('record_training_feedback', dict(plan_id=plan['plan_id'], session_id='climb-01', feedback={'rpe': 7, 'completion': 1})))
                assert feedback['plan_revision'] == 1
                state = result_json(await session.call_tool('read_training_state', dict(kind='actuals', record_id=plan['plan_id'])))
                assert len(state) == 1
                print(json.dumps(dict(status='passed', tool_count=len(listed.tools), state_roundtrip=True, account_writes=0)))


if __name__ == '__main__':
    anyio.run(main)
