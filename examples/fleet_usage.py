"""
Fleet simulation example: 10 identical devices sharing a pool of maintenance teams.

Compares fleet availability and team utilization as the number of teams varies.
"""

import farofa
from time import time


def run(n_devices, n_teams, reps=200):
    fleet = farofa.Fleet(n_devices=n_devices, n_teams=n_teams)
    fleet.set_failure_dist('weibull_grp', 200.0, 1.8, 0.4)  # imperfect repair
    fleet.set_repair_dist('lognormal', 2.0, 0.4)
    fleet.set_mission_time(8760)  # 1 year

    start = time()
    result = fleet.simulate(reps=reps)
    elapsed = time() - start
    return result, elapsed


if __name__ == '__main__':
    n_devices = 10
    for n_teams in (1, 2, 5, 10):
        result, elapsed = run(n_devices, n_teams)
        print(f'--- {n_devices} devices, {n_teams} teams ({elapsed:.2f}s) ---')
        print(result)
        print()
