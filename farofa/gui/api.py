"""Engine-facing logic of the GUI: scenarios, runs, sweeps and fits.

Plain functions on top of the public farofa API, kept apart from HTTP so that
they can be tested directly. Nothing here changes how a simulation behaves:
a scenario becomes a ``SimpleDevice`` or a ``Fleet`` configured exactly as a
script would configure it, and validation calls the same distribution
factories and validators as the engine, so the messages shown next to a
field are the engine's own.

Two quantities are computed here rather than read from a result object:

* the interval of the mean wait for a team, a delta-method interval of the
  pooled ratio (total wait over started repairs) with one (sum, count) pair
  per replication, so the replication stays the statistical unit; and
* the mean function of a fitted failure process, by Monte Carlo through the
  fitted sampler (closed form for the power law).
"""
from __future__ import annotations

import copy
import inspect
import math
import re
import secrets
from statistics import NormalDist
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from ..device import SimpleDevice
from ..distributions import DISTRIBUTIONS
from ..estimation import fit_power_law, fit_weibull_grp, laplace_trend_test
from ..fleet import Fleet
from ..results import FleetSimulationResult, _json_safe, mean_confidence_interval
from ..utils import validate_mission_time, validate_reps, validate_trace
from .datasets import DATASETS

CONFIDENCE = 0.95
MAX_TRACE = 50
MAX_REPS = 1_000_000
MAX_SWEEP_POINTS = 60
MAX_FAILURE_TIMES = 20_000
# Per-replication outcomes sent to the page (histograms) are capped; every
# metric and interval still uses all replications.
PER_REP_LIMIT = 50_000
STATE_CODES = {'up': 0, 'waiting': 1, 'repair': 2}
SCENARIO_SCHEMA = 'farofa-gui-scenario'
# Half the 95% chi-square(1) quantile: the profile log-likelihood drop that
# bounds a 95% likelihood-ratio interval.
LR_DROP_95 = NormalDist().inv_cdf(0.975) ** 2 / 2.0
MEAN_FUNCTION_REPS = 1000
MEAN_FUNCTION_SEED = 20261007


def farofa_version() -> str:
    try:
        from importlib.metadata import version
        return version('farofa')
    except Exception:  # pragma: no cover - not installed as a distribution
        return 'dev'


def dist_params(name: str) -> List[str]:
    """Parameter names of a built-in distribution factory, in call order."""
    return list(inspect.signature(DISTRIBUTIONS[name]).parameters)


def meta() -> Dict[str, Any]:
    """Static facts the page needs: distributions, limits and data sets."""
    return {
        'version': farofa_version(),
        'confidence': CONFIDENCE,
        'distributions': {name: {'params': dist_params(name)} for name in DISTRIBUTIONS},
        'limits': {'max_trace': MAX_TRACE, 'max_reps': MAX_REPS, 'max_sweep_points': MAX_SWEEP_POINTS},
        'datasets': DATASETS,
    }


# --------------------------------------------------------------- scenario --
class ScenarioError(ValueError):
    """Invalid scenario. ``errors`` lists ``{field, message, code}`` items:
    ``message`` is the engine's text when the engine rejected the value, and
    ``code`` names a GUI-level problem the page translates (missing value,
    not a number, above a GUI limit)."""

    def __init__(self, errors: List[Dict[str, Any]]):
        self.errors = errors
        super().__init__('; '.join(f"{e['field']}: {e['message']}" for e in errors))


