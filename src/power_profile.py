"""Read-only power evidence and progressive intake; no threshold/account mutation.

Group coefficients predict 60-min power, not measured LT2 (Sitko et al., 2023,
doi:10.1055/a-2079-1363). Study groups were based on VO2max, not FTP W/kg.
"""
from datetime import date
import math
from statistics import mean, pstdev

DURATIONS = (6, 30, 60, 180, 300, 720, 1200, 2400, 3600)
LABELS = dict(zip(DURATIONS, ('6s', '30s', '1m', '3m', '5m', '12m', '20m', '40m', '60m')))
GROUP_FACTORS = {'recreational': .88, 'trained': .92, 'well_trained': .95, 'professional': .96}
GROUP_SOURCE = 'https://pubmed.ncbi.nlm.nih.gov/37802084/'


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def scaling_tier(watts, weight_kg, *, basis='working_ftp'):
    if not positive(watts) or not positive(weight_kg):
        return None
    wkg = watts / weight_kg
    # Legacy template policy, NOT research group definitions or a FTP equation.
    high, middle = (4.75, 3.35) if basis == 'p20' else (4.5, 3.2)
    tier = 'full_pro' if wkg >= high else 'scaled' if wkg >= middle else 'double_scaled'
    return dict(tier=tier, watts_per_kg=round(wkg, 3), basis=basis,
                cutoffs_wkg=[middle, high], evidence='legacy_template_heuristic',
                research_group_inferred=False, interval_volume_requires_history=True)


def prepare_intake(cp20_watts=None, weight_kg=None, known_points=None,
                   working_ftp_w=None, performance_group=None, group_basis=None, effort_status='unknown'):
    if effort_status not in ('unknown', 'training_not_maximal', 'maximal_claimed'):
        raise ValueError('Unknown effort status')
    for name, value in [('cp20_watts', cp20_watts), ('weight_kg', weight_kg), ('working_ftp_w', working_ftp_w)]:
        if value is not None and not positive(value):
            raise ValueError(name + ' must be finite and positive')
    points = {}
    for key, value in (known_points or {}).items():
        duration = int(key)
        if str(duration) != str(key) or duration not in DURATIONS or not positive(value):
            raise ValueError('Known points require supported duration seconds and positive watts')
        points[duration] = value
    if cp20_watts is not None:
        if 1200 in points and points[1200] != cp20_watts:
            raise ValueError('Conflicting supplied 20-minute powers; retain separate provenance')
        points[1200] = cp20_watts
    else:
        cp20_watts = points.get(1200)
    if performance_group is not None and performance_group not in GROUP_FACTORS:
        raise ValueError('Unknown performance group')
    if performance_group is not None and group_basis not in ('vo2max_report', 'self_report', 'wkg_heuristic'):
        raise ValueError('Declare group_basis: vo2max_report, self_report or wkg_heuristic')
    missing = [LABELS[t] for t in DURATIONS if t not in points]
    questions = []
    if missing:
        questions.append('你是否知道自己的' + '、'.join(missing) + '最佳平均功率？知道的提供即可，不知道可留空；也可授权从Intervals.icu补齐。')
    questions.append('这些成绩分别是哪天、什么设备/室内外场景、是否接近全力？20分钟成绩采用什么测试/热身协议？')
    if weight_kg is None:
        questions.append('请提供当前体重及日期，以便展示功体比；历史功体比优先使用活动当天体重。')
    if working_ftp_w is None:
        questions.append('是否有近期已验证的FTP或持续努力？没有时先保留估计候选，不自动采用20分钟功率×0.95。')
    candidates = []
    if cp20_watts:
        candidates = [dict(group=g, coefficient=k, predicted_p60_w=round(cp20_watts*k, 1),
                           selected=g == performance_group, source=GROUP_SOURCE,
                           status=('illustrative_only_submaximal_p20' if effort_status == 'training_not_maximal'
                                   else 'population_p60_prediction_not_measured_ftp_or_lt2'))
                      for g, k in GROUP_FACTORS.items()]
    selected = next((c for c in candidates if c['selected']), None)
    return dict(known_points={str(t): points[t] for t in sorted(points)}, optional_missing=missing,
                followup_questions=questions, default_lookback_days=[42, 90, 365],
                primary_window='90d', group_candidates=candidates, selected_candidate=selected,
                group_basis=group_basis, study_group_basis='VO2max, not FTP W/kg',
                effort_status=effort_status, prediction_eligible=effort_status == 'maximal_claimed',
                group_model_validation_mae_w=25, mae_is_not_individual_confidence_interval=True,
                scaling=scaling_tier(working_ftp_w or cp20_watts, weight_kg,
                                     basis='working_ftp' if working_ftp_w else 'p20'),
                working_ftp_w=working_ftp_w, automatically_changed_ftp=False)


