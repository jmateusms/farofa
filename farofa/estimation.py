"""Estimate repairable-system failure models from one system's failure times.

The input is the ordered cumulative *operating* times ``t_1 < ... < t_n`` at
which one system failed, observed from ``t = 0`` (new, virtual age 0) until
``end_time``. Without ``end_time`` the record is failure-truncated at ``t_n``;
with it, time-truncated (no failure in ``(t_n, end_time]``).

Repair durations do not enter these likelihoods. Fit them separately and pass
both to a simulation::

    fit = fit_weibull_grp(times, end_time=T)
    device.set_failure_dist(*fit.distribution())

All parameters follow the samplers in :mod:`farofa.distributions`: Weibull
scale ``a``, shape ``b`` and Kijima repair factor ``q`` (0 = as good as new,
1 = as bad as old). The power-law NHPP with intensity ``lambda*beta*t**(beta-1)``
is ``weibull_min(a, b)`` with ``b = beta`` and ``a = lambda**(-1/beta)``.
"""
import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

_LOG_B_BOUNDS = (math.log(0.02), math.log(50.0))
_GOLDEN = (math.sqrt(5.0) - 1.0) / 2.0


@dataclass(frozen=True)
class RepairableFit:
    """Maximum-likelihood fit of a single-system failure process.

    ``model`` is ``'power_law'`` (minimal repair), ``'weibull_grp'`` (Kijima
    Type I) or ``'weibull_grp2'`` (Kijima Type II). ``q`` is 1 for the power
    law. ``q_fixed`` tells whether ``q`` was given instead of estimated.
    """

    model: str
    a: float
    b: float
    q: float
    log_likelihood: float
    n_failures: int
    end_time: float
    failure_truncated: bool
    q_fixed: bool = False

    @property
    def n_params(self) -> int:
        return 2 if self.model == 'power_law' or self.q_fixed else 3

    @property
    def aic(self) -> float:
        return 2.0 * self.n_params - 2.0 * self.log_likelihood

    def distribution(self) -> tuple:
        """Arguments for ``set_failure_dist(*fit.distribution())``."""
        if self.model == 'power_law':
            return ('weibull_min', self.a, self.b)
        return (self.model, self.a, self.b, self.q)


def _validate(times, end_time, min_failures) -> Tuple[np.ndarray, float, bool]:
    t = np.asarray(times, dtype=float)
    if t.ndim != 1 or t.size < min_failures:
        raise ValueError(f'times must be a 1-D sequence with at least {min_failures} failures.')
    if not np.all(np.isfinite(t)) or t[0] <= 0.0:
        raise ValueError('failure times must be finite and greater than 0.')
    if np.any(np.diff(t) <= 0.0):
        raise ValueError('failure times must be strictly increasing cumulative times '
                         '(ties give zero-length intervals; record them with more precision).')
    if end_time is None:
        return t, float(t[-1]), True
    end = float(end_time)
    if not math.isfinite(end) or end < t[-1]:
        raise ValueError('end_time must be finite and not earlier than the last failure.')
    return t, end, False


def fit_power_law(times, end_time: Optional[float] = None) -> RepairableFit:
    """Closed-form MLE of the power-law NHPP (Crow-AMSAA, minimal repair).

    ``beta = n / sum(ln(T / t_i))`` and ``lambda = n / T**beta`` with ``T`` the
    end of observation (``t_n`` if failure-truncated). ``beta > 1`` means the
    failure intensity grows with age (deterioration).
    """
    t, end, failure_truncated = _validate(times, end_time, 2)
    n = t.size
    log_ratio_sum = float(np.sum(np.log(end / t)))
    if log_ratio_sum <= 0.0:
        raise ValueError('cannot estimate the shape: all failures at the end of observation.')
    b = n / log_ratio_sum
    a = end * n ** (-1.0 / b)
    loglik = (n * math.log(b) - n * b * math.log(a)
              + (b - 1.0) * float(np.sum(np.log(t))) - n)
    return RepairableFit('power_law', a, b, 1.0, loglik, n, end, failure_truncated)


def _virtual_ages(s, q, kijima):
    """Virtual age before each failure interval and after the last failure."""
    x = np.diff(s, prepend=0.0)
    v = np.empty(s.size + 1)
    v[0] = 0.0
    if kijima == 1:
        v[1:] = q * s
    else:
        for i, xi in enumerate(x):
            v[i + 1] = q * (v[i] + xi)
    return v[:-1], x, v[-1]


def _hazard_increment(v, x, b):
    """(v + x)**b - v**b without cancellation; v and x arrays, b array (m,)."""
    v = v[:, None]
    x = x[:, None]
    with np.errstate(divide='ignore', invalid='ignore'):
        aged = np.power(v, b) * np.expm1(b * np.log1p(x / v))
    return np.where(v > 0.0, aged, np.power(x, b))


