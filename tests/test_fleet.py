import numpy as np
import pytest

from farofa.fleet import Fleet
from farofa.device import SimpleDevice
from farofa.results import FleetSimulationResult


class TestFleetSetup:
    def test_default_state(self):
        fleet = Fleet(n_devices=5, n_teams=2)
        assert fleet.n_devices == 5
        assert fleet.n_teams == 2
        assert fleet._failure_spec is None
        assert fleet._repair_spec is None
        assert fleet.mission_time is None

    def test_n_devices_must_be_positive(self):
        with pytest.raises(ValueError):
            Fleet(n_devices=0, n_teams=1)
        with pytest.raises(ValueError):
            Fleet(n_devices=-1, n_teams=1)

    def test_n_teams_must_be_positive(self):
        with pytest.raises(ValueError):
            Fleet(n_devices=1, n_teams=0)

    def test_unknown_distribution_raises(self):
        fleet = Fleet(n_devices=1, n_teams=1)
        with pytest.raises(ValueError, match="Unknown distribution"):
            fleet.set_failure_dist('not_a_dist', 1.0)

    def test_prebuilt_sampler_instance_rejected(self):
        from farofa.distributions import exponential

        fleet = Fleet(n_devices=2, n_teams=1)
        with pytest.raises(TypeError, match='factory'):
            fleet.set_failure_dist(exponential(0.01))

    def test_set_mission_time_validation(self):
        fleet = Fleet(n_devices=1, n_teams=1)
        with pytest.raises(ValueError):
            fleet.set_mission_time(-1)
        with pytest.raises(ValueError):
            fleet.set_mission_time(0)
        with pytest.raises(TypeError):
            fleet.set_mission_time('nope')

    def test_simulate_requires_setup(self):
        fleet = Fleet(n_devices=1, n_teams=1)
        with pytest.raises(ValueError, match="Failure distribution"):
            fleet.simulate()
        fleet.set_failure_dist('exponential', 0.01)
        with pytest.raises(ValueError, match="Repair distribution"):
            fleet.simulate()
        fleet.set_repair_dist('exponential', 0.1)
        with pytest.raises(ValueError, match="Mission time"):
            fleet.simulate()


class TestFleetBasic:
    def _make_fleet(self, n_devices=5, n_teams=2, T=1000):
        fleet = Fleet(n_devices=n_devices, n_teams=n_teams)
        fleet.set_failure_dist('exponential', 0.001)
        fleet.set_repair_dist('exponential', 0.1)
        fleet.set_mission_time(T)
        return fleet

    def test_simulate_returns_result(self):
        fleet = self._make_fleet()
        result = fleet.simulate(reps=10)
        assert isinstance(result, FleetSimulationResult)

    def test_simulate_shapes(self):
        fleet = self._make_fleet(n_devices=4, n_teams=2)
        result = fleet.simulate(reps=7)
        assert result.failure_counts.shape == (7, 4)
        assert result.repair_counts.shape == (7, 4)
        assert result.device_uptime.shape == (7, 4)
        assert result.device_downtime.shape == (7, 4)
        assert result.busy_team_hours.shape == (7,)
        assert result.max_queue.shape == (7,)
        assert len(result.wait_times) == 7

    def test_uptime_plus_downtime_equals_mission_time(self):
        T = 1000.0
        fleet = self._make_fleet(n_devices=5, n_teams=2, T=T)
        result = fleet.simulate(reps=50)
        per_device_total = result.device_uptime + result.device_downtime
        np.testing.assert_allclose(per_device_total, T, rtol=1e-10)

    def test_availability_between_0_and_1(self):
        fleet = self._make_fleet()
        result = fleet.simulate(reps=20)
        assert 0.0 <= result.fleet_availability <= 1.0

    def test_utilization_between_0_and_1(self):
        fleet = self._make_fleet()
        result = fleet.simulate(reps=20)
        assert 0.0 <= result.server_utilization <= 1.0


class TestFleetParityWithSimpleDevice:
    """An N=1, K=1 fleet must reproduce SimpleDevice *exactly* under the same
    seed: both spawn the identical pair of child streams from the seed and
    consume draws in the same order, so trajectories are bit-identical (times
    agree to float summation-order differences)."""

    def _pair(self, seed, failure=('exponential', 0.005), repair=('exponential', 0.1),
              T=5000.0, reps=200):
        device = SimpleDevice()
        device.set_failure_dist(*failure)
        device.set_repair_dist(*repair)
        device.set_mission_time(T)
        dev_result = device.simulate(reps=reps, seed=seed)

        fleet = Fleet(n_devices=1, n_teams=1)
        fleet.set_failure_dist(*failure)
        fleet.set_repair_dist(*repair)
        fleet.set_mission_time(T)
        fleet_result = fleet.simulate(reps=reps, seed=seed)
        return dev_result, fleet_result

    def test_failure_counts_identical(self):
        dev, fl = self._pair(seed=42)
        np.testing.assert_array_equal(dev.failure_counts, fl.failure_counts.ravel())
        np.testing.assert_array_equal(dev.repair_counts, fl.repair_counts.ravel())

    def test_uptime_downtime_match(self):
        dev, fl = self._pair(seed=42)
        np.testing.assert_allclose(dev.total_uptime, fl.device_uptime.ravel(), rtol=1e-9)
        np.testing.assert_allclose(dev.total_downtime, fl.device_downtime.ravel(), rtol=1e-9)

    def test_parity_holds_for_stateful_grp(self):
        dev, fl = self._pair(seed=7, failure=('weibull_grp', 200.0, 1.8, 0.4),
                             repair=('lognormal', 2.0, 0.4), T=8760.0, reps=100)
        np.testing.assert_array_equal(dev.failure_counts, fl.failure_counts.ravel())
        np.testing.assert_allclose(dev.total_uptime, fl.device_uptime.ravel(), rtol=1e-9)

    def test_availability_matches_theory(self):
        # lambda=0.005, mu=0.1: steady-state A = mu/(lambda+mu) ~= 0.9524
        dev, fl = self._pair(seed=11, reps=500)
        assert abs(dev.availability - 0.9524) < 0.01
        assert abs(fl.fleet_availability - 0.9524) < 0.01


