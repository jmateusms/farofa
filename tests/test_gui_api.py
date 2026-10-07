"""GUI logic (farofa.gui.api): scenarios validate through the engine, runs
match direct engine calls, and the estimation view reproduces the fits."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

import farofa
from farofa.distributions import DISTRIBUTIONS
from farofa.gui import api
from farofa.gui.datasets import GRAMPUS, GRAMPUS_END, HALFBEAK


def fleet_scenario(**over):
    sc = {
        'system': 'fleet', 'n_devices': 6, 'n_teams': 2,
        'failure': {'dist': 'weibull_grp', 'params': {'a': 200.0, 'b': 1.8, 'q': 0.4}},
        'repair': {'dist': 'lognormal', 'params': {'mu': 3.0, 'sigma': 0.5}},
        'mission_time': 2000.0, 'reps': 40, 'seed': 11, 'trace': 3,
    }
    sc.update(over)
    return sc


def device_scenario(**over):
    sc = {
        'system': 'device',
        'failure': {'dist': 'exponential', 'params': {'rate': 0.01}},
        'repair': {'dist': 'exponential', 'params': {'rate': 0.1}},
        'mission_time': 1000.0, 'reps': 200, 'seed': 5, 'trace': 2,
    }
    sc.update(over)
    return sc


def errors_by_field(scenario):
    out = api.validate(scenario)
    assert not out['ok']
    return {e['field']: e for e in out['errors']}


class TestMeta:
    def test_distributions_follow_the_engine(self):
        meta = api.meta()
        assert list(meta['distributions']) == list(DISTRIBUTIONS)
        assert meta['distributions']['weibull_grp']['params'] == ['a', 'b', 'q']
        assert meta['distributions']['gamma']['params'] == ['shape', 'scale']

    def test_datasets_match_the_example(self):
        path = Path(__file__).resolve().parents[1] / 'examples' / 'repairable_data_fit.py'
        spec = importlib.util.spec_from_file_location('repairable_data_fit', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert HALFBEAK == module.HALFBEAK
        assert GRAMPUS == module.GRAMPUS
        assert GRAMPUS_END == module.GRAMPUS_END


class TestValidation:
    def test_valid_scenario_is_normalized(self):
        out = api.validate(fleet_scenario(failure={'dist': 'weibull', 'params': [300, 1.5]}))
        assert out['ok']
        sc = out['scenario']
        assert sc['schema'] == api.SCENARIO_SCHEMA
        assert sc['failure'] == {'dist': 'weibull', 'params': {'a': 300.0, 'b': 1.5}}
        assert sc['n_devices'] == 6 and sc['n_teams'] == 2

    def test_engine_messages_reach_the_right_field(self):
        errs = errors_by_field(fleet_scenario(
            n_teams=0, mission_time=-1, reps=1.5, seed=-3,
            failure={'dist': 'weibull_grp', 'params': {'a': 100, 'b': 0, 'q': 0.5}},
            repair={'dist': 'weibull_grp2', 'params': {'a': 10, 'b': 1, 'q': 1.5}}))
        assert errs['n_teams']['message'] == 'n_teams must be a positive integer.'
        assert errs['mission_time']['message'] == 'Mission time must be finite and greater than 0.'
        assert errs['reps']['message'] == 'reps must be a positive integer.'
        assert errs['failure.b']['message'] == 'b must be greater than 0.'
        assert errs['repair.q']['message'] == 'q (repair effectiveness) must be between 0 and 1.'
        assert 'seed' in errs
        assert all(e['code'] is None for e in errs.values())  # all straight from the engine

    def test_distribution_level_message(self):
        errs = errors_by_field(device_scenario(repair={'dist': 'normal', 'params': {'mu': -100, 'sigma': 1}}))
        assert 'practically no positive mass' in errs['repair']['message']

    def test_gui_level_codes(self):
        errs = errors_by_field(device_scenario(
            failure={'dist': 'weibull', 'params': {'a': 'x'}}, trace=api.MAX_TRACE + 1, seed=1.5))
        assert errs['failure.a']['code'] == 'number'
        assert errs['failure.b']['code'] == 'missing'
        assert errs['trace']['code'] == 'trace_max'
        assert errs['seed']['code'] == 'seed_int'

    def test_unknown_distribution_and_system(self):
        errs = errors_by_field(device_scenario(system='plant', failure={'dist': 'cauchy', 'params': {}}))
        assert 'system' in errs
        assert errs['failure.dist']['message'].startswith("Unknown distribution 'cauchy'")

    def test_non_object(self):
        with pytest.raises(api.ScenarioError):
            api.build([1, 2])


class TestRuns:
    def test_fleet_run_matches_the_engine(self):
        payload, export = api.run_simulation(fleet_scenario())
        export = export()
        fleet = farofa.Fleet(n_devices=6, n_teams=2)
        fleet.set_failure_dist('weibull_grp', 200.0, 1.8, 0.4)
        fleet.set_repair_dist('lognormal', 3.0, 0.5)
        fleet.set_mission_time(2000.0)
        direct = fleet.simulate(reps=40, seed=11, trace=3)
        m = payload['metrics']
        assert m['availability']['value'] == pytest.approx(direct.fleet_availability, rel=0, abs=0)
        assert m['availability']['ci'] == list(direct.availability_confidence_interval())
        assert m['utilization']['ci'] == list(direct.server_utilization_confidence_interval())
        assert m['mean_wait']['value'] == direct.mean_wait_time
        assert m['max_queue']['value'] == direct.max_queue_observed
        assert payload['per_rep']['failures'] == direct.total_failures_per_rep.tolist()
        assert payload['per_device']['availability'] == direct.per_device_availability.tolist()
        expected = direct.to_dict()
        assert export['replications'] == expected['replications']
        assert export['event_log'] == expected['event_log']
        assert export['scenario']['seed'] == 11

    def test_traces_follow_the_timeline(self):
        payload, _ = api.run_simulation(fleet_scenario())
        model, kwargs, _ = api.build(fleet_scenario())
        result = model.simulate(reps=kwargs['reps'], seed=kwargs['seed'], trace=kwargs['trace'])
        assert len(payload['traces']) == 3
        for rep, tr in enumerate(payload['traces']):
            tl = result.timeline(rep)
            assert tr['start'] == tl['start'].tolist()
            assert [('up', 'waiting', 'repair')[s] for s in tr['state']] == tl['state'].tolist()
            log = result.event_log[(result.event_log['rep'] == rep) & (result.event_log['event'] == 'FAILURE')]
            assert tr['failure_time'] == log['time'].tolist()

    def test_device_run_and_empty_seed(self):
        payload, _ = api.run_simulation(device_scenario(seed=None))
        assert isinstance(payload['seed'], int)
        again, _ = api.run_simulation(device_scenario(seed=payload['seed']))
        assert again['per_rep'] == payload['per_rep']
        assert payload['system'] == 'device' and 'utilization' not in payload['metrics']

    def test_per_rep_arrays_are_capped(self, monkeypatch):
        monkeypatch.setattr(api, 'PER_REP_LIMIT', 50)
        payload, export = api.run_simulation(device_scenario(reps=120))
        assert payload['per_rep_shown'] == 50 and len(payload['per_rep']['availability']) == 50
        assert len(export()['replications']['availability']) == 120

    def test_progress_and_cancel(self):
        seen = []
        api.run_simulation(device_scenario(reps=10), progress=lambda d, n: seen.append((d, n)))
        assert seen[-1] == (10, 10)

    def test_ratio_interval(self):
        num = np.array([3.0, 5.0, 2.0, 6.0, 4.0])
        den = np.array([2.0, 3.0, 1.0, 4.0, 2.0])
        lo, hi = api.ratio_confidence_interval(num, den)
        ratio = num.sum() / den.sum()
        resid = num - ratio * den
        half = 1.959963984540054 * resid.std(ddof=1) / math.sqrt(5) / den.mean()
        assert lo == pytest.approx(ratio - half) and hi == pytest.approx(ratio + half)
        assert all(math.isnan(v) for v in api.ratio_confidence_interval([1.0], [1.0]))
        assert all(math.isnan(v) for v in api.ratio_confidence_interval([0.0, 0.0], [0.0, 0.0]))


class TestSweeps:
    def test_team_sweep_uses_common_random_numbers(self):
        out = api.run_sweep(fleet_scenario(trace=0), {'param': 'n_teams', 'values': [1, 3], 'reps': 30})
        assert [p['value'] for p in out['points']] == [1, 3]
        fleet = farofa.Fleet(n_devices=6, n_teams=3)
        fleet.set_failure_dist('weibull_grp', 200.0, 1.8, 0.4)
        fleet.set_repair_dist('lognormal', 3.0, 0.5)
        fleet.set_mission_time(2000.0)
        direct = fleet.simulate(reps=30, seed=11)
        assert out['points'][1]['metrics']['availability']['value'] == direct.fleet_availability
        assert out['points'][1]['n_teams'] == 3

    def test_distribution_parameter_sweep(self):
        out = api.run_sweep(fleet_scenario(), {'param': 'failure.q', 'values': [0.0, 1.0], 'reps': 10})
        assert [p['value'] for p in out['points']] == [0.0, 1.0]
        assert out['scenario']['failure']['params']['q'] == 0.4

    def test_progress_spans_all_points(self):
        seen = []
        api.run_sweep(fleet_scenario(), {'param': 'n_teams', 'values': [1, 2], 'reps': 5},
                      progress=lambda d, n: seen.append((d, n)))
        assert seen[0] == (1, 10) and seen[-1] == (10, 10)

    @pytest.mark.parametrize('sweep, code', [
        ({'param': 'nope', 'values': [1]}, 'sweep_param'),
        ({'param': 'n_teams', 'values': []}, 'sweep_values'),
        ({'param': 'n_teams', 'values': list(range(1, api.MAX_SWEEP_POINTS + 2))}, 'sweep_max'),
    ])
    def test_invalid_sweeps(self, sweep, code):
        with pytest.raises(api.ScenarioError) as exc:
            api.sweep_plan(fleet_scenario(), sweep)
        assert exc.value.errors[0]['code'] == code

    def test_invalid_point_reports_the_value(self):
        with pytest.raises(api.ScenarioError) as exc:
            api.sweep_plan(fleet_scenario(), {'param': 'failure.q', 'values': [0.5, 1.5]})
        err = exc.value.errors[0]
        assert err['value'] == 1.5
        assert err['message'] == 'q (repair effectiveness) must be between 0 and 1.'

    def test_device_cannot_sweep_teams(self):
        assert 'n_teams' not in api.sweep_fields(device_scenario())


class TestParseTimes:
    @pytest.mark.parametrize('text, values, skipped', [
        ('1\n2\n3.5\n', [1.0, 2.0, 3.5], 0),
        ('1, 2, 3', [1.0, 2.0, 3.0], 0),
        ('[1382, 2990,\n 4124]', [1382.0, 2990.0, 4124.0], 0),
        ('tempo\n1,5\n2,25', [1.0, 5.0, 2.0, 25.0], 1),
        ('tempo;\n1,5;\n2,25', [1.5, 2.25], 1),
        ('time\t\n10\t\n20,5', [10.0, 20.5], 1),
    ])
    def test_formats(self, text, values, skipped):
        assert api.parse_times(text) == (values, skipped)

    def test_errors(self):
        with pytest.raises(api.EstimateInputError) as exc:
            api.parse_times('1, 2, x, 4')
        assert exc.value.code == 'not_number' and exc.value.detail == 'x'
        with pytest.raises(api.EstimateInputError) as exc:
            api.parse_times('   ')
        assert exc.value.code == 'empty'
        with pytest.raises(api.EstimateInputError) as exc:
            api.parse_times('1, inf')
        assert exc.value.code == 'not_number'


@pytest.fixture(scope='module')
def halfbeak():
    return api.estimate(HALFBEAK)


class TestEstimate:
    def test_fits_match_the_library(self, halfbeak):
        by_key = {m['key']: m for m in halfbeak['models']}
        expected = {
            'power_law': farofa.fit_power_law(HALFBEAK),
            'grp1': farofa.fit_weibull_grp(HALFBEAK, kijima=1),
            'grp2': farofa.fit_weibull_grp(HALFBEAK, kijima=2),
            'renewal': farofa.fit_weibull_grp(HALFBEAK, q=0.0),
        }
        for key, fit in expected.items():
            m = by_key[key]
            assert (m['a'], m['b'], m['q'], m['aic']) == (fit.a, fit.b, fit.q, fit.aic)
            assert m['distribution'] == list(fit.distribution())
        assert halfbeak['best'] == min(expected, key=lambda k: expected[k].aic)
        u, p = farofa.laplace_trend_test(HALFBEAK)
        assert halfbeak['laplace'] == {'u': u, 'p': p}
        assert halfbeak['failure_truncated'] and halfbeak['end_time'] == HALFBEAK[-1]

    def test_curves(self, halfbeak):
        for m in halfbeak['models']:
            comp = m['compensator']
            # MLE with the scale profiled out: the fitted cumulative intensity
            # given the record ends exactly at the number of failures.
            assert comp['m'][-1] == pytest.approx(len(HALFBEAK), rel=1e-9)
            assert np.all(np.diff(comp['m']) >= -1e-9)
            mean = np.array(m['mean_function']['m'])
            assert mean[0] == 0 and np.all(np.diff(mean) >= -1e-12)
        pl = next(m for m in halfbeak['models'] if m['key'] == 'power_law')
        t = np.array(pl['mean_function']['t'])
        assert pl['mean_function']['m'] == pytest.approx((t / pl['a']) ** pl['b'])
        assert pl['compensator']['m'] == pytest.approx((np.array(pl['compensator']['t']) / pl['a']) ** pl['b'])

    def test_profile(self, halfbeak):
        prof = halfbeak['profile']
        g1 = prof['grp1']
        lo, hi = g1['interval']
        assert lo <= g1['q_hat'] <= hi
        assert max(r for r in g1['rel'] if r is not None) <= 1e-9
        q = np.array(prof['q'])
        k = int(np.argmin(np.abs(q - 0.5)))
        direct = farofa.fit_weibull_grp(HALFBEAK, q=float(q[k])).log_likelihood
        assert g1['ll'][k] == pytest.approx(direct)

    def test_ties_report_the_engine_message(self):
        out = api.estimate(GRAMPUS, end_time=GRAMPUS_END)
        by_key = {m['key']: m for m in out['models']}
        assert 'aic' in by_key['power_law']
        assert 'without ties' in by_key['grp1']['error']
        assert out['best'] == 'power_law'
        assert 'error' in out['profile']['grp1']

    def test_intervals_input(self):
        gaps = np.diff(HALFBEAK[:20], prepend=0).tolist()
        a = api.estimate(gaps, intervals=True, profile_points=5)
        b = api.estimate(HALFBEAK[:20], profile_points=5)
        assert a['times'] == b['times']
        assert a['models'][0]['aic'] == b['models'][0]['aic']

    def test_input_errors(self):
        with pytest.raises(api.EstimateInputError) as exc:
            api.estimate(HALFBEAK, end_time=100.0)
        assert exc.value.code == 'engine' and 'end_time' in str(exc.value)
        with pytest.raises(api.EstimateInputError) as exc:
            api.estimate([3.0, -1.0], intervals=True)
        assert exc.value.code == 'intervals_positive'
        with pytest.raises(api.EstimateInputError) as exc:
            api.estimate(HALFBEAK, end_time='late')
        assert exc.value.code == 'end_number'
