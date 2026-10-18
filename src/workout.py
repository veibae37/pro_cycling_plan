"""One expanded representation for metrics, calendar payloads and exports."""
from dataclasses import dataclass
from .metrics import estimate, parse_workout, _number


@dataclass(frozen=True)
class Step:
    duration_seconds: int
    low_pct: float
    high_pct: float

    def __post_init__(self):
        if type(self.duration_seconds) is not int or self.duration_seconds <= 0:
            raise ValueError('Step duration must be positive integer seconds')
        low = _number(self.low_pct, 'low power')
        high = _number(self.high_pct, 'high power')
        if high < low:
            raise ValueError('Reversed power range')
        object.__setattr__(self, 'low_pct', low)
        object.__setattr__(self, 'high_pct', high)

    def target(self, scenario='midpoint'):
        if scenario not in ('low', 'midpoint', 'high'):
            raise ValueError('Unknown power-range scenario')
        return {'low': self.low_pct, 'high': self.high_pct,
                'midpoint': (self.low_pct + self.high_pct) / 2}[scenario]


@dataclass(frozen=True)
class Workout:
    steps: tuple[Step, ...]

    def __post_init__(self):
        object.__setattr__(self, 'steps', tuple(self.steps))
        if not self.steps or any(not isinstance(s, Step) for s in self.steps):
            raise ValueError('Workout requires steps')
        if self.duration_seconds > 172800:
            raise ValueError('A workout cannot exceed 48 hours')

    @classmethod
    def from_text(cls, text):
        return cls(tuple(Step(*s) for s in parse_workout(text)))

    @classmethod
    def from_dict(cls, data):
        if data.get('schema_version') != 1:
            raise ValueError('Unsupported workout schema_version')
        return cls(tuple(Step(**s) for s in data['steps']))

    @property
    def duration_seconds(self):
        return sum(s.duration_seconds for s in self.steps)

    def to_dict(self):
        return {'schema_version': 1, 'steps': [
            {'duration_seconds': s.duration_seconds, 'low_pct': s.low_pct,
             'high_pct': s.high_pct} for s in self.steps]}

    def to_text(self, scenario=None):
        """Serialize expanded steps. A scenario resolves ranges for consistent upload."""
        lines = []
        for s in self.steps:
            target = (f'{s.target(scenario):g}' if scenario else
                      f'{s.low_pct:g}' if s.low_pct == s.high_pct else
                      f'{s.low_pct:g}-{s.high_pct:g}')
            lines.append(f'- {s.duration_seconds}s {target}%')
        return '\n'.join(lines)

    def metrics(self, ftp, **kwargs):
        return estimate([(s.duration_seconds, s.low_pct, s.high_pct)
                         for s in self.steps], ftp, **kwargs)
