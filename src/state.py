"""Private versioned records. Completed-session feedback is append-only."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4
from .metrics import _number
from .planning import identifier, normalize_plan, validate_profile
from .workout import Workout


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


class TrainingStore:
    def __init__(self, root='.training-state'):
        self.root = Path(root).resolve()

    def _directory(self, kind, record_id):
        folder = self.root / kind / identifier(record_id)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def history(self, kind, record_id):
        if kind not in ('profiles', 'plans', 'actuals', 'syncs'):
            raise ValueError('Unknown record kind')
        folder = self.root / kind / identifier(record_id)
        records = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*.json'))]
        return sorted(records, key=lambda r: (r.get('revision', 0), r['recorded_at']))

    def latest(self, kind, record_id):
        records = self.history(kind, record_id)
        if not records:
            raise ValueError(f'No saved {kind} record for this ID')
        return records[-1]

    @staticmethod
    def _write_new(folder, filename, data):
        """Publish a complete JSON atomically without replacing an existing revision."""
        encoded = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        lock = folder / '.write-lock'
        lock.mkdir()  # Atomic exclusion across cooperating writers.
        temporary = None
        try:
            target = folder / filename
            if target.exists():
                raise FileExistsError('Revision already exists; reload and retry the save')
            fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=folder)
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
                f.write(encoded)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, target)
        finally:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
            lock.rmdir()

    def _save(self, kind, record_id, data, reason, *, expected_previous_hash=Ellipsis, **metadata):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('A revision reason is required')
        folder = self._directory(kind, record_id)
        history = self.history(kind, record_id)
        previous_hash = history[-1]['hash'] if history else None
        if expected_previous_hash is not Ellipsis and previous_hash != expected_previous_hash:
            raise ValueError('Plan changed while preparing revision; reload before saving')
        revision = len(history) + 1
        record = dict(revision=revision, recorded_at=stamp(), reason=reason,
                      previous_hash=previous_hash,
                      data=data, **metadata)
        record['hash'] = fingerprint(record)
        self._write_new(folder, f'{revision:06d}.json', record)
        return record

    def save_profile(self, profile, reason):
        return self._save('profiles', profile['profile_id'], validate_profile(profile), reason)

    def save_plan(self, plan, reason, profile_id):
        plan = normalize_plan(plan)
        profile = self.latest('profiles', profile_id)
        history = self.history('plans', plan['plan_id'])
        previous = history[-1]['data'] if history else None
        if history and history[-1]['profile_id'] != profile_id:
            raise ValueError('A plan cannot change athlete profile ownership')
        old = {s['session_id']: s for s in previous['sessions']} if previous else {}
        new = {s['session_id']: s for s in plan['sessions']}
        diff = dict(added=sorted(new.keys()-old.keys()), removed=sorted(old.keys()-new.keys()),
                    changed=[sid for sid in sorted(old.keys() & new.keys()) if old[sid] != new[sid]],
                    settings_changed=[k for k in sorted((previous or {}).keys() | plan.keys())
                                      if k != 'sessions' and (previous or {}).get(k) != plan.get(k)])
        return self._save('plans', plan['plan_id'], plan, reason, diff=diff,
                          expected_previous_hash=history[-1]['hash'] if history else None,
                          profile_id=profile_id, profile_revision=profile['revision'], profile_hash=profile['hash'])

    def record_actual(self, plan_id, session_id, feedback, plan_revision=None):
        feedback = dict(feedback)
        record = self.latest('plans', plan_id)
        if plan_revision is not None:
            candidates = [r for r in self.history('plans', plan_id) if r['revision'] == plan_revision]
            if type(plan_revision) is not int or not candidates:
                raise ValueError('Unknown plan_revision')
            record = candidates[0]
        identifier(session_id)
        sessions = {s['session_id']: s for s in record['data']['sessions']}
        if session_id not in sessions:
            raise ValueError('Unknown session_id in saved plan revision')
        for key in ('rpe', 'completion', 'duration_seconds', 'work_kj', 'tss', 'carbs_g', 'sleep_hours'):
            if key in feedback:
                feedback[key] = _number(feedback[key], key)
        if feedback.get('rpe', 0) > 10 or feedback.get('completion', 0) > 1:
            raise ValueError('RPE must be 0-10 and completion 0-1')
        prescribed = Workout.from_dict(sessions[session_id]['workout']).metrics(
            record['data']['ftp'], scenario=record['data']['power_range_scenario'])
        comparison = {k: {'planned': prescribed[p], 'actual': feedback[k],
                          'difference': round(feedback[k]-prescribed[p], 3)}
                      for k, p in [('duration_seconds', 'duration_seconds'), ('work_kj', 'work_kj'), ('tss', 'estimated_tss')]
                      if k in feedback and prescribed[p] is not None}
        actual = dict(actual_id=uuid4().hex, recorded_at=stamp(), plan_id=plan_id,
                      plan_revision=record['revision'], session_id=session_id,
                      feedback=feedback, comparison=comparison)
        folder = self._directory('actuals', plan_id)
        self._write_new(folder, actual['actual_id'] + '.json', actual)
        return actual

    def record_sync(self, plan, result, review_note):
        audit = dict(recorded_at=stamp(), plan_hash=fingerprint(normalize_plan(plan)),
                     review_note=review_note, result=result)
        folder = self._directory('syncs', plan['plan_id'])
        self._write_new(folder, uuid4().hex + '.json', audit)
        return audit
