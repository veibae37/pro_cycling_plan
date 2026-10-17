#!/usr/bin/env python3
"""
Pro Cycling Plan - Complete 6-Dimension Adaptive Workout & Microcycle Engine
Supports all 6 WorldTour Pro Workout Models + Polarized Recovery + 7-Day Microcycle:
  1. lt1             - LT1 (Z2) Aerobic Capacity (6x20m -> 3x20m -> 3x12m)
  2. fast_vo2        - Fast-Start VO2Max Intervals (30s Surge + 4m VO2 + 15s Sprint)
  3. lt2             - LT2 Threshold Stacking + Pro Ramp & Sprint Primer (10x9m -> 6x8m -> 4x7m)
  4. z3_z4_spikes    - Z3/Z4 & Anaerobic Spikes (1m50s Z3 + 10s >150% Spike + Over-Unders)
  5. vo2_over_under  - Fatigued VO2Max 2m/1m Alternating (Z2 Preload + 2m 110% / 1m 75%)
  6. short_30_30     - 30/30s High-Float & 5m 120% VO2Max Booster
  7. recovery        - Post-Bonk / Leg-Day Polarized Z2 + Alactic Neuromuscular Primers

6 Rider Classification & Scaling Dimensions:
  1. Weight (kg) + CP60 or CP20 -> Base W/kg Tier (Full Pro / Scaled / Double-Scaled)
  2. Optional CP1 (1-min power) -> Anaerobic Phenotype (Puncheur/Sprinter vs. Diesel/TT)
  3. Weekly Cycling Hours       -> 0-5h / 5-10h / 10h+
  4. Leg Strength Training      -> none (0%) / moderate (-20% vol) / heavy (-35% vol, cap torque)
  5. Age Range                  -> <30 / 30-44 / 45-54 / 55+
  6. Environment                -> indoor (shorten duration 25-40%, -3% thermal offset) / outdoor
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import argparse
import json


@dataclass
class RiderProfile:
    weight_kg: float
    cp60_watts: Optional[float] = None
    cp20_watts: Optional[float] = None
    cp1_watts: Optional[float] = None
    weekly_hours: str = "5-10"       # "0-5", "5-10", "10+"
    leg_strength: str = "none"       # "none", "moderate", "heavy"
    age_group: str = "<30"           # "<30", "30-44", "45-54", "55+"
    indoor: bool = True
    sex: str = "male"

    def analyze(self) -> Dict[str, Any]:
        if not self.cp60_watts and not self.cp20_watts:
            raise ValueError("Must provide either cp60_watts or cp20_watts.")

        prelim_ftp = self.cp60_watts if self.cp60_watts else (self.cp20_watts * 0.95)
        cp1_ratio = (self.cp1_watts / prelim_ftp) if self.cp1_watts else None

        if self.cp60_watts:
            effective_ftp = round(self.cp60_watts, 1)
            ftp_source = "CP60 (100%)"
        else:
            if cp1_ratio and cp1_ratio > 2.2:
                effective_ftp = round(self.cp20_watts * 0.92, 1)
                ftp_source = "CP20 * 0.92 (High Anaerobic VLamax Adjustment)"
            elif cp1_ratio and cp1_ratio < 1.85:
                effective_ftp = round(self.cp20_watts * 0.96, 1)
                ftp_source = "CP20 * 0.96 (Diesel/TT Adjustment)"
            else:
                effective_ftp = round(self.cp20_watts * 0.95, 1)
                ftp_source = "CP20 * 0.95 (Standard)"

        w_kg = round(effective_ftp / self.weight_kg, 2)
        cp1_w_kg = round(self.cp1_watts / self.weight_kg, 2) if self.cp1_watts else None

        # 1. Base W/kg Tier
        pro_thr = 3.9 if self.sex.lower() == "female" else 4.5
        scaled_thr = 2.8 if self.sex.lower() == "female" else 3.2

        if w_kg >= pro_thr:
            tier_id, tier_label, base_reps_scale = "full_pro", "Tier 1: Full Pro (与 Pro 原版一致)", 1.00
        elif w_kg >= scaled_thr:
            tier_id, tier_label, base_reps_scale = "scaled", "Tier 2: Scaled (退阶档)", 0.65
        else:
            tier_id, tier_label, base_reps_scale = "double_scaled", "Tier 3: Double-Scaled (退退阶档)", 0.45

        # 2. Weekly Hours Modifier (0-5 / 5-10 / 10+)
        hours_map = {
            "0-5": ("Low Volume (0-5h/wk: 2-3 rides/wk, 45-75m compact sessions)", 0.75, 3),
            "5-10": ("Medium Volume (5-10h/wk: 4-5 rides/wk, 80/20 Polarized)", 1.00, 4),
            "10+": ("High Volume (10h+/wk: 5-6 rides/wk, Full Pro Preload & Finish)", 1.20, 6),
        }
        hours_desc, hours_endurance_mult, recommended_days = hours_map.get(self.weekly_hours, hours_map["5-10"])

        # 3. Leg Strength Training Interference (-20% to -40%)
        strength_map = {
            "none": ("No Leg Strength Training (0% reduction)", 1.00),
            "moderate": ("Moderate Leg Strength (-20% interval volume)", 0.80),
            "heavy": ("Heavy Leg Strength <48h (-35% interval volume, cap high-torque spikes)", 0.65),
        }
        strength_desc, strength_mult = strength_map.get(self.leg_strength, strength_map["none"])

        # 4. Age Range Modifier
        age_map = {
            "<30": ("<30 (U30: Standard recovery kinetics)", 1.00, 0, 0),
            "30-44": ("30-44 (Masters A: +30s inter-rep recovery, min 48h hard gap)", 1.00, 30, 0),
            "45-54": ("45-54 (Masters B: -15% interval volume, +45s recovery, >=15m warmup)", 0.85, 45, -2),
            "55+": ("55+ (Senior Masters: -25% interval volume, +60s recovery, -4% peak offset)", 0.75, 60, -4),
        }
        age_desc, age_vol_mult, extra_rec_sec, age_int_offset = age_map.get(self.age_group, age_map["<30"])

        # 5. Indoor vs. Outdoor Modifier
        if self.indoor:
            env_desc = "Indoor Smart Trainer (Shortened duration -30%, Thermal offset -3% FTP)"
            env_endurance_mult = 0.65
            env_int_offset = -3
        else:
            env_desc = "Outdoor Road (Full endurance duration, 100% target %FTP)"
            env_endurance_mult = 1.00
            env_int_offset = 0

        # 6. CP1 Phenotype Calibration
        if cp1_ratio is None:
            phenotype = "Standard All-Rounder (No CP1 provided)"
            spike_pct = 142 if tier_id != "double_scaled" else 132
        elif cp1_ratio > 2.2:
            phenotype = "Puncheur / Sprinter (High Anaerobic Capacity, CP1/FTP > 2.2)"
            spike_pct = 150
        elif cp1_ratio < 1.85:
            phenotype = "Diesel / Time-Trialist (High Aerobic Stability, CP1/FTP < 1.85 -> Cap spikes)"
            spike_pct = 130
        else:
            phenotype = "Balanced All-Rounder (1.85 <= CP1/FTP <= 2.2)"
            spike_pct = 142

        if self.leg_strength == "heavy":
            spike_pct = min(spike_pct, 130)

        # Safeguard floor so combined multipliers never crush a workout below 30% of Pro volume
        combined_interval_scale = max(0.30, round(base_reps_scale * strength_mult * age_vol_mult, 2))
        combined_endurance_scale = max(0.40, round(env_endurance_mult * hours_endurance_mult, 2))

        return {
            "weight_kg": self.weight_kg,
            "effective_ftp_w": effective_ftp,
            "ftp_source": ftp_source,
            "ftp_w_kg": w_kg,
            "cp1_watts": self.cp1_watts,
            "cp1_w_kg": cp1_w_kg,
            "cp1_to_ftp_ratio": round(cp1_ratio, 2) if cp1_ratio else None,
            "base_tier_id": tier_id,
            "base_tier_label": tier_label,
            "phenotype": phenotype,
            "modifiers": {
                "weekly_hours": hours_desc,
                "leg_strength": strength_desc,
                "age_group": age_desc,
                "environment": env_desc,
            },
            "recommended_weekly_rides": recommended_days,
            "combined_interval_scale": combined_interval_scale,
            "combined_endurance_scale": combined_endurance_scale,
            "extra_recovery_sec": extra_rec_sec,
            "intensity_offset_pct": env_int_offset + age_int_offset,
            "recommended_spike_pct": spike_pct,
        }


def _fmt_sec(sec: int) -> str:
    sec = max(10, int(round(sec / 5.0) * 5))
    m, s = divmod(sec, 60)
    if m and s:
        return f"{m}m{s}s"
    elif m:
        return f"{m}m"
    return f"{s}s"


def generate_workout(analysis: Dict[str, Any], model: str = "lt2") -> Dict[str, Any]:
    scale = analysis["combined_interval_scale"]
    end_mult = analysis["combined_endurance_scale"]
    offset = analysis["intensity_offset_pct"]
    extra_rec = analysis["extra_recovery_sec"]
    spike = analysis["recommended_spike_pct"]
    ftp = analysis["effective_ftp_w"]
    heavy_legs = "Heavy Leg" in analysis["modifiers"]["leg_strength"]
    model = model.lower()

    if model == "lt1":
        wu = max(10, round(30 * end_mult))
        cd = max(8, round(40 * end_mult))
        total_reps = max(2, min(6, round(6 * scale)))
        rep_m = 20 if scale >= 0.55 else 14
        low_p, high_p = max(74, 80 + offset), max(78, 85 + offset)
        rec_s = _fmt_sec(180 + extra_rec)
        if total_reps >= 4:
            b1 = total_reps // 2
            b2 = total_reps - b1
            mid_rec = max(10, round(25 * end_mult))
            code = (
                f"Warmup\n- {wu}m 50-60%\n\n"
                f"LT1 Block 1 {b1}x\n- {rep_m}m {low_p}-{high_p}%\n- {rec_s} 50%\n\n"
                f"Mid Endurance\n- {mid_rec}m 50-60%\n\n"
                f"LT1 Block 2 {b2}x\n- {rep_m}m {high_p}%\n- {rec_s} 50%\n\n"
                f"Cooldown\n- {cd}m 50-60%"
            )
            dur_m = wu + total_reps * (rep_m + 3) + mid_rec + cd
        else:
            code = (
                f"Warmup\n- {wu}m 50-60%\n\n"
                f"Main Set {total_reps}x\n- {rep_m}m {low_p}-{high_p}%\n- {rec_s} 50%\n\n"
                f"Cooldown\n- {cd}m 50-60%"
            )
            dur_m = wu + total_reps * (rep_m + 3) + cd
        avg_if = 0.74
        title = f"Model 1: LT1 Aerobic Capacity ({total_reps}x{rep_m}m @ {low_p}-{high_p}% FTP)"

    elif model == "fast_vo2":
        wu = max(12, round(40 * end_mult))
        cd = max(12, round(50 * end_mult))
        reps = max(2, min(5, round(5 * scale)))
        steady_s = 240 if scale >= 0.75 else (210 if scale >= 0.50 else 180)
        vo2_low, vo2_high = max(95, 100 + offset), max(98, 105 + offset)
        rec_s = _fmt_sec(300 + extra_rec)
        code = (
            f"Warmup\n- {wu}m 50-60%\n\n"
            f"Main Set {reps}x\n- 30s {spike}%\n- {_fmt_sec(steady_s)} {vo2_low}-{vo2_high}%\n- 15s {spike - 10}%\n- {rec_s} 50%\n\n"
            f"Cooldown\n- {cd}m 55-65%"
        )
        dur_m = wu + reps * ((steady_s + 45 + 300 + extra_rec) / 60.0) + cd
        avg_if = 0.78
        title = f"Model 2: Fast-Start VO2Max ({reps}x {_fmt_sec(steady_s + 45)})"

    elif model == "lt2":
        wu = max(6, round(10 * end_mult))
        cd = max(6, round(13 * end_mult))
        reps = max(3, min(10, round(10 * scale)))
        rep_m = 9 if scale >= 0.80 else (8 if scale >= 0.50 else 7)
        low_p, high_p = max(86, 90 + offset), max(89, 95 + offset)
        rec_s = _fmt_sec(90 + extra_rec)
        ramp_sets = 2 if scale >= 0.55 else 1
        code = (
            f"Warmup\n- {wu}m 50%\n\n"
            f"Ramp Primer {ramp_sets}x\n- 1m 50%\n- 30s 60%\n- 30s 70%\n- 30s 80%\n- 30s 92%\n\n"
            f"Sprint Primer 2x\n- 2m 50%\n- 10s {spike}%\n\n"
            f"Settle\n- 4m 50%\n\n"
            f"Main Set {reps}x\n- {rep_m}m {low_p}-{high_p}%\n- {rec_s} 50%\n\n"
            f"Cooldown\n- 5m 75%\n- {cd}m 60-65%"
        )
        dur_m = wu + (ramp_sets * 3) + 8 + reps * (rep_m + (90 + extra_rec) / 60.0) + 5 + cd
        avg_if = 0.81
        title = f"Model 3: LT2 Threshold Stacking ({reps}x{rep_m}m @ {low_p}-{high_p}% FTP)"

    elif model == "z3_z4_spikes":
        wu = max(10, round(20 * end_mult))
        spikes_reps = max(4, min(10, round(10 * scale)))
        b2_high = max(5, round(12 * scale))
        b2_low = max(4, round(8 * scale))
        b3_reps = max(2, min(4, round(4 * scale)))
        z3_p = max(76, 80 + offset)
        z4_p = max(88, 95 + offset)
        rec1 = max(6, round(12 * end_mult))
        code = (
            f"Warmup\n- {wu}m 50%\n\n"
            f"Spikes Set {spikes_reps}x\n- 1m50s {z3_p}%\n- 10s {spike}%\n\n"
            f"Recovery 1\n- {rec1}m 50%\n\n"
            f"Step Block\n- {b2_high}m {z4_p}%\n- {b2_low}m {z3_p + 3}%\n\n"
            f"Recovery 2\n- {max(5, rec1 - 2)}m 50%\n\n"
            f"Alternating Block {b3_reps}x\n- 3m {z3_p + 3}%\n- 2m {z4_p}%\n\n"
            f"Cooldown\n- 8m 60-65%\n- 5m 50%"
        )
        dur_m = wu + spikes_reps * 2 + rec1 + b2_high + b2_low + max(5, rec1 - 2) + b3_reps * 5 + 13
        avg_if = 0.79
        title = f"Model 4: Z3/Z4 & Spikes ({spikes_reps}x Spikes + Over-Unders)"

    elif model == "vo2_over_under":
        wu = max(15, round(75 * end_mult))
        cd = max(12, round(50 * end_mult))
        blocks = 3 if scale >= 0.65 else 2
        reps_per_block = 5 if scale >= 0.80 else 4
        on_p = max(103, 110 + offset)
        float_p = max(68, 75 + offset)
        rec_m = max(5, round(8 * end_mult))
        code = f"Warmup\n- {wu}m 55-63%\n\n"
        for b in range(1, blocks + 1):
            code += f"VO2 Alternating Block {b} {reps_per_block}x\n- 2m {on_p}%\n- 1m {float_p}%\n\n"
            if b < blocks:
                code += f"Block Recovery {b}\n- {rec_m}m 50%\n\n"
        code += f"Cooldown\n- {cd}m 55-63%"
        dur_m = wu + blocks * (reps_per_block * 3) + (blocks - 1) * rec_m + cd
        avg_if = 0.77
        title = f"Model 5: VO2Max 2m/1m Over-Unders ({blocks}x{reps_per_block} reps)"

    elif model == "short_30_30":
        wu = max(12, round(23 * end_mult))
        cd = max(15, round(40 * end_mult))
        reps = max(4, min(6, round(6 * scale)))
        on_p = min(spike, max(125, 145 + offset))
        float_p = max(75, 85 + offset)
        rec_m = max(5, round(9 * end_mult))
        booster_m = 5 if scale >= 0.85 else (4 if scale >= 0.55 else 3)
        booster_p = max(108, 120 + offset)
        code = (
            f"Warmup\n- {wu}m 50-60%\n\n"
            f"30/30 Set 1 {reps}x\n- 30s {on_p}%\n- 30s {float_p}%\n\n"
            f"Recovery 1\n- {rec_m}m 50-55%\n\n"
            f"30/30 Set 2 {reps}x\n- 30s {on_p}%\n- 30s {float_p}%\n\n"
            f"Recovery 2\n- {rec_m}m 50-55%\n\n"
        )
        if not heavy_legs:
            code += f"VO2Max Booster\n- {booster_m}m {booster_p}%\n\n"
        code += f"Endurance Finish\n- {cd}m 55-63%"
        dur_m = wu + reps * 2 + rec_m * 2 + (0 if heavy_legs else booster_m) + cd
        avg_if = 0.76
        title = f"Model 6: 30/30s High-Float (2x{reps}m) + VO2 Booster"

    else:  # recovery / post-bonk polarized Z2
        wu = max(12, round(20 * end_mult))
        cd = max(10, round(15 * end_mult))
        main_m = max(25, round(45 * end_mult))
        code = (
            f"Warmup\n- {wu}m 50-58%\n\n"
            f"Alactic Primers 6x\n- 8s 130%\n- 3m52s 58-62%\n\n"
            f"Polarized Z2 Cruise\n- {main_m}m 58-63%\n\n"
            f"Cooldown\n- {cd}m 50-55%"
        )
        dur_m = wu + 24 + main_m + cd
        avg_if = 0.63
        title = "Polarized Z2 Recovery + 6x8s Alactic Primers"

    est_tss = round((dur_m / 60.0) * (avg_if ** 2) * 100)
    est_kj = round(ftp * avg_if * (dur_m / 60.0) * 3.6)
    carbs_g_h = 35 if model == "recovery" else (85 if dur_m > 110 else (65 if avg_if >= 0.77 else 50))

    return {
        "model": model,
        "workout_name": title,
        "total_duration_min": round(dur_m),
        "estimated_tss": est_tss,
        "estimated_work_kj": est_kj,
        "recommended_carbs_g_per_h": carbs_g_h,
        "intervals_icu_code": code,
    }


def generate_weekly_microcycle(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    hours_desc = analysis["modifiers"]["weekly_hours"]
    if "0-5h" in hours_desc:
        schedule = [
            ("Day 1 (Tue)", "High-Intensity Quality A", "fast_vo2"),
            ("Day 2 (Thu)", "Threshold Quality B", "lt2"),
            ("Day 3 (Sat)", "Aerobic Capacity LT1", "lt1"),
        ]
    elif "10h+" in hours_desc:
        schedule = [
            ("Day 1 (Tue)", "VO2Max Quality A", "fast_vo2"),
            ("Day 2 (Wed)", "Polarized Z2 + Primers", "recovery"),
            ("Day 3 (Thu)", "LT2 Threshold Quality B", "lt2"),
            ("Day 4 (Fri)", "Active Recovery / Rest", "recovery"),
            ("Day 5 (Sat)", "Pro LT1 Aerobic Volume", "lt1"),
            ("Day 6 (Sun)", "Fatigued VO2 / Spikes", "z3_z4_spikes"),
        ]
    else:
        schedule = [
            ("Day 1 (Tue)", "VO2Max Quality A", "short_30_30"),
            ("Day 2 (Wed)", "True Polarized Z2", "recovery"),
            ("Day 3 (Thu)", "LT2 Threshold Quality B", "lt2"),
            ("Day 4 (Sat)", "LT1 Aerobic Capacity", "lt1"),
            ("Day 5 (Sun)", "Polarized Z2 Endurance", "recovery"),
        ]

    plan = []
    for day_label, focus, mod in schedule:
        w = generate_workout(analysis, model=mod)
        plan.append({
            "day": day_label,
            "focus": focus,
            "workout_name": w["workout_name"],
            "duration_min": w["total_duration_min"],
            "estimated_tss": w["estimated_tss"],
            "estimated_work_kj": w["estimated_work_kj"],
            "carbs_g_per_h": w["recommended_carbs_g_per_h"],
        })
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pro Cycling Plan 6-Dimension Calculator")
    parser.add_argument("--weight", type=float, required=True, help="Weight in kg")
    parser.add_argument("--cp60", type=float, default=None, help="CP60 / FTP in watts")
    parser.add_argument("--cp20", type=float, default=None, help="CP20 in watts")
    parser.add_argument("--cp1", type=float, default=None, help="Optional CP1 (1-min power) in watts")
    parser.add_argument("--hours", type=str, default="5-10", choices=["0-5", "5-10", "10+"])
    parser.add_argument("--strength", type=str, default="none", choices=["none", "moderate", "heavy"])
    parser.add_argument("--age", type=str, default="<30", choices=["<30", "30-44", "45-54", "55+"])
    parser.add_argument("--outdoor", action="store_true", help="Outdoor ride flag")
    parser.add_argument(
        "--model",
        type=str,
        default="lt2",
        choices=["lt1", "fast_vo2", "lt2", "z3_z4_spikes", "vo2_over_under", "short_30_30", "recovery"],
    )
    parser.add_argument("--weekly", action="store_true", help="Generate full weekly polarized microcycle")
    args = parser.parse_args()

    rider = RiderProfile(
        weight_kg=args.weight,
        cp60_watts=args.cp60,
        cp20_watts=args.cp20,
        cp1_watts=args.cp1,
        weekly_hours=args.hours,
        leg_strength=args.strength,
        age_group=args.age,
        indoor=not args.outdoor,
    )
    analysis = rider.analyze()
    output: Dict[str, Any] = {"analysis": analysis, "workout": generate_workout(analysis, model=args.model)}
    if args.weekly:
        output["weekly_microcycle"] = generate_weekly_microcycle(analysis)
    print(json.dumps(output, indent=2, ensure_ascii=False))
