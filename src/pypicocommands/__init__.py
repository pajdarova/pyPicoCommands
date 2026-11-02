"""pypicocommands - control PicoScope 2000/3000/4000/5000 series oscilloscopes
with short text commands.

    from pypicocommands import Picoscope

    ps = Picoscope()
    ps.cmd("OPEN; A ON; A RANGE 2")

See ``pypicocommands.picoscope`` for the command language and the notes on
each supported driver family.
"""
from .picoscope import ExceptionNotSupported, ExceptionPicoscope, Picoscope

__all__ = ["Picoscope", "ExceptionPicoscope", "ExceptionNotSupported"]
__version__ = "0.1.0"
