import numpy as np
import pytest
from farofa.device import SimpleDevice
from farofa.results import SimulationResult


class TestSimpleDeviceSetup:
    def test_default_state(self):
        device = SimpleDevice()
        assert device.operational is True
        assert device.failure_dist is None
        assert device.repair_dist is None
        assert device.mission_time is None

    def test_set_failure_dist_by_name(self):
        device = SimpleDevice()
        device.set_failure_dist('exponential', 0.01)
        assert device.failure_dist is not None

    def test_set_repair_dist_by_name(self):
        device = SimpleDevice()
        device.set_repair_dist('exponential', 0.1)
        assert device.repair_dist is not None

    def test_unknown_distribution_raises(self):
        device = SimpleDevice()
        with pytest.raises(ValueError, match="Unknown distribution"):
            device.set_failure_dist('invalid_dist', 0.01)

    def test_set_mission_time(self):
        device = SimpleDevice()
        device.set_mission_time(8760)
        assert device.mission_time == 8760.0

    def test_mission_time_negative_raises(self):
        device = SimpleDevice()
        with pytest.raises(ValueError):
            device.set_mission_time(-1)

    def test_mission_time_zero_raises(self):
        device = SimpleDevice()
        with pytest.raises(ValueError):
            device.set_mission_time(0)

    def test_mission_time_string_conversion(self):
        device = SimpleDevice()
        device.set_mission_time('100')
        assert device.mission_time == 100.0

    def test_mission_time_invalid_string_raises(self):
        device = SimpleDevice()
        with pytest.raises(TypeError):
            device.set_mission_time('not_a_number')


class TestSimpleDeviceCustomDist:
    def test_custom_callable_failure_dist(self):
        from farofa.distributions import exponential

        device = SimpleDevice()
        device.set_failure_dist(exponential, 0.001)
        assert device.failure_dist is not None

    def test_custom_callable_repair_dist(self):
        from farofa.distributions import lognormal

        device = SimpleDevice()
        device.set_repair_dist(lognormal, 1.0, 0.5)
        assert device.repair_dist is not None

    def test_prebuilt_sampler_instance_rejected(self):
        # Passing exponential(0.01) instead of (exponential, 0.01) would be
        # silently treated as a factory and stored as a float — reject early.
        from farofa.distributions import exponential

        device = SimpleDevice()
        with pytest.raises(TypeError, match='factory'):
            device.set_failure_dist(exponential(0.01))
        with pytest.raises(TypeError, match='factory'):
            device.set_repair_dist(exponential(0.1))


class TestSimpleDeviceSimulate:
    def _make_device(self, mission_time=8760):
        device = SimpleDevice()
        device.set_failure_dist('exponential', 0.0001)
        device.set_repair_dist('exponential', 0.01)
        device.set_mission_time(mission_time)
        return device

    def test_simulate_returns_result(self):
        device = self._make_device()
        result = device.simulate(reps=10)
        assert isinstance(result, SimulationResult)

    def test_simulate_correct_reps(self):
        device = self._make_device()
        result = device.simulate(reps=50)
        assert result.reps == 50
        assert len(result.failure_counts) == 50

    def test_simulate_no_failure_dist_raises(self):
        device = SimpleDevice()
        device.set_repair_dist('exponential', 0.01)
        device.set_mission_time(100)
        with pytest.raises(ValueError, match="Failure distribution not set"):
            device.simulate()

    def test_simulate_no_repair_dist_raises(self):
        device = SimpleDevice()
        device.set_failure_dist('exponential', 0.01)
        device.set_mission_time(100)
        with pytest.raises(ValueError, match="Repair distribution not set"):
            device.simulate()

    def test_simulate_no_mission_time_raises(self):
        device = SimpleDevice()
        device.set_failure_dist('exponential', 0.01)
        device.set_repair_dist('exponential', 0.01)
        with pytest.raises(ValueError, match="Mission time not set"):
            device.simulate()

    def test_simulate_zero_reps_raises(self):
        device = self._make_device()
        with pytest.raises(ValueError):
            device.simulate(reps=0)

    def test_uptime_plus_downtime_equals_mission_time(self):
        device = self._make_device(mission_time=1000)
        result = device.simulate(reps=100)
        total = result.total_uptime + result.total_downtime
        np.testing.assert_allclose(total, 1000.0, rtol=1e-10)

    def test_failure_counts_nonnegative(self):
        device = self._make_device()
        result = device.simulate(reps=100)
        assert np.all(result.failure_counts >= 0)

    def test_availability_between_0_and_1(self):
        device = self._make_device()
        result = device.simulate(reps=100)
        assert 0.0 <= result.availability <= 1.0


class TestSimulationResult:
    def test_repr(self):
        device = SimpleDevice()
        device.set_failure_dist('exponential', 0.001)
        device.set_repair_dist('exponential', 0.1)
        device.set_mission_time(1000)
        result = device.simulate(reps=10)
        text = repr(result)
        assert 'SimulationResult' in text
        assert 'MTTF' in text

    def test_summary_keys(self):
        device = SimpleDevice()
        device.set_failure_dist('exponential', 0.001)
        device.set_repair_dist('exponential', 0.1)
        device.set_mission_time(1000)
        result = device.simulate(reps=10)
        s = result.summary()
        expected_keys = {
            'mission_time', 'replications', 'mean_failures', 'std_failures',
            'mean_repairs', 'mttf', 'mttr', 'availability', 'failure_rate',
        }
        assert set(s.keys()) == expected_keys
