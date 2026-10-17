#!/usr/bin/env python3
"""
Intervals.icu MCP Server (Model Context Protocol) for pro_cycling_plan
Allows Claude Desktop, Claude Code, Cursor, and Windsurf to:
1. Read athlete FTP, Weight, eFTP, W', and sport settings
2. Read CTL (Fitness), ATL (Fatigue), TSB (Form), and recent rides
3. Automatically generate a 6-dimension calibrated Pro workout and push it to Intervals.icu
"""

import os
import sys
import json
import urllib.request
import base64
from mcp.server.fastmcp import FastMCP

# Import local 6-dimension calculator if available
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from tier_calculator import RiderProfile, generate_workout
except ImportError:
    RiderProfile = None
    generate_workout = None

mcp = FastMCP("intervals-icu")

ATHLETE_ID = os.environ.get("INTERVALS_ATHLETE_ID", "i0")
API_KEY = os.environ.get("INTERVALS_API_KEY", "")
BASE_URL = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}"


def _request(path: str, method: str = "GET", payload: dict = None) -> dict:
    if not API_KEY:
        raise RuntimeError("Missing INTERVALS_API_KEY environment variable.")
    url = f"{BASE_URL}{path}"
    auth_str = base64.b64encode(f"API_KEY:{API_KEY}".encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


@mcp.tool()
def get_athlete_profile() -> str:
    """Fetch athlete weight, FTP, eFTP, W', and sport settings from Intervals.icu."""
    data = _request("")
    summary = {
        "id": data.get("id"),
        "name": data.get("name"),
        "weight_kg": data.get("icu_weight"),
        "sportSettings": data.get("sportSettings", []),
    }
    return json.dumps(summary, indent=2, ensure_ascii=False)


@mcp.tool()
def get_recent_wellness_and_activities(oldest_date: str, newest_date: str) -> str:
    """Fetch recent activities and CTL/ATL/TSB fitness metrics between oldest_date and newest_date (YYYY-MM-DD)."""
    activities = _request(f"/activities?oldest={oldest_date}&newest={newest_date}")
    wellness = _request(f"/wellness?oldest={oldest_date}&newest={newest_date}")
    return json.dumps({"activities": activities, "wellness": wellness}, indent=2, ensure_ascii=False)


@mcp.tool()
def create_intervals_workout(target_date: str, name: str, description_code: str, moving_time_sec: int = 4500) -> str:
    """Push a structured cycling workout (Warmup / Main Set / Cooldown) to the athlete's Intervals.icu calendar."""
    payload = {
        "category": "WORKOUT",
        "start_date_local": f"{target_date}T00:00:00",
        "type": "Ride",
        "name": name,
        "description": description_code,
        "moving_time": moving_time_sec,
    }
    res = _request("/events", method="POST", payload=payload)
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def generate_and_push_pro_workout(
    target_date: str,
    weight_kg: float,
    cp60_or_cp20_watts: float,
    is_cp20: bool = True,
    cp1_watts: float = 0.0,
    weekly_hours: str = "5-10",
    leg_strength: str = "none",
    age_group: str = "<30",
    indoor: bool = True,
    model: str = "lt2",
) -> str:
    """Calculate 6-dimension adaptive workout and automatically push it to Intervals.icu on target_date (YYYY-MM-DD)."""
    if RiderProfile is None or generate_workout is None:
        raise RuntimeError("tier_calculator module not found.")
    rider = RiderProfile(
        weight_kg=weight_kg,
        cp60_watts=None if is_cp20 else cp60_or_cp20_watts,
        cp20_watts=cp60_or_cp20_watts if is_cp20 else None,
        cp1_watts=cp1_watts if cp1_watts > 0 else None,
        weekly_hours=weekly_hours,
        leg_strength=leg_strength,
        age_group=age_group,
        indoor=indoor,
    )
    analysis = rider.analyze()
    w = generate_workout(analysis, model=model)
    payload = {
        "category": "WORKOUT",
        "start_date_local": f"{target_date}T00:00:00",
        "type": "VirtualRide" if indoor else "Ride",
        "name": w["workout_name"],
        "description": f"Fueling Target: {w['recommended_carbs_g_per_h']}g/h carbs (~{w['estimated_work_kj']} kJ)\n\n{w['intervals_icu_code']}",
        "moving_time": w["total_duration_min"] * 60,
    }
    res = _request("/events", method="POST", payload=payload)
    return json.dumps({"analysis": analysis, "workout": w, "intervals_response": res}, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