def _error(field: str, message: str, code: Optional[str] = None) -> Dict[str, Any]:
    return {'field': field, 'message': message, 'code': code}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_dist(role: str, spec: Any, errors: List[Dict[str, Any]]) -> Optional[Tuple[str, List[float]]]:
    """Validate one distribution through its engine factory."""
    if not isinstance(spec, dict) or not spec.get('dist'):
        errors.append(_error(f'{role}.dist', 'distribution not set', 'missing'))
        return None
    name = spec['dist']
    if name not in DISTRIBUTIONS:
        errors.append(_error(f'{role}.dist',
                             f"Unknown distribution '{name}'. Available: {', '.join(DISTRIBUTIONS)}"))
        return None
    names = dist_params(name)
    raw = spec.get('params') or {}
    if isinstance(raw, (list, tuple)):
        raw = dict(zip(names, raw))
    if not isinstance(raw, dict):
        errors.append(_error(f'{role}.dist', 'params must be an object', 'missing'))
        return None
    values, ok = [], True
    for p in names:
        v = raw.get(p)
        if v is None or v == '':
            errors.append(_error(f'{role}.{p}', f'{p} is missing', 'missing'))
            ok = False
        elif not _is_number(v):
            errors.append(_error(f'{role}.{p}', f'{p} must be a finite number', 'number'))
            ok = False
        else:
            values.append(float(v))
    if not ok:
        return None
    try:
        DISTRIBUTIONS[name](*values)
    except (ValueError, TypeError) as exc:
        message = str(exc)
        field = next((f'{role}.{p}' for p in names if message.startswith(p + ' ')), role)
        errors.append(_error(field, message))
        return None
    return name, values


def _check_count(field: str, value: Any, errors: List[Dict[str, Any]]) -> Optional[int]:
    """n_devices / n_teams through the Fleet constructor's own check."""
    try:
        if field == 'n_devices':
            Fleet(n_devices=value, n_teams=1)
        else:
            Fleet(n_devices=1, n_teams=value)
    except (ValueError, TypeError) as exc:
        errors.append(_error(field, str(exc)))
        return None
    return value


def build(scenario: Any) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    """Validate a scenario and return ``(model, run_kwargs, normalized)``.

    ``model`` is a configured ``SimpleDevice`` or ``Fleet``; ``run_kwargs``
    holds ``reps``, ``seed`` (``None`` for fresh entropy) and ``trace``.
    Raises :class:`ScenarioError` listing every invalid field.
    """
    if not isinstance(scenario, dict):
        raise ScenarioError([_error('scenario', 'scenario must be a JSON object', 'missing')])
    errors: List[Dict[str, Any]] = []
    system = scenario.get('system', 'device')
    if system not in ('device', 'fleet'):
        errors.append(_error('system', "system must be 'device' or 'fleet'", 'missing'))
    fleet = system == 'fleet'
    n = k = 1
    if fleet:
        n = _check_count('n_devices', scenario.get('n_devices'), errors)
        k = _check_count('n_teams', scenario.get('n_teams'), errors)
    failure = _check_dist('failure', scenario.get('failure'), errors)
    repair = _check_dist('repair', scenario.get('repair'), errors)

    mission_time = None
    try:
        mission_time = validate_mission_time(scenario.get('mission_time'))
    except (TypeError, ValueError) as exc:
        errors.append(_error('mission_time', str(exc)))

    reps = None
    try:
        reps = validate_reps(scenario.get('reps'))
        if reps > MAX_REPS:
            errors.append(_error('reps', f'at most {MAX_REPS} replications in the GUI', 'reps_max'))
    except ValueError as exc:
        errors.append(_error('reps', str(exc)))

    trace = 0
    try:
        trace = validate_trace(scenario.get('trace', 0) or 0)
        if trace > MAX_TRACE:
            errors.append(_error('trace', f'at most {MAX_TRACE} traced replications in the GUI', 'trace_max'))
    except ValueError as exc:
        errors.append(_error('trace', str(exc)))

    seed = scenario.get('seed')
    if seed == '':
        seed = None
    if seed is not None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            errors.append(_error('seed', 'seed must be a whole number', 'seed_int'))
        else:
            try:
                np.random.SeedSequence(seed)
            except (ValueError, TypeError) as exc:
                errors.append(_error('seed', str(exc)))

    if errors:
        raise ScenarioError(errors)

    model = Fleet(n_devices=n, n_teams=k) if fleet else SimpleDevice()
    model.set_failure_dist(failure[0], *failure[1])
    model.set_repair_dist(repair[0], *repair[1])
    model.set_mission_time(mission_time)
    normalized = {
        'schema': SCENARIO_SCHEMA,
        'version': 1,
        'system': system,
        'n_devices': n,
        'n_teams': k,
        'failure': {'dist': failure[0], 'params': dict(zip(dist_params(failure[0]), failure[1]))},
        'repair': {'dist': repair[0], 'params': dict(zip(dist_params(repair[0]), repair[1]))},
        'mission_time': mission_time,
        'reps': reps,
        'seed': seed,
        'trace': trace,
    }
    if isinstance(scenario.get('name'), str):
        normalized['name'] = scenario['name']
    return model, {'reps': reps, 'seed': seed, 'trace': trace}, normalized