def normalize_curves(payload, as_of):
    date.fromisoformat(as_of)
    if not isinstance(payload, dict) or not isinstance(payload.get('list'), list):
        raise ValueError('Expected Intervals curve set with list and activities')
    activities = payload.get('activities') or {}
    if not isinstance(activities, dict):
        raise ValueError('Expected source activities keyed by ID')
    curves = []
    for raw in payload['list']:
        secs, watts = raw.get('secs', []), raw.get('watts', raw.get('values', []))
        if (not isinstance(secs, list) or not isinstance(watts, list) or len(secs) != len(watts) or
                any(type(t) is not int or t <= 0 for t in secs) or len(set(secs)) != len(secs)):
            raise ValueError('Malformed duration/watts arrays; cannot align evidence')
        ids = raw.get('activity_id') or []
        if ids and len(ids) != len(secs):
            raise ValueError('Malformed source activity array')
        by_time = {t: i for i, t in enumerate(secs)}
        points, flags = [], ['maximality_unconfirmed', 'device_and_recording_quality_unverified']
        for t in DURATIONS:
            i = by_time.get(t)
            p = watts[i] if i is not None else None
            aid = ids[i] if i is not None and ids else None
            activity = activities.get(aid, {})
            weight = activity.get('icu_weight')
            if not positive(p):
                p = None
            points.append(dict(duration_seconds=t, label=LABELS[t], watts=p,
                               activity_id=aid, date=(activity.get('start_date_local') or '')[:10] or None,
                               activity_weight_kg=weight if positive(weight) else None,
                               watts_per_kg=round(p/weight, 3) if p and positive(weight) else None,
                               weight_basis='activity_metadata' if positive(weight) else 'unknown',
                               maximality='unknown', device='unknown', context='mixed_or_unknown',
                               source='intervals_aggregate_mmp'))
        inversions = []
        valid = [p for p in points if p['watts'] is not None]
        for a, b in zip(valid, valid[1:]):
            if b['watts'] > a['watts']:
                inversions.append([a['duration_seconds'], b['duration_seconds']])
        if inversions:
            flags.append('nonmonotonic_selected_points_review_sampling_and_sources')
        curves.append(dict(window=raw.get('id'), start=raw.get('start_date_local'),
                           end=raw.get('end_date_local'), api_reported_days=raw.get('days'),
                           contributing_activity_count=len({p['activity_id'] for p in points if p['activity_id']}),
                           points=points, quality_flags=flags, inversions=inversions,
                           platform_models=[{k: m.get(k) for k in ('type', 'ftp', 'criticalPower', 'wPrime')}
                                            for m in raw.get('powerModels', [])], as_of=as_of))
    return curves


def _fit(points, work_time=False):
    x = [p['duration_seconds'] if work_time else 1/p['duration_seconds'] for p in points]
    y = [p['watts']*p['duration_seconds'] if work_time else p['watts'] for p in points]
    xm, ym = mean(x), mean(y)
    denominator = sum((a-xm)**2 for a in x)
    if denominator == 0:
        raise ValueError('Distinct durations required')
    slope = sum((a-xm)*(b-ym) for a, b in zip(x, y))/denominator
    intercept = ym-slope*xm
    cp, wp = (slope, intercept) if work_time else (intercept, slope)
    error = [p['watts']-(cp+wp/p['duration_seconds']) for p in points]
    return dict(method='work_time' if work_time else 'power_inverse_time',
                cp_w=round(cp, 2), w_prime_j=round(wp, 1),
                rmse_w=round(math.sqrt(mean([e*e for e in error])), 2))


