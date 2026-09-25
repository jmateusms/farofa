"""Event trace (``simulate(..., trace=k)``): recording must not change any result,
and every aggregate metric must be recoverable from the event log and timeline.
"""
import json

import numpy as np
import pytest

from farofa.device import SimpleDevice
from farofa.fleet import Fleet
from farofa.results import EVENT_DTYPE, TIMELINE_DTYPE


def make_device(T=2000.0):
    device = SimpleDevice()
    device.set_failure_dist('weibull_grp', 200.0, 1.8, 0.4)
    device.set_repair_dist('lognormal', 2.0, 0.4)
    device.set_mission_time(T)
    return device


def make_fleet(n=6, k=2, T=2000.0):
    fleet = Fleet(n_devices=n, n_teams=k)
    fleet.set_failure_dist('weibull_grp', 200.0, 1.8, 0.4)
    fleet.set_repair_dist('lognormal', 3.0, 0.5)  # long repairs: the queue is exercised
    fleet.set_mission_time(T)
    return fleet


def durations(tl, entity, states):
    rows = tl[(tl['entity'] == entity) & np.isin(tl['state'], states)]
    return float(np.sum(rows['end'] - rows['start']))


class TestTraceDoesNotChangeResults:
    def test_device(self):
        a = make_device().simulate(reps=50, seed=11)
        b = make_device().simulate(reps=50, seed=11, trace=5)
        np.testing.assert_array_equal(a.failure_counts, b.failure_counts)
        np.testing.assert_array_equal(a.total_uptime, b.total_uptime)
        np.testing.assert_array_equal(a.total_downtime, b.total_downtime)
        np.testing.assert_array_equal(np.concatenate(a.uptimes), np.concatenate(b.uptimes))
        assert a.event_log is None and b.event_log is not None

    def test_fleet(self):
        a = make_fleet().simulate(reps=30, seed=5)
        b = make_fleet().simulate(reps=30, seed=5, trace=30)
        for name in ('failure_counts', 'repair_counts', 'device_uptime', 'device_downtime',
                     'busy_team_hours', 'max_queue'):
            np.testing.assert_array_equal(getattr(a, name), getattr(b, name))
        for wa, wb in zip(a.wait_times, b.wait_times):
            np.testing.assert_array_equal(wa, wb)


class TestFleetTraceReproducesMetrics:
    @pytest.fixture(scope='class')
    def result(self):
        return make_fleet(n=6, k=2).simulate(reps=4, seed=2026, trace=4)

    def test_log_shape(self, result):
        log = result.event_log
        assert log.dtype == EVENT_DTYPE
        assert result.traced_reps == 4
        assert set(np.unique(log['event'])) <= {'FAILURE', 'REPAIR_START', 'REPAIR_DONE'}
        assert np.all((log['time'] > 0) & (log['time'] < result.mission_time))
        for r in range(4):
            times = log['time'][log['rep'] == r]
            assert np.all(np.diff(times) >= 0), 'events are recorded in time order'

    def test_counts(self, result):
        log = result.event_log
        for r in range(result.reps):
            for d in range(result.n_devices):
                sel = (log['rep'] == r) & (log['entity'] == d)
                assert np.sum(sel & (log['event'] == 'FAILURE')) == result.failure_counts[r, d]
                assert np.sum(sel & (log['event'] == 'REPAIR_DONE')) == result.repair_counts[r, d]

    def test_timeline_matches_uptime_downtime_and_team_hours(self, result):
        T = result.mission_time
        for r in range(result.reps):
            tl = result.timeline(r)
            assert tl.dtype == TIMELINE_DTYPE
            busy = 0.0
            for d in range(result.n_devices):
                mine = tl[tl['entity'] == d]
                # contiguous cover of [0, T]
                assert mine['start'][0] == 0.0 and mine['end'][-1] == pytest.approx(T)
                np.testing.assert_allclose(mine['start'][1:], mine['end'][:-1])
                assert durations(tl, d, ['up']) == pytest.approx(result.device_uptime[r, d], rel=1e-12)
                assert durations(tl, d, ['waiting', 'repair']) == pytest.approx(result.device_downtime[r, d], rel=1e-12)
                busy += durations(tl, d, ['repair'])
            assert busy == pytest.approx(result.busy_team_hours[r], rel=1e-12)

    def test_waits(self, result):
        # wait = REPAIR_START - FAILURE, in the order the engine starts repairs
        log = result.event_log
        for r in range(result.reps):
            failed_at, waits = {}, []
            for row in log[log['rep'] == r]:
                d, ev, t = int(row['entity']), str(row['event']), float(row['time'])
                if ev == 'FAILURE':
                    failed_at[d] = t
                elif ev == 'REPAIR_START':
                    waits.append(t - failed_at[d])
            np.testing.assert_array_equal(np.array(waits), result.wait_times[r])
        assert any(len(w) and np.max(w) > 0 for w in result.wait_times), 'the fixture must queue'

    def test_max_queue_from_timeline(self, result):
        for r in range(result.reps):
            tl = result.timeline(r)
            waiting = tl[tl['state'] == 'waiting']
            edges = sorted({*waiting['start'], *waiting['end']})
            peak = max([int(np.sum((waiting['start'] <= t) & (t < waiting['end']))) for t in edges] or [0])
            assert peak == result.max_queue[r]