def validate(scenario: Any) -> Dict[str, Any]:
    """``{'ok': True, 'scenario': normalized}`` or ``{'ok': False, 'errors': [...]}``."""
    try:
        _, _, normalized = build(scenario)
    except ScenarioError as exc:
        return {'ok': False, 'errors': exc.errors}
    return {'ok': True, 'scenario': normalized}


# ------------------------------------------------------------------ runs ---
def ratio_confidence_interval(numerators, denominators, confidence: float = CONFIDENCE) -> Tuple[float, float]:
    """Delta-method interval for ``sum(numerators) / sum(denominators)``.

    One (numerator, denominator) pair per replication, e.g. total wait and
    number of started repairs. With ``R`` the pooled ratio, the residuals
    ``n_r - R * d_r`` have mean zero and the interval is
    ``R ± z * s_res / (sqrt(reps) * mean(d))``. ``(nan, nan)`` when there are
    fewer than two replications or no denominator mass. Lower end clipped at 0
    (for non-negative numerators).
    """
    num = np.asarray(numerators, dtype=float)
    den = np.asarray(denominators, dtype=float)
    if num.size < 2 or den.sum() <= 0:
        return (float('nan'), float('nan'))
    ratio = num.sum() / den.sum()
    lo, hi = mean_confidence_interval(num - ratio * den, confidence)
    half = (hi - lo) / 2.0 / den.mean()
    return (float(max(0.0, ratio - half)), float(ratio + half))


def _metric(value: Any, ci: Optional[Tuple[float, float]] = None, **extra: Any) -> Dict[str, Any]:
    out = {'value': value}
    if ci is not None:
        out['ci'] = list(ci)
    out.update(extra)
    return out


def result_payload(result: Any, scenario: Dict[str, Any], seed: int, per_rep: bool = True) -> Dict[str, Any]:
    """Compact JSON view of a result for the dashboard."""
    fleet = isinstance(result, FleetSimulationResult)
    T = result.mission_time
    failures_rep = result.total_failures_per_rep
    metrics = {
        'availability': _metric(result.fleet_availability if fleet else result.availability,
                                result.availability_confidence_interval(CONFIDENCE)),
        'failures': _metric(result.mean_failures, result.failure_count_confidence_interval(CONFIDENCE),
                            std=float(np.std(failures_rep, ddof=1)) if result.reps > 1 else None),
        'mttf': _metric(result.mttf),
        'mttr': _metric(result.mttr),
        'failure_rate': _metric(result.mean_failures / T),
        'repairs': _metric(result.mean_repairs if fleet else float(np.mean(result.repair_counts))),
    }
    reps_out = {
        'availability': result.availability_per_rep,
        'failures': failures_rep,
    }
    if fleet:
        started = np.array([len(w) for w in result.wait_times], dtype=float)
        wait_sum = np.array([float(np.sum(w)) for w in result.wait_times])
        waits = np.concatenate(result.wait_times) if started.sum() else np.array([])
        metrics.update({
            'utilization': _metric(result.server_utilization,
                                   result.server_utilization_confidence_interval(CONFIDENCE)),
            'mean_wait': _metric(result.mean_wait_time, ratio_confidence_interval(wait_sum, started)),
            'p_wait': _metric(float(np.mean(waits > 0)) if waits.size else None),
            'max_queue': _metric(result.max_queue_observed, mean=float(np.mean(result.max_queue))),
        })
        reps_out.update({
            'utilization': result.server_utilization_per_rep,
            'mean_wait': [float(s / c) if c else None for s, c in zip(wait_sum, started)],
            'max_queue': result.max_queue,
        })
        per_device = {
            'availability': result.per_device_availability,
            'failures': result.failure_counts.mean(axis=0),
        }
    else:
        per_device = {'availability': [result.availability], 'failures': [result.mean_failures]}

    payload = {
        'system': 'fleet' if fleet else 'device',
        'n_devices': result.n_devices if fleet else 1,
        'n_teams': result.n_teams if fleet else 1,
        'mission_time': T,
        'reps': result.reps,
        'seed': seed,
        'confidence': CONFIDENCE,
        'traced_reps': result.traced_reps,
        'metrics': metrics,
        'per_device': per_device,
        'scenario': scenario,
    }
    if per_rep:
        shown = min(result.reps, PER_REP_LIMIT)
        payload['per_rep'] = {k: list(v)[:shown] if not isinstance(v, np.ndarray) else v[:shown] for k, v in reps_out.items()}
        payload['per_rep_shown'] = shown
        payload['traces'] = [_trace(result, i) for i in range(result.traced_reps)]
    return _json_safe(payload)