def fit_cp_candidate(points, effort_status='unknown'):
    if effort_status == 'training_not_maximal':
        return dict(status='submaximal_only_no_ftp_inference', models=[], adopted_as_ftp=False,
                    reason='User states these efforts were ordinary training, not maximal tests; do not fit capacity.')
    anchors = [p for p in points if p['duration_seconds'] in (180, 300, 720) and positive(p.get('watts'))]
    if len(anchors) < 3:
        return dict(status='insufficient_anchors', required_seconds=[180, 300, 720], adopted_as_ftp=False)
    models = [_fit(anchors), _fit(anchors, True)]
    if any(m['cp_w'] <= 0 or m['w_prime_j'] <= 0 for m in models):
        return dict(status='invalid_model', models=models, adopted_as_ftp=False)
    sources = {p.get('activity_id') for p in anchors if p.get('activity_id')}
    reasons = ['three_five_twelve_protocol_not_identical_to_validated_three_seven_twelve',
               'model_cp_is_not_ftp_or_lt2']
    if not all(p.get('maximality') == 'confirmed' for p in anchors):
        reasons.append('maximal_efforts_not_confirmed')
    if len(sources) < 3:
        reasons.append('fewer_than_three_source_activities_correlated_efforts')
    dates = [date.fromisoformat(p['date']) for p in anchors if p.get('date')]
    if len(dates) != 3 or (max(dates)-min(dates)).days > 42:
        reasons.append('anchor_dates_missing_or_spread_over_more_than_42_days')
    pair_models = [_fit([anchors[i], anchors[j]]) for i, j in ((0, 1), (0, 2), (1, 2))]
    sensitivity = [m['cp_w'] for m in pair_models + models]
    primary = models[0]
    longer = [dict(duration_seconds=p['duration_seconds'], observed_w=p['watts'],
                   model_prediction_w=round(primary['cp_w']+primary['w_prime_j']/p['duration_seconds'], 1),
                   validation='context_and_maximality_unverified')
              for p in points if p['duration_seconds'] >= 1200 and positive(p.get('watts'))]
    return dict(status='observational_candidate_requires_validation', models=models,
                cp_sensitivity_range_w=[min(sensitivity), max(sensitivity)],
                sensitivity_is_not_confidence_interval=True,
                source_activity_count=len(sources), quality_reasons=reasons,
                long_duration_crosschecks=longer, adopted_as_ftp=False)


def assess_power_curves(payload, as_of, working_ftp_w=None, weight_kg=None,
                        primary_window='90d', performance_group=None, group_basis=None,
                        effort_status='unknown', working_ftp_note=None):
    curves = normalize_curves(payload, as_of)
    primary = next((c for c in curves if c['window'] == primary_window), None)
    if primary is None:
        raise ValueError('Primary curve missing; choose a returned window explicitly')
    known = {str(p['duration_seconds']): p['watts'] for p in primary['points'] if p['watts']}
    intake = prepare_intake(weight_kg=weight_kg, known_points=known, working_ftp_w=working_ftp_w,
                            performance_group=performance_group, group_basis=group_basis, effort_status=effort_status)
    intake['working_ftp_note'] = working_ftp_note
    p20, p60 = known.get('1200'), known.get('3600')
    return dict(schema_version=1, as_of=as_of, source='Intervals.icu read-only',
                primary_window=primary_window, curves=curves, intake=intake,
                cp=fit_cp_candidate(primary['points'], effort_status),
                observed_p60_p20_ratio=round(p60/p20, 4) if p20 and p60 else None,
                observed_ratio_is_calibration=False,
                thresholds=dict(lt1=dict(status='not_measured', watts=None),
                                lt2=dict(status='not_measured', watts=None)),
                next_actions=['Confirm effort dates, devices and maximality before adopting a candidate.',
                              'Review comparable steady rides with HR, RPE, fueling and heat context.',
                              'Keep current FTP until evidence is reviewed; no calendar writes.'],
                account_writes=0)


