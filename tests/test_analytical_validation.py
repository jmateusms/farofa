"""Independent analytical-oracle checks for the simulation engines."""
import math

import numpy as np
import pytest

from farofa.device import SimpleDevice
from farofa.distributions import weibull_grp, weibull_grp2
from farofa.fleet import Fleet


def exp_exp_finite_horizon_availability(rate, repair_rate, horizon):
    """Time-average P(up) for a two-state CTMC starting operational."""
    total = rate + repair_rate
    return repair_rate / total + rate * (1.0 - math.exp(-total * horizon)) / (total * total * horizon)


def finite_fleet_markov_availability(n_devices, n_teams, rate, repair_rate, horizon):
    """Independent finite CTMC oracle, states = number of failed devices."""
    q = np.zeros((n_devices + 1, n_devices + 1))
    for down in range(n_devices + 1):
        if down < n_devices:
            q[down, down + 1] = (n_devices - down) * rate
        if down:
            q[down, down - 1] = min(down, n_teams) * repair_rate
        q[down, down] = -q[down].sum()
    # Spectral integral of exp(Qs). This is an oracle for the finite birth-
    # death CTMC, separate from the simulator's event queue. The zero mode is
    # handled by its limiting integral T rather than by a singular inverse Q.
    vals, vecs = np.linalg.eig(q)
    factors = np.array([
        horizon if abs(value) < 1e-12 else math.expm1(value * horizon) / value
        for value in vals
    ])
    integral = (vecs * factors) @ np.linalg.inv(vecs)
    initial = np.zeros(n_devices + 1)
    initial[0] = 1.0
    expected_down_time = initial @ integral @ np.arange(n_devices + 1)
    return 1.0 - expected_down_time / (n_devices * horizon)


def test_exp_exp_matches_exact_finite_horizon_transient_not_steady_state():
    rate, repair_rate, horizon = 0.4, 0.2, 1.5
    device = SimpleDevice()
    device.set_failure_dist('exponential', rate)
    device.set_repair_dist('exponential', repair_rate)
    device.set_mission_time(horizon)
    result = device.simulate(reps=30_000, seed=20260919)
    expected = exp_exp_finite_horizon_availability(rate, repair_rate, horizon)
    # Four estimated standard errors is intentionally conservative for a
    # seeded regression: a nominal 95% CI would make this test flaky by design.
    error = abs(result.availability - expected)
    four_se = 4.0 * result.availability_per_rep.std(ddof=1) / math.sqrt(result.reps)
    assert error <= four_se
    assert expected - repair_rate / (rate + repair_rate) > 0.1


@pytest.mark.parametrize('q', [0.0, 1.0])
def test_grp_types_are_identical_at_repair_extremes(q):
    left, right = weibull_grp(30.0, 2.5, q), weibull_grp2(30.0, 2.5, q)
    left.set_rng(np.random.default_rng(87))
    right.set_rng(np.random.default_rng(87))
    assert [left() for _ in range(1000)] == [right() for _ in range(1000)]


def test_grp_perfect_repair_is_weibull_renewal():
    # Samplers consume different NumPy transforms, so equality of random-bit
    # streams is not the claim. q=0 resets virtual age, giving the Weibull
    # renewal law; verify its independent first moment.
    grp = weibull_grp(30.0, 2.5, 0.0)
    grp.set_rng(np.random.default_rng(88))
    draws = np.array([grp() for _ in range(30_000)])
    expected = 30.0 * math.gamma(1.0 + 1.0 / 2.5)
    assert draws.mean() == pytest.approx(expected, rel=0.02)


def test_minimal_repair_grp_count_matches_power_law_nhpp_oracle():
    scale, shape, horizon = 100.0, 2.0, 100.0
    # The NHPP formula uses operational age. Draw the q=1 sampler directly
    # until that age reaches T, so repair downtime cannot alter the calendar.
    sampler = weibull_grp(scale, shape, 1.0)
    sampler.set_rng(np.random.default_rng(91))
    counts = []
    for _ in range(20_000):
        sampler.reset()
        age = 0.0
        count = 0
        while True:
            age += sampler()
            if age >= horizon:
                break
            count += 1
        counts.append(count)
    expected = (horizon / scale) ** shape
    counts = np.asarray(counts, dtype=float)
    four_se = 4.0 * counts.std(ddof=1) / math.sqrt(len(counts))
    assert abs(counts.mean() - expected) <= four_se


def test_shared_team_fleet_matches_finite_markov_oracle():
    n_devices, n_teams, rate, repair_rate, horizon = 3, 1, 0.2, 0.5, 8.0
    fleet = Fleet(n_devices=n_devices, n_teams=n_teams)
    fleet.set_failure_dist('exponential', rate)
    fleet.set_repair_dist('exponential', repair_rate)
    fleet.set_mission_time(horizon)
    result = fleet.simulate(reps=30_000, seed=20260919)
    expected = finite_fleet_markov_availability(n_devices, n_teams, rate, repair_rate, horizon)
    error = abs(result.fleet_availability - expected)
    four_se = 4.0 * result.availability_per_rep.std(ddof=1) / math.sqrt(result.reps)
    assert error <= four_se