def _trace(result: Any, rep: int) -> Dict[str, Any]:
    tl = result.timeline(rep)
    events = result.event_log[result.event_log['rep'] == rep]
    failures = events[events['event'] == 'FAILURE']
    return {
        'rep': rep,
        'entity': tl['entity'].tolist(),
        'state': [STATE_CODES[str(s)] for s in tl['state']],
        'start': tl['start'].tolist(),
        'end': tl['end'].tolist(),
        'failure_entity': failures['entity'].tolist(),
        'failure_time': failures['time'].tolist(),
    }


def _seed_for(kwargs: Dict[str, Any]) -> int:
    # An empty seed field still yields a reproducible, reported run.
    return kwargs['seed'] if kwargs['seed'] is not None else secrets.randbits(32)


def run_simulation(scenario: Any, progress: Optional[Callable[[int, int], None]] = None
                   ) -> Tuple[Dict[str, Any], Callable[[], Dict[str, Any]]]:
    """Run one scenario. Returns ``(dashboard payload, export)``.

    ``export()`` builds, on demand, the engine's own ``to_dict()`` (schema,
    summary, intervals, every replication, event log) plus the scenario.
    """
    model, kwargs, normalized = build(scenario)
    seed = _seed_for(kwargs)
    normalized['seed'] = seed
    result = model.simulate(reps=kwargs['reps'], seed=seed, trace=kwargs['trace'], progress=progress)

    def export() -> Dict[str, Any]:
        out = result.to_dict(CONFIDENCE)
        out['scenario'] = normalized
        return out

    return result_payload(result, normalized, seed), export


# ----------------------------------------------------------------- sweeps --
def sweep_fields(scenario: Dict[str, Any]) -> List[str]:
    fields = ['mission_time']
    if scenario.get('system') == 'fleet':
        fields = ['n_teams', 'n_devices'] + fields
    for role in ('failure', 'repair'):
        spec = scenario.get(role) or {}
        if spec.get('dist') in DISTRIBUTIONS:
            fields += [f'{role}.{p}' for p in dist_params(spec['dist'])]
    return fields


def _with_value(scenario: Dict[str, Any], field: str, value: Any) -> Dict[str, Any]:
    s = copy.deepcopy(scenario)
    if '.' in field:
        role, p = field.split('.', 1)
        spec = s.setdefault(role, {})
        params = spec.get('params') or {}
        if isinstance(params, (list, tuple)):
            params = dict(zip(dist_params(spec['dist']), params))
        params[p] = value
        spec['params'] = params
    else:
        s[field] = value
    return s


