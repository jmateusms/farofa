"""Reproducibility tests (roadmap Phase 1 exit criteria).

A disclosed seed must reproduce a run bit-for-bit in the same environment,
and every device in a fleet must have an independent stream: the variate
sequence device d consumes depends only on the seed and d, never on fleet
size (SeedSequence.spawn children are a deterministic prefix). Full
trajectories are additionally fleet-size-invariant when there is no repair
queueing (n_teams >= n_devices) — with queueing, waits shift event times.
"""
import numpy as np

from farofa.device import SimpleDevice
from farofa.fleet import Fleet


def make_device(failure=('exponential', 0.001), repair=('exponential', 0.1), T=8760):
    device = SimpleDevice()
    device.set_failure_dist(*failure)
    device.set_repair_dist(*repair)
    device.set_mission_time(T)
    return device


def make_fleet(n, k, T=2000.0):
    fleet = Fleet(n_devices=n, n_teams=k)
    fleet.set_failure_dist('weibull_grp', 200.0, 1.8, 0.4)
    fleet.set_repair_dist('lognormal', 2.0, 0.4)
    fleet.set_mission_time(T)
    return fleet


class TestDeviceSeeding:
    def test_same_seed_bit_identical(self):
        r1 = make_device().simulate(reps=200, seed=42)
        r2 = make_device().simulate(reps=200, seed=42)
        np.testing.assert_array_equal(r1.failure_counts, r2.failure_counts)
        np.testing.assert_array_equal(r1.total_uptime, r2.total_uptime)
        np.testing.assert_array_equal(r1.total_downtime, r2.total_downtime)
        np.testing.assert_array_equal(
            np.concatenate(r1.uptimes), np.concatenate(r2.uptimes)
        )

    def test_reusing_the_same_device_object_is_reproducible(self):
        device = make_device()
        r1 = device.simulate(reps=100, seed=7)
        r2 = device.simulate(reps=100, seed=7)
        np.testing.assert_array_equal(r1.total_uptime, r2.total_uptime)

    def test_stateful_sampler_seeded_runs_identical(self):
        failure = ('weibull_grp2', 150.0, 2.5, 0.6)
        r1 = make_device(failure=failure).simulate(reps=100, seed=3)
        r2 = make_device(failure=failure).simulate(reps=100, seed=3)
        np.testing.assert_array_equal(r1.failure_counts, r2.failure_counts)
        np.testing.assert_array_equal(r1.total_uptime, r2.total_uptime)

    def test_different_seeds_differ(self):
        r1 = make_device().simulate(reps=50, seed=1)
        r2 = make_device().simulate(reps=50, seed=2)
        assert not np.array_equal(r1.total_uptime, r2.total_uptime)

    def test_unseeded_runs_differ(self):
        device = make_device()
        r1 = device.simulate(reps=50)
        r2 = device.simulate(reps=50)
        assert not np.array_equal(r1.total_uptime, r2.total_uptime)

    def test_seed_sequence_accepted(self):
        ss = np.random.SeedSequence(99)
        r1 = make_device().simulate(reps=50, seed=np.random.SeedSequence(99))
        r2 = make_device().simulate(reps=50, seed=ss)
        np.testing.assert_array_equal(r1.total_uptime, r2.total_uptime)

    def test_seed_sequence_instance_reuse_is_reproducible(self):
        # Regression: simulate() must not spawn from (and thereby mutate) the
        # caller's SeedSequence — reusing one instance must give identical runs.
        ss = np.random.SeedSequence(99)
        r1 = make_device().simulate(reps=50, seed=ss)
        r2 = make_device().simulate(reps=50, seed=ss)
        np.testing.assert_array_equal(r1.total_uptime, r2.total_uptime)
        np.testing.assert_array_equal(r1.failure_counts, r2.failure_counts)
        assert ss.n_children_spawned == 0  # caller's object left untouched

    def test_seed_sequence_reuse_fleet(self):
        ss = np.random.SeedSequence(7)
        r1 = make_fleet(4, 2).simulate(reps=20, seed=ss)
        r2 = make_fleet(4, 2).simulate(reps=20, seed=ss)
        np.testing.assert_array_equal(r1.device_uptime, r2.device_uptime)
        assert ss.n_children_spawned == 0


class TestFleetSeeding:
    def test_same_seed_bit_identical(self):
        r1 = make_fleet(5, 2).simulate(reps=50, seed=42)
        r2 = make_fleet(5, 2).simulate(reps=50, seed=42)
        np.testing.assert_array_equal(r1.failure_counts, r2.failure_counts)
        np.testing.assert_array_equal(r1.device_uptime, r2.device_uptime)
        np.testing.assert_array_equal(r1.busy_team_hours, r2.busy_team_hours)
        np.testing.assert_array_equal(r1.max_queue, r2.max_queue)

    def test_different_seeds_differ(self):
        r1 = make_fleet(5, 2).simulate(reps=20, seed=1)
        r2 = make_fleet(5, 2).simulate(reps=20, seed=2)
        assert not np.array_equal(r1.device_uptime, r2.device_uptime)

    def test_per_device_streams_independent_of_fleet_size(self):
        # With K=N (no queueing), device d's trajectory depends only on its own
        # streams — so growing the fleet must leave existing devices' results
        # bit-identical (spawn(2N) children are a deterministic prefix).
        r3 = make_fleet(3, 3).simulate(reps=30, seed=11)
        r5 = make_fleet(5, 5).simulate(reps=30, seed=11)
        np.testing.assert_array_equal(r3.failure_counts, r5.failure_counts[:, :3])
        np.testing.assert_array_equal(r3.device_uptime, r5.device_uptime[:, :3])
        np.testing.assert_array_equal(r3.device_downtime, r5.device_downtime[:, :3])


class TestCustomCallableSamplers:
    def test_plain_callable_without_set_rng_still_works(self):
        # User samplers that don't expose set_rng() are outside seed control
        # but must keep working.
        def constant_factory(value):
            def gen():
                return value
            return gen

        device = SimpleDevice()
        device.set_failure_dist(constant_factory, 30.0)
        device.set_repair_dist(constant_factory, 10.0)
        device.set_mission_time(100)
        result = device.simulate(reps=3, seed=1)
        # Deterministic path: fail at 30, repaired at 40, fail at 70, repaired
        # at 80, censored at 100 -> 2 failures, uptime 80, downtime 20.
        np.testing.assert_array_equal(result.failure_counts, [2, 2, 2])
        np.testing.assert_allclose(result.total_uptime, 80.0)
        np.testing.assert_allclose(result.total_downtime, 20.0)
