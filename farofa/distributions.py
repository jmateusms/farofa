"""Random variate samplers for failure and repair times.

Every factory below returns a sampler object that yields one positive float
per call. Each sampler owns a ``numpy.random.Generator`` (PCG64):

- Standalone use draws from a fresh, OS-entropy-seeded generator.
- ``sampler.set_rng(generator)`` attaches a specific stream; the engines call
  this from ``simulate(seed=...)`` so that a disclosed seed reproduces a run
  bit-for-bit and every device in a fleet gets a provably independent stream
  (``SeedSequence.spawn``).

Stateless samplers draw in vectorized batches through an internal refill
buffer, which is why the per-call cost stays close to NumPy's native bulk
generation. Stateful GRP samplers (virtual age feeds back into every draw)
are inherently sequential, but buffer their underlying uniforms the same way.

Reproducibility is same-environment: identical results require the same
numpy version and platform.
"""
import math

import numpy as np

# Draws consumed per vectorized refill. Large enough to amortize the numpy
# call overhead, small enough that short simulations don't waste draws.
_BUFFER_SIZE = 512

# Smallest positive normal double. Batch draws are clamped here so exact-zero
# variates (measure-zero, but representable) and log(0) can never occur.
_TINY = float(np.finfo(np.float64).tiny)


class Sampler:
    """Base class for variate samplers: owns an RNG and a refill buffer.

    Subclasses implement ``_fill(rng, n)`` returning ``n`` variates (or, for
    stateful samplers, the uniforms they transform). ``reset()`` clears
    sampler state (e.g. GRP virtual age) between replications — the RNG
    stream deliberately continues, so replications stay independent.
    """

    stateful = False

    def __init__(self):
        self._rng = np.random.default_rng()
        self._buf = None
        self._i = 0

    def set_rng(self, rng):
        """Attach a numpy Generator; discards buffered draws so subsequent
        output is fully determined by ``rng``."""
        self._rng = rng
        self._buf = None
        self._i = 0

    def reset(self):
        """Reset sampler state between replications (no-op when stateless)."""

    def _next_buffered(self):
        buf = self._buf
        i = self._i
        if buf is None or i >= buf.shape[0]:
            buf = np.maximum(self._fill(self._rng, _BUFFER_SIZE), _TINY)
            self._buf = buf
            i = 0
        self._i = i + 1
        return buf.item(i)

    def _fill(self, rng, n):
        raise NotImplementedError

    def __call__(self):
        return self._next_buffered()


class _BatchSampler(Sampler):
    """Stateless sampler around a vectorized fill function."""

    def __init__(self, fill):
        super().__init__()
        self._fill_fn = fill

    def _fill(self, rng, n):
        return self._fill_fn(rng, n)


def _grp_inverse(v, a, b, u):
    """Next inter-failure time for a Weibull GRP given virtual age ``v``.

    Inversion of the conditional Weibull CDF
        F(x | v) = 1 - exp[(v/a)^b - ((x+v)/a)^b]
    which in exact arithmetic gives x = a*[(v/a)^b - ln(u)]^(1/b) - v.
    That textbook form is numerically catastrophic for large v: the
    subtraction cancels (returning zero or negative times) and (v/a)^b
    overflows. With w = -ln(u) / (v/a)^b, the identity
        x = v * [(1 + w)^(1/b) - 1] = v * expm1(log1p(w) / b)
    is cancellation-free; w is computed in log space so (v/a)^b never
    overflows, with asymptotic branches where log1p/expm1 would saturate.
    The formula is identical for Kijima Type I and Type II — only the
    virtual age update between failures differs (handled by the caller).

    Reference: Yañez et al. (2002), Reliability Engineering & System
    Safety, 77.
    """
    neg_log_u = -math.log(u)  # > 0: callers supply u in (0, 1)
    if v <= 0.0:
        x = a * neg_log_u ** (1.0 / b)
    else:
        log_w = math.log(neg_log_u) - b * math.log(v / a)
        if log_w > 30.0:
            # w >= ~1e13: v is negligible against the fresh draw; the direct
            # form has no cancellation here (ratio to v is at least e^(30/b)).
            x = a * neg_log_u ** (1.0 / b) - v
        elif log_w < -30.0:
            # w <= ~1e-13: expm1(log1p(w)/b) == w/b to double precision.
            x = v * math.exp(log_w) / b
        else:
            x = v * math.expm1(math.log1p(math.exp(log_w)) / b)
    # Clamp genuine underflow (astronomical virtual age) to the smallest
    # positive double rather than emitting 0.
    return x if x > 0.0 else _TINY


class _GRPSampler(Sampler):
    """Stateful Weibull sampler with a Kijima virtual-age update rule.

    kijima=1: v_i = v_{i-1} + q * x_i      (Type I)
    kijima=2: v_i = q * (v_{i-1} + x_i)    (Type II)

    The virtual age is exposed as ``.v``. ``reset()`` returns it to 0 at the
    start of each replication.
    """

    stateful = True

    def __init__(self, a, b, q, kijima):
        super().__init__()
        self.a = a
        self.b = b
        self.q = q
        self.kijima = kijima
        self.v = 0.0

    def reset(self):
        self.v = 0.0

    def _fill(self, rng, n):
        return rng.random(n)

    def __call__(self):
        u = self._next_buffered()
        x = _grp_inverse(self.v, self.a, self.b, u)
        if self.kijima == 1:
            self.v += self.q * x
        else:
            self.v = self.q * (self.v + x)
        return x


def _require_positive(**params):
    for name, value in params.items():
        if not value > 0:
            raise ValueError(f'{name} must be greater than 0.')