def _profile(s, c, q, kijima, log_b):
    """Profile log-likelihood (scaled times) over a vector of log-shapes."""
    n = s.size
    v_prev, x, v_last = _virtual_ages(s, q, kijima)
    b = np.exp(np.atleast_1d(log_b))
    total = _hazard_increment(v_prev, x, b).sum(axis=0)
    if c > 0.0:
        total = total + _hazard_increment(np.array([v_last]), np.array([c]), b)[0]
    log_age_sum = float(np.sum(np.log(v_prev + x)))
    with np.errstate(divide='ignore'):
        ll = n * np.log(b) - n * np.log(total / n) + (b - 1.0) * log_age_sum - n
    return np.where(total > 0.0, ll, -np.inf), total


def _golden_max(f, lo, hi, iterations=60):
    a, b = lo, hi
    c = b - _GOLDEN * (b - a)
    d = a + _GOLDEN * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(iterations):
        if fc >= fd:
            b, d, fd = d, c, fc
            c = b - _GOLDEN * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + _GOLDEN * (b - a)
            fd = f(d)
    return (c, fc) if fc >= fd else (d, fd)


def _best_shape(s, c, q, kijima):
    grid = np.linspace(*_LOG_B_BOUNDS, 161)
    ll, _ = _profile(s, c, q, kijima, grid)
    k = int(np.argmax(ll))
    if k in (0, grid.size - 1):
        raise ValueError('the Weibull shape is not identified within [0.02, 50] '
                         'for these data (too few failures or degenerate pattern).')
    log_b, best = _golden_max(lambda u: float(_profile(s, c, q, kijima, u)[0][0]),
                              grid[k - 1], grid[k + 1])
    return log_b, best


def fit_weibull_grp(times, end_time: Optional[float] = None, kijima: int = 1,
                    q: Optional[float] = None) -> RepairableFit:
    """MLE of the Weibull generalized renewal process (Kijima Type I or II).

    The scale has a closed form given shape and ``q``, so the likelihood is
    maximized over ``(b, q)`` only: a grid on ``q`` in [0, 1] and on log ``b``,
    refined by golden-section search. Pass ``q`` to fix it (``q=1`` reproduces
    :func:`fit_power_law`, ``q=0`` a Weibull renewal process); fixing ``q`` on
    a grid also traces its profile likelihood for interval estimates.
    """
    if kijima not in (1, 2):
        raise ValueError('kijima must be 1 or 2.')
    if q is not None and not 0.0 <= q <= 1.0:
        raise ValueError('q must be between 0 and 1.')
    t, end, failure_truncated = _validate(times, end_time, 3)
    n = t.size
    # Work in units of the observation window so powers neither overflow nor
    # underflow; the log-likelihood shifts by -n*ln(end) and a scales by end.
    s = t / end
    c = 1.0 - s[-1]

    def profile_q(qv):
        return _best_shape(s, c, qv, kijima)[1]

    if q is None:
        q_grid = np.linspace(0.0, 1.0, 51)
        values = [profile_q(qv) for qv in q_grid]
        k = int(np.argmax(values))
        q_hat, _ = _golden_max(profile_q, q_grid[max(k - 1, 0)],
                               q_grid[min(k + 1, q_grid.size - 1)], iterations=40)
        if values[k] > profile_q(q_hat):
            q_hat = float(q_grid[k])
    else:
        q_hat = float(q)
    log_b, ll_scaled = _best_shape(s, c, q_hat, kijima)
    b = math.exp(log_b)
    _, total = _profile(s, c, q_hat, kijima, log_b)
    a = end * (float(total[0]) / n) ** (1.0 / b)
    model = 'weibull_grp' if kijima == 1 else 'weibull_grp2'
    return RepairableFit(model, a, b, q_hat, ll_scaled - n * math.log(end), n, end,
                         failure_truncated, q_fixed=q is not None)


def laplace_trend_test(times, end_time: Optional[float] = None) -> Tuple[float, float]:
    """Laplace test of a trend in the failure intensity (H0: homogeneous Poisson).

    Returns ``(U, p_value)`` with a two-sided normal p-value. ``U > 0`` means
    failures concentrate late in the window (deterioration); ``U < 0`` means
    reliability growth. A failure-truncated record drops the last failure,
    which only marks the end of the window.
    """
    t, end, failure_truncated = _validate(times, end_time, 2)
    if failure_truncated:
        t = t[:-1]
    m = t.size
    u = (float(np.mean(t)) - end / 2.0) / (end * math.sqrt(1.0 / (12.0 * m)))
    return u, math.erfc(abs(u) / math.sqrt(2.0))
