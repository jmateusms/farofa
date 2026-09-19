import math

import numpy as np
import pytest

from farofa.results import FleetSimulationResult, SimulationResult, mean_confidence_interval


def test_replication_mean_interval_matches_closed_form():
    values = np.array([0.2, 0.4, 0.6, 0.8])
    lo, hi = mean_confidence_interval(values)
    expected_half_width = 1.959963984540054 * values.std(ddof=1) / math.sqrt(len(values))
    assert (lo, hi) == pytest.approx((values.mean() - expected_half_width,
                                      values.mean() + expected_half_width))


def test_device_availability_interval_uses_replications_and_clips_bounds():
    result = SimulationResult(
        mission_time=10.0,
        failure_counts=[0, 0, 0], repair_counts=[0, 0, 0],
        uptimes=[np.array([])] * 3, downtimes=[np.array([])] * 3,
        total_uptime=[0.0, 5.0, 10.0], total_downtime=[10.0, 5.0, 0.0],
    )
    assert result.availability_confidence_interval() == pytest.approx((0.0, 1.0))


def test_fleet_interval_uses_one_observation_per_replication():
    # Device values are deliberately different within each replication. The
    # interval must use [0, .5, 1], not six pseudo-independent devices.
    result = FleetSimulationResult(
        mission_time=10.0, n_devices=2, n_teams=1,
        failure_counts=np.zeros((3, 2)), repair_counts=np.zeros((3, 2)),
        device_uptime=np.array([[0.0, 0.0], [0.0, 10.0], [10.0, 10.0]]),
        device_downtime=np.zeros((3, 2)), busy_team_hours=[0, 0, 0],
        max_queue=[0, 0, 0], wait_times=[np.array([])] * 3,
    )
    assert result.availability_per_rep == pytest.approx([0.0, 0.5, 1.0])
    assert result.availability_confidence_interval() == pytest.approx(
        mean_confidence_interval(result.availability_per_rep, lower=0.0, upper=1.0)
    )


def test_interval_is_nan_with_one_replication():
    assert all(np.isnan(mean_confidence_interval([0.5])))


def test_nonfinite_value_is_rejected_even_with_one_replication():
    with pytest.raises(ValueError, match='finite'):
        mean_confidence_interval([float('nan')])


def test_invalid_bounds_are_rejected_even_with_one_replication():
    with pytest.raises(ValueError, match='lower'):
        mean_confidence_interval([0.5], lower=2.0, upper=1.0)


@pytest.mark.parametrize('confidence', [0, 1, float('nan'), True, '0.95'])
def test_invalid_confidence_is_rejected(confidence):
    with pytest.raises((TypeError, ValueError)):
        mean_confidence_interval([0.2, 0.3], confidence)


@pytest.mark.parametrize('kwargs', [
    {'lower': float('nan')}, {'upper': float('inf')}, {'lower': True},
    {'upper': '1'}, {'lower': 2.0, 'upper': 1.0},
])
def test_invalid_bounds_are_rejected(kwargs):
    with pytest.raises((TypeError, ValueError)):
        mean_confidence_interval([0.2, 0.3], **kwargs)


def test_confidence_just_below_one_has_finite_quantile():
    lo, hi = mean_confidence_interval([0.2, 0.3], np.nextafter(1.0, 0.0))
    assert np.isfinite(lo)
    assert np.isfinite(hi)


def test_failure_and_utilization_intervals_use_replication_totals():
    result = FleetSimulationResult(
        mission_time=10.0, n_devices=2, n_teams=2,
        failure_counts=np.array([[1, 2], [3, 4], [5, 6]]),
        repair_counts=np.zeros((3, 2)), device_uptime=np.full((3, 2), 10.0),
        device_downtime=np.zeros((3, 2)), busy_team_hours=[0.0, 10.0, 20.0],
        max_queue=[0, 0, 0], wait_times=[np.array([])] * 3,
    )
    assert result.total_failures_per_rep == pytest.approx([3.0, 7.0, 11.0])
    assert result.server_utilization_per_rep == pytest.approx([0.0, 0.5, 1.0])
    assert result.failure_count_confidence_interval() == pytest.approx(
        mean_confidence_interval(result.total_failures_per_rep, lower=0.0)
    )
    assert result.server_utilization_confidence_interval() == pytest.approx(
        mean_confidence_interval(result.server_utilization_per_rep, lower=0.0, upper=1.0)
    )
