"""Numerical regression tests for the GRP sampler and positive-support guards.

These target BUG-2 (misc/CRITICAL_ANALYSIS.md): the textbook inversion form
x = a*((v/a)^b - ln u)^(1/b) - v suffers catastrophic cancellation at high
virtual age (0.16% of draws <= 0 at v=1e6; 100% at v=1e9 for a=100, b=3) and
(v/a)^b overflow for large shapes. The rewritten log-space form must produce
strictly positive, finite times everywhere — and still sample the correct
conditional distribution.
"""
import math

import numpy as np
import pytest

from farofa.device import SimpleDevice
from farofa.distributions import _TINY, _grp_inverse, normal, weibull_grp
from farofa.fleet import Fleet


def draws(v, a, b, n, seed=20260804):
    u = np.maximum(np.random.default_rng(seed).random(n), _TINY)
    return np.array([_grp_inverse(v, a, b, ui) for ui in u.tolist()])


class TestGRPPositivity:
    def test_moderate_virtual_age(self):
        # Regime where ~0.16% of draws were non-positive before the fix.
        x = draws(1e6, 100.0, 3.0, 100_000)
        assert np.all(x > 0)
        assert np.all(np.isfinite(x))

    def test_high_virtual_age(self):
        # Regime where 100% of draws were non-positive before the fix.
        x = draws(1e9, 100.0, 3.0, 10_000)
        assert np.all(x > 0)
        assert np.all(np.isfinite(x))

    def test_extreme_virtual_age(self):
        # Roadmap Phase 0 exit criterion: positive and finite up to v >= 1e12.
        x = draws(1e12, 100.0, 3.0, 10_000)
        assert np.all(x > 0)
        assert np.all(np.isfinite(x))

    def test_overflow_regime_large_shape(self):
        # (v/a)^b = (1e4)^80 overflows to inf in the old form.
        x = draws(1e6, 100.0, 80.0, 10_000)
        assert np.all(x > 0)
        assert np.all(np.isfinite(x))

    def test_shape_below_one(self):
        x = draws(1e9, 100.0, 0.5, 10_000)
        assert np.all(x > 0)
        assert np.all(np.isfinite(x))

    def test_fresh_device(self):
        x = draws(0.0, 100.0, 2.0, 10_000)
        assert np.all(x > 0)
        assert np.all(np.isfinite(x))


class TestGRPDistributionalCorrectness:
    def test_conditional_survival_at_median(self):
        # S(x | v) = exp[(v/a)^b - ((x+v)/a)^b]. At the conditional median x50,
        # the empirical survival fraction must be ~0.5 (checks the rewritten
        # algebra against the definition, not against the old implementation).
        v, a, b = 500.0, 100.0, 2.0
        x50 = a * ((v / a) ** b + math.log(2.0)) ** (1.0 / b) - v
        x = draws(v, a, b, 200_000)
        frac_above = np.mean(x > x50)
        assert frac_above == pytest.approx(0.5, abs=0.01)

    def test_asymptotic_branch_mean(self):
        # For huge v the conditional time collapses to x ~= v * (-ln u) / (b (v/a)^b),
        # so E[x] = v / (b (v/a)^b). For v=1e9, a=100, b=3: 3.333e-13.
        v, a, b = 1e9, 100.0, 3.0
        expected = v / (b * (v / a) ** b)
        x = draws(v, a, b, 100_000)
        assert np.mean(x) == pytest.approx(expected, rel=0.05)

    def test_grp_sampler_end_to_end_still_degrades(self):
        # Sanity: the fixed formula preserves the aging behaviour (b>1, q>0).
        gen = weibull_grp(100.0, 2.0, 0.8)
        samples = [gen() for _ in range(5000)]
        assert np.mean(samples[:500]) > np.mean(samples[-500:])


class TestTruncatedNormal:
    def test_all_draws_positive(self):
        gen = normal(1.0, 2.0)  # substantial negative mass before truncation
        x = np.array([gen() for _ in range(10_000)])
        assert np.all(x > 0)

    def test_mean_preserved_when_truncation_negligible(self):
        gen = normal(100.0, 10.0)
        x = np.array([gen() for _ in range(10_000)])
        assert np.mean(x) == pytest.approx(100.0, rel=0.05)

    def test_degenerate_parameters_raise(self):
        with pytest.raises(ValueError, match='positive mass'):
            normal(-10.0, 1.0)

    def test_nonpositive_sigma_raises(self):
        with pytest.raises(ValueError):
            normal(1.0, 0.0)


def _constant_factory(value):
    def factory():
        def gen():
            return value
        return gen
    return factory


class TestEnginePositiveSupportGuard:
    @pytest.mark.parametrize('bad', [-5.0, 0.0, float('nan'), float('inf')])
    def test_device_rejects_bad_failure_times(self, bad):
        device = SimpleDevice()
        device.set_failure_dist(_constant_factory(bad))
        device.set_repair_dist('exponential', 0.1)
        device.set_mission_time(100)
        with pytest.raises(ValueError, match='strictly positive'):
            device.simulate(reps=1)

    def test_device_rejects_bad_repair_times(self):
        device = SimpleDevice()
        device.set_failure_dist(_constant_factory(1.0))
        device.set_repair_dist(_constant_factory(-1.0))
        device.set_mission_time(100)
        with pytest.raises(ValueError, match='strictly positive'):
            device.simulate(reps=1)

    def test_fleet_rejects_bad_failure_times(self):
        fleet = Fleet(n_devices=3, n_teams=1)
        fleet.set_failure_dist(_constant_factory(-2.0))
        fleet.set_repair_dist('exponential', 0.1)
        fleet.set_mission_time(100)
        with pytest.raises(ValueError, match='strictly positive'):
            fleet.simulate(reps=1)