def sweep_plan(scenario: Any, sweep: Any) -> Tuple[List[Tuple[Any, Any, Dict[str, Any]]], Dict[str, Any]]:
    """Validate a sweep and return ``([(value, model, normalized)], info)``."""
    _, base_kwargs, base = build(scenario)  # the base scenario must be valid
    if not isinstance(sweep, dict):
        raise ScenarioError([_error('sweep', 'sweep must be a JSON object', 'missing')])
    field = sweep.get('param')
    if field not in sweep_fields(base):
        raise ScenarioError([_error('sweep.param', f'cannot sweep {field!r}', 'sweep_param')])
    values = sweep.get('values')
    if (not isinstance(values, list) or not values
            or not all(_is_number(v) for v in values)):
        raise ScenarioError([_error('sweep.values', 'values must be a non-empty list of numbers', 'sweep_values')])
    if len(values) > MAX_SWEEP_POINTS:
        raise ScenarioError([_error('sweep.values', f'at most {MAX_SWEEP_POINTS} points', 'sweep_max')])
    reps = sweep.get('reps', base['reps'])
    plan, errors = [], []
    for value in values:
        point = _with_value(base, field, value)
        point.update(reps=reps, trace=0)
        try:
            model, kwargs, normalized = build(point)
        except ScenarioError as exc:
            for e in exc.errors:
                errors.append(dict(e, field=f'sweep[{value}].{e["field"]}', value=value))
            continue
        plan.append((value, model, normalized))
    if errors:
        raise ScenarioError(errors)
    info = {'param': field, 'values': values, 'reps': plan[0][2]['reps'], 'seed': base_kwargs['seed']}
    return plan, info


def run_sweep(scenario: Any, sweep: Any, progress: Optional[Callable[[int, int], None]] = None
              ) -> Dict[str, Any]:
    """Simulate every point of a one-parameter sweep with the same seed.

    Every point uses the same seed (common random numbers), so differences
    between neighbouring points are not blurred by independent noise.
    """
    plan, info = sweep_plan(scenario, sweep)
    seed = info['seed'] if info['seed'] is not None else secrets.randbits(32)
    reps = info['reps']
    total = reps * len(plan)
    points = []

    def point_progress(offset):
        if progress is None:
            return None
        return lambda done, _reps: progress(offset + done, total)

    for i, (value, model, normalized) in enumerate(plan):
        result = model.simulate(reps=reps, seed=seed, trace=0, progress=point_progress(i * reps))
        row = result_payload(result, normalized, seed, per_rep=False)
        points.append({
            'value': value,
            'n_devices': row['n_devices'],
            'n_teams': row['n_teams'],
            'mission_time': row['mission_time'],
            'metrics': row['metrics'],
        })
    _, _, base = build(scenario)
    base['seed'] = seed
    return _json_safe({
        'param': info['param'],
        'values': info['values'],
        'reps': reps,
        'seed': seed,
        'confidence': CONFIDENCE,
        'system': base['system'],
        'scenario': base,
        'points': points,
    })


# ------------------------------------------------------------- estimation --
class EstimateInputError(ValueError):
    """Unreadable failure-time input; ``code`` and ``detail`` for the page."""

    def __init__(self, code: str, message: str, detail: Any = None):
        self.code = code
        self.detail = detail
        super().__init__(message)


_SPLIT_SEMI = re.compile(r'[;\s]+')
_SPLIT_COMMA = re.compile(r'[,\s]+')


def parse_times(text: str) -> Tuple[List[float], int]:
    """Read numbers from pasted text or a CSV/plain-text file.

    Values may be separated by new lines, spaces, tabs, commas or semicolons.
    When the text contains a semicolon or a tab, a comma is read as the
    decimal separator (``1,5`` = 1.5), as in spreadsheets saved with a
    Portuguese locale. Brackets are ignored, so a pasted Python list works.
    Leading non-numeric tokens (a header such as ``time``) are skipped and
    counted; any later one is an error. Returns ``(values, skipped)``.
    """
    if not isinstance(text, str) or not text.strip():
        raise EstimateInputError('empty', 'no failure times given')
    cleaned = re.sub(r'[\[\]()]', ' ', text)
    decimal_comma = ';' in cleaned or '\t' in cleaned
    tokens = (_SPLIT_SEMI if decimal_comma else _SPLIT_COMMA).split(cleaned.strip())
    values: List[float] = []
    skipped = 0
    for token in tokens:
        if not token:
            continue
        candidate = token.replace(',', '.') if decimal_comma else token
        try:
            value = float(candidate)
        except ValueError:
            if not values:
                skipped += 1
                continue
            raise EstimateInputError('not_number', f'not a number: {token!r}', token)
        if not math.isfinite(value):
            raise EstimateInputError('not_number', f'not a number: {token!r}', token)
        values.append(value)
    if not values:
        raise EstimateInputError('empty', 'no failure times given')
    if len(values) > MAX_FAILURE_TIMES:
        raise EstimateInputError('too_many', f'at most {MAX_FAILURE_TIMES} failure times', MAX_FAILURE_TIMES)
    return values, skipped


