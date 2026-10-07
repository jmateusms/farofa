"""Local web server of the farofa GUI (standard library only).

Serves the page from ``farofa/gui/static`` and a small JSON API:

========================  =====================================================
``GET  /api/meta``         distributions, limits, data sets
``POST /api/validate``     check a scenario with the engine's own validators
``POST /api/simulate``     start a run in a worker thread, returns a job
``POST /api/sweep``        start a one-parameter sweep, returns a job
``GET  /api/jobs/<id>``    progress, then the result
``POST /api/jobs/<id>/cancel``
``GET  /api/jobs/<id>/export``  the engine's ``to_dict()`` as a JSON download
``POST /api/estimate``     trend test, fits, curves and q profiles
========================  =====================================================

Binds 127.0.0.1 by default and answers only requests addressed to that host
name (a guard against DNS rebinding); cross-site POSTs are refused.
"""
from __future__ import annotations

import errno
import json
import mimetypes
import re
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote, urlsplit

from . import api
from .jobs import JobManager

STATIC_DIR = Path(__file__).with_name('static')
DEFAULT_PORT = 8765
MAX_BODY = 8 * 1024 * 1024
LOOPBACK = ('127.0.0.1', 'localhost', '::1')
_JOB = re.compile(r'^/api/jobs/([0-9a-f]{12})(/cancel|/export)?$')
_TYPES = {'.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml',
          '.json': 'application/json', '.png': 'image/png', '.ico': 'image/x-icon'}


class BadRequest(Exception):
    def __init__(self, code: int, payload: Dict[str, Any]):
        super().__init__(payload.get('message', ''))
        self.code = code
        self.payload = payload


def _reject_constant(name: str) -> Any:
    raise ValueError(f'{name} is not a valid JSON number')


def static_file(name: str) -> Optional[Path]:
    """Resolve ``name`` inside the static directory (no path traversal)."""
    base = STATIC_DIR.resolve()
    target = (base / name).resolve()
    if base in target.parents and target.is_file():
        return target
    return None


class GuiState:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.jobs = JobManager()

    def allowed_hosts(self):
        """Host headers accepted on a loopback binding; ``None`` (no check)
        when the user chose to bind another interface."""
        if self.host not in LOOPBACK:
            return None
        out = set()
        for name in LOOPBACK:
            shown = f'[{name}]' if ':' in name else name
            out.update({shown, f'{shown}:{self.port}'})
        return out