def history_coverage(activities, curves):
    if not isinstance(activities, list):
        raise ValueError('Activity metadata must be an array')
    ride_types = {'Ride', 'VirtualRide', 'MountainBikeRide', 'GravelRide', 'TrackRide', 'Cyclocross'}
    unique = {a['id']: a for a in activities if isinstance(a, dict) and a.get('id')}
    windows = []
    for curve in curves:
        if not curve.get('start') or not curve.get('end'):
            continue
        matched = [a for a in unique.values() if curve['start'] <= a.get('start_date_local', '') <= curve['end']]
        rides = [a for a in matched if a.get('type') in ride_types]
        power = [a for a in rides if positive(a.get('icu_average_watts')) and not a.get('icu_ignore_power')]
        windows.append(dict(window=curve['window'], returned_activities=len(matched), rides=len(rides),
                            rides_with_power_metadata=len(power),
                            unclassified_in_window=sum(not a.get('type') for a in matched)))
    return dict(status='metadata_only_not_full_sensor_audit', returned_count=len(activities),
                unique_ids=len(unique), possibly_truncated=len(activities) >= 1000,
                type_missing_count=sum(not a.get('type') for a in unique.values()),
                date_missing_count=sum(not a.get('start_date_local') for a in unique.values()), windows=windows)


def summarize_steady_streams(streams, start_seconds=900, duration_seconds=2400):
    """Describe one specified continuous window; not an LT1 detector or all-ride average."""
    if (type(start_seconds) is not int or type(duration_seconds) is not int or
            start_seconds < 0 or duration_seconds < 600):
        raise ValueError('Select a nonnegative start and at least 600 seconds')
    if not isinstance(streams, list):
        raise ValueError('Expected stream array')
    data = {s.get('type'): s.get('data') for s in streams if isinstance(s, dict)}
    time, power, hr = data.get('time'), data.get('watts'), data.get('heartrate')
    result = dict(start_seconds=start_seconds, duration_seconds=duration_seconds,
                  lt1_w=None, status='insufficient_streams', interpretation='descriptive_only_not_measured_lt1')
    if not all(isinstance(x, list) for x in (time, power, hr)):
        return result
    if len(time) != len(power) or len(time) != len(hr):
        raise ValueError('Stream lengths differ')
    indexes = [i for i, t in enumerate(time) if type(t) in (int, float) and math.isfinite(t) and
               start_seconds <= t < start_seconds+duration_seconds]
    if len(indexes) < 2:
        return result
    if (time[indexes[0]] != start_seconds or time[indexes[-1]] != start_seconds+duration_seconds-1 or
            any(time[b]-time[a] != 1 for a, b in zip(indexes, indexes[1:]))):
        return dict(**{**result, 'status': 'not_continuous_1hz_window_no_interpolation'})
    if any(type(power[i]) not in (int, float) or not math.isfinite(power[i]) or power[i] < 0 or
           not positive(hr[i]) for i in indexes):
        return dict(**{**result, 'status': 'missing_or_invalid_samples_no_interpolation'})
    pairs = [(power[i], hr[i]) for i in indexes]
    half = len(pairs)//2
    first, last = pairs[:half], pairs[half:]
    first_ratio = mean(p for p, _ in first)/mean(h for _, h in first)
    last_ratio = mean(p for p, _ in last)/mean(h for _, h in last)
    avg = mean(p for p, _ in pairs)
    if avg <= 0 or first_ratio <= 0:
        return result
    return dict(**{**result, 'status': 'descriptive_window_requires_context'},
                mean_power_w=round(avg, 1), mean_hr_bpm=round(mean(h for _, h in pairs), 1),
                power_cv=round(pstdev(p for p, _ in pairs)/avg, 3),
                power_hr_decoupling_pct=round(100*(first_ratio-last_ratio)/first_ratio, 2),
                followup=['Was this power steady and easy? RPE 0-10 and talk comfort?',
                          'Fueling, temperature, ventilation, fatigue and stops?'])
