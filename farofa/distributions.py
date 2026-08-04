import math

import numpy as np
from numba import njit, float64
from .utils import safe_random


def exponential(rate):
    """
    Instantiates an exponential random variable generator.

    Parameters:
        rate: rate of failures/events per time unit (lambda).

    Returns:
        A callable that generates exponentially distributed random times.
    """

    @njit
    def exponential_rvs(rate=rate):
        u = safe_random()
        return -np.log(u) / rate

    return exponential_rvs


def weibull(a, b):
    """
    Instantiates a Weibull random variable generator.
    Assumes perfect repair (device age reset to 0 after repair).
    Equivalent to weibull_grp with q=0.

    Parameters:
        a: scale parameter
        b: shape parameter

    Returns:
        A callable that generates Weibull distributed random times.
    """

    @njit
    def weibull_rvs(a=a, b=b):
        u = safe_random()
        return a * (-np.log(u)) ** (1 / b)

    return weibull_rvs


# Smallest positive normal double: clamp target when the conditional
# inter-failure time genuinely underflows (astronomically large virtual age).
_TINY = np.finfo(np.float64).tiny


@njit(float64(float64, float64, float64))
def _sample_grp(v, a, b):
    """
    Inversion-method sampler for the next inter-failure time given virtual age v.
    Derived from the conditional Weibull CDF:
        F(x | v) = 1 - exp[(v/a)^b - ((x+v)/a)^b]
    Solving F(x | v) = 1 - u gives, in exact arithmetic:
        x = a * [(v/a)^b - ln(u)]^(1/b) - v
    That textbook form is numerically catastrophic for large v: the subtraction
    cancels (returning zero or negative times) and (v/a)^b overflows. With
    w = -ln(u) / (v/a)^b, the identity
        x = v * [(1 + w)^(1/b) - 1] = v * expm1(log1p(w) / b)
    is cancellation-free; w is computed in log space so (v/a)^b never overflows,
    with asymptotic branches where log1p/expm1 would themselves saturate.
    The formula is identical for Kijima Type I and Type II — only the virtual
    age update rule between failures differs (handled by the caller).

    Reference: Yañez et al. (2002), Reliability Engineering & System Safety, 77.
    """
    u = safe_random()
    neg_log_u = -np.log(u)  # > 0 since safe_random() returns u in (0, 1)
    if v <= 0.0:
        x = a * neg_log_u ** (1.0 / b)
    else:
        log_w = np.log(neg_log_u) - b * np.log(v / a)
        if log_w > 30.0:
            # w >= ~1e13: v is negligible against the fresh draw; the direct
            # form has no cancellation here (ratio to v is at least e^(30/b)).
            x = a * neg_log_u ** (1.0 / b) - v
        elif log_w < -30.0:
            # w <= ~1e-13: expm1(log1p(w)/b) == w/b to double precision.
            x = v * np.exp(log_w) / b
        else:
            x = v * np.expm1(np.log1p(np.exp(log_w)) / b)
    if x > 0.0:
        return x
    return _TINY


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
    class _Sampler:
        def __init__(self):
            self.v = 0.0

        def __call__(self):
            x = _sample_grp(self.v, a, b)
            self.v += x
            return x

        def reset(self):
            self.v = 0.0

    return _Sampler()


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
    class _Sampler:
        def __init__(self):
            self.v = 0.0

        def __call__(self):
            x = _sample_grp(self.v, a, b)
            self.v += q * x
            return x

        def reset(self):
            self.v = 0.0

    return _Sampler()


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
    class _Sampler:
        def __init__(self):
            self.v = 0.0

        def __call__(self):
            x = _sample_grp(self.v, a, b)
            self.v = q * (self.v + x)
            return x

        def reset(self):
            self.v = 0.0

    return _Sampler()


def lognormal(mu, sigma):
    """
    Instantiates a lognormal random variable generator.

    Parameters:
        mu: mean of the underlying normal distribution (log-scale)
        sigma: standard deviation of the underlying normal distribution (log-scale)

    Returns:
        A callable that generates lognormally distributed random times.
    """

    @njit
    def lognormal_rvs(mu=mu, sigma=sigma):
        # Box-Muller transform for standard normal
        u1 = safe_random()
        u2 = safe_random()
        z = np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2)
        return np.exp(mu + sigma * z)

    return lognormal_rvs


def normal(mu, sigma):
    """
    Instantiates a normal random variable generator, truncated at zero.

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
    if sigma <= 0:
        raise ValueError('sigma must be greater than 0.')
    # P(X > 0) for the untruncated normal; refuse practically-degenerate cases
    # where rejection sampling would loop (nearly) forever.
    p_positive = 0.5 * math.erfc(-mu / (sigma * math.sqrt(2.0)))
    if p_positive < 1e-6:
        raise ValueError(
            f'normal(mu={mu}, sigma={sigma}) has practically no positive mass '
            f'(P(X>0)={p_positive:.2e}); failure/repair times must be positive.'
        )

    @njit
    def normal_rvs(mu=mu, sigma=sigma):
        # Box-Muller transform, rejecting non-positive draws (truncation at 0)
        while True:
            u1 = safe_random()
            u2 = safe_random()
            z = np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2)
            x = mu + sigma * z
            if x > 0.0:
                return x

    return normal_rvs


def gamma(shape, scale):
    """
    Instantiates a gamma random variable generator using Marsaglia and Tsang's method.

    Parameters:
        shape: shape parameter (k > 0)
        scale: scale parameter (theta > 0)

    Returns:
        A callable that generates gamma distributed random times.
    """

    @njit
    def gamma_rvs(shape=shape, scale=scale):
        # Marsaglia and Tsang's method for shape >= 1
        # For shape < 1, use the identity: Gamma(a) = Gamma(a+1) * U^(1/a)
        if shape < 1.0:
            boost = True
            a = shape + 1.0
        else:
            boost = False
            a = shape

        d = a - 1.0 / 3.0
        c = 1.0 / np.sqrt(9.0 * d)

        while True:
            # Generate normal via Box-Muller
            u1 = safe_random()
            u2 = safe_random()
            z = np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2)

            v = (1.0 + c * z) ** 3
            if v <= 0.0:
                continue

            u = safe_random()
            if u < 1.0 - 0.0331 * z ** 4:
                x = d * v * scale
                if boost:
                    x *= safe_random() ** (1.0 / shape)
                return x

            if np.log(u) < 0.5 * z ** 2 + d * (1.0 - v + np.log(v)):
                x = d * v * scale
                if boost:
                    x *= safe_random() ** (1.0 / shape)
                return x

    return gamma_rvs
