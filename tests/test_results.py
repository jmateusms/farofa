"""Regression tests for result metrics against analytical values.

These target BUG-1 (misc/CRITICAL_ANALYSIS.md): the naive mean of completed
inter-failure intervals in a fixed mission window is length-biased and
underestimated MTTF by ~3x in the heavily-censored regime tested here.
"""
import numpy as np
import pytest

from farofa.device import SimpleDevice
from farofa.fleet import Fleet


def constant(value):
    """Factory for a degenerate distribution that always returns `value`."""
    def gen():
        return value
    return gen


class TestMTTFRenewalEstimator:
    def test_mttf_heavily_censored_regime(self):
        # True MTTF (10000) is larger than the mission time (8760): most
        # replications see 0 or 1 failures and the final interval is censored.
        # The length-biased estimator reported ~3300 here; the renewal
        # estimator must stay close to 10000.
        device = SimpleDevice()
        device.set_failure_dist('exponential', 1e-4)
        device.set_repair_dist('exponential', 0.01)
        device.set_mission_time(8760)
        result = device.simulate(reps=4000)
        assert result.mttf == pytest.approx(10000.0, rel=0.08)

    def test_mttr_matches_analytical(self):
        device = SimpleDevice()
        device.set_failure_dist('exponential', 1e-3)
        device.set_repair_dist('exponential', 0.01)  # true MTTR = 100
        device.set_mission_time(8760)
        result = device.simulate(reps=2000)
        assert result.mttr == pytest.approx(100.0, rel=0.08)

    def test_availability_matches_steady_state(self):
        # lambda=1e-3, mu=1e-2: A ~= mu/(lambda+mu) = 0.9091 (T >> transient)
        device = SimpleDevice()
        device.set_failure_dist('exponential', 1e-3)
        device.set_repair_dist('exponential', 1e-2)
        device.set_mission_time(50000)
        result = device.simulate(reps=500)
        assert result.availability == pytest.approx(10.0 / 11.0, rel=0.02)


class TestEmptySetConventions:
    def _no_failure_result(self, reps=10):
        device = SimpleDevice()
        device.set_failure_dist(constant, 1e9)  # never fails within T
        device.set_repair_dist('exponential', 0.1)
        device.set_mission_time(100)
        return device.simulate(reps=reps)

    def test_mttf_nan_when_no_failures(self):
        result = self._no_failure_result()
        assert np.isnan(result.mttf)

    def test_mttr_nan_when_no_repairs(self):
        result = self._no_failure_result()
        assert np.isnan(result.mttr)

    def test_availability_one_when_no_failures(self):
        result = self._no_failure_result()
        assert result.availability == pytest.approx(1.0)

    def test_std_failures_nan_at_one_rep(self):
        result = self._no_failure_result(reps=1)
        assert np.isnan(result.std_failures)

    def test_repr_survives_nan_metrics(self):
        result = self._no_failure_result()
        assert 'SimulationResult' in repr(result)


class TestFleetMTTFMTTR:
    def test_fleet_mttf_mttr_no_queueing(self):
        # K = N: no queue, so device downtime == active repair time and both
        # renewal estimators must match the analytical means.
        fleet = Fleet(n_devices=5, n_teams=5)
        fleet.set_failure_dist('exponential', 2e-3)  # MTTF = 500
        fleet.set_repair_dist('exponential', 5e-2)   # MTTR = 20
        fleet.set_mission_time(5000)
        result = fleet.simulate(reps=300)
        assert result.mttf == pytest.approx(500.0, rel=0.08)
        assert result.mttr == pytest.approx(20.0, rel=0.08)

    def test_fleet_mttf_nan_when_no_failures(self):
        fleet = Fleet(n_devices=3, n_teams=1)
        fleet.set_failure_dist(constant, 1e9)
        fleet.set_repair_dist('exponential', 0.1)
        fleet.set_mission_time(100)
        result = fleet.simulate(reps=5)
        assert np.isnan(result.mttf)
        assert np.isnan(result.mttr)
        assert 'FleetSimulationResult' in repr(result)
