"""Progress callback (``simulate(..., progress=f)``): reported after every
replication, never changes a result, and can stop a run by raising.
"""
import numpy as np
import pytest

from farofa.device import SimpleDevice
from farofa.fleet import Fleet


def make_device():
    device = SimpleDevice()
    device.set_failure_dist('weibull_grp', 200.0, 1.8, 0.4)
    device.set_repair_dist('lognormal', 2.0, 0.4)
    device.set_mission_time(2000.0)
    return device


def make_fleet():
    fleet = Fleet(n_devices=5, n_teams=2)
    fleet.set_failure_dist('weibull_grp', 200.0, 1.8, 0.4)
    fleet.set_repair_dist('lognormal', 3.0, 0.5)
    fleet.set_mission_time(2000.0)
    return fleet


class Stop(Exception):
    pass


@pytest.mark.parametrize('make', [make_device, make_fleet])
def test_called_after_each_replication(make):
    calls = []
    make().simulate(reps=7, seed=3, progress=lambda done, total: calls.append((done, total)))
    assert calls == [(i, 7) for i in range(1, 8)]


def test_device_results_unchanged():
    a = make_device().simulate(reps=40, seed=11, trace=2)
    b = make_device().simulate(reps=40, seed=11, trace=2, progress=lambda done, total: None)
    np.testing.assert_array_equal(a.failure_counts, b.failure_counts)
    np.testing.assert_array_equal(a.total_uptime, b.total_uptime)
    np.testing.assert_array_equal(a.event_log, b.event_log)


def test_fleet_results_unchanged():
    a = make_fleet().simulate(reps=40, seed=11, trace=2)
    b = make_fleet().simulate(reps=40, seed=11, trace=2, progress=lambda done, total: None)
    np.testing.assert_array_equal(a.failure_counts, b.failure_counts)
    np.testing.assert_array_equal(a.device_uptime, b.device_uptime)
    np.testing.assert_array_equal(a.busy_team_hours, b.busy_team_hours)
    np.testing.assert_array_equal(a.event_log, b.event_log)


@pytest.mark.parametrize('make', [make_device, make_fleet])
def test_exception_stops_the_run(make):
    seen = []

    def progress(done, total):
        seen.append(done)
        if done == 3:
            raise Stop()

    with pytest.raises(Stop):
        make().simulate(reps=50, seed=1, progress=progress)
    assert seen == [1, 2, 3]


@pytest.mark.parametrize('make', [make_device, make_fleet])
def test_rejects_non_callable(make):
    with pytest.raises(TypeError, match='progress'):
        make().simulate(reps=2, progress=5)
