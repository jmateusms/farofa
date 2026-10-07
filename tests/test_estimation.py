import math

import numpy as np
import pytest

import farofa
from farofa.estimation import fit_power_law, fit_weibull_grp, laplace_trend_test


def _history(sampler_factory, n, seed):
    """Cumulative failure times of one system drawn from a farofa sampler."""
    sampler = sampler_factory()
    sampler.set_rng(np.random.default_rng(seed))
    sampler.reset()
    return np.cumsum([sampler() for _ in range(n)])


def _grp_loglik(times, end, a, b, q, kijima):
    """Direct log-likelihood in the original time units (no scaling)."""
    ll, v = 0.0, 0.0
    prev = 0.0
    for t in times:
        x = t - prev
        ll += math.log(b / a) + (b - 1) * math.log((v + x) / a) - ((v + x) / a) ** b + (v / a) ** b
        v = v + q * x if kijima == 1 else q * (v + x)
        prev = t
    c = end - prev
    return ll - ((v + c) / a) ** b + (v / a) ** b


def test_power_law_matches_crow_closed_form():
    times = np.array([12.0, 30.0, 41.0, 77.0, 90.0, 101.0, 117.0])
    fit = fit_power_law(times, end_time=130.0)
    beta = len(times) / np.sum(np.log(130.0 / times))
    lam = len(times) / 130.0 ** beta
    assert fit.b == pytest.approx(beta)
    assert fit.a == pytest.approx(lam ** (-1 / beta))
    assert fit.distribution() == ('weibull_min', fit.a, fit.b)
    assert fit.log_likelihood == pytest.approx(_grp_loglik(times, 130.0, fit.a, fit.b, 1.0, 1))
    assert not fit.failure_truncated


@pytest.mark.parametrize('end_time', [None, 130.0])
def test_grp_with_q_one_reproduces_power_law(end_time):
    times = np.array([12.0, 30.0, 41.0, 77.0, 90.0, 101.0, 117.0])
    pl = fit_power_law(times, end_time)
    grp = fit_weibull_grp(times, end_time, q=1.0)
    assert grp.b == pytest.approx(pl.b, rel=1e-6)
    assert grp.a == pytest.approx(pl.a, rel=1e-6)
    assert grp.log_likelihood == pytest.approx(pl.log_likelihood, rel=1e-9)
    assert grp.n_params == 2


def test_grp_with_q_zero_solves_weibull_renewal_score():
    rng = np.random.default_rng(3)
    gaps = 50.0 * rng.weibull(1.7, 200)
    fit = fit_weibull_grp(np.cumsum(gaps), q=0.0)
    b = fit.b
    score = 1 / b + np.mean(np.log(gaps)) - np.sum(gaps ** b * np.log(gaps)) / np.sum(gaps ** b)
    assert score == pytest.approx(0.0, abs=1e-6)
    assert fit.a == pytest.approx(np.mean(gaps ** b) ** (1 / b), rel=1e-6)


@pytest.mark.parametrize('kijima', [1, 2])
def test_reported_log_likelihood_is_the_unscaled_one(kijima):
    times = _history(lambda: farofa.weibull_grp(20.0, 2.2, 0.5), 40, seed=5)
    fit = fit_weibull_grp(times, end_time=times[-1] + 3.0, kijima=kijima)
    direct = _grp_loglik(times, times[-1] + 3.0, fit.a, fit.b, fit.q, kijima)
    assert fit.log_likelihood == pytest.approx(direct, rel=1e-9)


@pytest.mark.parametrize('factory, kijima', [
    (lambda: farofa.weibull_grp(1.0, 2.0, 0.3), 1),
    (lambda: farofa.weibull_grp2(1.0, 2.0, 0.3), 2),
])
def test_grp_recovers_simulated_parameters(factory, kijima):
    times = _history(factory, 1500, seed=11)
    fit = fit_weibull_grp(times, kijima=kijima)
    assert fit.b == pytest.approx(2.0, abs=0.2)
    assert fit.q == pytest.approx(0.3, abs=0.1)
    assert fit.distribution()[0] == ('weibull_grp' if kijima == 1 else 'weibull_grp2')
    assert fit.n_params == 3


def test_estimated_q_is_at_least_as_likely_as_its_extremes():
    times = _history(lambda: farofa.weibull_grp(10.0, 2.5, 0.4), 80, seed=2)
    best = fit_weibull_grp(times)
    for q in (0.0, 1.0):
        assert best.log_likelihood >= fit_weibull_grp(times, q=q).log_likelihood - 1e-9


def test_laplace_trend_test_detects_deterioration_only_when_present():
    hpp = np.cumsum(np.random.default_rng(1).exponential(10.0, 300))
    u, p = laplace_trend_test(hpp)
    assert p > 0.01
    worn = _history(lambda: farofa.weibull_min(100.0, 3.0), 60, seed=4)
    u, p = laplace_trend_test(worn)
    assert u > 3.0 and p < 1e-3


@pytest.mark.parametrize('times, end_time', [
    ([3.0, 2.0, 5.0], None),
    ([0.0, 2.0, 5.0], None),
    ([1.0, 1.0, 5.0], None),
    ([1.0, 2.0, 5.0], 4.0),
    ([1.0, 2.0, float('nan')], None),
    ([1.0, 2.0], None),
])
def test_invalid_records_are_rejected(times, end_time):
    with pytest.raises(ValueError):
        fit_weibull_grp(times, end_time)


def test_power_law_and_trend_test_accept_tied_records():
    times = [100.0, 250.0, 250.0, 400.0, 610.0]
    fit = fit_power_law(times, end_time=700.0)
    assert fit.b == pytest.approx(5 / np.sum(np.log(700.0 / np.array(times))))
    assert math.isfinite(laplace_trend_test(times, end_time=700.0)[0])
    with pytest.raises(ValueError, match='ties'):
        fit_weibull_grp(times, end_time=700.0)


def test_fit_feeds_a_simulation():
    times = _history(lambda: farofa.weibull_min(100.0, 2.0), 30, seed=8)
    fit = fit_power_law(times)
    device = farofa.SimpleDevice()
    device.set_failure_dist(*fit.distribution())
    device.set_repair_dist('exponential', 1e6)  # near-instant repair
    device.set_mission_time(fit.end_time)
    low, high = device.simulate(reps=2000, seed=1).failure_count_confidence_interval()
    # The MLE makes the fitted mean number of failures over the window equal n.
    assert low < 30 < high
