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


@njit(float64(float64, float64, float64))
def _sample_grp(v, a, b):
    """
    Inversion-method sampler for the next inter-failure time given virtual age v.
    Derived from the conditional Weibull CDF:
        F(x | v) = 1 - exp[(v/a)^b - ((x+v)/a)^b]
    Solving F(x | v) = 1 - u gives:
        x = a * [(v/a)^b - ln(u)]^(1/b) - v
    Formula is identical for Kijima Type I and Type II — only the virtual age
    update rule between failures differs (handled by the caller).

    Reference: Yañez et al. (2002), Reliability Engineering & System Safety, 77.
    """
    u = safe_random()
    return a * ((v / a) ** b - np.log(u)) ** (1.0 / b) - v


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
    Instantiates a normal random variable generator.
    Note: can generate negative values — use with care for time distributions.

    Parameters:
        mu: mean
        sigma: standard deviation

    Returns:
        A callable that generates normally distributed random values.
    """

    @njit
    def normal_rvs(mu=mu, sigma=sigma):
        # Box-Muller transform
        u1 = safe_random()
        u2 = safe_random()
        z = np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2)
        return mu + sigma * z

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
