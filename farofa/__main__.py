"""``python -m farofa gui``: same as the ``farofa`` command."""
import sys

from .cli import main

sys.exit(main())
