import numpy as np
import pytest

from farofa.device import SimpleDevice
from farofa.fleet import Fleet


def _constant_factory(value):
    def factory():
        return lambda: value
    return factory


def _configured_device():
    device = SimpleDevice()
    device.set_failure_dist('exponential', 0.01)
    device.set_repair_dist('exponential', 0.1)
    return device


def _configured_fleet():
    fleet = Fleet(n_devices=1, n_teams=1)
    fleet.set_failure_dist('exponential', 0.01)
    fleet.set_repair_dist('exponential', 0.1)
    return fleet


@pytest.mark.parametrize('model_factory', [_configured_device, _configured_fleet])
@pytest.mark.parametrize('mission_time', [float('nan'), float('inf'), float('-inf')])
def test_mission_time_must_be_finite_and_positive(model_factory, mission_time):
    with pytest.raises(ValueError, match='finite'):
        model_factory().set_mission_time(mission_time)


@pytest.mark.parametrize('model_factory', [_configured_device, _configured_fleet])
def test_mission_time_rejects_boolean(model_factory):
    with pytest.raises(TypeError, match='number'):
        model_factory().set_mission_time(True)


@pytest.mark.parametrize('model_factory', [_configured_device, _configured_fleet])
@pytest.mark.parametrize('reps', [1.5, '2.5', float('nan'), float('inf'), True])
def test_reps_must_be_a_positive_whole_number(model_factory, reps):
    model = model_factory()
    model.set_mission_time(10)
    with pytest.raises(ValueError, match='positive integer'):
        model.simulate(reps=reps)


@pytest.mark.parametrize('model_factory', [_configured_device, _configured_fleet])
def test_integral_reps_remain_accepted(model_factory):
    model = model_factory()
    model.set_mission_time(10)
    result = model.simulate(reps=2.0, seed=7)
    assert result.reps == 2


@pytest.mark.parametrize('model_factory', [_configured_device, _configured_fleet])
def test_event_exactly_at_mission_end_is_censored(model_factory):
    """The interval [0, T) is simulated; events at T do not affect metrics."""
    model = model_factory()
    model.set_failure_dist(_constant_factory(10.0))
    model.set_repair_dist(_constant_factory(1.0))
    model.set_mission_time(10.0)

    result = model.simulate(reps=1, seed=7)

    if isinstance(model, SimpleDevice):
        np.testing.assert_array_equal(result.failure_counts, [0])
        np.testing.assert_array_equal(result.repair_counts, [0])
        np.testing.assert_allclose(result.total_uptime, [10.0])
        np.testing.assert_allclose(result.total_downtime, [0.0])
    else:
        np.testing.assert_array_equal(result.failure_counts, [[0]])
        np.testing.assert_array_equal(result.repair_counts, [[0]])
        np.testing.assert_allclose(result.device_uptime, [[10.0]])
        np.testing.assert_allclose(result.device_downtime, [[0.0]])


@pytest.mark.parametrize('model_factory', [_configured_device, _configured_fleet])
def test_repair_completion_exactly_at_mission_end_is_censored(model_factory):
    model = model_factory()
    model.set_failure_dist(_constant_factory(5.0))
    model.set_repair_dist(_constant_factory(5.0))
    model.set_mission_time(10.0)

    result = model.simulate(reps=1, seed=7)

    if isinstance(model, SimpleDevice):
        np.testing.assert_array_equal(result.failure_counts, [1])
        np.testing.assert_array_equal(result.repair_counts, [0])
        np.testing.assert_allclose(result.total_uptime, [5.0])
        np.testing.assert_allclose(result.total_downtime, [5.0])
    else:
        np.testing.assert_array_equal(result.failure_counts, [[1]])
        np.testing.assert_array_equal(result.repair_counts, [[0]])
        np.testing.assert_allclose(result.device_uptime, [[5.0]])
        np.testing.assert_allclose(result.device_downtime, [[5.0]])