def _require_q(q):
    if not 0.0 <= q <= 1.0:
        raise ValueError('q (repair effectiveness) must be between 0 and 1.')


def exponential(rate):
    """
    Instantiates an exponential random variate sampler.

    Parameters:
        rate: rate of failures/events per time unit (lambda).

    Returns:
        A callable that generates exponentially distributed random times.
    """
    _require_positive(rate=rate)
    scale = 1.0 / rate
    return _BatchSampler(lambda rng, n: rng.exponential(scale, n))


def weibull(a, b):
    """
    Instantiates a Weibull random variate sampler.
    Assumes perfect repair (device age reset to 0 after repair).
    Equivalent to weibull_grp with q=0.

    Parameters:
        a: scale parameter
        b: shape parameter

    Returns:
        A callable that generates Weibull distributed random times.
    """
    _require_positive(a=a, b=b)
    return _BatchSampler(lambda rng, n: a * rng.weibull(b, n))


def weibull_min(a, b):
    """
    Instantiates a stateful Weibull minimal-repair (as-bad-as-old) sampler.
    Equivalent to weibull_grp with q=1: virtual age accumulates all elapsed time.

    Virtual age update: v_i = v_{i-1} + x_i  (q=1 Type I)

    Call reset() at the start of each simulation replication.

    Parameters:
        a: scale parameter
        b: shape parameter

    Returns:
        A stateful callable generating successive Weibull inter-failure times.
    """
    _require_positive(a=a, b=b)
    return _GRPSampler(a, b, q=1.0, kijima=1)


def weibull_grp(a, b, q):
    """
    Instantiates a stateful Weibull GRP Kijima Type I sampler.

    Virtual age update after each failure:
        v_i = v_{i-1} + q * x_i

    q=0: perfect repair (as good as new, virtual age stays 0)
    q=1: minimal repair (as bad as old, equivalent to weibull_min)
    0<q<1: imperfect repair (partial damage removal from the last interval)

    Call reset() at the start of each simulation replication.

    Parameters:
        a: scale parameter
        b: shape parameter
        q: repair effectiveness (0 to 1)

    Returns:
        A stateful callable generating successive GRP Type I inter-failure times.
    """
    _require_positive(a=a, b=b)
    _require_q(q)
    return _GRPSampler(a, b, q=q, kijima=1)


def weibull_grp2(a, b, q):
    """
    Instantiates a stateful Weibull GRP Kijima Type II sampler.

    Virtual age update after each failure:
        v_i = q * (v_{i-1} + x_i)

    q=0: perfect repair (as good as new, virtual age collapses to 0)
    q=1: minimal repair (as bad as old, identical to Type I with q=1)
    0<q<1: imperfect repair (damage removal applied to total accumulated age,
           not just the last interval — differs from Type I for 0<q<1)

    Call reset() at the start of each simulation replication.

    Parameters:
        a: scale parameter
        b: shape parameter
        q: repair effectiveness (0 to 1)

    Returns:
        A stateful callable generating successive GRP Type II inter-failure times.
    """
    _require_positive(a=a, b=b)
    _require_q(q)
    return _GRPSampler(a, b, q=q, kijima=2)


def lognormal(mu, sigma):
    """
    Instantiates a lognormal random variate sampler.

    Parameters:
        mu: mean of the underlying normal distribution (log-scale)
        sigma: standard deviation of the underlying normal distribution (log-scale)

    Returns:
        A callable that generates lognormally distributed random times.
    """
    _require_positive(sigma=sigma)
    return _BatchSampler(lambda rng, n: rng.lognormal(mu, sigma, n))


def normal(mu, sigma):
    """
    Instantiates a normal random variate sampler, truncated at zero.

    Negative variates would run simulated time backwards, so draws are
    rejected until positive (i.e., this samples the normal distribution
    conditioned on X > 0). The truncation is negligible when mu >> sigma;
    the factory refuses parameters whose positive mass is vanishingly small.

    Parameters:
        mu: mean (of the untruncated distribution)
        sigma: standard deviation (of the untruncated distribution)

    Returns:
        A callable that generates positive, normally distributed random values.
    """
    _require_positive(sigma=sigma)
    # P(X > 0) for the untruncated normal; refuse practically-degenerate cases
    # where rejection sampling would loop (nearly) forever.
    p_positive = 0.5 * math.erfc(-mu / (sigma * math.sqrt(2.0)))
    if p_positive < 1e-6:
        raise ValueError(
            f'normal(mu={mu}, sigma={sigma}) has practically no positive mass '
            f'(P(X>0)={p_positive:.2e}); failure/repair times must be positive.'
        )

    def fill(rng, n):
        x = rng.normal(mu, sigma, n)
        bad = x <= 0.0
        while bad.any():
            x[bad] = rng.normal(mu, sigma, int(bad.sum()))
            bad = x <= 0.0
        return x

    return _BatchSampler(fill)


def gamma(shape, scale):
    """
    Instantiates a gamma random variate sampler.

    Parameters:
        shape: shape parameter (k > 0)
        scale: scale parameter (theta > 0)

    Returns:
        A callable that generates gamma distributed random times.
    """
    _require_positive(shape=shape, scale=scale)
    return _BatchSampler(lambda rng, n: rng.gamma(shape, scale, n))


# Single registry shared by every engine (SimpleDevice, Fleet).
DISTRIBUTIONS = {
    'exponential': exponential,
    'weibull': weibull,
    'weibull_min': weibull_min,
    'weibull_grp': weibull_grp,
    'weibull_grp2': weibull_grp2,
    'lognormal': lognormal,
    'normal': normal,
    'gamma': gamma,
}
