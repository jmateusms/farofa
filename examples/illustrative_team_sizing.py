"""Reproducible *illustrative* maintenance-team sizing experiment.

This is a teaching/example scenario, not a calibrated engineering study. The
rates, fleet size, horizon and target are deliberately synthetic. Do not use
the printed comparison to choose a real staffing level: calibrate a model from
domain data, justify its assumptions, and assess model uncertainty first.

Run from the repository root:

    python3 examples/illustrative_team_sizing.py

It writes ``illustrative_team_sizing_results.json`` with assumptions, seed,
replication outcomes and normal-approximation Monte Carlo intervals.
"""

import json
from pathlib import Path

import farofa


SEED = 20260919
REPLICATIONS = 2_000
MISSION_HOURS = 1_000.0
N_DEVICES = 8
TEAM_OPTIONS = (1, 2, 3)

# Deliberately synthetic, in units of hours. These are scenario inputs only.
FAILURE_RATE_PER_HOUR = 1 / 300
REPAIR_RATE_PER_HOUR = 1 / 24
CONFIDENCE = 0.95
OUTPUT = Path('illustrative_team_sizing_results.json')


def run_case(n_teams):
    fleet = farofa.Fleet(n_devices=N_DEVICES, n_teams=n_teams)
    fleet.set_failure_dist('exponential', FAILURE_RATE_PER_HOUR)
    fleet.set_repair_dist('exponential', REPAIR_RATE_PER_HOUR)
    fleet.set_mission_time(MISSION_HOURS)
    # A deterministic derived seed makes each row independently reproducible.
    return fleet.simulate(reps=REPLICATIONS, seed=SEED + n_teams)


def main():
    cases = {}
    for n_teams in TEAM_OPTIONS:
        result = run_case(n_teams)
        availability_ci = result.availability_confidence_interval(CONFIDENCE)
        utilization_ci = result.server_utilization_confidence_interval(CONFIDENCE)
        print(
            f'K={n_teams}: availability={result.fleet_availability:.5f} '
            f'CI{CONFIDENCE:.0%}=[{availability_ci[0]:.5f}, {availability_ci[1]:.5f}], '
            f'utilization={result.server_utilization:.5f} '
            f'CI{CONFIDENCE:.0%}=[{utilization_ci[0]:.5f}, {utilization_ci[1]:.5f}]'
        )
        cases[str(n_teams)] = result.to_dict(confidence=CONFIDENCE)

    payload = {
        'schema_version': 1,
        'study_kind': 'illustrative_team_sizing',
        'warning': 'Synthetic scenario only; not a recommendation for real team sizing.',
        'assumptions': {
            'fleet_is_homogeneous': True,
            'queue_discipline': 'FIFO',
            'failure_distribution': {'name': 'exponential', 'rate_per_hour': FAILURE_RATE_PER_HOUR},
            'repair_distribution': {'name': 'exponential', 'rate_per_hour': REPAIR_RATE_PER_HOUR},
            'mission_hours': MISSION_HOURS,
            'n_devices': N_DEVICES,
            'team_options': list(TEAM_OPTIONS),
            'finite_horizon_censoring': '[0, T)',
        },
        'reproducibility': {
            'base_seed': SEED,
            'seed_for_team_count': 'base_seed + n_teams',
            'replications_per_case': REPLICATIONS,
            'confidence': CONFIDENCE,
            'rng_contract': 'PCG64 streams via SeedSequence; same environment required for bit identity.',
        },
        'cases': cases,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Wrote {OUTPUT}')


if __name__ == '__main__':
    main()
