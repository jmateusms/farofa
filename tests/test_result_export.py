import json

import numpy as np

from farofa.results import FleetSimulationResult, SimulationResult


def test_device_result_export_is_json_serializable_and_keeps_replications(tmp_path):
    result = SimulationResult(
        mission_time=10.0,
        failure_counts=[1, 2], repair_counts=[1, 2],
        uptimes=[np.array([4.0]), np.array([3.0, 2.0])],
        downtimes=[np.array([6.0]), np.array([5.0, 0.0])],
        total_uptime=[4.0, 5.0], total_downtime=[6.0, 5.0],
    )
    payload = result.to_dict()
    assert json.loads(json.dumps(payload))['replications']['availability'] == [0.4, 0.5]
    destination = result.export_json(tmp_path / 'device.json')
    assert json.loads(destination.read_text())['result_kind'] == 'simple_device'


def test_fleet_result_export_uses_replication_level_metrics(tmp_path):
    result = FleetSimulationResult(
        mission_time=10.0, n_devices=2, n_teams=1,
        failure_counts=np.array([[1, 0], [2, 1]]),
        repair_counts=np.array([[1, 0], [2, 1]]),
        device_uptime=np.array([[8.0, 10.0], [6.0, 10.0]]),
        device_downtime=np.array([[2.0, 0.0], [4.0, 0.0]]),
        busy_team_hours=[2.0, 4.0], max_queue=[0, 1],
        wait_times=[np.array([0.0]), np.array([1.0])],
    )
    payload = result.to_dict()
    assert payload['replications']['availability'] == [0.9, 0.8]
    assert payload['replications']['server_utilization'] == [0.2, 0.4]
    assert len(payload['replications']['failure_counts']) == 2
    destination = result.export_json(tmp_path / 'fleet.json')
    assert json.loads(destination.read_text())['result_kind'] == 'fleet'


def test_export_replaces_unavailable_estimates_with_json_null(tmp_path):
    result = SimulationResult(
        mission_time=10.0,
        failure_counts=[0], repair_counts=[0],
        uptimes=[np.array([])], downtimes=[np.array([])],
        total_uptime=[10.0], total_downtime=[0.0],
    )
    payload = result.to_dict()
    assert payload['summary']['mttf'] is None
    assert payload['confidence_intervals']['availability'] == [None, None]
    destination = result.export_json(tmp_path / 'strict.json')
    # The parser hook would reject JavaScript's non-standard NaN/Infinity.
    parsed = json.loads(destination.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(AssertionError(value)))
    assert parsed['summary']['mttr'] is None