class TestFleetQueueing:
    def test_no_queue_when_teams_match_devices(self):
        # K = N: every device can always be repaired immediately.
        fleet = Fleet(n_devices=4, n_teams=4)
        fleet.set_failure_dist('exponential', 0.01)
        fleet.set_repair_dist('exponential', 0.05)
        fleet.set_mission_time(2000)
        result = fleet.simulate(reps=20)
        assert result.max_queue_observed == 0
        assert result.mean_wait_time == 0.0

    def test_queue_builds_under_load(self):
        # K=1 with many degrading devices and slow repairs: queue must form.
        fleet = Fleet(n_devices=8, n_teams=1)
        fleet.set_failure_dist('exponential', 0.05)
        fleet.set_repair_dist('exponential', 0.05)
        fleet.set_mission_time(1000)
        result = fleet.simulate(reps=10)
        assert result.max_queue_observed > 0
        assert result.mean_wait_time > 0.0

    def test_more_teams_increase_availability(self):
        # Same seed = common random numbers per device stream, so more teams
        # must not hurt availability.
        def avail(k):
            fleet = Fleet(n_devices=6, n_teams=k)
            fleet.set_failure_dist('exponential', 0.02)
            fleet.set_repair_dist('exponential', 0.05)
            fleet.set_mission_time(1500)
            return fleet.simulate(reps=30, seed=1).fleet_availability

        assert avail(6) >= avail(1)

    def test_utilization_higher_under_load(self):
        light = Fleet(n_devices=3, n_teams=3)
        light.set_failure_dist('exponential', 0.005)
        light.set_repair_dist('exponential', 0.5)
        light.set_mission_time(1000)
        u_light = light.simulate(reps=20, seed=0).server_utilization

        heavy = Fleet(n_devices=10, n_teams=2)
        heavy.set_failure_dist('exponential', 0.05)
        heavy.set_repair_dist('exponential', 0.05)
        heavy.set_mission_time(1000)
        u_heavy = heavy.simulate(reps=20, seed=0).server_utilization

        assert u_heavy > u_light


class TestFleetStatefulSamplers:
    """GRP virtual age must be independent per device — degradation on one device
    shouldn't shorten another device's first inter-failure time."""

    def test_grp_virtual_age_per_device(self):
        # Strongly degrading: b=3, q=1 (minimal repair). After many failures the
        # mean inter-failure time on a single sampler drops a lot; with N devices
        # sharing the same params but independent state, each device starts fresh
        # and the fleet-level mean failure rate should stay close to first-failure
        # rate × N (not blown up by shared state).
        fleet = Fleet(n_devices=10, n_teams=10)
        fleet.set_failure_dist('weibull_grp', 100.0, 3.0, 1.0)
        fleet.set_repair_dist('exponential', 1.0)
        fleet.set_mission_time(500)
        result = fleet.simulate(reps=20)
        # If state leaked across devices, samplers would be ~10x more aged and
        # the failure count would explode. Sanity-bound it.
        assert result.mean_failures < 10 * 500  # absurd upper bound


class TestFleetCustomCallable:
    def test_custom_callable_factory(self):
        from farofa.distributions import exponential

        fleet = Fleet(n_devices=3, n_teams=1)
        fleet.set_failure_dist(exponential, 0.01)
        fleet.set_repair_dist(exponential, 0.1)
        fleet.set_mission_time(500)
        result = fleet.simulate(reps=5)
        assert isinstance(result, FleetSimulationResult)


class TestFleetSimulationResultRepr:
    def test_summary_keys(self):
        fleet = Fleet(n_devices=2, n_teams=1)
        fleet.set_failure_dist('exponential', 0.01)
        fleet.set_repair_dist('exponential', 0.1)
        fleet.set_mission_time(500)
        result = fleet.simulate(reps=5)
        s = result.summary()
        expected = {
            'mission_time', 'n_devices', 'n_teams', 'replications',
            'mean_failures', 'mean_repairs', 'mttf', 'mttr',
            'fleet_availability', 'server_utilization', 'mean_wait_time',
            'max_queue_observed',
        }
        assert set(s.keys()) == expected

    def test_repr_includes_key_metrics(self):
        fleet = Fleet(n_devices=2, n_teams=1)
        fleet.set_failure_dist('exponential', 0.01)
        fleet.set_repair_dist('exponential', 0.1)
        fleet.set_mission_time(500)
        result = fleet.simulate(reps=5)
        text = repr(result)
        assert 'FleetSimulationResult' in text
        assert 'Fleet availability' in text
        assert 'Server utilization' in text
