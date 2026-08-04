import numpy as np
import pytest
from farofa.distributions import (
    exponential, weibull, weibull_min, weibull_grp, weibull_grp2,
    lognormal, normal, gamma,
)


def generate_samples(factory, args, n=10000):
    """Generate n samples from a distribution factory."""
    gen = factory(*args)
    return np.array([gen() for _ in range(n)])


class TestExponential:
    def test_positive_values(self):
        samples = generate_samples(exponential, (0.01,))
        assert np.all(samples > 0)

    def test_mean_approximation(self):
        rate = 0.05
        samples = generate_samples(exponential, (rate,))
        expected_mean = 1.0 / rate
        assert abs(np.mean(samples) - expected_mean) < 1.0  # within 1 unit

    def test_different_rates(self):
        slow = generate_samples(exponential, (0.001,))
        fast = generate_samples(exponential, (1.0,))
        assert np.mean(slow) > np.mean(fast)


class TestWeibull:
    def test_positive_values(self):
        samples = generate_samples(weibull, (100.0, 2.0))
        assert np.all(samples > 0)

    def test_mean_scales_with_a(self):
        small = generate_samples(weibull, (10.0, 2.0))
        large = generate_samples(weibull, (100.0, 2.0))
        assert np.mean(large) > np.mean(small)

    def test_exponential_when_b_is_1(self):
        # Weibull with b=1 is exponential with rate=1/a
        a = 100.0
        samples = generate_samples(weibull, (a, 1.0))
        expected_mean = a
        assert abs(np.mean(samples) - expected_mean) / expected_mean < 0.05


class TestWeibullMin:
    def test_positive_values(self):
        samples = generate_samples(weibull_min, (100.0, 2.0))
        assert np.all(samples > 0)

    def test_degrading_sequence(self):
        # For b>1 (degrading Weibull), a single sampler's inter-failure times
        # should shrink as virtual age accumulates. Compare first vs last block.
        gen = weibull_min(100.0, 2.0)
        n = 5000
        samples = [gen() for _ in range(n)]
        block = n // 10
        assert np.mean(samples[:block]) > np.mean(samples[-block:])

    def test_reset_restarts_virtual_age(self):
        gen = weibull_min(100.0, 2.0)
        # Burn in to advance virtual age significantly
        for _ in range(500):
            gen()
        aged_sample = gen()
        gen.reset()
        # After reset, virtual age is 0 again — first samples should be much larger
        fresh_samples = [gen() for _ in range(200)]
        assert np.mean(fresh_samples) > aged_sample


class TestWeibullGRP:
    def test_positive_values(self):
        samples = generate_samples(weibull_grp, (100.0, 2.0, 0.5))
        assert np.all(samples > 0)

    def test_perfect_repair_matches_weibull(self):
        # q=0: virtual age never accumulates, each sample is an independent
        # Weibull(a, b) variate — mean should match standard Weibull.
        a, b = 100.0, 2.0
        grp_samples = generate_samples(weibull_grp, (a, b, 0.0))
        weib_samples = generate_samples(weibull, (a, b))
        assert abs(np.mean(grp_samples) - np.mean(weib_samples)) / np.mean(weib_samples) < 0.05

    def test_minimal_repair_same_distribution_as_weibull_min(self):
        # q=1 Type I and weibull_min use the same update rule: v_i = v_{i-1} + x_i.
        # Their sample means and overall degradation trend should be statistically identical.
        a, b = 100.0, 2.0
        grp_samples = generate_samples(weibull_grp, (a, b, 1.0))
        min_samples = generate_samples(weibull_min, (a, b))
        assert abs(np.mean(grp_samples) - np.mean(min_samples)) / np.mean(min_samples) < 0.05

    def test_degrading_for_partial_q(self):
        # 0<q<1: virtual age grows, inter-failure times should decrease over time
        gen = weibull_grp(100.0, 2.0, 0.8)
        n = 5000
        samples = [gen() for _ in range(n)]
        block = n // 10
        assert np.mean(samples[:block]) > np.mean(samples[-block:])

    def test_reset_restarts_virtual_age(self):
        gen = weibull_grp(100.0, 2.0, 0.5)
        for _ in range(500):
            gen()
        gen.reset()
        assert gen.v == 0.0


class TestWeibullGRP2:
    def test_positive_values(self):
        samples = generate_samples(weibull_grp2, (100.0, 2.0, 0.5))
        assert np.all(samples > 0)

    def test_perfect_repair_matches_weibull(self):
        # q=0: v_i = 0*(v+x) = 0 always — each sample is an independent Weibull variate
        a, b = 100.0, 2.0
        grp2_samples = generate_samples(weibull_grp2, (a, b, 0.0))
        weib_samples = generate_samples(weibull, (a, b))
        assert abs(np.mean(grp2_samples) - np.mean(weib_samples)) / np.mean(weib_samples) < 0.05

    def test_reset_restarts_virtual_age(self):
        gen = weibull_grp2(100.0, 2.0, 0.5)
        for _ in range(500):
            gen()
        gen.reset()
        assert gen.v == 0.0


class TestGRPTypeIDiffersFromTypeII:
    def test_different_virtual_age_paths(self):
        # For 0<q<1 and b>1, Type I and Type II accumulate virtual age differently.
        # Type I: v_i = v_{i-1} + q*x_i  → old history fully preserved
        # Type II: v_i = q*(v_{i-1}+x_i) → old history discounted each repair
        # After many failures, Type II virtual age grows more slowly than Type I.
        a, b, q = 100.0, 2.0, 0.5
        n = 200
        gen1 = weibull_grp(a, b, q)
        gen2 = weibull_grp2(a, b, q)
        for _ in range(n):
            gen1()
            gen2()
        # Type I accumulates more virtual age than Type II
        assert gen1.v > gen2.v


class TestLognormal:
    def test_positive_values(self):
        samples = generate_samples(lognormal, (1.0, 0.5))
        assert np.all(samples > 0)

    def test_mean_approximation(self):
        mu, sigma = 2.0, 0.5
        samples = generate_samples(lognormal, (mu, sigma))
        expected_mean = np.exp(mu + sigma**2 / 2)
        assert abs(np.mean(samples) - expected_mean) / expected_mean < 0.05


class TestNormal:
    def test_mean_approximation(self):
        mu, sigma = 100.0, 10.0
        samples = generate_samples(normal, (mu, sigma))
        assert abs(np.mean(samples) - mu) / mu < 0.05

    def test_std_approximation(self):
        mu, sigma = 100.0, 10.0
        samples = generate_samples(normal, (mu, sigma))
        assert abs(np.std(samples) - sigma) / sigma < 0.1


class TestGamma:
    def test_positive_values(self):
        samples = generate_samples(gamma, (2.0, 10.0))
        assert np.all(samples > 0)

    def test_mean_approximation(self):
        shape, scale = 3.0, 5.0
        samples = generate_samples(gamma, (shape, scale))
        expected_mean = shape * scale
        assert abs(np.mean(samples) - expected_mean) / expected_mean < 0.05

    def test_shape_less_than_1(self):
        samples = generate_samples(gamma, (0.5, 10.0))
        assert np.all(samples > 0)
        expected_mean = 0.5 * 10.0
        assert abs(np.mean(samples) - expected_mean) / expected_mean < 0.1

    def test_exponential_when_shape_is_1(self):
        # Gamma(1, scale) = Exponential(1/scale)
        scale = 20.0
        samples = generate_samples(gamma, (1.0, scale))
        assert abs(np.mean(samples) - scale) / scale < 0.05