def _mean_function_mc(distribution: Tuple, end: float, grid: np.ndarray, reps: int, seed: int,
                      cap: int) -> Tuple[np.ndarray, bool]:
    """Expected failures in ``[0, t]`` from new, by simulating the fitted
    failure process through the engine's sampler (repairs take no time)."""
    sampler = DISTRIBUTIONS[distribution[0]](*distribution[1:])
    sampler.set_rng(np.random.Generator(np.random.PCG64(seed)))
    counts = np.zeros(grid.size)
    truncated = False
    for _ in range(reps):
        sampler.reset()
        t, times = 0.0, []
        while True:
            t += float(sampler())
            if t > end:
                break
            times.append(t)
            if len(times) >= cap:
                truncated = True
                break
        counts += np.searchsorted(np.asarray(times), grid, side='right')
    return counts / reps, truncated


def _compensator(t: np.ndarray, a: float, b: float, q: float, kijima: int, points: np.ndarray) -> np.ndarray:
    """Cumulative intensity of the fitted model given the observed history.

    Between failures the virtual age grows with time and jumps after each
    repair (Kijima rule), so the curve is continuous but changes slope at
    every failure; for the power law it equals the mean function.
    """
    x = np.diff(t, prepend=0.0)
    v = np.zeros(t.size + 1)
    for i, xi in enumerate(x):
        v[i + 1] = v[i] + q * xi if kijima == 1 else q * (v[i] + xi)

    def H(u):
        return np.power(np.asarray(u, dtype=float) / a, b)

    cum = np.concatenate([[0.0], np.cumsum(H(v[:-1] + x) - H(v[:-1]))])
    k = np.searchsorted(t, points, side='left')
    prev = np.where(k > 0, t[np.maximum(k - 1, 0)], 0.0)
    with np.errstate(over='ignore'):
        return cum[k] + H(v[k] + points - prev) - H(v[k])


_MODELS = [
    # key, kijima, fixed q
    ('power_law', None, None),
    ('grp1', 1, None),
    ('grp2', 2, None),
    ('renewal', 1, 0.0),
]


def _profile(t: np.ndarray, end: Optional[float], kijima: int, grid: np.ndarray,
             ll_max: Optional[float]) -> Dict[str, Any]:
    ll = []
    for q in grid:
        try:
            ll.append(fit_weibull_grp(t, end_time=end, kijima=kijima, q=float(q)).log_likelihood)
        except ValueError:
            ll.append(float('nan'))
    ll = np.array(ll)
    if not np.any(np.isfinite(ll)):
        return {'ll': ll, 'interval': None}
    top = max(np.nanmax(ll), ll_max if ll_max is not None else -np.inf)
    rel = ll - top
    inside = np.where(np.isfinite(rel) & (rel >= -LR_DROP_95))[0]
    interval = None
    if inside.size:
        i0, i1 = int(inside[0]), int(inside[-1])

        def cross(i_in, i_out):
            r_in, r_out = rel[i_in], rel[i_out]
            if not np.isfinite(r_out) or r_in == r_out:
                return float(grid[i_in])
            w = (r_in + LR_DROP_95) / (r_in - r_out)
            return float(grid[i_in] + w * (grid[i_out] - grid[i_in]))

        lo = float(grid[0]) if i0 == 0 else cross(i0, i0 - 1)
        hi = float(grid[-1]) if i1 == grid.size - 1 else cross(i1, i1 + 1)
        interval = [lo, hi]
    return {'ll': ll, 'rel': rel, 'max': top, 'interval': interval}


