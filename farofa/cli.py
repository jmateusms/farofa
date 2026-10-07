"""Command line: ``farofa gui [--port N] [--host H] [--no-browser]``."""
import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='farofa',
        description='farofa: Monte Carlo simulation of repairable systems.')
    sub = parser.add_subparsers(dest='command')
    gui = sub.add_parser('gui', help='open the graphical interface in the browser',
                         description='Start the local graphical interface and open it in the browser.')
    gui.add_argument('--port', type=int, default=None,
                     help='port to listen on (default: 8765, or the next free one)')
    gui.add_argument('--host', default='127.0.0.1',
                     help='interface to bind (default: 127.0.0.1, this machine only)')
    gui.add_argument('--no-browser', action='store_true', help='do not open a browser window')
    args = parser.parse_args(argv)
    if args.command == 'gui':
        from .gui import serve
        return serve(host=args.host, port=args.port, open_browser=not args.no_browser)
    parser.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
