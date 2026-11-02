"""``python -m pypicocommands [SIM [variant]|serial]`` starts a console."""
import sys

from .picoscope import console

console(sys.argv[1:])