class TestDeviceTrace:
    def test_timeline_matches_totals(self):
        res = make_device().simulate(reps=3, seed=9, trace=3)
        for r in range(3):
            tl = res.timeline(r)
            assert durations(tl, 0, ['up']) == pytest.approx(res.total_uptime[r], rel=1e-12)
            assert durations(tl, 0, ['repair']) == pytest.approx(res.total_downtime[r], rel=1e-12)
            assert not np.any(tl['state'] == 'waiting')

    def test_parity_with_single_device_fleet(self):
        dev = make_device(T=1500.0).simulate(reps=5, seed=123, trace=5)
        fleet = Fleet(n_devices=1, n_teams=1)
        fleet.set_failure_dist('weibull_grp', 200.0, 1.8, 0.4)
        fleet.set_repair_dist('lognormal', 2.0, 0.4)
        fleet.set_mission_time(1500.0)
        fl = fleet.simulate(reps=5, seed=123, trace=5)
        np.testing.assert_array_equal(dev.event_log, fl.event_log)


class TestTraceArgument:
    @pytest.mark.parametrize('bad', [-1, 1.5, True, 'x', float('nan')])
    def test_rejects_invalid(self, bad):
        with pytest.raises(ValueError):
            make_device().simulate(reps=2, seed=1, trace=bad)

    def test_more_than_reps_records_all(self):
        res = make_fleet().simulate(reps=3, seed=1, trace=10)
        assert res.traced_reps == 3
        res.timeline(2)

    def test_untraced_replication_raises(self):
        res = make_fleet().simulate(reps=3, seed=1, trace=1)
        res.timeline(0)
        with pytest.raises(ValueError):
            res.timeline(1)
        with pytest.raises(ValueError):
            make_fleet().simulate(reps=2, seed=1).timeline(0)

    def test_traced_replication_without_events(self):
        device = SimpleDevice()
        device.set_failure_dist('exponential', 1e-9)
        device.set_repair_dist('exponential', 1.0)
        device.set_mission_time(10.0)
        res = device.simulate(reps=1, seed=0, trace=1)
        assert len(res.event_log) == 0
        tl = res.timeline(0)
        assert list(tl['state']) == ['up'] and tl['end'][0] == 10.0


class TestExport:
    def test_event_log_in_json_only_when_traced(self):
        traced = make_fleet().simulate(reps=2, seed=4, trace=1).to_dict()
        plain = make_fleet().simulate(reps=2, seed=4).to_dict()
        assert 'event_log' not in plain
        log = traced['event_log']
        assert log['columns'] == ['rep', 'entity', 'event', 'time'] and log['traced_reps'] == 1
        assert all(row[0] == 0 for row in log['rows'])
        json.dumps(traced, allow_nan=False)
