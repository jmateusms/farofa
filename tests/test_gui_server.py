"""GUI web server: static files, JSON endpoints, jobs, guards and the CLI."""
import json
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from farofa import cli
from farofa.gui import make_server
from farofa.gui.datasets import HALFBEAK
from farofa.gui.server import STATIC_DIR

SCENARIO = {
    'system': 'fleet', 'n_devices': 5, 'n_teams': 2,
    'failure': {'dist': 'exponential', 'params': {'rate': 0.01}},
    'repair': {'dist': 'exponential', 'params': {'rate': 0.1}},
    'mission_time': 1000, 'reps': 30, 'seed': 3, 'trace': 2,
}


@pytest.fixture(scope='module')
def server():
    httpd, state = make_server(port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{state.port}', state
    httpd.shutdown()
    httpd.server_close()


def request(url, body=None, headers=None, method=None):
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    req = urllib.request.Request(url, data=data, method=method, headers=dict({'Content-Type': 'application/json'}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()


def get_json(url, body=None, **kw):
    status, headers, raw = request(url, body, **kw)
    return status, json.loads(raw)


def wait_job(base, job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, st = get_json(f'{base}/api/jobs/{job_id}')
        assert status == 200
        if st['status'] != 'running':
            return st
        time.sleep(0.05)
    raise AssertionError('job did not finish')


class TestStatic:
    def test_index_and_modules(self, server):
        base, _ = server
        status, headers, raw = request(base + '/')
        assert status == 200 and headers['Content-Type'].startswith('text/html')
        html = raw.decode()
        assert 'type="module"' in html
        for ref in re.findall(r'(?:src|href)="/static/([^"]+)"', html):
            status, headers, _ = request(f'{base}/static/{ref}')
            assert status == 200, ref
        status, headers, _ = request(base + '/static/main.js')
        assert headers['Content-Type'].startswith('text/javascript')

    def test_every_module_import_resolves(self):
        for js in STATIC_DIR.glob('*.js'):
            for name in re.findall(r'from "\./([^"]+)"', js.read_text(encoding='utf-8')):
                assert (STATIC_DIR / name).is_file(), (js.name, name)

    def test_no_external_resources(self):
        for f in STATIC_DIR.iterdir():
            text = f.read_text(encoding='utf-8')
            assert not re.search(r'(?:src|href)=["\']https?://', text), f.name
            assert 'cdn.' not in text and '@import url(' not in text, f.name

    def test_no_traversal(self, server):
        base, _ = server
        for path in ['/static/../api.py', '/static/%2e%2e/server.py', '/static/nope.js']:
            status, _, _ = request(base + path)
            assert status == 404


class TestGuards:
    def test_foreign_host_is_refused(self, server):
        base, _ = server
        status, _, _ = request(base + '/api/meta', headers={'Host': 'attacker.example'})
        assert status == 403

    def test_cross_origin_post_is_refused(self, server):
        base, _ = server
        status, _, _ = request(base + '/api/validate', {'scenario': SCENARIO}, headers={'Origin': 'http://attacker.example'})
        assert status == 403
        status, _, _ = request(base + '/api/validate', {'scenario': SCENARIO}, headers={'Origin': base})
        assert status == 200

    def test_bad_json(self, server):
        base, _ = server
        assert request(base + '/api/validate', b'{nope')[0] == 400
        assert request(base + '/api/validate', b'{"scenario": NaN}')[0] == 400
        assert request(base + '/api/simulate', {'scenario': 3})[0] == 400


class TestApi:
    def test_meta(self, server):
        base, _ = server
        status, meta = get_json(base + '/api/meta')
        assert status == 200
        assert 'weibull_grp2' in meta['distributions']
        assert meta['datasets'][0]['times'] == HALFBEAK

    def test_validate(self, server):
        base, _ = server
        status, out = get_json(base + '/api/validate', {'scenario': SCENARIO})
        assert status == 200 and out['ok']
        status, out = get_json(base + '/api/validate', {'scenario': dict(SCENARIO, n_devices=-2)})
        assert status == 200 and not out['ok']
        assert out['errors'][0] == {'field': 'n_devices', 'message': 'n_devices must be a positive integer.', 'code': None}

    def test_simulate_job_and_export(self, server):
        base, _ = server
        status, job = get_json(base + '/api/simulate', {'scenario': SCENARIO})
        assert status == 202 and job['status'] in ('running', 'done')
        st = wait_job(base, job['id'])
        assert st['status'] == 'done' and st['done'] == st['total'] == 30
        result = st['result']
        assert result['reps'] == 30 and len(result['traces']) == 2
        status, headers, raw = request(f"{base}/api/jobs/{job['id']}/export")
        assert status == 200 and 'attachment' in headers['Content-Disposition']
        export = json.loads(raw)
        assert export['result_kind'] == 'fleet' and export['scenario']['seed'] == 3
        assert export['replications']['availability'] == result['per_rep']['availability']

    def test_invalid_scenario_is_rejected_before_running(self, server):
        base, _ = server
        status, out = get_json(base + '/api/simulate', {'scenario': dict(SCENARIO, mission_time=0)})
        assert status == 422
        assert out['errors'][0]['field'] == 'mission_time'

    def test_cancel(self, server):
        base, _ = server
        status, job = get_json(base + '/api/simulate', {'scenario': dict(SCENARIO, reps=500000, trace=0)})
        assert status == 202
        time.sleep(0.2)
        status, _ = get_json(f"{base}/api/jobs/{job['id']}/cancel", {})
        assert status == 200
        st = wait_job(base, job['id'])
        assert st['status'] == 'cancelled' and 0 < st['done'] < 500000
        assert request(f"{base}/api/jobs/{job['id']}/export")[0] == 409

    def test_unknown_job(self, server):
        base, _ = server
        assert request(base + '/api/jobs/0123456789ab')[0] == 404
        assert request(base + '/api/jobs/0123456789ab/cancel', {})[0] == 404

    def test_sweep(self, server):
        base, _ = server
        status, job = get_json(base + '/api/sweep', {'scenario': SCENARIO, 'sweep': {'param': 'n_teams', 'values': [1, 2, 3], 'reps': 10}})
        assert status == 202
        st = wait_job(base, job['id'])
        assert st['status'] == 'done' and st['total'] == 30
        assert [p['value'] for p in st['result']['points']] == [1, 2, 3]
        status, out = get_json(base + '/api/sweep', {'scenario': SCENARIO, 'sweep': {'param': 'failure.rate', 'values': [0.01, -1]}})
        assert status == 422 and out['errors'][0]['value'] == -1

    def test_estimate(self, server):
        base, _ = server
        status, out = get_json(base + '/api/estimate', {'text': 'hours\n' + '\n'.join(map(str, HALFBEAK))})
        assert status == 200
        assert out['n'] == 71 and out['skipped'] == 1 and out['best'] == 'grp1'
        status, out = get_json(base + '/api/estimate', {'text': '1, 2, oops'})
        assert status == 422 and out['code'] == 'not_number' and out['detail'] == 'oops'
        status, out = get_json(base + '/api/estimate', {'times': HALFBEAK, 'end_time': 10})
        assert status == 422 and out['code'] == 'engine'


class TestCli:
    def test_help_and_no_command(self, capsys):
        with pytest.raises(SystemExit) as exc:
            cli.main(['gui', '--help'])
        assert exc.value.code == 0
        assert '--no-browser' in capsys.readouterr().out
        assert cli.main([]) == 2

    def test_python_m_farofa_gui_serves(self):
        proc = subprocess.Popen([sys.executable, '-m', 'farofa', 'gui', '--port', '0', '--no-browser'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                cwd=Path(__file__).resolve().parents[1])
        try:
            line = proc.stdout.readline()
            url = re.search(r'http://127\.0\.0\.1:\d+/', line).group(0)
            status, headers, _ = request(url + 'api/meta')
            assert status == 200
        finally:
            proc.terminate()
            proc.wait(timeout=10)


def test_i18n_dictionary_covers_every_key():
    """Every key the page asks for exists in both languages."""
    src = (STATIC_DIR / 'i18n.js').read_text(encoding='utf-8')
    entries = dict(re.findall(r'^\s*"([^"]+)":\s*(\[.*?\]),?\s*$', src, re.M | re.S))
    defined = set(re.findall(r'^\s*"([^"]+)":\s*\[', src, re.M))
    used = set()
    for js in STATIC_DIR.glob('*.js'):
        used |= set(re.findall(r'\bt\("([^"]+)"', js.read_text(encoding='utf-8')))
    used |= set(re.findall(r'data-i18n(?:-[a-z-]+)?="([^"]+)"', (STATIC_DIR / 'index.html').read_text(encoding='utf-8')))
    assert not sorted(used - defined)
    for key in defined:  # pt and en present for one-line entries
        if key in entries:
            assert entries[key].count('"') >= 4, key