def build_handler(state: GuiState) -> type:
    class Handler(BaseHTTPRequestHandler):
        server_version = 'farofa-gui'
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            pass

        # -- responses ------------------------------------------------------
        def send_bytes(self, code: int, body: bytes, content_type: str,
                       headers: Optional[Dict[str, str]] = None) -> None:
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def send_json(self, code: int, obj: Any, headers: Optional[Dict[str, str]] = None) -> None:
            body = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_bytes(code, body, 'application/json; charset=utf-8', headers)

        def send_static(self, name: str) -> None:
            target = static_file(name)
            if target is None:
                self.send_json(404, {'message': 'not found'})
                return
            ctype = _TYPES.get(target.suffix) or mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            if ctype.startswith('text/') or ctype.endswith('json') or ctype.endswith('xml'):
                ctype += '; charset=utf-8'
            self.send_bytes(200, target.read_bytes(), ctype)

        # -- guards ---------------------------------------------------------
        def host_ok(self) -> bool:
            allowed = state.allowed_hosts()
            host = (self.headers.get('Host') or '').strip().lower()
            if allowed is not None and host not in allowed:
                self.send_json(403, {'message': 'unexpected Host header'})
                return False
            return True

        def origin_ok(self) -> bool:
            origin = self.headers.get('Origin')
            if origin is None:
                return True
            if urlsplit(origin).netloc.lower() == (self.headers.get('Host') or '').strip().lower():
                return True
            self.send_json(403, {'message': 'cross-origin request refused'})
            return False

        def body_json(self) -> Any:
            try:
                length = int(self.headers.get('Content-Length') or 0)
            except ValueError:
                raise BadRequest(400, {'message': 'bad Content-Length'})
            if length > MAX_BODY:
                raise BadRequest(413, {'message': 'request body too large'})
            raw = self.rfile.read(length) if length > 0 else b''
            if not raw:
                return {}
            try:
                return json.loads(raw.decode('utf-8'), parse_constant=_reject_constant)
            except (UnicodeDecodeError, ValueError) as exc:
                raise BadRequest(400, {'message': f'invalid JSON: {exc}'})

        # -- routing --------------------------------------------------------
        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def do_GET(self) -> None:  # noqa: N802
            if not self.host_ok():
                return
            path = urlsplit(self.path).path
            try:
                if path in ('/', '/index.html'):
                    self.send_static('index.html')
                elif path.startswith('/static/'):
                    self.send_static(unquote(path[len('/static/'):]))
                elif path == '/api/meta':
                    self.send_json(200, api.meta())
                elif _JOB.match(path):
                    self.job_get(*_JOB.match(path).groups())
                else:
                    self.send_json(404, {'message': 'not found'})
            except Exception as exc:  # pragma: no cover - defensive
                traceback.print_exc()
                self.send_json(500, {'message': f'{type(exc).__name__}: {exc}'})

        def do_POST(self) -> None:  # noqa: N802
            if not self.host_ok() or not self.origin_ok():
                return
            path = urlsplit(self.path).path
            try:
                body = self.body_json()
                if path == '/api/validate':
                    self.send_json(200, api.validate(body.get('scenario') if isinstance(body, dict) else None))
                elif path == '/api/simulate':
                    scenario = self.object(body, 'scenario')
                    api.build(scenario)  # reject an invalid scenario before starting a thread
                    job = state.jobs.start('simulate', lambda j: api.run_simulation(scenario, j.progress))
                    self.send_json(202, job.status_dict())
                elif path == '/api/sweep':
                    scenario = self.object(body, 'scenario')
                    sweep = self.object(body, 'sweep')
                    api.sweep_plan(scenario, sweep)
                    job = state.jobs.start('sweep', lambda j: api.run_sweep(scenario, sweep, j.progress))
                    self.send_json(202, job.status_dict())
                elif path == '/api/estimate':
                    self.send_json(200, self.estimate(body))
                elif _JOB.match(path) and _JOB.match(path).group(2) == '/cancel':
                    job = state.jobs.get(_JOB.match(path).group(1))
                    if job is None:
                        self.send_json(404, {'message': 'no such job'})
                    else:
                        job.cancel()
                        self.send_json(200, job.status_dict(with_result=False))
                else:
                    self.send_json(404, {'message': 'not found'})
            except BadRequest as exc:
                self.send_json(exc.code, exc.payload)
            except api.ScenarioError as exc:
                self.send_json(422, {'message': str(exc), 'errors': exc.errors})
            except api.EstimateInputError as exc:
                self.send_json(422, {'message': str(exc), 'code': exc.code, 'detail': exc.detail})
            except Exception as exc:  # pragma: no cover - defensive
                traceback.print_exc()
                self.send_json(500, {'message': f'{type(exc).__name__}: {exc}'})

        # -- handlers -------------------------------------------------------
        @staticmethod
        def object(body: Any, key: str) -> Dict[str, Any]:
            value = body.get(key) if isinstance(body, dict) else None
            if not isinstance(value, dict):
                raise BadRequest(400, {'message': f'{key} must be a JSON object'})
            return value

        def estimate(self, body: Any) -> Dict[str, Any]:
            if not isinstance(body, dict):
                raise BadRequest(400, {'message': 'body must be a JSON object'})
            skipped = 0
            if isinstance(body.get('text'), str):
                times, skipped = api.parse_times(body['text'])
            else:
                times = body.get('times')
                if not isinstance(times, list):
                    raise api.EstimateInputError('empty', 'no failure times given')
            out = api.estimate(times, end_time=body.get('end_time'), intervals=bool(body.get('intervals')))
            out['skipped'] = skipped
            return out

        def job_get(self, job_id: str, action: Optional[str]) -> None:
            job = state.jobs.get(job_id)
            if job is None:
                self.send_json(404, {'message': 'no such job'})
            elif action == '/export':
                if job.status != 'done' or job.export is None:
                    self.send_json(409, {'message': 'nothing to export for this job'})
                else:
                    data = job.export() if callable(job.export) else job.export
                    self.send_json(200, data, {
                        'Content-Disposition': f'attachment; filename="farofa-result-{job.id}.json"'})
            elif action is None:
                self.send_json(200, job.status_dict())
            else:
                self.send_json(405, {'message': 'use POST'})

    return Handler


def make_server(host: str = '127.0.0.1', port: int = DEFAULT_PORT,
                fallback: int = 0) -> Tuple[ThreadingHTTPServer, GuiState]:
    """Create the server without serving (used by tests). When ``port`` is
    taken, try the next ``fallback`` ports; ``port=0`` picks a free one."""
    last_error: Optional[OSError] = None
    for candidate in range(port, port + fallback + 1) if port else [0]:
        state = GuiState(host, candidate)
        try:
            httpd = ThreadingHTTPServer((host, candidate), build_handler(state))
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
            last_error = exc
            continue
        httpd.daemon_threads = True
        state.port = httpd.server_address[1]
        return httpd, state
    raise last_error  # type: ignore[misc]


def serve(host: str = '127.0.0.1', port: Optional[int] = None, open_browser: bool = True) -> int:
    """Run the GUI until Ctrl+C."""
    explicit = port is not None
    httpd, state = make_server(host, DEFAULT_PORT if port is None else port, fallback=0 if explicit else 20)
    shown = f'[{host}]' if ':' in host else host
    url = f'http://{"127.0.0.1" if host in ("", "0.0.0.0") else shown}:{state.port}/'
    print(f'farofa GUI: {url}', flush=True)
    print('Press Ctrl+C to stop.', flush=True)
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nstopping...')
    finally:
        state.jobs.cancel_all()
        httpd.server_close()
    return 0