def estimate(times: Any, end_time: Optional[float] = None, intervals: bool = False,
             profile_points: int = 101) -> Dict[str, Any]:
    """Trend test, the four failure-process fits, curves and q profiles.

    ``times`` are cumulative operating times at each failure, or times
    between failures when ``intervals`` is true. Models: power law (minimal
    repair, q = 1), Weibull GRP Kijima I and II (q estimated) and the Weibull
    renewal process (GRP with q = 0). A model the data cannot support (for
    example tied times in a GRP likelihood) reports the engine's message.
    """
    try:
        t = np.asarray(times, dtype=float)
    except (TypeError, ValueError):
        raise EstimateInputError('not_number', 'times must be numbers')
    if t.ndim != 1 or t.size == 0:
        raise EstimateInputError('empty', 'no failure times given')
    if intervals:
        if np.any(t <= 0):
            raise EstimateInputError('intervals_positive', 'times between failures must be greater than 0')
        t = np.cumsum(t)
    end = None if end_time is None or end_time == '' else end_time
    if end is not None and not _is_number(end):
        raise EstimateInputError('end_number', 'end_time must be a number')
    try:
        u, p = laplace_trend_test(t, end_time=end)
    except ValueError as exc:  # input the engine rejects for every model
        raise EstimateInputError('engine', str(exc))
    end_value = float(t[-1] if end is None else end)
    grid = np.linspace(0.0, end_value, 241)
    points = np.union1d(grid, t)
    cap = 50 * t.size + 1000

    models = []
    for key, kijima, q_fixed in _MODELS:
        entry: Dict[str, Any] = {'key': key, 'kijima': kijima}
        try:
            if key == 'power_law':
                fit = fit_power_law(t, end_time=end)
            else:
                fit = fit_weibull_grp(t, end_time=end, kijima=kijima, q=q_fixed)
        except ValueError as exc:
            entry['error'] = str(exc)
            models.append(entry)
            continue
        distribution = fit.distribution()
        entry.update({
            'model': fit.model, 'a': fit.a, 'b': fit.b, 'q': fit.q, 'q_fixed': fit.q_fixed,
            'log_likelihood': fit.log_likelihood, 'n_params': fit.n_params, 'aic': fit.aic,
            'distribution': list(distribution),
        })
        if key == 'power_law':
            entry['mean_function'] = {'t': grid, 'm': np.power(grid / fit.a, fit.b), 'method': 'closed_form'}
        else:
            m, truncated = _mean_function_mc(distribution, end_value, grid, MEAN_FUNCTION_REPS,
                                             MEAN_FUNCTION_SEED, cap)
            entry['mean_function'] = {'t': grid, 'm': m, 'method': 'monte_carlo',
                                      'reps': MEAN_FUNCTION_REPS, 'truncated': truncated}
        entry['compensator'] = {'t': points, 'm': _compensator(t, fit.a, fit.b, fit.q, kijima or 1, points)}
        models.append(entry)

    fitted = [m for m in models if 'aic' in m]
    best = min(fitted, key=lambda m: m['aic']) if fitted else None
    for m in fitted:
        m['delta_aic'] = m['aic'] - best['aic']

    q_grid = np.linspace(0.0, 1.0, profile_points)
    by_key = {m['key']: m for m in models}
    profile = {'q': q_grid, 'drop': LR_DROP_95}
    for kijima, key in ((1, 'grp1'), (2, 'grp2')):
        fit = by_key[key]
        if 'error' in fit:
            profile[key] = {'error': fit['error']}
        else:
            profile[key] = _profile(t, end, kijima, q_grid, fit['log_likelihood'])
            profile[key]['q_hat'] = fit['q']

    return _json_safe({
        'n': int(t.size),
        'times': t,
        'end_time': end_value,
        'failure_truncated': end is None,
        'intervals': bool(intervals),
        'laplace': {'u': u, 'p': p},
        'models': models,
        'best': best['key'] if best else None,
        'profile': profile,
    })
