"""From published failure records to a simulation model.

Two main-propulsion diesel engines with real, published failure histories
(cumulative operating hours at each unscheduled maintenance action):

- USS Halfbeak: 71 failures, failure-truncated at 25,518 h. Ascher, H. and
  Feingold, H. (1984), Repairable Systems Reliability, Marcel Dekker.
- USS Grampus: 56 failures in the first 16,000 h. Lee, L. (1980), Testing
  adequacy of the Weibull and log linear rate models for a Poisson process,
  Technometrics 22(2), 195-199.

Values as distributed in the data sets ``halfbeak`` and ``grampus`` of the R
package SMRD, the companion of Meeker and Escobar (1998), Statistical Methods
for Reliability Data, converted from thousands of hours to hours.

The script tests each record for a trend, fits the power-law NHPP and the
Weibull GRP, traces the profile likelihood of the repair factor q, and feeds
the fitted model into a simulation. Run from the repository root:

    python3 examples/repairable_data_fit.py
"""

import numpy as np

import farofa

HALFBEAK = [
    1382, 2990, 4124, 6827, 7472, 7567, 8845, 9450, 9794, 10848, 11993, 12300,
    15413, 16497, 17352, 17632, 18122, 19067, 19172, 19299, 19360, 19686, 19940,
    19944, 20121, 20132, 20431, 20525, 21057, 21061, 21309, 21310, 21378, 21391,
    21456, 21461, 21603, 21658, 21688, 21750, 21815, 21820, 21822, 21888, 21930,
    21943, 21946, 22181, 22311, 22634, 22635, 22669, 22691, 22846, 22947, 23149,
    23305, 23491, 23526, 23774, 23791, 23822, 24006, 24286, 25000, 25010, 25048,
    25268, 25400, 25500, 25518,
]
GRAMPUS = [
    860, 1258, 1317, 1442, 1897, 2011, 2122, 2439, 3203, 3298, 3902, 3910, 4000,
    4247, 4411, 4456, 4517, 4899, 4910, 5676, 5755, 6137, 6221, 6311, 6613, 6975,
    7335, 8158, 8498, 8690, 9042, 9330, 9394, 9426, 9872, 10191, 11511, 11575,
    12100, 12126, 12368, 12681, 12795, 13399, 13668, 13780, 13877, 14007, 14028,
    14035, 14173, 14173, 14449, 14587, 14610, 15070,
]
GRAMPUS_END = 16000.0


def main():
    for name, times, end in [('Halfbeak', HALFBEAK, None), ('Grampus', GRAMPUS, GRAMPUS_END)]:
        u, p = farofa.laplace_trend_test(times, end_time=end)
        fit = farofa.fit_power_law(times, end_time=end)
        print(f'{name}: Laplace U = {u:.2f} (p = {p:.2g}), power-law beta = {fit.b:.3f}')

    # Halfbeak deteriorates: which repair model? (Grampus has a tie, which the
    # GRP likelihood cannot take; it shows no trend anyway.)
    models = {
        'renewal (q = 0)': farofa.fit_weibull_grp(HALFBEAK, q=0.0),
        'power law (q = 1)': farofa.fit_power_law(HALFBEAK),
        'GRP Kijima I': farofa.fit_weibull_grp(HALFBEAK, kijima=1),
        'GRP Kijima II': farofa.fit_weibull_grp(HALFBEAK, kijima=2),
    }
    for label, fit in models.items():
        print(f'  {label:18s} a = {fit.a:8.1f}  b = {fit.b:.3f}  q = {fit.q:.3f}  AIC = {fit.aic:.1f}')

    grp = models['GRP Kijima I']
    q_grid = np.linspace(0.0, 1.0, 101)
    profile = np.array([farofa.fit_weibull_grp(HALFBEAK, q=q).log_likelihood for q in q_grid])
    inside = q_grid[profile >= grp.log_likelihood - 1.92]  # 95% likelihood-ratio interval
    print(f'  q = {grp.q:.2f}, 95% profile-likelihood interval [{inside.min():.2f}, {inside.max():.2f}]')

    # The fitted model drives a simulation; near-instant repairs count failures
    # over operating time, so the expected count should be close to the 71 observed.
    engine = farofa.SimpleDevice()
    engine.set_failure_dist(*grp.distribution())
    engine.set_repair_dist('exponential', 1e6)
    engine.set_mission_time(grp.end_time)
    result = engine.simulate(reps=2000, seed=17)
    low, high = result.failure_count_confidence_interval()
    print(f'  simulated failures in {grp.end_time:.0f} h: {result.mean_failures:.1f} (95% CI {low:.1f}-{high:.1f}); observed 71')


if __name__ == '__main__':
    main()
