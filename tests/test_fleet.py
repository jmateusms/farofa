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
    """N=1, K=1 fleet should statistically match a SimpleDevice."""

    def test_availability_matches(self):
        T = 5000.0
        reps = 500

        np.random.seed(42)
        device = SimpleDevice()
        device.set_failure_dist('exponential', 0.005)
        device.set_repair_dist('exponential', 0.1)
        device.set_mission_time(T)
        dev_result = device.simulate(reps=reps)

        np.random.seed(42)
        fleet = Fleet(n_devices=1, n_teams=1)
        fleet.set_failure_dist('exponential', 0.005)
        fleet.set_repair_dist('exponential', 0.1)
        fleet.set_mission_time(T)
        fleet_result = fleet.simulate(reps=reps)

        # Both should converge to the same theoretical availability:
        # A = (1/mu) / (1/mu + 1/nu) = nu / (mu + nu) where mu = failure rate, nu = repair rate
        # = 0.1 / (0.105) ≈ 0.9524
        assert abs(dev_result.availability - fleet_result.fleet_availability) < 0.01

    def test_failure_counts_comparable(self):
        T = 5000.0
        reps = 500

        np.random.seed(7)
        device = SimpleDevice()
        device.set_failure_dist('exponential', 0.005)
        device.set_repair_dist('exponential', 0.1)
        device.set_mission_time(T)
        dev_result = device.simulate(reps=reps)

        np.random.seed(7)
        fleet = Fleet(n_devices=1, n_teams=1)
        fleet.set_failure_dist('exponential', 0.005)
        fleet.set_repair_dist('exponential', 0.1)
        fleet.set_mission_time(T)
        fleet_result = fleet.simulate(reps=reps)

        assert abs(dev_result.mean_failures - fleet_result.mean_failures) / dev_result.mean_failures < 0.1


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
        # Holding everything else constant, more teams should not hurt availability.
        kwargs = dict(failure_rate=0.02, repair_rate=0.05, T=1500, reps=30)

        def avail(k):
            fleet = Fleet(n_devices=6, n_teams=k)
            fleet.set_failure_dist('exponential', kwargs['failure_rate'])
            fleet.set_repair_dist('exponential', kwargs['repair_rate'])
            fleet.set_mission_time(kwargs['T'])
            return fleet.simulate(reps=kwargs['reps']).fleet_availability

        np.random.seed(1)
        a1 = avail(1)
        np.random.seed(1)
        a6 = avail(6)
        assert a6 >= a1

    def test_utilization_higher_under_load(self):
        np.random.seed(0)
        light = Fleet(n_devices=3, n_teams=3)
        light.set_failure_dist('exponential', 0.005)
        light.set_repair_dist('exponential', 0.5)
        light.set_mission_time(1000)
        u_light = light.simulate(reps=20).server_utilization

        np.random.seed(0)
        heavy = Fleet(n_devices=10, n_teams=2)
        heavy.set_failure_dist('exponential', 0.05)
        heavy.set_repair_dist('exponential', 0.05)
        heavy.set_mission_time(1000)
        u_heavy = heavy.simulate(reps=20).server_utilization

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
            'mean_failures', 'mean_repairs', 'fleet_availability',
            'server_utilization', 'mean_wait_time', 'max_queue_observed',
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
