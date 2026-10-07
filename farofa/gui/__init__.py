"""Local graphical interface: ``farofa gui`` or ``python -m farofa gui``.

A standard-library HTTP server (:mod:`farofa.gui.server`) serves a static
page and a JSON API built on the public engine (:mod:`farofa.gui.api`).
No extra dependencies, no network access: everything runs on this machine.
"""
from .server import DEFAULT_PORT, make_server, serve

__all__ = ['DEFAULT_PORT', 'make_server', 'serve']
