# *****************************************************************************
# Independent module for PicoScope oscilloscopes driven through pyPicoSDK
# (Pico Technology's official Python package) by short text commands.
# *****************************************************************************
"""
pypicocommands.picoscope - text-command interface to PicoScope 2000, 3000, 4000
and 5000 series oscilloscopes.

Overview
========
One module for several oscilloscope families (class ``Picoscope``).
``OPEN`` finds the connected instrument,
loads the driver of its series, reads the model (VARIANT) and from then on
the commands the model cannot do fail with ``ExceptionNotSupported``.

    from pypicocommands import Picoscope

    ps = Picoscope()
    ps.cmd("OPEN; A ON; A RANGE 2; A COUPLING DC; B OFF")
    ps.cmd("OSC INTERVAL 10n; OSC PRETRIGGER 200; OSC POSTTRIGGER 2000; OSC RECORDS 50")
    ps.cmd("TRG EDGE A RISING 0.5; TRG AUTO 100m")
    ps.cmd("RUN")
    ps.cmd("WAIT 5")               # -> "READY", "TIMEOUT" or "ABORTED"
    volts = ps.get_float("A")      # ndarray (records, samples) in volts
    t = ps.get_time()              # ndarray (samples,) in seconds, 0 = trigger
    ps.cmd("CLOSE")

``OPEN SIM [variant]`` opens a simulated instrument (5443D, 2408B, 2204A,
3404D MSO, 3206D or 4824A) that needs neither the hardware nor a driver; it
is used by the unit tests.

Supported oscilloscope families
===============================
==============  ========  ======================================================
series          driver    notes
==============  ========  ======================================================
PicoScope 2000  ps2000a   2000A/B, e.g. 2408B. NOT TESTED on hardware
PicoScope 3000  ps3000a   3000A/B/D (and MSO). NOT TESTED on hardware
PicoScope 4000  ps4000a   4000A, e.g. 4824A (8 channels A-H). NOT TESTED
PicoScope 5000  ps5000a   5000A/B/D, e.g. 5443D. Tested on a 5443D
==============  ========  ======================================================

The 3000E and 5000E series (driver psospa), the 6000 series, the old
ps2000/ps3000/ps4000/ps5000 drivers and the 4444 (selectable resolution in
ps4000a) are not supported.

The drivers are loaded directly through ctypes (no pyPicoSDK and no
picosdk-python-wrappers needed): the PicoSDK or PicoScope 7 installation is
searched (``PICO_SDK_DIR`` may name the folder with the DLLs). The function
prototypes are taken from the driver headers ``ps2000aApi.h`` ...
``ps5000aApi.h``.

How the instrument is found and what it can do
==============================================
* ``OPEN`` asks each driver for its connected units (ps5000a, ps4000a,
  ps3000a, ps2000a in this order, ``EnumerateUnits``) and opens the first
  one; ``OPEN <serial>`` opens that serial number, ``OPEN PS3000A``
  restricts the search to one driver. ``DEVICES?`` lists what is connected.
* The VARIANT string tells the model: the second digit is the number of
  analog channels (2408B 4, 4824A 8), "MSO" marks digital inputs.
* Static differences between the series (known from the API) are checked
  by the module: selectable resolution only in ps5000a, pulse-width trigger
  not in ps4000a, ``TRG WITHINPRE`` / ``TRG EDGEDETECT`` only in ps5000a, digital
  inputs only on MSO models, trigger information only in ps3000a / ps5000a.
* Differences that depend on the model (input ranges, bandwidth limiter,
  ETS, signal generator, coupling, offset) are decided by the driver: its
  "not supported" statuses (``PICO_NOT_SUPPORTED_BY_THIS_DEVICE``,
  ``PICO_INVALID_VOLTAGE_RANGE`` ...) become ``ExceptionNotSupported``.
  ``CAPS?`` summarizes the model.
* In ``strict=False`` mode a refused command returns
  ``ERR <command>: Not supported: <reason>``.

Differences that matter in use
==============================
* Timebase: the module does not compute it from formulas. It finds the
  largest timebase whose interval does not exceed the request with
  ``GetTimebase2`` (ps5000a starts from ``GetMinimumTimebaseStateless``, the
  other drivers from the first timebase that ``GetTimebase2`` accepts).
  ``OSC TBINDEX <n>`` sets any index directly.
* Resolution: ps5000a ``OSC BITS`` 8-16; ps2000a/ps3000a are 8-bit, ps4000a
  12-bit (``OSC BITS`` then only accepts that value, ``OSC BITS?`` returns it).
* Auto trigger: ps5000a counts microseconds, the other drivers milliseconds
  (``TRG AUTO`` is rounded up to a whole millisecond there).
* Input ranges: the ``X RANGE`` request is rounded up to the next range the
  driver knows (10 mV ... 200 V); a range the model does not have is
  refused by the driver as not supported.
* The signal generator of ps2000a/ps3000a/ps4000a models and the AWG dwell
  time unit are NOT TESTED (VERIFY in HW_TEST_PLAN.md).

Why the driver functions are called directly
============================================
The module binds the driver functions with ``ctypes`` using its own function
objects (``_FuncPtr`` of the loaded library) and argument types from the
headers. Reasons: one code path for four driver families that differ in a
few arguments (oversample, resolution, trigger functions), no dependency on
the wrappers' declarations (the picosdk wrapper declares
``ps5000aSetAutoTriggerMicroSeconds`` with a 32-bit argument), and the
text interface must report an error and continue (an invalid timebase is a
normal answer while the timebase is searched) - pyPicoSDK's call wrapper
closes the unit on most errors.

Command syntax
==============
* One string may carry several commands separated by ``;`` or new lines.
  They are executed from left to right.
* Keywords are case insensitive (``a range 2`` == ``A RANGE 2``).
* A query ends with ``?`` (``A RANGE?``, ``OSC INTERVAL?``); summary queries
  (``A?``, ``TRG?``, ``GEN?``, ``OSC?``) return ``KEY=value`` pairs.
* Numbers accept an SI prefix and an optional unit. The unit is ignored
  (but must fit the quantity if written), the prefix is honoured:

  - volts and seconds: ``p n u µ m``; the letter case does not matter and
    ``M`` also means milli (there are no megavolts or megaseconds here):
    ``500m`` = ``500mV`` = ``500MV`` = 0.5 V, ``1us`` = ``1US`` = 1 µs;
  - frequency: ``m k M G`` with ``m`` = milli and ``M`` = mega (case
    matters): ``100mHz``, ``10kHz``, ``1MHz``;
  - counts (samples, records, segments, ...): ``k M G``, ``M`` = mega:
    ``10k``, ``2M``;
  - exponent notation always works: ``2.5e-6``, ``1E3Hz``.
* Setting commands return ``OK``. Queries return only the value. Responses of
  several queries in one string are joined by ``"; "`` in the order of the
  queries, e.g. ``"A RANGE?; OSC BITS?"`` -> ``"2; 12"``.
* An invalid command raises ``ExceptionPicoscope`` (default, ``strict=True``).
  With ``Picoscope(strict=False)`` the response is ``"ERR <reason>"``
  instead, which suits a text link (socket, serial line). Commands preceding
  the failing one in the same string stay executed; the rest is skipped.
* Settings may be entered before ``OPEN``; they are stored and sent to the
  instrument when it is opened. With an open instrument, channel, resolution
  and generator settings are sent immediately (errors appear at once), the
  trigger, timebase and memory segmentation are sent by ``ARM``/``RUN``
  because they depend on all other settings.

The full command list is printed by ``HELP?`` (or ``help()``) and is kept in
``_HELP`` at the end of this file.

Interrupting long operations
============================
* ``RUN`` returns immediately; the capture runs in the instrument.
* ``WAIT [timeout]`` polls ``ps5000aIsReady`` itself (pyPicoSDK's
  ``is_ready()`` would block forever). It returns ``ABORTED`` when ``STOP``
  is called from another thread (e.g. a GUI button), ``TIMEOUT`` when the
  timeout expires (the capture keeps running, WAIT may be called again),
  and it stops the instrument on Ctrl+C (KeyboardInterrupt is re-raised).
* ``STOP`` calls ``ps5000aStop``. It is safe to call from any thread at any
  time; it does not wait for the internal lock. After a rapid block run is
  stopped, the already completed records stay readable (``CAPTURES?``).
* Streaming runs in a background thread and ends with ``STOP`` (or autostop).
* The data transfer (first ``get_*`` call after a capture) is interruptible
  by ``STOP``: a single block uses ``ps5000aGetValuesAsync`` (aborted by
  ``ps5000aStop``), rapid block data are read in chunks of segments and the
  abort request is checked between the chunks.
* ``OPEN`` cannot be interrupted (driver limitation; it takes a few seconds).
* ``start(callback)`` registers the driver's ``ps5000aBlockReady`` callback
  as an alternative to ``WAIT`` polling.

Decisions and notes
===================
* Errors raise ``ExceptionPicoscope`` by default (``strict=False`` gives text).
* Query responses carry the value only (no echo of the command).
* ``cmd()`` is the main entry point; ``set()`` is an alias.
* ``X FACTOR <n>`` multiplies the volts returned by ``get_float`` and
  ``get_stream``; ``OSC RESET`` is the same as ``RESET``.
* Voltage = ADC / maxADC * range - analog offset. The guide (ps5000aSetChannel)
  defines the offset as "a voltage to add to the input channel before
  digitization".
* EXT trigger input: +-5 V corresponds to +-32767 counts (guide, 3.2).
  Digital port logic level: -32767 (-5 V) .. 32767 (+5 V) (guide, 4.50).
* Trigger logic: conditions passed in one ps5000aSetTriggerChannelConditionsV2
  call are ANDed, repeated calls with PS5000A_ADD are ORed (guide, 4.68).
* Digital (MSO) inputs are implemented according to the guide but were NOT
  TESTED on hardware (test instrument PicoScope 5443D has no digital inputs).

Sources: the driver headers ps2000aApi.h, ps3000aApi.h, ps4000aApi.h,
ps5000aApi.h and PicoStatus.h of the PicoSDK; PicoScope 5000 Series (A API)
Programmer's Guide (ps5000apg.en r4) for the ps5000a behaviour.
"""

import ctypes
import ctypes.util
import math
import os
import re
import sys
import threading
import time

import numpy as np


# *****************************************************************************
# Exception
# *****************************************************************************
class ExceptionPicoscope(Exception):
    """Error raised by the PicoScope module (invalid command, driver error).
    The message contains the failing command and the reason; driver errors
    also carry the PICO_STATUS code."""

    def __init__(self, message: str, status: int = None):
        """`status` is the PICO_STATUS code of a driver error, otherwise None."""
        super().__init__(message)
        self.status = status


class ExceptionNotSupported(ExceptionPicoscope):
    """The connected instrument cannot do what the command asks (a feature
    its series does not have, an input range or channel it does not have).
    The message starts with "Not supported". In ``strict=False`` mode the
    text response is "ERR <command>: Not supported: <reason>"."""

    def __init__(self, message: str, status: int = None):
        super().__init__(message if "Not supported" in message
                         else "Not supported: " + message, status)


class _Aborted(Exception):
    """Internal: an operation was interrupted by STOP."""


# *****************************************************************************
# Driver constants (values from the ps5000a Programmer's Guide)
# *****************************************************************************
#> Input ranges: (full scale in volts, PSxxxxA_RANGE value). The values are
#> the same in all four drivers (PS4000A also has 50, 100 and 200 V);
#> which of them a model has is decided by the driver.
_RANGES = [(0.01, 0), (0.02, 1), (0.05, 2), (0.1, 3), (0.2, 4), (0.5, 5),
           (1.0, 6), (2.0, 7), (5.0, 8), (10.0, 9), (20.0, 10), (50.0, 11),
           (100.0, 12), (200.0, 13)]
#> PS5000A_DEVICE_RESOLUTION, guide 4.49.1
_RESOLUTIONS = {8: 0, 12: 1, 14: 2, 15: 3, 16: 4}
#> PS5000A_COUPLING, guide 4.7.2
_COUPLING = {"AC": 0, "DC": 1}
#> PS5000A_BANDWIDTH_LIMITER, guide 4.45.1
_BANDWIDTH = {"FULL": 0, "20MHZ": 1}
#> Channel codes: A-D = 0-3 in every driver, E-H = 4-7 (ps4000a, 8 channels).
#> The EXT input has a different driver code per family; the command layer
#> uses _EXT and the backend translates it (_Family.ext).
_CHANNELS = "ABCDEFGH"
_EXT = 100
_CH = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6, "H": 7,
       "EXT": _EXT}
_PORT = {"D0": 0x80, "D1": 0x81}
_PULSE_WIDTH_SOURCE = 0x10000000
#> PS5000A_CHANNEL_FLAGS, guide 4.2.1
_CH_FLAGS = {"A": 1, "B": 2, "C": 4, "D": 8, "E": 0, "F": 0, "G": 0,
             "H": 0, "D0": 0x10000, "D1": 0x20000}
#> PS5000A_THRESHOLD_DIRECTION, guide 4.69.1 (name -> (value, window mode))
_DIRECTIONS = {
    "ABOVE": (0, False), "BELOW": (1, False), "RISING": (2, False),
    "FALLING": (3, False), "BOTH": (4, False),
    "ABOVELOWER": (5, False), "BELOWLOWER": (6, False),
    "RISINGLOWER": (7, False), "FALLINGLOWER": (8, False),
    "INSIDE": (0, True), "OUTSIDE": (1, True), "ENTER": (2, True),
    "EXIT": (3, True), "ENTEROREXIT": (4, True),
    "POSITIVERUNT": (9, True), "NEGATIVERUNT": (10, True),
}
#> Directions usable by the simple edge trigger shortcut
_EDGE_DIRECTIONS = ("RISING", "FALLING", "BOTH", "ABOVE", "BELOW")
#> Directions the EXT input accepts. Measured on a 5443D: ABOVE and BELOW
#> fire at any level on EXT (they work on A-D), the edges work correctly.
_EXT_DIRECTIONS = ("RISING", "FALLING", "BOTH")
#> PS5000A_THRESHOLD_MODE, guide 4.70.2
_LEVEL, _WINDOW = 0, 1
#> PS5000A_TRIGGER_STATE, guide 4.68.2
_CONDITION_TRUE = 1
#> PS5000A_CONDITIONS_INFO, guide 4.58.1
_CLEAR, _ADD = 1, 2
#> PS5000A_PULSE_WIDTH_TYPE, guide 4.60.1
_PW_TYPES = {"NONE": 0, "LESS": 1, "GREATER": 2, "INSIDE": 3, "OUTSIDE": 4}
#> PS5000A_DIGITAL_DIRECTION, guide 4.74.3
_DIG_DIRECTIONS = {"X": 0, "LOW": 1, "HIGH": 2, "RISING": 3, "FALLING": 4,
                   "BOTH": 5}
#> PS5000A_RATIO_MODE, guide 4.22.1
_RATIO_MODES = {"NONE": 0, "AGGREGATE": 1, "DECIMATE": 2, "AVERAGE": 4}
#> PS5000A_TIME_UNITS: exponent of each unit (FS, PS, NS, US, MS, S)
_TIME_UNIT_FACTOR = [1e-15, 1e-12, 1e-9, 1e-6, 1e-3, 1.0]
#> PS5000A_ETS_MODE, guide 4.51.1
_ETS_MODES = {"OFF": 0, "FAST": 1, "SLOW": 2}
#> PS5000A_WAVE_TYPE, guide 4.62.3 (NOISE and PRBS are extra operations)
_WAVES = {"SINE": 0, "SQUARE": 1, "TRIANGLE": 2, "RAMPUP": 3, "RAMPDOWN": 4,
          "SINC": 5, "GAUSSIAN": 6, "HALFSINE": 7, "DC": 8}
#> PS5000A_EXTRA_OPERATIONS, guide 4.61.4
_OP_OFF, _OP_WHITENOISE, _OP_PRBS = 0, 1, 2
#> PS5000A_SWEEP_TYPE, guide 4.61.3
_SWEEPS = {"UP": 0, "DOWN": 1, "UPDOWN": 2, "DOWNUP": 3}
#> PS5000A_SIGGEN_TRIG_TYPE, guide 4.62.1
_GEN_TRIG_TYPES = {"RISING": 0, "FALLING": 1, "GATEHIGH": 2, "GATELOW": 3}
#> PS5000A_SIGGEN_TRIG_SOURCE, guide 4.62.2
_GEN_TRIG_SOURCES = {"NONE": 0, "SCOPE": 1, "AUX": 2, "EXT": 3, "SOFT": 4}
#> PS5000A_SHOT_SWEEP_TRIGGER_CONTINUOUS_RUN (value from ps5000aApi.h;
#> not printed in the guide - verify on hardware)
_CONTINUOUS_RUN = 0xFFFFFFFF
#> PICO_STATUS values used by the module (PicoStatus.h)
_PICO_OK = 0x00
_PICO_BUSY = 0x27
_PICO_POWER_SUPPLY_CONNECTED = 0x119
_PICO_POWER_SUPPLY_NOT_CONNECTED = 0x11A
_PICO_USB3_0_DEVICE_NON_USB3_0_PORT = 0x11E
#> Full-scale voltage of the EXT input and of the digital logic level
_EXT_FULL_SCALE = 5.0
_EXT_MAX_COUNTS = 32767
#> PICO_INFO codes, guide 4.21
_UNIT_INFO = [(0, "DRIVER"), (1, "USB"), (2, "HARDWARE"), (3, "VARIANT"),
              (4, "SERIAL"), (5, "CALDATE"), (6, "KERNEL"),
              (7, "DIGITALHW"), (8, "ANALOGHW"), (9, "FIRMWARE1"),
              (10, "FIRMWARE2")]
#> Maximum number of samples read by one ps5000aGetValuesBulk call; the
#> abort request is checked between such chunks.
_BULK_CHUNK_SAMPLES = 4_000_000


# *****************************************************************************
# Small helpers
# *****************************************************************************
#> Allowed SI prefixes per quantity.  The PicoScope never needs megavolts or
#> megaseconds, so for volts and seconds the prefix letter is case
#> insensitive and both "m" and "M" mean milli.  For frequency "m" (milli)
#> and "M" (mega) must stay distinct, so the case matters there.  Counts
#> (samples, records, ...) cannot be fractional, so they have no sub-unit
#> prefixes and "M" means mega.
_PREFIXES = {
    "V": {"": 1.0, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3},
    "s": {"": 1.0, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3},
    "Hz": {"": 1.0, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9,
           "g": 1e9},
    "": {"": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "g": 1e9},
}
#> Quantities whose prefix letter is matched case insensitively.
_PREFIX_NOCASE = ("V", "s")
_NUM_RE = re.compile(
    r"^([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)([^\d\s.+-]*)$")


def _num(text: str, kind: str = "") -> float:
    """Convert a number with an optional SI prefix and unit to float.

    ``kind`` is the physical quantity expected by the command: ``"V"``
    (volts), ``"s"`` (seconds), ``"Hz"`` (hertz) or ``""`` (a plain number,
    e.g. a count).  The unit itself is optional and ignored, but when it is
    written it must match ``kind`` (any letter case, so ``mv``, ``MS`` and
    ``hz`` are fine).  The prefix is always honoured:

    ====  =====================================  =========================
    kind  prefixes                               examples
    ====  =====================================  =========================
    V     p n u µ m (case insensitive, M = m)    500m, 500mV, 500MV -> 0.5
    s     p n u µ m (case insensitive, M = m)    1us, 1US -> 1e-6; 10Ms -> 0.01
    Hz    m k K M G (case sensitive: m milli,    10kHz -> 1e4, 1MHz -> 1e6,
          M mega)                                100mHz -> 0.1
    ""    k K M G (M = mega)                     10k -> 1e4, 2M -> 2e6
    ====  =====================================  =========================

    Exponent notation always works: ``2.5e-6``, ``1E3Hz``.
    """
    #> Group 1 is the number itself, group 2 everything after it
    #> (prefix and unit, e.g. "mV", "kHz", "us").
    m = _NUM_RE.match(text.strip())
    if not m:
        raise ExceptionPicoscope(f"invalid number '{text}'")
    suffix = m.group(2)
    #> Strip the unit (in any letter case); what remains must be a prefix.
    unit = kind.lower()
    if unit and suffix.lower().endswith(unit):
        suffix = suffix[:len(suffix) - len(unit)]
    #> Volts and seconds: "M" is read as "m" (milli), "U" as "u" etc.
    if kind in _PREFIX_NOCASE:
        suffix = suffix.lower()
    table = _PREFIXES[kind]
    if suffix not in table:
        what = f"unit '{kind}'" if kind else "a plain number"
        raise ExceptionPicoscope(
            f"invalid prefix or unit in '{text}' (expected {what}, "
            f"prefixes: {' '.join(p for p in table if p) or 'none'})")
    return float(m.group(1)) * table[suffix]


def _int(text: str) -> int:
    """Convert a non-negative integer (prefixes k, M, G allowed, e.g. '10k')."""
    value = _num(text)
    #> Rejects negative numbers and fractions such as "1.5" or "10u".
    if value < 0 or value != int(value):
        raise ExceptionPicoscope(f"'{text}' is not a non-negative integer")
    return int(value)


def _cont(value: int) -> str:
    """Format a generator SHOTS/SWEEPS count; the 'run forever' constant is
    shown as CONT, the keyword that sets it."""
    return "CONT" if value == _CONTINUOUS_RUN else str(value)


def _fmt(value) -> str:
    """Format a value for a text response."""
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _choice(text: str, table, what: str):
    """Return the key of `table` matching `text` (case insensitive)."""
    key = text.upper()
    if key not in table:
        raise ExceptionPicoscope(
            f"invalid {what} '{text}', expected one of: {', '.join(table)}")
    return key


def _onoff(text: str) -> bool:
    """Convert ON/OFF (or 1/0, any case) to bool."""
    key = text.upper()
    if key in ("ON", "1"):
        return True
    if key in ("OFF", "0"):
        return False
    raise ExceptionPicoscope(f"expected ON or OFF, got '{text}'")


def _range_index(volts: float) -> int:
    """Index into _RANGES of the smallest range covering |volts|."""
    for i, (full_scale, _) in enumerate(_RANGES):
        if abs(volts) <= full_scale * (1 + 1e-9):
            return i
    raise ExceptionNotSupported(
        f"range {volts} V exceeds the maximum of {_RANGES[-1][0]:g} V")


#> Names of the PICO_STATUS codes the module meets most often (PicoStatus.h);
#> other codes are looked up in the optional packages or shown in hex.
_STATUS_NAMES = {
    0x00: "PICO_OK", 0x01: "PICO_MAX_UNITS_OPENED", 0x02: "PICO_MEMORY_FAIL",
    0x03: "PICO_NOT_FOUND", 0x04: "PICO_FW_FAIL", 0x05: "PICO_OPEN_OPERATION_IN_PROGRESS",
    0x06: "PICO_OPERATION_FAILED", 0x07: "PICO_NOT_RESPONDING",
    0x08: "PICO_CONFIG_FAIL", 0x09: "PICO_KERNEL_DRIVER_TOO_OLD",
    0x0A: "PICO_EEPROM_CORRUPT", 0x0B: "PICO_OS_NOT_SUPPORTED",
    0x0C: "PICO_INVALID_HANDLE", 0x0D: "PICO_INVALID_PARAMETER",
    0x0E: "PICO_INVALID_TIMEBASE", 0x0F: "PICO_INVALID_VOLTAGE_RANGE",
    0x10: "PICO_INVALID_CHANNEL", 0x11: "PICO_INVALID_TRIGGER_CHANNEL",
    0x12: "PICO_INVALID_CONDITION_CHANNEL", 0x13: "PICO_NO_SIGNAL_GENERATOR",
    0x14: "PICO_STREAMING_FAILED", 0x15: "PICO_BLOCK_MODE_FAILED",
    0x16: "PICO_NULL_PARAMETER", 0x1A: "PICO_ETS_NOT_SUPPORTED",
    0x27: "PICO_BUSY", 0x3F: "PICO_NOT_USED", 0x47: "PICO_RATIO_MODE_NOT_SUPPORTED",
    0x5D: "PICO_NO_CAPTURES_AVAILABLE", 0x10C: "PICO_COUPLING_NOT_SUPPORTED",
    0x10D: "PICO_BANDWIDTH_NOT_SUPPORTED", 0x10F: "PICO_AWG_NOT_SUPPORTED",
    0x111: "PICO_SIG_GEN_WHITENOISE_NOT_SUPPORTED",
    0x112: "PICO_SIG_GEN_WAVETYPE_NOT_SUPPORTED",
    0x116: "PICO_SIG_GEN_PRBS_NOT_SUPPORTED",
    0x119: "PICO_POWER_SUPPLY_CONNECTED", 0x11A: "PICO_POWER_SUPPLY_NOT_CONNECTED",
    0x11E: "PICO_USB3_0_DEVICE_NON_USB3_0_PORT",
    0x11F: "PICO_NOT_SUPPORTED_BY_THIS_DEVICE",
}
#> Statuses that mean "this instrument cannot do that": raised as
#> ExceptionNotSupported. INVALID_VOLTAGE_RANGE / INVALID_CHANNEL are what the
#> drivers answer to a range or channel the model does not have.
_NOT_SUPPORTED = frozenset((0x0F, 0x10, 0x1A, 0x13, 0x3F, 0x47, 0x10C, 0x10D,
                            0x10F, 0x111, 0x112, 0x116, 0x11F))


_HEADER_NAMES = None


def _header_names() -> dict:
    """Names of all PICO_STATUS codes below 0x200, read once from
    ``PicoStatus.h`` of the PicoSDK installation (folder ``inc`` next to the
    ``lib`` folder of the driver DLLs); empty when the header is not found."""
    global _HEADER_NAMES
    if _HEADER_NAMES is None:
        _HEADER_NAMES = {}
        for folder in _SDK_DIRS:
            path = os.path.join(os.path.dirname(folder), "inc",
                                "PicoStatus.h") if folder else ""
            if path and os.path.isfile(path):
                try:
                    text = open(path, encoding="utf-8",
                                errors="ignore").read()
                except OSError:
                    continue
                for name, value in re.findall(
                        r"#define\s+(PICO_[A-Z0-9_]+)\s+0x([0-9A-Fa-f]+)UL",
                        text):
                    if int(value, 16) < 0x200:
                        _HEADER_NAMES.setdefault(int(value, 16), name)
                break
    return _HEADER_NAMES


def _status_name(status: int) -> str:
    """Symbolic name of a PICO_STATUS code, e.g. 'PICO_INVALID_TIMEBASE'
    (the hex value when the code is not known)."""
    return _STATUS_NAMES.get(status) or _header_names().get(status)         or hex(status)


def _driver_error(function: str, status: int) -> ExceptionPicoscope:
    """Exception for a failed driver call: ExceptionNotSupported for the
    statuses of _NOT_SUPPORTED, otherwise ExceptionPicoscope."""
    text = f"{function} failed: {_status_name(status)}"
    if status in _NOT_SUPPORTED:
        return ExceptionNotSupported(text, status)
    return ExceptionPicoscope(text, status)


# *****************************************************************************
# Configuration containers
# *****************************************************************************
class _Channel:
    """Settings of one analog channel."""

    def __init__(self, enabled=False):
        """Defaults: DC coupling, +-5 V range, no offset, full bandwidth,
        output scale factor 1.
        """
        self.enabled = enabled
        self.coupling = "DC"
        self.range_idx = _range_index(5.0)
        self.offset = 0.0
        self.bw = "FULL"
        #> Software multiplier of the volts returned by get_float/get_stream
        #> (e.g. 10 for a 10:1 probe). The instrument never sees it.
        self.factor = 1.0

    @property
    def range_v(self) -> float:
        """Full scale of the selected range in volts (e.g. 2.0 for +-2 V)."""
        return _RANGES[self.range_idx][0]


class _Digital:
    """Settings of one MSO digital port (8 bits)."""

    def __init__(self):
        """Defaults: port disabled, logic threshold 1.5 V."""
        self.enabled = False
        self.level = 1.5


class _TrigSource:
    """Trigger settings of one analog source (A-D or EXT)."""

    def __init__(self):
        """Defaults: rising edge at 0 V, automatic hysteresis."""
        self.direction = "RISING"
        self.level = 0.0
        self.lower = 0.0
        self.hyst = None   # volts; None = 1 % of the full scale


class _Trigger:
    """Complete trigger configuration."""

    def __init__(self):
        """Defaults: no condition (free run), AND logic, no delay, no auto
        trigger, output edge detection on (driver default).
        """
        self.sources = {}          # name -> _TrigSource
        self.logic = "AND"
        self.delay = 0             # samples
        self.auto = 0.0            # seconds, 0 = wait forever
        self.digital = {}          # bit 0..15 -> direction name
        self.pw_type = "NONE"
        self.pw_source = None
        self.pw_direction = "FALLING"
        self.pw_level = None       # volts; None = LEVEL of the source
        self.pw_lower = 0.0        # seconds
        self.pw_upper = 0.0        # seconds
        self.within_pre = False
        self.edge_detect = True

    @property
    def enabled(self) -> bool:
        """True when at least one trigger condition is configured."""
        return bool(self.sources or self.digital or self.pw_type != "NONE")


class _Generator:
    """Signal generator settings."""

    def __init__(self):
        """Defaults: output off, 1 kHz sine, 1 Vpp, no offset, no sweep,
        no generator trigger.
        """
        self.enabled = False
        self.wave = "SINE"
        self.freq = 1000.0
        self.ampl = 1.0            # Vpp
        self.offset = 0.0
        self.sweep = None          # (stop Hz, increment Hz, dwell s, type)
        self.shots = 0
        self.sweeps = 0
        self.trig_source = "NONE"
        self.trig_type = "RISING"
        self.ext_level = 0.0
        self.arb = None            # np.ndarray normalized to -1..1


class _Acquisition:
    """Scope-wide acquisition settings (the OSC command group)."""

    def __init__(self):
        """Defaults: 8 bits, 1 us interval, 100 + 1000 samples, one record,
        block mode, no downsampling, ETS off.
        """
        self.bits = 8
        self.bits_set = False      # True once the user entered OSC BITS
        self.interval = 1e-6       # requested sampling interval in s
        self.tbindex = None        # fixed timebase index or None = automatic
        self.pre = 100
        self.post = 1000
        self.records = 1
        self.mode = "BLOCK"
        self.ds_mode = "NONE"
        self.ds_ratio = 1
        self.streambuf = 100_000
        self.autostop = False
        self.ets = "OFF"
        self.ets_cycles = 20
        self.ets_interleave = 10

    @property
    def samples(self) -> int:
        """Raw samples per record (PRETRIGGER + POSTTRIGGER)."""
        return self.pre + self.post


# *****************************************************************************
# Hardware backend: one class for the ps2000a, ps3000a, ps4000a and ps5000a
# drivers, loaded directly through ctypes
# *****************************************************************************
#> ctypes shortcuts for the prototype tables below
_i16, _u16, _i32, _u32 = (ctypes.c_int16, ctypes.c_uint16, ctypes.c_int32,
                          ctypes.c_uint32)
_i64, _u64, _f32, _f64 = (ctypes.c_int64, ctypes.c_uint64, ctypes.c_float,
                          ctypes.c_double)
_ptr = ctypes.c_void_p
_str = ctypes.c_char_p


class _Family:
    """Description of one driver family: the differences of its API that the
    backend has to know. The values come from the driver headers installed
    with the PicoSDK (``ps2000aApi.h`` ... ``ps5000aApi.h``).

    key        driver name in capitals (PS2000A ...), also the OPEN argument
    prefix     lower case function prefix ("ps3000a")
    max_channels   most analog channels of any model of the family
    ext        driver code of the EXT trigger input
    resolution True when the resolution is selectable (OpenUnit takes it and
               ps5000aSetDeviceResolution exists): ps5000a only
    fixed_bits ADC resolution of the models without a selectable resolution
    oversample True when GetTimebase2 and RunBlock have the (unused)
               ``oversample`` argument: ps2000a and ps3000a
    trigger    trigger API: "v2" (ps5000a: *V2 functions with condition,
               direction and property arrays), "arr" (ps4000a: the same
               arrays, direction without mode), "v1" (ps2000a, ps3000a: one
               condition structure with a state per source, directions as
               arguments)
    pwq        True when a pulse-width qualifier exists (not in ps4000a)
    extras     True when TriggerWithinPreTriggerSamples, SetOutputEdgeDetect,
               SetAutoTriggerMicroSeconds and GetMinimumTimebaseStateless
               exist (ps5000a only)
    trig_info  True when GetTriggerInfoBulk exists
    builtin    name of the built-in generator function (without prefix)
    wave_type  ctypes type of its waveType argument
    awg_tick   AWG dwell time unit in seconds (dwellCount, VERIFY)
    """

    def __init__(self, key, max_channels, ext, resolution=False, fixed_bits=8,
                 oversample=False, trigger="v2", pwq=True, extras=False,
                 trig_info=True, builtin="SetSigGenBuiltInV2",
                 wave_type=_i32, awg_tick=50e-9):
        self.key = key
        self.prefix = key.lower()
        self.max_channels = max_channels
        self.ext = ext
        self.resolution = resolution
        self.fixed_bits = fixed_bits
        self.oversample = oversample
        self.trigger = trigger
        self.pwq = pwq
        self.extras = extras
        self.trig_info = trig_info
        self.builtin = builtin
        self.wave_type = wave_type
        self.awg_tick = awg_tick


#> The four supported families. EXT is code 4 where the driver has four
#> analog channels and code 8 in ps4000a (channels A-H come first).
_FAMILIES = {
    "PS2000A": _Family("PS2000A", 4, 4, oversample=True, trigger="v1",
                       trig_info=False, wave_type=_i16),
    "PS3000A": _Family("PS3000A", 4, 4, oversample=True, trigger="v1",
                       wave_type=_i16),
    "PS4000A": _Family("PS4000A", 8, 8, fixed_bits=12, trigger="arr",
                       pwq=False, trig_info=False, builtin="SetSigGenBuiltIn",
                       awg_tick=1 / 80e6),
    "PS5000A": _Family("PS5000A", 4, 4, resolution=True, extras=True),
}
#> Order in which OPEN looks for instruments without an explicit family.
_FAMILY_ORDER = ("PS5000A", "PS4000A", "PS3000A", "PS2000A")


#> Argument types of the functions that have the same prototype in all four
#> drivers (checked in the headers). The key is the function name without
#> the prefix; every function returns PICO_STATUS (uint32).
_COMMON_PROTOTYPES = {
    "EnumerateUnits": [_ptr, _ptr, _ptr],
    "CloseUnit": [_i16],
    "GetUnitInfo": [_i16, _str, _i16, _ptr, _u32],
    "CurrentPowerSource": [_i16],
    "ChangePowerSource": [_i16, _u32],
    "FlashLed": [_i16, _i16],
    "MaximumValue": [_i16, _ptr],
    "SetChannel": [_i16, _i32, _i16, _i32, _i32, _f32],
    "SetBandwidthFilter": [_i16, _i32, _i32],
    "GetAnalogueOffset": [_i16, _i32, _i32, _ptr, _ptr],
    "SetDigitalPort": [_i16, _i32, _i16, _i16],
    "GetMaxSegments": [_i16, _ptr],
    "MemorySegments": [_i16, _u32, _ptr],
    "SetNoOfCaptures": [_i16, _u32],
    "GetNoOfCaptures": [_i16, _ptr],
    "SetEts": [_i16, _i32, _i16, _i16, _ptr],
    "SetEtsTimeBuffer": [_i16, _ptr, _i32],
    "SetSimpleTrigger": [_i16, _i16, _i32, _i16, _i32, _u32, _i16],
    "SetTriggerDelay": [_i16, _u32],
    "IsReady": [_i16, _ptr],
    "Stop": [_i16],
    "SetDataBuffer": [_i16, _i32, _ptr, _i32, _u32, _i32],
    "SetDataBuffers": [_i16, _i32, _ptr, _ptr, _i32, _u32, _i32],
    "GetValues": [_i16, _u32, _ptr, _u32, _i32, _u32, _ptr],
    "GetValuesAsync": [_i16, _u32, _u32, _u32, _i32, _u32, _ptr, _ptr],
    "GetValuesBulk": [_i16, _ptr, _u32, _u32, _u32, _i32, _ptr],
    "GetTriggerTimeOffset64": [_i16, _ptr, _ptr, _u32],
    "GetValuesTriggerTimeOffsetBulk64": [_i16, _ptr, _ptr, _u32, _u32],
    "RunStreaming": [_i16, _ptr, _i32, _u32, _u32, _i16, _u32, _i32, _u32],
    "GetStreamingLatestValues": [_i16, _ptr, _ptr],
    "SetSigGenArbitrary": [_i16, _i32, _u32, _u32, _u32, _u32, _u32, _ptr,
                           _i32, _i32, _i32, _i32, _u32, _u32, _i32, _i32,
                           _i16],
    "SigGenArbitraryMinMaxValues": [_i16, _ptr, _ptr, _ptr, _ptr],
    "SigGenFrequencyToPhase": [_i16, _f64, _i32, _u32, _ptr],
    "SigGenSoftwareControl": [_i16, _i16],
}


def _prototypes(fam: _Family) -> dict:
    """Argument types of all functions of the family `fam` (name without
    the prefix -> list). Functions that exist in only some drivers are added
    according to the family flags; the backend reports a missing function as
    "not supported".
    """
    p = dict(_COMMON_PROTOTYPES)
    #> OpenUnit: ps5000a also takes the resolution.
    p["OpenUnit"] = [_ptr, _str] + ([_i32] if fam.resolution else [])
    #> GetTimebase2 and RunBlock: the oversample argument (ps2000a/3000a).
    if fam.oversample:
        p["GetTimebase2"] = [_i16, _u32, _i32, _ptr, _i16, _ptr, _u32]
        p["RunBlock"] = [_i16, _i32, _i32, _u32, _i16, _ptr, _u32, _ptr, _ptr]
    else:
        p["GetTimebase2"] = [_i16, _u32, _i32, _ptr, _ptr, _u32]
        p["RunBlock"] = [_i16, _i32, _i32, _u32, _ptr, _u32, _ptr, _ptr]
    p[fam.builtin] = [_i16, _i32, _u32, fam.wave_type, _f64, _f64, _f64,
                      _f64, _i32, _i32, _u32, _u32, _i32, _i32, _i16]
    if fam.trigger == "v2":
        p.update({
            "SetTriggerChannelPropertiesV2": [_i16, _ptr, _i16, _i16],
            "SetTriggerChannelConditionsV2": [_i16, _ptr, _i16, _i32],
            "SetTriggerChannelDirectionsV2": [_i16, _ptr, _u16],
            "SetTriggerDigitalPortProperties": [_i16, _ptr, _i16],
            "SetPulseWidthQualifierConditions": [_i16, _ptr, _i16, _i32],
            "SetPulseWidthQualifierProperties": [_i16, _u32, _u32, _i32],
            "SetPulseWidthQualifierDirections": [_i16, _ptr, _i16],
        })
    elif fam.trigger == "arr":
        p.update({
            "SetTriggerChannelProperties": [_i16, _ptr, _i16, _i16, _i32],
            "SetTriggerChannelConditions": [_i16, _ptr, _i16, _i32],
            "SetTriggerChannelDirections": [_i16, _ptr, _i16],
        })
    else:
        #> ps3000a has the V2 conditions (with the digital state); ps2000a
        #> has the same layout under the name without V2.
        cond = ("SetTriggerChannelConditionsV2" if fam.key == "PS3000A"
                else "SetTriggerChannelConditions")
        pwq = ("SetPulseWidthQualifierV2" if fam.key == "PS3000A"
               else "SetPulseWidthQualifier")
        p.update({
            "SetTriggerChannelProperties": [_i16, _ptr, _i16, _i16, _i32],
            cond: [_i16, _ptr, _i16],
            "SetTriggerChannelDirections": [_i16] + [_i32] * 6,
            pwq: [_i16, _ptr, _i16, _i32, _u32, _u32, _i32],
        })
    if fam.extras:
        p.update({
            "SetDeviceResolution": [_i16, _i32],
            "GetMinimumTimebaseStateless": [_i16, _u32, _ptr, _ptr, _i32],
            "SetAutoTriggerMicroSeconds": [_i16, _u64],
            "TriggerWithinPreTriggerSamples": [_i16, _i32],
            "SetOutputEdgeDetect": [_i16, _i16],
        })
    if fam.trig_info:
        p["GetTriggerInfoBulk"] = [_i16, _ptr, _u32, _u32]
    return p


#> Driver structures. All driver headers pack them to 1 byte; the field
#> layouts are taken from ps2000aApi.h ... ps5000aApi.h.
class _TriggerChannelPropertiesV2(ctypes.Structure):
    """PS5000A_TRIGGER_CHANNEL_PROPERTIES_V2: thresholds in ADC counts and
    hysteresis of one trigger source."""
    _pack_ = 1
    _fields_ = [("thresholdUpper", _i16),
                ("thresholdUpperHysteresis", _u16),
                ("thresholdLower", _i16),
                ("thresholdLowerHysteresis", _u16),
                ("channel", _i32)]


class _TriggerChannelProperties(ctypes.Structure):
    """PS2000A/PS3000A/PS4000A_TRIGGER_CHANNEL_PROPERTIES: like the V2
    structure plus the threshold mode (level or window)."""
    _pack_ = 1
    _fields_ = [("thresholdUpper", _i16),
                ("thresholdUpperHysteresis", _u16),
                ("thresholdLower", _i16),
                ("thresholdLowerHysteresis", _u16),
                ("channel", _i32),
                ("thresholdMode", _i32)]


class _Condition(ctypes.Structure):
    """PS4000A/PS5000A_CONDITION: source and its required state."""
    _pack_ = 1
    _fields_ = [("source", _i32), ("condition", _i32)]


class _Direction(ctypes.Structure):
    """PS5000A_DIRECTION: direction and threshold mode of one source."""
    _pack_ = 1
    _fields_ = [("channel", _i32), ("direction", _i32), ("mode", _i32)]


class _Direction4(ctypes.Structure):
    """PS4000A_DIRECTION: direction of one source (the mode is a property)."""
    _pack_ = 1
    _fields_ = [("channel", _i32), ("direction", _i32)]


class _ConditionsV1(ctypes.Structure):
    """PS2000A_TRIGGER_CONDITIONS / PS3000A_TRIGGER_CONDITIONS_V2: one
    required state per source; all fields of one structure are ANDed, several
    structures are ORed."""
    _pack_ = 1
    _fields_ = [("channelA", _i32), ("channelB", _i32), ("channelC", _i32),
                ("channelD", _i32), ("external", _i32), ("aux", _i32),
                ("pulseWidthQualifier", _i32), ("digital", _i32)]


class _PwqConditionsV1(ctypes.Structure):
    """PS2000A_PWQ_CONDITIONS / PS3000A_PWQ_CONDITIONS_V2."""
    _pack_ = 1
    _fields_ = [("channelA", _i32), ("channelB", _i32), ("channelC", _i32),
                ("channelD", _i32), ("external", _i32), ("aux", _i32),
                ("digital", _i32)]


class _DigitalChannelDirections(ctypes.Structure):
    """PS5000A_DIGITAL_CHANNEL_DIRECTIONS: one MSO bit."""
    _pack_ = 1
    _fields_ = [("channel", _i32), ("direction", _i32)]


class _TriggerInfo(ctypes.Structure):
    """PS3000A/PS5000A_TRIGGER_INFO: per-segment trigger data."""
    _pack_ = 1
    _fields_ = [("status", _u32),
                ("segmentIndex", _u32),
                ("triggerIndex", _u32),
                ("triggerTime", _i64),
                ("timeUnits", _i16),
                ("reserved0", _i16),
                ("timeStampCounter", _u64)]


#> Callback types. The drivers use the stdcall convention on 32-bit Windows
#> (WINFUNCTYPE); on 64-bit Windows and other systems both are the same.
_CALLBACK = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
#> psXXXXaBlockReady(handle, status, pParameter)
_BlockReadyType = _CALLBACK(None, _i16, _u32, _ptr)
#> psXXXXaDataReady(handle, status, noOfSamples, overflow, pParameter)
_DataReadyType = _CALLBACK(None, _i16, _u32, _u32, _i16, _ptr)
#> psXXXXaStreamingReady(handle, noOfSamples, startIndex, overflow,
#> triggerAt, triggered, autoStop, pParameter)
_StreamingReadyType = _CALLBACK(None, _i16, _i32, _u32, _i16, _u32, _i16,
                                _i16, _ptr)

#> Directories searched for the driver DLLs after the system search path.
_SDK_DIRS = [os.environ.get("PICO_SDK_DIR", ""),
             r"C:\Program Files\Pico Technology\SDK\lib",
             r"C:\Program Files (x86)\Pico Technology\SDK\lib",
             r"C:\Program Files\Pico Technology\PicoScope 7 T&M Stable",
             r"C:\Program Files\Pico Technology\PicoScope 7 T&M Early Access",
             "/opt/picoscope/lib"]
_LOADED = {}                       # family key -> loaded library


def _load_driver(fam: _Family):
    """Load the driver library of `fam` (cached) and return it.

    ``PICO_SDK_DIR`` (when set) is tried first, then the system search
    path, then the PicoSDK and PicoScope 7 installation directories. On Windows the
    directory of the DLL is added to the DLL search path so that the DLLs it
    depends on are found. Raises ExceptionPicoscope when it is not installed.
    """
    if fam.key in _LOADED:
        return _LOADED[fam.key]
    #> PICO_SDK_DIR (the first entry of _SDK_DIRS) wins over the system path,
    #> so that a chosen driver folder is really the one used.
    override = _SDK_DIRS[0]
    pattern = "{}.dll" if sys.platform == "win32" else "lib{}.so"
    names = []
    if override:
        names.append(os.path.join(override, pattern.format(fam.prefix)))
    names.append(ctypes.util.find_library(fam.prefix))
    names += [os.path.join(d, pattern.format(fam.prefix))
              for d in _SDK_DIRS[1:] if d]
    for path in names:
        if not path:
            continue
        if os.path.dirname(path) and not os.path.isfile(path):
            continue
        try:
            if sys.platform == "win32" and os.path.isabs(path):
                os.add_dll_directory(os.path.dirname(path))
            loader = getattr(ctypes, "WinDLL", ctypes.CDLL)
            _LOADED[fam.key] = loader(path)
            return _LOADED[fam.key]
        except OSError:
            continue
    raise ExceptionPicoscope(
        f"the {fam.prefix} driver is not installed (install PicoSDK or "
        f"PicoScope 7, or set PICO_SDK_DIR to the folder with "
        f"{fam.prefix}.dll)")


def _enumerate(fam: _Family) -> list:
    """Serial numbers of the unopened units served by driver `fam`; an
    empty list when none is connected or the driver is not installed."""
    try:
        backend = _HwBackend(fam.key)
    except ExceptionPicoscope:
        return []
    return backend.enumerate()


class _HwBackend:
    """Backend of one driver family (see _Family): it has exactly the
    interface of the simulator (_SimBackend), so the command layer does not
    know which one it talks to. Only this class touches ctypes. All methods
    raise ExceptionPicoscope on a driver error and never close the unit on
    their own; a function or a feature the instrument does not have raises
    ExceptionNotSupported.
    """

    def __init__(self, family: str):
        """Load the driver library of `family` and bind its functions.

        Raises ExceptionPicoscope when the driver is not installed, so the
        error appears at OPEN and not at the import of this module.
        """
        self.fam = _FAMILIES[family]
        self.FAMILY = family
        self.dll = _load_driver(self.fam)
        self._fn = {name: self._bind(name, argtypes)
                    for name, argtypes in _prototypes(self.fam).items()}
        self.handle = ctypes.c_int16(0)
        self._keep = []            # references kept alive for the driver
        self._keep_awg = None
        self._stream = None

    def _bind(self, name, argtypes):
        """Return a new ctypes function object for <prefix><name> with the
        given argument types, or None when the driver lacks the function
        (older driver versions, other models). ``dll._FuncPtr`` creates an
        independent object, so nothing else using the library is affected.
        """
        try:
            func = self.dll._FuncPtr((self.fam.prefix + name, self.dll))
        except AttributeError:
            return None
        func.restype = ctypes.c_uint32
        func.argtypes = argtypes
        return func

    def _call(self, name, *args, ok=(_PICO_OK,)):
        """Call <prefix><name> and raise unless the returned PICO_STATUS is
        in `ok`. A missing function and the "not supported" statuses of
        _NOT_SUPPORTED raise ExceptionNotSupported. Returns the status.
        """
        func = self._fn.get(name)
        if func is None:
            raise ExceptionNotSupported(
                f"the {self.fam.prefix} driver has no {name}")
        status = func(*args)
        if status not in ok:
            raise _driver_error(f"{self.fam.prefix}{name}", status)
        return status

    def _ch(self, code):
        """Driver code of a source code of the command layer (the command
        layer uses _EXT for the EXT input)."""
        return self.fam.ext if code == _EXT else code

    # ----- device -----------------------------------------------------------
    def enumerate(self) -> list:
        """Serial numbers of the connected, not opened units of this driver
        (ps...EnumerateUnits; PICO_NOT_FOUND means none)."""
        count, length = ctypes.c_int16(), ctypes.c_int16(1024)
        buf = ctypes.create_string_buffer(1024)
        status = self._fn["EnumerateUnits"](ctypes.byref(count), buf,
                                            ctypes.byref(length))
        if status != _PICO_OK or count.value <= 0:
            return []
        return [s for s in buf.value.decode(errors="replace").split(",") if s]

    def open(self, serial, resolution):
        """Open the unit and complete the power-up when needed (ps5000a also
        selects the resolution). Returns the power state name (DC, USB or
        USB2).

        A USB-powered unit (or a USB 3 unit in a USB 2 port) answers
        PICO_POWER_SUPPLY_NOT_CONNECTED / PICO_USB3_0_DEVICE_NON_USB3_0_PORT;
        the driver then needs ChangePowerSource with that status (guide
        "ChangePowerSource"). Such a unit has fewer usable channels.
        """
        ser = serial.encode() if serial else None
        args = [ctypes.byref(self.handle), ser]
        if self.fam.resolution:
            args.append(resolution)
        status = self._fn["OpenUnit"](*args)
        power = "DC"
        if status in (_PICO_POWER_SUPPLY_NOT_CONNECTED,
                      _PICO_USB3_0_DEVICE_NON_USB3_0_PORT):
            self._call("ChangePowerSource", self.handle, status)
            power = ("USB" if status == _PICO_POWER_SUPPLY_NOT_CONNECTED
                     else "USB2")
        elif status != _PICO_OK:
            raise _driver_error(f"{self.fam.prefix}OpenUnit", status)
        return power

    def close(self):
        """CloseUnit (safe to call when the unit is not open)."""
        if self.handle.value > 0:
            try:
                self._fn["CloseUnit"](self.handle)
            finally:
                self.handle = ctypes.c_int16(0)

    def unit_info(self, info: int) -> str:
        """GetUnitInfo: one PICO_INFO string (see _UNIT_INFO)."""
        buf = ctypes.create_string_buffer(64)
        req = ctypes.c_int16()
        self._call("GetUnitInfo", self.handle, buf, 64, ctypes.byref(req),
                   info)
        return buf.value.decode(errors="replace")

    def power_source(self) -> str:
        """CurrentPowerSource as DC, USB or USB2; a driver without the
        function (ps2000a) serves bus-powered units only: USB."""
        func = self._fn.get("CurrentPowerSource")
        if func is None:
            return "USB"
        status = func(self.handle)
        return {_PICO_POWER_SUPPLY_CONNECTED: "DC",
                _PICO_POWER_SUPPLY_NOT_CONNECTED: "USB",
                _PICO_USB3_0_DEVICE_NON_USB3_0_PORT: "USB2",
                _PICO_OK: "DC"}.get(status, _status_name(status))

    def change_power(self, dc: bool):
        """ChangePowerSource: confirm DC (adaptor) or USB power. All
        settings must be sent again afterwards."""
        state = (_PICO_POWER_SUPPLY_CONNECTED if dc
                 else _PICO_POWER_SUPPLY_NOT_CONNECTED)
        self._call("ChangePowerSource", self.handle, state)

    def flash_led(self, count: int):
        """FlashLed: <0 flash forever, 0 stop, >0 flash count times."""
        self._call("FlashLed", self.handle, count)

    def set_resolution(self, res: int):
        """SetDeviceResolution (ps5000a; the code is the
        PS5000A_DEVICE_RESOLUTION value). The other drivers have a fixed
        resolution, which the command layer checks before this call."""
        self._call("SetDeviceResolution", self.handle, res)

    def max_adc(self) -> int:
        """MaximumValue: ADC count of the full scale (32512 for 8 bits,
        32767 otherwise)."""
        value = ctypes.c_int16()
        self._call("MaximumValue", self.handle, ctypes.byref(value))
        return value.value

    # ----- inputs -----------------------------------------------------------
    def set_channel(self, ch, enabled, coupling, range_code, offset):
        """SetChannel; `offset` is the analog offset in volts."""
        self._call("SetChannel", self.handle, ch, int(enabled), coupling,
                   range_code, offset)

    def set_bandwidth(self, ch, bw):
        """SetBandwidthFilter (full or 20 MHz); not supported by every
        driver and model."""
        self._call("SetBandwidthFilter", self.handle, ch, bw)

    def offset_limits(self, range_code, coupling):
        """GetAnalogueOffset: (min, max) allowed offset in volts for the
        range and coupling."""
        vmax, vmin = ctypes.c_float(), ctypes.c_float()
        self._call("GetAnalogueOffset", self.handle, range_code, coupling,
                   ctypes.byref(vmax), ctypes.byref(vmin))
        return vmin.value, vmax.value

    def set_digital_port(self, port, enabled, level_counts):
        """SetDigitalPort (MSO only); `level_counts` is the logic threshold
        in counts (+-32767 = +-5 V). NOT TESTED."""
        self._call("SetDigitalPort", self.handle, port, int(enabled),
                   level_counts)

    # ----- timebase and memory ----------------------------------------------
    def min_timebase(self, flags, res):
        """Fastest (timebase, interval in s) for the enabled channels.

        ps5000a: GetMinimumTimebaseStateless (no change of the instrument
        state). The other drivers have no such function: the smallest
        timebase that GetTimebase2 accepts for the present channel settings
        is searched upwards from 0 (the fastest ones are among the first
        few indexes of every model).
        """
        if self.fam.extras:
            tb, dt = ctypes.c_uint32(), ctypes.c_double()
            self._call("GetMinimumTimebaseStateless", self.handle, flags,
                       ctypes.byref(tb), ctypes.byref(dt), res)
            return tb.value, dt.value
        for tb in range(0, 1000):
            info = self.timebase(tb, 1)
            if info is not None:
                return tb, info[0]
        raise ExceptionPicoscope("no valid timebase found (is a channel "
                                 "enabled?)")

    def timebase(self, tb, nsamples):
        """GetTimebase2: (interval in s, max samples), or None for a
        timebase that is invalid for the present settings. An invalid
        timebase is a normal answer during the timebase search, so it is not
        an error and the unit stays open."""
        dt, mx = ctypes.c_float(), ctypes.c_int32()
        args = [self.handle, tb, nsamples, ctypes.byref(dt)]
        if self.fam.oversample:
            args.append(0)
        args += [ctypes.byref(mx), 0]
        status = self._fn["GetTimebase2"](*args)
        if status != _PICO_OK:
            return None
        return dt.value * 1e-9, mx.value

    def max_segments(self) -> int:
        """GetMaxSegments: largest number of memory segments."""
        value = ctypes.c_uint32()
        self._call("GetMaxSegments", self.handle, ctypes.byref(value))
        return value.value

    def memory_segments(self, n) -> int:
        """MemorySegments: split the memory into `n` segments; returns the
        maximum samples per segment."""
        value = ctypes.c_int32()
        self._call("MemorySegments", self.handle, n, ctypes.byref(value))
        return value.value

    def set_captures(self, n):
        """SetNoOfCaptures: records of the next rapid block run."""
        self._call("SetNoOfCaptures", self.handle, n)

    def set_ets(self, mode, cycles, interleave) -> float:
        """SetEts; returns the effective ETS interval in s (the driver
        reports picoseconds); 0 when ETS is off."""
        ps_time = ctypes.c_int32()
        self._call("SetEts", self.handle, mode, cycles, interleave,
                   ctypes.byref(ps_time))
        return ps_time.value * 1e-12

    # ----- trigger ----------------------------------------------------------
    def set_trigger(self, spec):
        """Apply a trigger specification prepared by Picoscope._trig_spec.
        spec keys: props [(upper, uhyst, lower, lhyst, ch)] (thresholds in
        counts), directions [(ch, dir, mode)], terms [[source, ...], ...]
        (OR of AND terms), digital [(bit, dir)], pwq None or dict(type,
        lower, upper, conditions [ch], directions [(ch, dir, mode)]), delay,
        auto_us, within_pre, edge_detect. Source codes are channel codes,
        _EXT, _PORT values or _PULSE_WIDTH_SOURCE.

        The three trigger APIs (see _Family.trigger) are served by
        _trigger_v2, _trigger_arr and _trigger_v1.
        """
        if spec["within_pre"] and not self.fam.extras:
            raise ExceptionNotSupported(
                f"TRG WITHINPRE is not available in the {self.fam.prefix} "
                f"driver")
        if not spec["terms"]:
            #> No trigger: SetSimpleTrigger(enable = 0) exists in every
            #> driver and clears whatever was set before.
            self._call("SetSimpleTrigger", self.handle, 0, 0, 0, 2, 0, 0)
            return
        if spec["digital"] and self.fam.trigger != "v2":
            raise ExceptionNotSupported(
                f"digital triggers are not implemented for the "
                f"{self.fam.prefix} driver")
        getattr(self, "_trigger_" + self.fam.trigger)(spec)
        self._call("SetTriggerDelay", self.handle, spec["delay"])
        if self.fam.extras:
            self._call("TriggerWithinPreTriggerSamples", self.handle,
                       int(spec["within_pre"]))
            self._call("SetOutputEdgeDetect", self.handle,
                       int(spec["edge_detect"]))

    def _trigger_v2(self, spec):
        """ps5000a: *V2 functions with arrays of properties, conditions and
        directions; the auto trigger time is set in microseconds."""
        h = self.handle
        #> 0. Forget the previous trigger. Measured on a 5443D: after a
        #>    window trigger the driver kept the window mode and refused
        #>    every later level trigger whose thresholds were not a valid
        #>    window (PICO_INVALID_TRIGGER_PROPERTY).
        self._call("SetSimpleTrigger", h, 0, 0, 0, 2, 0, 0)
        #> 0b. Direction and threshold mode (level/window) of every source go
        #>    first: the driver checks the new thresholds against the mode.
        dirs = spec["directions"]
        if dirs:
            darr = (_Direction * len(dirs))(
                *[_Direction(self._ch(d[0]), d[1], d[2]) for d in dirs])
            self._call("SetTriggerChannelDirectionsV2", h, darr, len(dirs))
        #> 1. Thresholds and hysteresis of every source.
        props = spec["props"]
        arr = (_TriggerChannelPropertiesV2 * len(props))(
            *[_TriggerChannelPropertiesV2(*p[:4], self._ch(p[4]))
              for p in props])
        self._call("SetTriggerChannelPropertiesV2", h, arr, len(props), 0)
        #> 2. Conditions: the first call clears the old ones, the others
        #>    add OR terms; the sources inside one term are ANDed.
        for i, term in enumerate(spec["terms"]):
            conds = (_Condition * len(term))(
                *[_Condition(self._ch(src), _CONDITION_TRUE) for src in term])
            info = (_CLEAR | _ADD) if i == 0 else _ADD
            self._call("SetTriggerChannelConditionsV2", h, conds, len(term),
                       info)
        #> 4. MSO digital bit conditions (NOT TESTED); clearing them on a
        #>    model without digital inputs returns an error that is ignored.
        dig = spec["digital"]
        if dig:
            dd = (_DigitalChannelDirections * len(dig))(
                *[_DigitalChannelDirections(*d) for d in dig])
            self._call("SetTriggerDigitalPortProperties", h, dd, len(dig))
        else:
            self._call("SetTriggerDigitalPortProperties", h, None, 0,
                       ok=(_PICO_OK, 0x0D, 0x111, 0x11F))  # "not MSO" (0x11F seen on a 5443D)
        #> 5. Pulse-width qualifier (or remove a previous one).
        pwq = spec["pwq"]
        if pwq:
            conds = (_Condition * len(pwq["conditions"]))(
                *[_Condition(self._ch(src), _CONDITION_TRUE)
                  for src in pwq["conditions"]])
            self._call("SetPulseWidthQualifierConditions", h, conds,
                       len(pwq["conditions"]), _CLEAR | _ADD)
            self._call("SetPulseWidthQualifierProperties", h, pwq["lower"],
                       pwq["upper"], pwq["type"])
            pd = (_Direction * len(pwq["directions"]))(
                *[_Direction(self._ch(d[0]), d[1], d[2])
                  for d in pwq["directions"]])
            self._call("SetPulseWidthQualifierDirections", h, pd,
                       len(pwq["directions"]))
        else:
            self._call("SetPulseWidthQualifierConditions", h, None, 0,
                       _CLEAR)
        self._call("SetAutoTriggerMicroSeconds", h, spec["auto_us"])

    @staticmethod
    def _auto_ms(spec) -> int:
        """Auto trigger time in whole milliseconds (the older drivers have
        no finer resolution); a non-zero request is rounded up to 1 ms."""
        return int(math.ceil(spec["auto_us"] / 1000.0))

    def _props_with_mode(self, spec):
        """Trigger channel properties of the older drivers: the structure
        carries the threshold mode, which the command layer keeps in the
        directions."""
        mode = {d[0]: d[2] for d in spec["directions"]}
        props = spec["props"]
        return (_TriggerChannelProperties * len(props))(
            *[_TriggerChannelProperties(*p[:4], self._ch(p[4]),
                                        mode.get(p[4], _LEVEL))
              for p in props])

    def _trigger_arr(self, spec):
        """ps4000a: arrays like ps5000a, but the direction has no mode and
        the auto trigger time (ms) is an argument of the properties call."""
        h = self.handle
        props = self._props_with_mode(spec)
        self._call("SetTriggerChannelProperties", h, props, len(props), 0,
                   self._auto_ms(spec))
        for i, term in enumerate(spec["terms"]):
            conds = (_Condition * len(term))(
                *[_Condition(self._ch(src), _CONDITION_TRUE) for src in term])
            info = (_CLEAR | _ADD) if i == 0 else _ADD
            self._call("SetTriggerChannelConditions", h, conds, len(term),
                       info)
        dirs = spec["directions"]
        darr = (_Direction4 * len(dirs))(
            *[_Direction4(self._ch(d[0]), d[1]) for d in dirs])
        self._call("SetTriggerChannelDirections", h, darr, len(dirs))

    #> Field of the per-source condition structure of each source code
    _V1_FIELD = {0: "channelA", 1: "channelB", 2: "channelC", 3: "channelD",
                 _EXT: "external", _PULSE_WIDTH_SOURCE: "pulseWidthQualifier",
                 0x80: "digital", 0x81: "digital"}

    def _trigger_v1(self, spec):
        """ps2000a / ps3000a: one condition structure per OR term with a
        state for each source, directions as six arguments (A-D, EXT, AUX)
        and the auto trigger time (ms) in the properties call."""
        h = self.handle
        pfx = "SetTriggerChannelConditions" + (
            "V2" if self.fam.key == "PS3000A" else "")
        props = self._props_with_mode(spec)
        self._call("SetTriggerChannelProperties", h, props, len(props), 0,
                   self._auto_ms(spec))
        conds = (_ConditionsV1 * len(spec["terms"]))()
        for cond, term in zip(conds, spec["terms"]):
            for src in term:
                setattr(cond, self._V1_FIELD[src], _CONDITION_TRUE)
        self._call(pfx, h, conds, len(conds))
        #> Directions of the sources that are not used stay RISING, the
        #> driver's "none" value; their conditions are "don't care".
        slots = {0: 2, 1: 2, 2: 2, 3: 2, _EXT: 2}
        for ch, direction, _mode in spec["directions"]:
            slots[ch] = direction
        self._call("SetTriggerChannelDirections", h, slots[0], slots[1],
                   slots[2], slots[3], slots[_EXT], 2)
        pwq = spec["pwq"]
        pname = "SetPulseWidthQualifier" + (
            "V2" if self.fam.key == "PS3000A" else "")
        if pwq:
            pc = (_PwqConditionsV1 * 1)()
            for src in pwq["conditions"]:
                setattr(pc[0], self._V1_FIELD[src], _CONDITION_TRUE)
            self._call(pname, h, pc, 1, pwq["directions"][0][1],
                       pwq["lower"], pwq["upper"], pwq["type"])
        else:
            #> No qualifier: type NONE (0) with no conditions.
            self._call(pname, h, None, 0, 2, 0, 0, 0)

    # ----- block / rapid block ----------------------------------------------
    def run_block(self, pre, post, tb, callback=None):
        """RunBlock with any timebase index `tb` (no restriction here; an
        index the hardware cannot do is refused by the driver). When
        `callback` is given, the driver calls callback(status) from its own
        thread when the capture is complete (BlockReady). The ctypes callback
        object is kept in self._keep, otherwise it would be garbage
        collected while the driver still holds its address.
        """
        lp = None
        if callback is not None:
            def _ready(handle, status, param):
                callback(status)
            lp = _BlockReadyType(_ready)
            self._keep = [lp]
        cb = ctypes.cast(lp, _ptr) if lp else None
        if self.fam.oversample:
            self._call("RunBlock", self.handle, pre, post, tb, 0, None, 0, cb,
                       None)
        else:
            self._call("RunBlock", self.handle, pre, post, tb, None, 0, cb,
                       None)

    def is_ready(self) -> bool:
        """IsReady: True when the block / all records are captured. One
        non-blocking poll; WAIT repeats it."""
        ready = ctypes.c_int16(0)
        self._call("IsReady", self.handle, ctypes.byref(ready))
        return bool(ready.value)

    def stop(self):
        """Stop: abort a capture, streaming or GetValuesAsync. Called
        without the lock from any thread, so it must not raise."""
        if self.handle.value > 0:
            self._fn["Stop"](self.handle)

    def n_captures(self) -> int:
        """GetNoOfCaptures: records completed in rapid block mode."""
        value = ctypes.c_uint32()
        self._call("GetNoOfCaptures", self.handle, ctypes.byref(value))
        return value.value

    def _register(self, code, mx, mn, n, seg, mode):
        """Register the NumPy array(s) of one source/segment with the driver
        (SetDataBuffers for AGGREGATE, which returns max and min, otherwise
        SetDataBuffer). The arrays must stay alive until the transfer is
        finished; the caller keeps them."""
        if mn is not None:
            self._call("SetDataBuffers", self.handle, code, mx.ctypes.data,
                       mn.ctypes.data, n, seg, mode)
        else:
            self._call("SetDataBuffer", self.handle, code, mx.ctypes.data, n,
                       seg, mode)

    def get_values(self, codes, n_raw, ratio, mode, count, abort, ets=False):
        """Read `count` records of `n_raw` raw samples for the sources in
        `codes` (dict name -> driver code). Returns (data, overflow, times)
        where data[name] = (max array, min array or None) with shape
        (count, n), overflow is an int16 array per record and times are the
        ETS sample times (or None)."""
        aggregate = mode == _RATIO_MODES["AGGREGATE"]
        n_out = n_raw // ratio if mode else n_raw
        #> ETS: measured on a 5443D, GetValues returns the requested number
        #> of samples (not `interleave` times more; more gives
        #> PICO_TOO_MANY_SAMPLES) with a finer, irregular time step.
        data = {}
        for name in codes:
            data[name] = (np.zeros((count, n_out), np.int16),
                          np.zeros((count, n_out), np.int16)
                          if aggregate else None)
        overflow = np.zeros(count, np.int16)
        times = None
        #> ETS: only one record; the driver also returns the time of each
        #> sample in femtoseconds (SetEtsTimeBuffer).
        if ets:
            times = np.zeros(n_out, np.int64)
            for name, code in codes.items():
                self._register(code, data[name][0][0], None, n_out, 0, 0)
            self._call("SetEtsTimeBuffer", self.handle, times.ctypes.data,
                       n_out)
            n = ctypes.c_uint32(n_out)
            ovf = ctypes.c_int16()
            self._call("GetValues", self.handle, 0, ctypes.byref(n), 1, 0, 0,
                       ctypes.byref(ovf))
            overflow[0] = ovf.value
            got = n.value
            data = {k: (v[0][:, :got], None) for k, v in data.items()}
            return data, overflow, times[:got] * 1e-15
        if count == 1:
            got = self._get_async(codes, data, n_raw, n_out, ratio, mode,
                                  overflow, abort)
        else:
            got = self._get_bulk(codes, data, n_raw, n_out, ratio, mode,
                                 count, overflow, abort)
        data = {k: (mx[:, :got], None if mn is None else mn[:, :got])
                for k, (mx, mn) in data.items()}
        return data, overflow, None

    def _get_async(self, codes, data, n_raw, n_out, ratio, mode, overflow,
                   abort):
        """Single block transfer with GetValuesAsync.

        The call returns at once and the driver signals the end through the
        DataReady callback. Waiting in 10 ms steps allows STOP (abort event)
        to cancel the transfer with Stop. Returns the number of samples
        delivered per source.
        """
        for name, code in codes.items():
            mx, mn = data[name]
            self._register(code, mx[0], None if mn is None else mn[0],
                           n_out, 0, mode)
        done = threading.Event()
        result = {}

        def _ready(handle, status, nsamples, ovf, param):
            """Driver callback (runs in the driver's thread)."""
            result.update(status=status, n=nsamples, ovf=ovf)
            done.set()
        cb = _DataReadyType(_ready)
        self._keep = [cb]
        self._call("GetValuesAsync", self.handle, 0, n_raw, ratio, mode, 0,
                   ctypes.cast(cb, _ptr), None)
        while not done.wait(0.01):
            if abort.is_set():
                self.stop()
                done.wait(1.0)
                raise _Aborted()
        if result["status"] != _PICO_OK:
            raise _driver_error(f"{self.fam.prefix}GetValuesAsync",
                                result["status"])
        overflow[0] = result["ovf"]
        return result["n"]

    def _get_bulk(self, codes, data, n_raw, n_out, ratio, mode, count,
                  overflow, abort):
        """Rapid block transfer with GetValuesBulk in chunks.

        GetValuesBulk blocks until it is done, so the segments are read in
        chunks of about _BULK_CHUNK_SAMPLES samples and the abort event is
        checked between the chunks. Returns the smallest number of samples
        delivered by any chunk.
        """
        per_chunk = max(1, _BULK_CHUNK_SAMPLES // max(1, n_raw * len(codes)))
        got = n_out
        for first in range(0, count, per_chunk):
            if abort.is_set():
                raise _Aborted()
            last = min(count, first + per_chunk) - 1
            for seg in range(first, last + 1):
                for name, code in codes.items():
                    mx, mn = data[name]
                    self._register(code, mx[seg],
                                   None if mn is None else mn[seg],
                                   n_out, seg, mode)
            n = ctypes.c_uint32(n_raw)
            ovf = (ctypes.c_int16 * (last - first + 1))()
            self._call("GetValuesBulk", self.handle, ctypes.byref(n), first,
                       last, ratio, mode, ovf)
            overflow[first:last + 1] = list(ovf)
            got = min(got, n.value)
        return got

    def trigger_offsets(self, count) -> np.ndarray:
        """Sub-sample trigger time offsets of `count` records in seconds
        (GetTriggerTimeOffset64 / GetValuesTriggerTimeOffsetBulk64)."""
        if count == 1:
            t, unit = ctypes.c_int64(), ctypes.c_int32()
            self._call("GetTriggerTimeOffset64", self.handle,
                       ctypes.byref(t), ctypes.byref(unit), 0)
            return np.array([t.value * _TIME_UNIT_FACTOR[unit.value]])
        times = (ctypes.c_int64 * count)()
        units = (ctypes.c_int32 * count)()
        self._call("GetValuesTriggerTimeOffsetBulk64", self.handle, times,
                   units, 0, count - 1)
        return np.array([times[i] * _TIME_UNIT_FACTOR[units[i]]
                         for i in range(count)])

    def trigger_info(self, count):
        """GetTriggerInfoBulk (ps3000a, ps5000a): per record trigger index,
        time stamp counter (samples since the previous trigger) and status.
        Status 0x01000000 (PICO_DEVICE_TIME_STAMP_RESET) is accepted."""
        if not self.fam.trig_info:
            raise ExceptionNotSupported(
                f"trigger information is not available in the "
                f"{self.fam.prefix} driver")
        info = (_TriggerInfo * count)()
        self._call("GetTriggerInfoBulk", self.handle, info, 0, count - 1,
                   ok=(_PICO_OK, 0x01000000))
        return [dict(segment=i.segmentIndex, trigger_index=i.triggerIndex,
                     trigger_time=i.triggerTime *
                     _TIME_UNIT_FACTOR[i.timeUnits],
                     timestamp=i.timeStampCounter, status=i.status)
                for i in info]

    # ----- streaming --------------------------------------------------------
    def run_streaming(self, codes, interval, pre, post, autostop, ratio,
                      mode, bufsize) -> float:
        """Start streaming; returns the actual sampling interval in s."""
        aggregate = mode == _RATIO_MODES["AGGREGATE"]
        bufs = {}
        for name, code in codes.items():
            mx = np.zeros(bufsize, np.int16)
            mn = np.zeros(bufsize, np.int16) if aggregate else None
            self._register(code, mx, mn, bufsize, 0, mode)
            bufs[name] = (mx, mn)
        #> Pick a time unit so that the interval is an integer with
        #> at least ~3 significant digits (PS, NS, US, MS).
        for unit in (1, 2, 3, 4):
            if interval / _TIME_UNIT_FACTOR[unit] < 1e6:
                break
        value = ctypes.c_uint32(max(1, round(interval /
                                             _TIME_UNIT_FACTOR[unit])))
        stream = dict(bufs=bufs, chunks=[], autostop=False, trigger=None)

        #> The driver reuses the buffers, so every new part is copied out.
        def _ready(handle, n, start, ovf, trig_at, triggered, auto, param):
            """Driver callback (runs in the driver's thread)."""
            chunk = {k: (mx[start:start + n].copy(),
                         None if mn is None else mn[start:start + n].copy())
                     for k, (mx, mn) in bufs.items()}
            stream["chunks"].append((chunk, ovf,
                                     trig_at if triggered else None))
            if auto:
                stream["autostop"] = True
        stream["cb"] = _StreamingReadyType(_ready)
        self._stream = stream
        self._call("RunStreaming", self.handle, ctypes.byref(value), unit,
                   pre, post, int(autostop), ratio, mode, bufsize)
        return value.value * _TIME_UNIT_FACTOR[unit]

    def stream_poll(self):
        """Return (list of (chunk, overflow, trigger index or None),
        autostop flag)."""
        stream = self._stream
        stream["chunks"] = []
        self._call("GetStreamingLatestValues", self.handle,
                   ctypes.cast(stream["cb"], _ptr), None,
                   ok=(_PICO_OK, _PICO_BUSY))
        return stream["chunks"], stream["autostop"]

    # ----- signal generator -------------------------------------------------
    def siggen_builtin(self, offset_uv, pkpk_uv, wave, f0, f1, inc, dwell,
                       sweep, op, shots, sweeps, ttype, tsrc, ext):
        """SetSigGenBuiltIn / SetSigGenBuiltInV2 (offset and amplitude in
        microvolts, frequencies in Hz, dwell time in s). Models without a
        generator answer with a "not supported" status."""
        self._call(self.fam.builtin, self.handle, offset_uv, pkpk_uv, wave,
                   f0, f1, inc, dwell, sweep, op, shots, sweeps, ttype, tsrc,
                   ext)

    def siggen_limits(self):
        """SigGenArbitraryMinMaxValues: (min sample value, max sample value,
        min length, max length) of the AWG buffer."""
        vmin, vmax = ctypes.c_int16(), ctypes.c_int16()
        lmin, lmax = ctypes.c_uint32(), ctypes.c_uint32()
        self._call("SigGenArbitraryMinMaxValues", self.handle,
                   ctypes.byref(vmin), ctypes.byref(vmax),
                   ctypes.byref(lmin), ctypes.byref(lmax))
        return vmin.value, vmax.value, lmin.value, lmax.value

    def _phase(self, freq, length) -> int:
        """SigGenFrequencyToPhase: DDS delta phase giving `freq` Hz for a
        waveform of `length` samples (single index mode)."""
        phase = ctypes.c_uint32()
        self._call("SigGenFrequencyToPhase", self.handle, freq, 0, length,
                   ctypes.byref(phase))
        return phase.value

    def siggen_arb(self, offset_uv, pkpk_uv, samples, f0, f1, inc, dwell,
                   sweep, op, shots, sweeps, ttype, tsrc, ext):
        """SetSigGenArbitrary. Frequencies are converted to delta phases;
        the dwell time is given to the driver in AWG clock periods
        (_Family.awg_tick; VERIFY for ps2000a/ps3000a). The sample buffer is
        kept alive in self._keep_awg."""
        n = len(samples)
        buf = np.ascontiguousarray(samples, np.int16)
        self._keep_awg = buf
        p0, p1 = self._phase(f0, n), self._phase(f1, n)
        pinc = self._phase(inc, n) if inc > 0 else 0
        dwell_count = max(1, round(dwell / self.fam.awg_tick))
        self._call("SetSigGenArbitrary", self.handle, offset_uv, pkpk_uv, p0,
                   p1, pinc, dwell_count, buf.ctypes.data, n, sweep, op, 0,
                   shots, sweeps, ttype, tsrc, ext)

    def siggen_soft(self, state):
        """SigGenSoftwareControl: software trigger / gate (1 = on)."""
        self._call("SigGenSoftwareControl", self.handle, state)



# *****************************************************************************
# Simulated backend (tests without hardware and driver)
# *****************************************************************************
#> Instruments the simulator can imitate (OPEN SIM <variant>): driver family,
#> analog channels, sample memory, MSO digital inputs, lowest and highest
#> input range index of _RANGES and whether a signal generator exists. The
#> values only have to be plausible; the simulator is a test tool.
_SIM_MODELS = {
    "5443D": dict(family="PS5000A", channels=4, memory=512 * 2 ** 20,
                  mso=False, ranges=(0, 10), siggen=True),
    "2408B": dict(family="PS2000A", channels=4, memory=128 * 2 ** 20,
                  mso=False, ranges=(2, 10), siggen=True),
    "2204A": dict(family="PS2000A", channels=2, memory=8 * 2 ** 20,
                  mso=False, ranges=(2, 10), siggen=False),
    "3404D MSO": dict(family="PS3000A", channels=4, memory=512 * 2 ** 20,
                      mso=True, ranges=(1, 10), siggen=True),
    "3206D": dict(family="PS3000A", channels=2, memory=256 * 2 ** 20,
                  mso=False, ranges=(1, 10), siggen=True),
    "4824A": dict(family="PS4000A", channels=8, memory=256 * 2 ** 20,
                  mso=False, ranges=(0, 11), siggen=True),
}


#> Simulated model used by "OPEN <family> SIM"
_SIM_DEFAULTS = {"PS5000A": "5443D", "PS2000A": "2408B", "PS3000A": "3206D",
                 "PS4000A": "4824A"}


class _SimBackend:
    """Simulated PicoScope (default: the 4-channel 5443D, others from
    _SIM_MODELS). Inputs see a sine wave: the generator signal when the
    generator is on, otherwise 1 kHz, 1 Vpp. A trigger whose level the
    signal never reaches never fires, unless the auto trigger is set - this
    allows testing WAIT/STOP. The behaviour that differs between the
    driver families (selectable resolution, timebase formulas, missing
    functions) follows the real drivers."""

    def __init__(self, model="5443D"):
        """Simulated state: channels by driver code, ports, segmentation,
        the last trigger specification, generator and run descriptions.
        `model` is a key of _SIM_MODELS.
        """
        if model not in _SIM_MODELS:
            raise ExceptionPicoscope(
                f"unknown simulated model '{model}', expected one of: "
                f"{', '.join(_SIM_MODELS)}")
        spec = _SIM_MODELS[model]
        self.VARIANT = model
        self.fam = _FAMILIES[spec["family"]]
        self.FAMILY = spec["family"]
        self.MEMORY = spec["memory"]       # samples at 8 bits
        self.mso = spec["mso"]
        self.range_limits = spec["ranges"]
        self.siggen = spec["siggen"]
        self.res = 0
        self.ch = {i: dict(enabled=False, coupling=1, range=8, offset=0.0)
                   for i in range(spec["channels"])}
        self.ports = {0x80: False, 0x81: False}
        self.segments = 1
        self.captures = 1
        self.trigger = None
        self.gen = None
        self.run = None
        self.stream = None
        self.is_open = False

    def _no_function(self, name):
        """The error of a driver that lacks function <prefix><name>."""
        return ExceptionNotSupported(
            f"the {self.fam.prefix} driver has no {name}")

    # ----- device -----------------------------------------------------------
    def enumerate(self):
        """The simulated serial number."""
        return ["SIM0001"]

    def open(self, serial, resolution):
        """Accept '' or the simulated serial number; return the power state."""
        if serial and serial != "SIM0001":
            raise _driver_error(f"{self.fam.prefix}OpenUnit", 0x03)
        self.res = resolution
        self.is_open = True
        return self.power_source()

    def close(self):
        """Mark the simulated unit closed."""
        self.is_open = False

    def unit_info(self, info):
        """Fixed PICO_INFO strings of the simulated instrument."""
        return {0: "SIM 1.0", 1: "3.0", 2: "1", 3: self.VARIANT,
                4: "SIM0001", 5: "01Jan26", 6: "1.0", 7: "1", 8: "1",
                9: "1.0.0.0", 10: "1.0.0.0"}[info]

    def power_source(self):
        """ps2000a units are bus-powered; the others use the adaptor."""
        return "USB" if self.FAMILY == "PS2000A" else "DC"

    def change_power(self, dc):
        """Nothing to do in the simulator (ps2000a has no such function)."""
        if self.FAMILY == "PS2000A":
            raise self._no_function("ChangePowerSource")

    def flash_led(self, count):
        """Nothing to do in the simulator."""
        pass

    def set_resolution(self, res):
        """Store the resolution code (used by max_adc and the timebase);
        only ps5000a has a selectable resolution."""
        if not self.fam.resolution:
            raise self._no_function("SetDeviceResolution")
        self.res = res

    def max_adc(self):
        """ps5000a: 32512 at 8 bits, 32767 otherwise; ps2000a/ps3000a are
        8-bit (32512), ps4000a 12-bit (32767)."""
        if self.FAMILY == "PS5000A":
            return 32512 if self.res == 0 else 32767
        return 32767 if self.FAMILY == "PS4000A" else 32512

    # ----- inputs -----------------------------------------------------------
    def set_channel(self, ch, enabled, coupling, range_code, offset):
        """Store the channel; reject a range the model does not have and an
        offset outside offset_limits like the driver does.
        """
        if ch not in self.ch:
            raise _driver_error(f"{self.fam.prefix}SetChannel", 0x10)
        lo_range, hi_range = self.range_limits
        if not lo_range <= range_code <= hi_range:
            raise _driver_error(f"{self.fam.prefix}SetChannel", 0x0F)
        lo, hi = self.offset_limits(range_code, coupling)
        if not lo <= offset <= hi:
            raise ExceptionPicoscope(
                f"{self.fam.prefix}SetChannel failed: "
                f"PICO_INVALID_ANALOGUE_OFFSET")
        self.ch[ch] = dict(enabled=enabled, coupling=coupling,
                           range=range_code, offset=offset)

    def set_bandwidth(self, ch, bw):
        """The simulated signal has no bandwidth limit; ps2000a has no
        bandwidth limiter function."""
        if self.FAMILY == "PS2000A":
            raise self._no_function("SetBandwidthFilter")

    def offset_limits(self, range_code, coupling):
        """Approximate offset limits (+-0.25 V up to +-200 mV, +-2.5 V up
        to +-2 V, +-20 V above).
        """
        lim = 0.25 if range_code <= 4 else (2.5 if range_code <= 7 else 20.0)
        return -lim, lim

    def set_digital_port(self, port, enabled, level_counts):
        """MSO models store the port; the others answer PICO_NOT_USED."""
        if not self.mso:
            raise _driver_error(f"{self.fam.prefix}SetDigitalPort", 0x3F)
        self.ports[port] = enabled

    # ----- timebase and memory ----------------------------------------------
    def _n_enabled(self):
        """Number of enabled analog channels (at least 1)."""
        return max(1, sum(1 for c in self.ch.values() if c["enabled"]))

    def min_timebase(self, flags, res):
        """Fastest timebase per resolution and number of channels (ps5000a:
        guide 3.6 tables; ps2000a/ps3000a: 1, 2, 4 ns for 1, 2, 3-4
        channels; ps4000a: always timebase 0 = 12.5 ns).
        """
        n = bin(flags & 0xFF).count("1") or 1
        if self.FAMILY == "PS4000A":
            tb = 0
        elif self.FAMILY != "PS5000A" or res == 0:
            tb = {1: 0, 2: 1}.get(n, 2)
        elif res == 1:
            tb = {1: 1, 2: 2}.get(n, 3)
        elif res in (2, 3):
            tb = 3
        else:
            tb = 4
        return tb, self._interval(tb)

    def _interval(self, tb):
        """Sampling interval formulas of the programmer's guides."""
        if self.FAMILY == "PS4000A":
            return (tb + 1) / 80e6
        if self.FAMILY != "PS5000A" or self.res == 0:
            return 2 ** tb * 1e-9 if tb < 3 else (tb - 2) / 125e6
        if self.res == 1:
            return 2 ** (tb - 1) / 500e6 if tb < 4 else (tb - 3) / 62.5e6
        if self.res in (2, 3):
            return (tb - 2) / 125e6
        return (tb - 3) / 62.5e6

    def timebase(self, tb, nsamples):
        """Mimic ps5000aGetTimebase2: None when the timebase is invalid for
        the resolution/channels or the samples do not fit the memory
        (shared by the enabled channels and the segments).
        """
        n = self._n_enabled()
        if self.res == 3 and n > 2 or self.res == 4 and n > 1:
            return None
        flags = sum(1 << i for i, c in self.ch.items() if c["enabled"])
        if tb < self.min_timebase(flags, self.res)[0] or tb > 2 ** 32 - 2:
            return None
        mem = self.MEMORY // (1 if self.res == 0 else 2)
        mx = mem // {1: 1, 2: 2}.get(n, 4) // self.segments
        if nsamples > mx:
            return None
        return self._interval(tb), mx

    def max_segments(self):
        """Fixed number of simulated segments."""
        return 250_000

    def memory_segments(self, n):
        """Store the segmentation; return samples per segment."""
        if n > self.max_segments():
            raise ExceptionPicoscope(
                "ps5000aMemorySegments failed: PICO_TOO_MANY_SEGMENTS")
        self.segments = n
        return self.MEMORY // n

    def set_captures(self, n):
        """Store the number of rapid block records."""
        self.captures = n

    def set_ets(self, mode, cycles, interleave):
        """Store the ETS mode; the effective interval is 8 ns / interleave."""
        self.ets = (mode, interleave)
        return 8e-9 / max(1, interleave) if mode else 0.0

    # ----- trigger ----------------------------------------------------------
    def set_trigger(self, spec):
        """Keep the trigger specification for _triggers()."""
        self.trigger = spec

    def _triggers(self):
        """True when the simulated signal can fire the trigger."""
        spec = self.trigger
        if not spec or not spec["terms"] or spec["auto_us"]:
            return True
        #> Fires when some threshold lies within 90 % of the amplitude.
        #> spec["props"] tuples: (upper, upper hyst, lower, lower hyst,
        #> channel), see _HwBackend.set_trigger.
        for upper, _, _, _, ch in spec["props"]:
            if ch != _EXT and abs(upper) <= 0.9 * self._amplitude_counts(ch):
                return True
        return False

    def _amplitude_counts(self, ch):
        """Amplitude of the simulated signal in counts of channel `ch`."""
        amp = 0.5 if not self.gen else self.gen["pkpk"] / 2
        return amp / _RANGES[self.ch[ch]["range"]][0] * self.max_adc()

    # ----- block / rapid block ----------------------------------------------
    def run_block(self, pre, post, tb, callback=None):
        """Start a simulated capture that lasts as long as the real one
        (at least 5 ms). It completes only when the trigger can fire.
        """
        duration = (pre + post) * self._interval(tb) * self.captures
        self.run = dict(pre=pre, post=post, tb=tb, start=time.monotonic(),
                        duration=max(duration, 0.005),
                        fires=self._triggers(), stopped=False)
        if callback is not None and self.run["fires"]:
            threading.Timer(self.run["duration"], callback,
                            args=(_PICO_OK,)).start()

    def is_ready(self):
        """True when the simulated capture time has elapsed."""
        r = self.run
        return bool(r and r["fires"] and not r["stopped"] and
                    time.monotonic() - r["start"] >= r["duration"])

    def stop(self):
        """Abort: remember how many records were complete (rapid block)
        and stop streaming.
        """
        if self.run and not self.is_ready():
            elapsed = time.monotonic() - self.run["start"]
            self.run["done"] = (int(self.captures * elapsed /
                                    self.run["duration"])
                                if self.run["fires"] else 0)
            self.run["stopped"] = True
        if self.stream:
            self.stream["running"] = False

    def n_captures(self):
        """Completed records (all when ready, partial after stop)."""
        r = self.run
        if r is None:
            return 0
        if r["stopped"]:
            return min(self.captures, r.get("done", 0))
        return self.captures if self.is_ready() else 0

    def _signal(self, ch, n, dt, phase, digital=False):
        """Simulated ADC counts of channel `ch`: generator signal or 1 kHz
        1 Vpp sine, plus channel offset and 2 mV noise. Digital ports
        give a counter pattern.
        """
        if digital:
            return (np.arange(n) & 0xFF).astype(np.int16)
        g = self.gen
        freq = g["f0"] if g else 1000.0
        amp = g["pkpk"] / 2 if g else 0.5
        dc = g["offset"] if g else 0.0
        t = np.arange(n) * dt
        v = dc + amp * np.sin(2 * np.pi * freq * t + phase)
        c = self.ch[ch]
        v = v + c["offset"] + np.random.normal(0, 0.002, n)
        counts = v / _RANGES[c["range"]][0] * self.max_adc()
        return np.clip(np.round(counts), -32767, 32767).astype(np.int16)

    def get_values(self, codes, n_raw, ratio, mode, count, abort, ets=False):
        """Same contract as _HwBackend.get_values, data from _signal
        (downsampling is computed here as the driver would do).
        """
        if abort.is_set():
            raise _Aborted()
        dt = self._interval(self.run["tb"]) if self.run else 1e-6
        n_out = n_raw // ratio if mode else n_raw
        data = {}
        for name, code in codes.items():
            mx = np.zeros((count, n_out), np.int16)
            mn = np.zeros((count, n_out), np.int16) if mode == 1 else None
            for rec in range(count):
                raw = self._signal(code, n_raw, dt, 0.3 * rec,
                                   digital=code >= 0x80)
                if not mode:
                    mx[rec] = raw
                else:
                    blocks = raw[:n_out * ratio].reshape(n_out, ratio)
                    if mode == 1:
                        mx[rec], mn[rec] = blocks.max(1), blocks.min(1)
                    elif mode == 2:
                        mx[rec] = blocks[:, 0]
                    else:
                        mx[rec] = blocks.mean(1).round()
            data[name] = (mx, mn)
        overflow = np.zeros(count, np.int16)
        times = None
        if ets:
            times = np.arange(n_out) * dt / max(1, ets)
        return data, overflow, times

    def trigger_offsets(self, count):
        """The simulated trigger is always exactly on a sample."""
        return np.zeros(count)

    def trigger_info(self, count):
        """Trigger information with evenly spaced time stamps (only ps3000a
        and ps5000a have the function)."""
        if not self.fam.trig_info:
            raise self._no_function("GetTriggerInfoBulk")
        dt = self._interval(self.run["tb"]) if self.run else 1e-6
        step = int((self.run["pre"] + self.run["post"]) * 1.1) if self.run \
            else 1
        return [dict(segment=i, trigger_index=self.run["pre"],
                     trigger_time=0.0, timestamp=i * step, status=0)
                for i in range(count)] if dt else []

    # ----- streaming --------------------------------------------------------
    def run_streaming(self, codes, interval, pre, post, autostop, ratio,
                      mode, bufsize):
        """Start simulated streaming; data are generated from the elapsed
        time in stream_poll. Returns the interval unchanged.
        """
        self.stream = dict(codes=codes, dt=interval, start=time.monotonic(),
                           sent=0, total=pre + post if autostop else None,
                           ratio=ratio, mode=mode, bufsize=bufsize,
                           running=True)
        return interval

    def stream_poll(self):
        """Return the samples due since the previous poll (same contract
        as _HwBackend.stream_poll). The first chunk reports the trigger at
        index 0.
        """
        s = self.stream
        if not s["running"]:
            return [], True
        due = int((time.monotonic() - s["start"]) / s["dt"]) - s["sent"]
        if s["total"] is not None:
            due = min(due, s["total"] - s["sent"])
        due = min(due, s["bufsize"] * max(1, s["ratio"]))
        if due <= 0:
            return [], s["total"] is not None and s["sent"] >= s["total"]
        ratio = s["ratio"] if s["mode"] else 1
        n_out = due // ratio
        if n_out == 0:
            return [], False
        chunk = {}
        for name, code in s["codes"].items():
            raw = self._signal(code, n_out * ratio, s["dt"],
                               2 * np.pi * 1000 * s["sent"] * s["dt"],
                               digital=code >= 0x80)
            if s["mode"] == 1:
                b = raw.reshape(n_out, ratio)
                chunk[name] = (b.max(1), b.min(1))
            else:
                chunk[name] = (raw[::ratio][:n_out], None)
        s["sent"] += n_out * ratio
        auto = s["total"] is not None and s["sent"] >= s["total"]
        trig = 0 if s["sent"] == n_out * ratio else None
        return [(chunk, 0, trig)], auto

    # ----- signal generator -------------------------------------------------
    def siggen_builtin(self, offset_uv, pkpk_uv, wave, f0, f1, inc, dwell,
                       sweep, op, shots, sweeps, ttype, tsrc, ext):
        """Store the generator signal fed to the simulated inputs; the
        'off' setting (0 V DC) removes it. Models without a generator
        answer like the driver (PICO_NO_SIGNAL_GENERATOR).
        """
        if not self.siggen:
            raise _driver_error(f"{self.fam.prefix}SetSigGenBuiltIn", 0x13)
        self.gen = (None if pkpk_uv == 0 and offset_uv == 0 and wave == 8
                    else dict(offset=offset_uv * 1e-6, pkpk=pkpk_uv * 1e-6,
                              f0=f0, wave=wave))

    def siggen_limits(self):
        """AWG limits similar to the 5000D (32768 samples)."""
        return -32768, 32767, 1, 32768

    def siggen_arb(self, offset_uv, pkpk_uv, samples, f0, f1, inc, dwell,
                   sweep, op, shots, sweeps, ttype, tsrc, ext):
        """Store the AWG amplitude; the inputs see a sine of that size."""
        self.gen = dict(offset=offset_uv * 1e-6, pkpk=pkpk_uv * 1e-6, f0=f0,
                        wave=-1)

    def siggen_soft(self, state):
        """Nothing to do in the simulator."""
        pass


# *****************************************************************************
# Main class
# *****************************************************************************
class Picoscope:
    """PicoScope 2000, 3000, 4000 and 5000 series (drivers ps2000a, ps3000a,
    ps4000a, ps5000a) controlled by short text commands.

    OPEN finds the connected instrument, loads the matching driver and reads the model;
    commands the model cannot do raise ExceptionNotSupported.

    Parameters
    ----------
    strict : bool
        True (default): an invalid command raises ExceptionPicoscope.
        False: cmd() returns "ERR <reason>" instead.

    Thread safety: cmd() may be called from several threads. Driver calls are
    serialized by an internal lock, except STOP, which never waits for it,
    so that it can interrupt WAIT, a data transfer or streaming.
    """

    def __init__(self, strict: bool = True):
        """Create the object; the instrument is opened by the OPEN command."""
        self.strict = strict
        self._lock = threading.RLock()
        self._abort = threading.Event()
        #> Set while no STOP is being carried out; WAIT and every other
        #> command wait for it, so that nothing runs before the instrument
        #> and the state machine have finished stopping (see _stop).
        self._stop_idle = threading.Event()
        self._stop_idle.set()
        self._stop_count = 0
        self._stop_count_lock = threading.Lock()
        self._dev = None
        self._state = "CLOSED"
        self._sim = False
        self._power = ""
        self._variant = ""
        self._n_channels = 4
        self._mso = False
        self._max_adc = 32512
        self._family = ""
        self._gen_ok = True        # False: the model has no generator
        self._reset_settings()

    def _reset_settings(self):
        """Restore all default settings (used by __init__ and RESET)."""
        self.acq = _Acquisition()
        if self._dev is not None and not _FAMILIES[self._family].resolution:
            self.acq.bits = _FAMILIES[self._family].fixed_bits
        self.channels = {c: _Channel(c == "A") for c in _CHANNELS}
        self.ports = {p: _Digital() for p in _PORT}
        self.trig = _Trigger()
        self.gen = _Generator()
        self._clear_results()

    def _clear_results(self):
        """Forget the last run, its cached data and the streaming buffers."""
        self._run = None           # parameters of the last armed run
        self._data = None          # cached results of the last capture
        self._stream_data = {}
        self._stream_lock = threading.Lock()
        self._stream_thread = None
        self._stream_info = dict(samples=0, triggered_at=None, overflow=0)

    # =========================================================================
    # Public API
    # =========================================================================
    def cmd(self, commands: str) -> str:
        """Execute one or more text commands and return the text response."""
        responses = []
        #> Commands are separated by ";" or new lines and run in order.
        for command in re.split(r"[;\n]", commands):
            command = command.strip()
            if not command:
                continue
            try:
                answer = self._execute(command)
            except _Aborted:
                answer = "ABORTED"
            except ExceptionPicoscope as exc:
                #> Prefix the failing command so that the caller sees which
                #> one of several commands went wrong; the rest is skipped.
                message = f"{command}: {exc}"
                if self.strict:
                    raise type(exc)(message, exc.status) from None
                responses.append(f"ERR {message}")
                break
            #> Setting commands return None; only queries add a response.
            if answer is not None:
                responses.append(answer)
        return "; ".join(responses) if responses else "OK"

    #> Alias kept for the original draft of the module
    set = cmd

    def open(self, serial: str = ""):
        """Open the oscilloscope ('SIM' opens the simulator)."""
        return self.cmd(f"OPEN {serial}".strip())

    def close(self):
        """Close the instrument (command CLOSE)."""
        return self.cmd("CLOSE")

    def prepare(self):
        """Send all settings to the instrument (command ARM)."""
        return self.cmd("ARM")

    def start(self, callback=None):
        """Start the capture (command RUN). With `callback`, the function
        callback(status: int) is called from the driver's thread when a block
        or rapid block capture is complete."""
        with self._lock:
            return self._run_capture(callback)

    def stop(self):
        """Interrupt the running operation (command STOP); thread safe."""
        return self.cmd("STOP")

    def ready(self) -> bool:
        """True when the block / all rapid block records are captured."""
        return self.cmd("READY?") == "1"

    def wait(self, timeout: float = None) -> str:
        """Wait for the capture; returns READY, TIMEOUT or ABORTED (see
        WAIT). `timeout` in seconds, None = no limit.
        """
        return self._wait(timeout)

    def help(self, prefix: str = "") -> str:
        """Command reference, optionally only the lines starting with
        `prefix` (command HELP?).
        """
        return self.cmd(f"HELP? {prefix}".strip())

    def set_timebase(self, interval: float):
        """Request the sampling interval in seconds (OSC INTERVAL)."""
        return self.cmd(f"OSC INTERVAL {interval!r}")

    def set_preposttrigger(self, pretrigger: int, posttrigger: int):
        """Set the samples before and after the trigger."""
        return self.cmd(f"OSC PRETRIGGER {pretrigger}; OSC POSTTRIGGER "
                        f"{posttrigger}")

    def set_records(self, records: int):
        """Set the number of records per run (rapid block when > 1)."""
        return self.cmd(f"OSC RECORDS {records}")

    def set_awg(self, samples):
        """Load an arbitrary waveform normalized to -1..+1 and select it
        (GEN WAVE ARB)."""
        arr = np.asarray(samples, dtype=float).ravel()
        if arr.size < 1 or np.any(np.abs(arr) > 1.0 + 1e-9):
            raise ExceptionPicoscope("AWG samples must lie within -1..+1")
        with self._lock:
            self.gen.arb = arr
            self.gen.wave = "ARB"
            self._apply_generator()
        return "OK"

    # ----- data access ------------------------------------------------------
    def get_int(self, source: str = "A") -> np.ndarray:
        """Raw ADC counts, shape (records, samples). In AGGREGATE mode the
        maxima (use get_min for the minima)."""
        return self._fetch_source(source)[0]

    def get_min(self, source: str = "A") -> np.ndarray:
        """Minima of the AGGREGATE downsampling, shape (records, samples)."""
        mn = self._fetch_source(source)[1]
        if mn is None:
            raise ExceptionPicoscope("minima exist only with OSC DOWNSAMPLE "
                                    "AGGREGATE")
        return mn

    def get_float(self, source: str = "A", minimum: bool = False) \
            -> np.ndarray:
        """Data in volts multiplied by the channel's FACTOR, shape (records,
        samples)."""
        source = source.upper()
        if source not in _CHANNELS:
            raise ExceptionPicoscope("get_float needs an analog channel A-D")
        raw = self.get_min(source) if minimum else self.get_int(source)
        #> Range and offset valid at the time of the capture (stored by ARM),
        #> not the current settings, which may have changed since.
        #> The offset was added before digitization, so it is subtracted.
        ch = self._data["channels"][source]
        volts = raw.astype(float) / self._data["max_adc"] * ch["range"] \
            - ch["offset"]
        #> FACTOR is pure post-processing, so the current value is used.
        return volts * self.channels[source].factor

    def get_digital(self) -> np.ndarray:
        """MSO digital inputs as uint16, bit n = input Dn, shape (records,
        samples). NOT TESTED on hardware."""
        self._fetch()
        result = None
        for port, shift in (("D0", 0), ("D1", 8)):
            if port in self._data["raw"]:
                bits = (self._data["raw"][port][0].astype(np.uint16)
                        & 0xFF) << shift
                result = bits if result is None else result | bits
        if result is None:
            raise ExceptionPicoscope("no digital port was enabled")
        return result

    def get_time(self) -> np.ndarray:
        """Time axis in seconds relative to the trigger (ETS: sample times
        reported by the driver)."""
        self._fetch()
        d = self._data
        if d["ets_times"] is not None:
            return d["ets_times"]
        #> One downsampled value covers `ratio` raw samples. Sample index
        #> `pre` is the trigger point; a trigger delay shifts the record.
        ratio = d["ratio"] if d["ds_mode"] != "NONE" else 1
        return (np.arange(d["n"]) * ratio - d["pre"] + d["delay"]) * d["dt"]

    def get_trigger_times(self) -> np.ndarray:
        """Trigger time offsets of the records in seconds (sub-sample
        position of the trigger)."""
        self._fetch()
        with self._lock:
            return self._dev.trigger_offsets(self._data["records"])

    def get_trigger_info(self):
        """Trigger information of the records (list of dicts with segment,
        trigger_index, trigger_time, timestamp = sample count from the
        previous trigger point, status)."""
        self._fetch()
        with self._lock:
            return self._dev.trigger_info(self._data["records"])

    def get_stream(self, volts: bool = True) -> dict:
        """Streaming data received since the previous call: dict source ->
        ndarray (AGGREGATE adds 'X_MIN' keys). Volts for analog channels when
        `volts` is True."""
        #> Swap the buffer under the lock so that the streaming thread can
        #> continue appending while the data are converted here.
        with self._stream_lock:
            chunks, self._stream_data = self._stream_data, {}
        result = {}
        for key, parts in chunks.items():
            arr = np.concatenate(parts) if parts else np.zeros(0, np.int16)
            src = key.split("_")[0]
            if volts and src in _CHANNELS:
                r = self._run
                arr = arr.astype(float) / r["max_adc"] * \
                    r["channels"][src]["range"] - \
                    r["channels"][src]["offset"]
                arr = arr * self.channels[src].factor
            result[key] = arr
        return result

    def __enter__(self):
        """Context manager: `with Picoscope() as ps: ...`."""
        return self

    def __exit__(self, *exc):
        """Close the instrument at the end of the `with` block."""
        if self._state != "CLOSED":
            self.cmd("CLOSE")

    # =========================================================================
    # Command dispatcher
    # =========================================================================
    def _execute(self, command: str):
        """Execute one command (no ';') and return its response or None.

        The first word selects the handler. STOP and WAIT run without the
        lock: STOP must be able to interrupt a command that holds it, and
        WAIT takes the lock only for the short ps5000aIsReady calls so that
        other threads can still send commands (e.g. STOP or queries).
        """
        tokens = command.split()
        head = tokens[0].upper()
        args = tokens[1:]
        if head == "STOP":                 # never waits for the lock
            return self._stop()
        if head == "WAIT":
            return self._wait(_num(args[0], "s") if args else None)
        self._stop_idle.wait(5)
        with self._lock:
            name = head.rstrip("?")
            if name in _CHANNELS and len(name) == 1:
                self._check_channel(name)
                return self._cmd_channel(name, args, head.endswith("?"))
            if head in ("ALL", "ALL?"):
                return self._cmd_all(args, head.endswith("?"))
            if head in ("D0", "D1", "D0?", "D1?"):
                return self._cmd_digital(head.rstrip("?"), args,
                                         head.endswith("?"))
            handler = {
                "OSC": self._cmd_acq, "OSC?": self._cmd_acq,
                "TRG": self._cmd_trigger, "TRG?": self._cmd_trigger,
                "GEN": self._cmd_gen, "GEN?": self._cmd_gen,
            }.get(head)
            if handler:
                return handler(args, head.endswith("?"))
            simple = {
                "OPEN": self._cmd_open, "CLOSE": self._cmd_close,
                "DEVICES?": self._cmd_devices,
                "IDN?": self._cmd_idn, "INFO?": self._cmd_info,
                "POWER?": self._cmd_power, "POWER": self._cmd_power,
                "STATE?": lambda a: self._state,
                "CAPS?": self._cmd_caps,
                "LED": self._cmd_led, "RESET": self._cmd_reset,
                "HELP?": self._cmd_help, "HELP": self._cmd_help,
                "ARM": lambda a: self._arm() and None,
                "RUN": lambda a: self._run_capture(None),
                "READY?": self._cmd_ready,
                "CAPTURES?": self._cmd_captures,
                "OVERFLOW?": self._cmd_overflow,
                "TRIGTIME?": self._cmd_trigtime,
                "DATA?": self._cmd_data,
            }.get(head)
            if simple is None:
                raise ExceptionPicoscope("unknown command")
            if head == "POWER?":
                return simple(None)
            return simple(args)

    @staticmethod
    def _split_query(args):
        """Return (KEY, query flag, rest) of a group command."""
        if not args:
            raise ExceptionPicoscope("missing parameter")
        key = args[0].upper()
        query = key.endswith("?")
        return key.rstrip("?"), query, args[1:]

    @staticmethod
    def _need(rest, count=1):
        """Raise 'missing value' when `rest` has fewer than `count` items;
        return `rest` so the call can be used inline.
        """
        if len(rest) < count:
            raise ExceptionPicoscope("missing value")
        return rest

    def _check_channel(self, name):
        """Raise ExceptionNotSupported when the open instrument has no
        analog channel `name` (before OPEN every name is accepted and the
        settings of missing channels are dropped at OPEN)."""
        if self._dev is not None and _CHANNELS.index(name) >= self._n_channels:
            raise ExceptionNotSupported(
                f"the {self._variant} has no channel {name}")

    def _require_open(self):
        """Raise unless the instrument is open."""
        if self._dev is None:
            raise ExceptionPicoscope("the oscilloscope is not open")

    def _idle(self):
        """Settings changing the capture require that no capture runs."""
        if self._state in ("ARMED", "STREAMING"):
            raise ExceptionPicoscope("a capture is running, use STOP first")
        #> Changing a setting after a capture discards its cached data:
        #> they would no longer match the settings.
        if self._state == "READY":
            self._state = "IDLE"
            self._data = None

    # =========================================================================
    # Device commands
    # =========================================================================
    def _cmd_open(self, args):
        """OPEN [serial | family [serial] | SIM [variant]]: open the
        instrument and send all stored settings.

        * ``OPEN`` opens the first instrument found; the drivers are tried in
          the order ps5000a, ps4000a, ps3000a, ps2000a (``DEVICES?`` lists
          what is connected).
        * ``OPEN <serial>`` opens the instrument with that serial number
          whichever driver serves it; ``OPEN PS3000A [serial]`` restricts the
          search to one driver.
        * ``OPEN SIM [variant]`` opens a simulated instrument (5443D unless
          a variant of _SIM_MODELS is given).

        The VARIANT string of the instrument decides the capabilities: its
        second digit is the number of analog channels (2408B -> 4,
        4824A -> 8), "MSO" marks digital inputs, the driver family decides
        the rest. On any error the unit is closed again.
        """
        if self._dev is not None:
            raise ExceptionPicoscope("already open")
        args = list(args)
        #> "OPEN PS3000A SIM" (family first) selects the default simulated
        #> model of that family.
        family = ""
        if len(args) > 1 and args[0].upper() in _FAMILIES and \
                args[1].upper() == "SIM":
            family = args.pop(0).upper()
        sim = bool(args) and args[0].upper() == "SIM"
        if sim:
            variant = " ".join(args[1:]) or _SIM_DEFAULTS.get(family, "5443D")
            dev, serial = _SimBackend(variant.upper()), ""
        else:
            dev, serial = self._find_device(args)
        self._sim = sim
        self._family = dev.FAMILY
        #> Models without a selectable resolution have a fixed one (8 bits
        #> ps2000a/ps3000a, 12 bits ps4000a); a BITS the user entered
        #> before OPEN must agree with it, the default follows the model.
        fam = _FAMILIES[dev.FAMILY]
        if not fam.resolution:
            if self.acq.bits_set and self.acq.bits != fam.fixed_bits:
                raise ExceptionNotSupported(
                    f"the {dev.FAMILY.lower()} instruments have a fixed "
                    f"resolution of {fam.fixed_bits} bits, not "
                    f"{self.acq.bits}")
            self.acq.bits = fam.fixed_bits
        self._power = dev.open(serial or None, _RESOLUTIONS.get(
            self.acq.bits, 0))
        self._dev = dev
        try:
            self._variant = dev.unit_info(3)
            #> Variant 5443D, 2408B, 4824A: the second digit is the number
            #> of channels, "MSO" marks the digital inputs.
            m = re.match(r"\d(\d)\d\d", self._variant)
            self._n_channels = min(int(m.group(1)) if m else 4,
                                   fam.max_channels)
            self._mso = "MSO" in self._variant.upper()
            self._state = "IDLE"
            self._max_adc = dev.max_adc()
            for name in _CHANNELS:
                if _CHANNELS.index(name) >= self._n_channels:
                    self.channels[name].enabled = False
                else:
                    self._apply_channel(name)
            if self._mso:
                for port in _PORT:
                    self._apply_port(port)
            self._gen_ok = True
            self._apply_generator()
        except Exception:
            dev.close()
            self._dev = None
            self._state = "CLOSED"
            raise
        return None

    def _find_device(self, args):
        """Return (backend, serial) of the instrument to open for the
        arguments of OPEN (see _cmd_open); raises when none is found."""
        families = list(_FAMILY_ORDER)
        if args and args[0].upper() in _FAMILIES:
            families = [args.pop(0).upper()]
        wanted = args[0] if args else ""
        found = []
        for key in families:
            try:
                dev = _HwBackend(key)
            except ExceptionPicoscope as exc:
                if len(families) == 1:
                    raise
                found.append((key, None, str(exc)))
                continue
            for serial in dev.enumerate():
                found.append((key, serial, ""))
                if not wanted or wanted == serial:
                    return dev, serial
        if wanted:
            raise ExceptionPicoscope(
                f"no PicoScope with serial number {wanted} found")
        missing = [f"{k.lower()}: {m}" for k, ser, m in found if ser is None]
        raise ExceptionPicoscope(
            "no PicoScope found" + (" (" + "; ".join(missing) + ")"
                                    if missing else ""), 0x03)

    def _cmd_devices(self, args):
        """DEVICES?: the connected instruments that are not open, as
        'FAMILY:serial' separated by commas ('NONE' when there is none).
        An opened instrument is not listed by its driver."""
        found = []
        for key in _FAMILY_ORDER:
            for serial in _enumerate(_FAMILIES[key]):
                found.append(f"{key}:{serial}")
        return ",".join(found) or "NONE"

    def _cmd_close(self, args):
        """CLOSE: stop, switch the generator output to 0 V and close."""
        if self._dev is None:
            return None
        self._stop()
        try:
            if self.gen.enabled:
                self._siggen_off()
        finally:
            self._dev.close()
            self._dev = None
            self._state = "CLOSED"
            self._clear_results()
        return None

    def _siggen_off(self):
        """Output 0 V DC (the API has no 'off'). A model without a
        generator answers with a "not supported" error, which only means
        that there is nothing to switch off; it is remembered in _gen_ok."""
        try:
            self._dev.siggen_builtin(0, 0, _WAVES["DC"], 0, 0, 0, 0, 0, 0, 0,
                                     0, 0, 0, 0)
        except ExceptionNotSupported:
            self._gen_ok = False

    def _cmd_idn(self, args):
        """IDN?: '<variant> <serial number>'."""
        self._require_open()
        return f"{self._variant} {self._dev.unit_info(4)}"

    def _cmd_caps(self, args):
        """CAPS?: what the open instrument can do, as KEY=value pairs:
        driver family, variant, analog channels, MSO ports, selectable
        resolutions, pulse-width trigger, trigger information, signal
        generator and the simulator flag. The generator entry comes from the
        attempt to switch the output to 0 V at OPEN (see _siggen_off); a few
        features (bandwidth limiter, ETS) are decided by the driver per model
        and are reported as "Not supported" by the command that uses them.
        """
        self._require_open()
        fam = _FAMILIES[self._family]
        bits = (",".join(str(b) for b in _RESOLUTIONS) if fam.resolution
                else str(fam.fixed_bits))
        return (f"FAMILY={self._family} VARIANT={self._variant} "
                f"CHANNELS={self._n_channels} MSO={_fmt(self._mso)} "
                f"BITS={bits} PULSEWIDTH={_fmt(fam.pwq)} "
                f"TRIGINFO={_fmt(fam.trig_info)} "
                f"GENERATOR={_fmt(self._gen_ok)} SIM={_fmt(self._sim)}")

    def _cmd_info(self, args):
        """INFO?: all PICO_INFO strings as KEY=value pairs."""
        self._require_open()
        return " ".join(f"{name}={self._dev.unit_info(code)}"
                        for code, name in _UNIT_INFO)

    def _cmd_power(self, args):
        """POWER? (args None) reports the power source; POWER DC|USB
        confirms a change of the power source.
        """
        self._require_open()
        if args is None:
            return self._dev.power_source()
        self._need(args)
        self._idle()
        self._dev.change_power(_choice(args[0], ("DC", "USB"), "power")
                               == "DC")
        return None

    def _cmd_led(self, args):
        """LED <count>|ON|STOP: flash the front LED."""
        self._require_open()
        self._need(args)
        value = args[0].upper()
        count = 0 if value == "STOP" else (-1 if value == "ON" else
                                           _int(value))
        self._dev.flash_led(count)
        return None

    def _cmd_reset(self, args):
        """RESET: default settings, sent to the instrument when it is open."""
        self._idle()
        self._reset_settings()
        if self._dev is not None:
            if _FAMILIES[self._family].resolution:
                self._dev.set_resolution(_RESOLUTIONS[self.acq.bits])
            self._max_adc = self._dev.max_adc()
            for name in _CHANNELS:
                self._apply_channel(name)
            if self._mso:
                for port in _PORT:
                    self._apply_port(port)
            self._siggen_off()
        return None

    def _cmd_help(self, args):
        """HELP? [prefix]: lines of _HELP starting with the prefix."""
        prefix = " ".join(args).upper()
        lines = [f"{syntax:<44} {text}" for syntax, text in _HELP
                 if syntax.upper().startswith(prefix)]
        if not lines:
            raise ExceptionPicoscope(f"no command starts with '{prefix}'")
        return "\n".join(lines)

    # =========================================================================
    # Acquisition settings (O)
    # =========================================================================
    def _cmd_acq(self, args, summary):
        """OSC ... : acquisition settings (resolution, timebase, samples,
        records, mode, downsampling, streaming, ETS). `summary` is True for
        'OSC?'. Settings that change the capture require an idle instrument.
        """
        a = self.acq
        if summary:
            return (f"BITS={a.bits} INTERVAL={_fmt(self._interval_now())} "
                    f"PRETRIGGER={a.pre} POSTTRIGGER={a.post} "
                    f"RECORDS={a.records} MODE={a.mode} "
                    f"DOWNSAMPLE={a.ds_mode},{a.ds_ratio} "
                    f"ETS={a.ets} STREAMBUF={a.streambuf} "
                    f"AUTOSTOP={_fmt(a.autostop)}")
        key, query, rest = self._split_query(args)
        if key == "RESET":
            #> Everything back to defaults, identical to the RESET command.
            return self._cmd_reset(rest)
        if key == "BITS":
            if query:
                return str(a.bits)
            bits = _int(self._need(rest)[0])
            if bits not in _RESOLUTIONS:
                raise ExceptionPicoscope("resolution must be 8, 12, 14, 15 "
                                        "or 16 bits")
            fam = _FAMILIES[self._family] if self._family else None
            if fam is not None and not fam.resolution:
                if bits != fam.fixed_bits:
                    raise ExceptionNotSupported(
                        f"the {self._variant} has a fixed resolution of "
                        f"{fam.fixed_bits} bits")
            self._idle()
            if self._dev is not None and fam.resolution:
                self._dev.set_resolution(_RESOLUTIONS[bits])
                self._max_adc = self._dev.max_adc()
                #> The guide (4.49) requires SetChannel after a change
                for name in _CHANNELS:
                    self._apply_channel(name)
            a.bits, a.bits_set = bits, True
        elif key in ("INTERVAL", "TIMEBASE"):
            if query:
                return _fmt(self._interval_now())
            value = _num(self._need(rest)[0], "s")
            if value <= 0:
                raise ExceptionPicoscope("interval must be positive")
            self._idle()
            a.interval, a.tbindex = value, None
        elif key == "TBINDEX":
            if query:
                return str(self._run["tb"] if self._run else a.tbindex)
            self._idle()
            a.tbindex = _int(self._need(rest)[0])
        elif key == "MININTERVAL":
            self._require_open()
            return _fmt(self._dev.min_timebase(self._flags(),
                                               _RESOLUTIONS[a.bits])[1])
        elif key in ("PRETRIGGER", "POSTTRIGGER", "RECORDS", "STREAMBUF"):
            attr = {"PRETRIGGER": "pre", "POSTTRIGGER": "post",
                    "RECORDS": "records", "STREAMBUF": "streambuf"}[key]
            if query:
                return str(getattr(a, attr))
            value = _int(self._need(rest)[0])
            if key in ("RECORDS", "STREAMBUF") and value < 1:
                raise ExceptionPicoscope(f"{key} must be at least 1")
            self._idle()
            setattr(a, attr, value)
        elif key == "SAMPLES":
            return str(a.samples)
        elif key == "MAXSAMPLES":
            self._require_open()
            self._apply_all_channels()
            self._dev.memory_segments(a.records)
            info = self._dev.timebase(self._find_timebase()[0], 0)
            return str(info[1] if info else 0)
        elif key == "MAXRECORDS":
            self._require_open()
            return str(self._dev.max_segments())
        elif key == "MODE":
            if query:
                return a.mode
            mode = _choice(self._need(rest)[0], ("BLOCK", "STREAM"), "mode")
            self._idle()
            a.mode = mode
        elif key == "DOWNSAMPLE":
            if query:
                return f"{a.ds_mode} {a.ds_ratio}"
            mode = _choice(self._need(rest)[0], _RATIO_MODES, "downsampling")
            ratio = _int(rest[1]) if len(rest) > 1 else \
                (1 if mode == "NONE" else a.ds_ratio)
            if ratio < 1:
                raise ExceptionPicoscope("ratio must be at least 1")
            self._idle()
            a.ds_mode, a.ds_ratio = mode, (1 if mode == "NONE" else ratio)
        elif key == "AUTOSTOP":
            if query:
                return _fmt(a.autostop)
            a.autostop = _onoff(self._need(rest)[0])
        elif key == "ETS":
            if query:
                return f"{a.ets} {a.ets_cycles} {a.ets_interleave}"
            mode = _choice(self._need(rest)[0], _ETS_MODES, "ETS mode")
            self._idle()
            a.ets = mode
            if len(rest) > 1:
                a.ets_cycles = _int(rest[1])
            if len(rest) > 2:
                a.ets_interleave = _int(rest[2])
        else:
            raise ExceptionPicoscope(f"unknown parameter '{key}'")
        return None

    def _interval_now(self) -> float:
        """Actual interval after ARM, otherwise the requested one."""
        if self._run is not None:
            return self._run["dt"]
        return self.acq.interval

    # =========================================================================
    # Channels (A-D) and digital ports (D0, D1)
    # =========================================================================
    def _cmd_channel(self, name, args, summary):
        """A..D ... : analog channel settings; 'X?' when `summary`.

        With an open instrument the channel is sent at once; when the
        driver rejects it (e.g. offset out of limits) the previous settings
        are restored so that the stored state matches the instrument.
        """
        ch = self.channels[name]
        if summary:
            return (f"{_fmt(ch.enabled)} COUPLING={ch.coupling} "
                    f"RANGE={_fmt(ch.range_v)} OFFSET={_fmt(ch.offset)} "
                    f"BW={ch.bw} FACTOR={_fmt(ch.factor)}")
        key, query, rest = self._split_query(args)
        old = (ch.enabled, ch.coupling, ch.range_idx, ch.offset, ch.bw)
        if key == "FACTOR":
            #> Output scaling only: no instrument call and no idle check,
            #> RANGE/OFFSET/trigger levels stay in input volts.
            if query:
                return _fmt(ch.factor)
            value = _num(self._need(rest)[0])
            if value == 0 or not math.isfinite(value):
                raise ExceptionPicoscope("FACTOR must be a non-zero number")
            ch.factor = value
            return None
        if key in ("ON", "OFF"):
            self._idle()
            if key == "ON" and self._dev is not None and \
                    _CHANNELS.index(name) >= self._n_channels:
                raise ExceptionPicoscope(
                    f"the {self._variant} has no channel {name}")
            ch.enabled = key == "ON"
        elif key == "COUPLING":
            if query:
                return ch.coupling
            self._idle()
            ch.coupling = _choice(self._need(rest)[0], _COUPLING, "coupling")
        elif key == "RANGE":
            if query:
                return _fmt(ch.range_v)
            self._idle()
            ch.range_idx = _range_index(_num(self._need(rest)[0], "V"))
        elif key == "OFFSET":
            if query:
                return _fmt(ch.offset)
            self._idle()
            ch.offset = _num(self._need(rest)[0], "V")
        elif key == "OFFSETLIMITS":
            self._require_open()
            lo, hi = self._dev.offset_limits(_RANGES[ch.range_idx][1],
                                             _COUPLING[ch.coupling])
            return f"{_fmt(lo)} {_fmt(hi)}"
        elif key == "BW":
            if query:
                return ch.bw
            self._idle()
            ch.bw = _choice(self._need(rest)[0], _BANDWIDTH, "bandwidth")
        else:
            raise ExceptionPicoscope(f"unknown parameter '{key}'")
        try:
            self._apply_channel(name)
        except ExceptionPicoscope:
            ch.enabled, ch.coupling, ch.range_idx, ch.offset, ch.bw = old
            raise
        return None

    def _cmd_all(self, args, summary):
        """ALL <channel command> : the same channel command for every analog
        channel of the model, e.g. ``ALL COUPLING DC``, ``ALL RANGE 2``,
        ``ALL OFF; A ON``. Before OPEN it means A-D.

        * ``ALL?`` gives one summary line per channel; ``ALL <KEY>?`` gives
          the values of all channels in the order A, B, ... separated by
          spaces (OFFSETLIMITS pairs are separated by ``;``).
        * The command is all or nothing: when the driver rejects it for one
          channel, the channels already changed are restored.
        """
        names = _CHANNELS[:self._n_channels]
        if summary:
            return "\n".join(f"{n}: {self._cmd_channel(n, [], True)}"
                             for n in names)
        key, query, _rest = self._split_query(args)
        if query:
            sep = " ; " if key == "OFFSETLIMITS" else " "
            return sep.join(self._cmd_channel(n, args, False) for n in names)
        fields = ("enabled", "coupling", "range_idx", "offset", "bw",
                  "factor")
        saved = {n: tuple(getattr(self.channels[n], f) for f in fields)
                 for n in names}
        done = []
        try:
            for n in names:
                self._cmd_channel(n, args, False)
                done.append(n)
        except ExceptionPicoscope:
            for n in done:
                for f, v in zip(fields, saved[n]):
                    setattr(self.channels[n], f, v)
                self._apply_channel(n)
            raise
        return None

    def _apply_channel(self, name):
        """Send the settings of channel `name` to the instrument (no-op
        when closed or when the model does not have the channel).
        """
        if self._dev is None:
            return
        ch = self.channels[name]
        if _CHANNELS.index(name) >= self._n_channels:
            return
        self._dev.set_channel(_CH[name], ch.enabled, _COUPLING[ch.coupling],
                              _RANGES[ch.range_idx][1], ch.offset)
        try:
            self._dev.set_bandwidth(_CH[name], _BANDWIDTH[ch.bw])
        except ExceptionNotSupported:
            #> A model without the limiter is fine as long as FULL is wanted.
            if ch.bw != "FULL":
                raise

    def _apply_all_channels(self):
        """Send all channels and (MSO only) digital ports."""
        for name in _CHANNELS:
            self._apply_channel(name)
        if self._mso:
            for port in _PORT:
                self._apply_port(port)

    def _cmd_digital(self, name, args, summary):
        """D0/D1 ... : MSO digital ports. On a model without digital
        inputs, enabling a port is an error; LEVEL is only stored.
        NOT TESTED on hardware.
        """
        port = self.ports[name]
        if summary:
            return f"{_fmt(port.enabled)} LEVEL={_fmt(port.level)}"
        key, query, rest = self._split_query(args)
        if key in ("ON", "OFF"):
            self._idle()
            port.enabled = key == "ON"
        elif key == "LEVEL":
            if query:
                return _fmt(port.level)
            level = _num(self._need(rest)[0], "V")
            if abs(level) > _EXT_FULL_SCALE:
                raise ExceptionPicoscope("logic level must be within +-5 V")
            self._idle()
            port.level = level
        else:
            raise ExceptionPicoscope(f"unknown parameter '{key}'")
        if self._dev is not None:
            if not self._mso:
                if port.enabled:
                    port.enabled = False
                    raise ExceptionNotSupported(
                        f"the {self._variant} has no digital inputs")
                return None
            self._apply_port(name)
        return None

    def _apply_port(self, name):
        """Send port `name` to the instrument; the logic level is converted
        to counts (+-32767 = +-5 V, guide 4.50). NOT TESTED.
        """
        port = self.ports[name]
        counts = int(round(port.level / _EXT_FULL_SCALE * _EXT_MAX_COUNTS))
        self._dev.set_digital_port(_PORT[name], port.enabled, counts)

    def _flags(self) -> int:
        """PS5000A_CHANNEL_FLAGS of the enabled channels and ports."""
        flags = sum(_CH_FLAGS[n] for n, c in self.channels.items()
                    if c.enabled)
        flags += sum(_CH_FLAGS[n] for n, p in self.ports.items()
                     if p.enabled)
        return flags

    def _sources(self) -> dict:
        """Enabled data sources: name -> driver code."""
        src = {n: _CH[n] for n, c in self.channels.items() if c.enabled}
        src.update({n: _PORT[n] for n, p in self.ports.items() if p.enabled})
        return src

    # =========================================================================
    # Trigger (T)
    # =========================================================================
    def _cmd_trigger(self, args, summary):
        """TRG ... : trigger settings. Sources (A-D, EXT) are handled by
        _cmd_trig_source, the pulse-width qualifier by _cmd_trig_pw.
        The trigger is sent to the instrument by ARM/RUN.
        """
        t = self.trig
        if summary:
            return self._trigger_summary()
        key, query, rest = self._split_query(args)
        if key in _CHANNELS or key == "EXT":
            if key != "EXT":
                self._check_channel(key)
            return self._cmd_trig_source(key, rest)
        if key == "EDGE":
            rest = self._need(rest, 3)
            src = _choice(rest[0], _CH, "trigger source")
            if src != "EXT":
                self._check_channel(src)
            direction = _choice(rest[1], _EDGE_DIRECTIONS, "direction")
            if src == "EXT" and direction not in _EXT_DIRECTIONS:
                raise ExceptionNotSupported("EXT supports only RISING, FALLING and BOTH "
                         "directions, ABOVE/BELOW do not work on the EXT "
                         "input")
            self._idle()
            t.sources = {src: _TrigSource()}
            t.sources[src].direction = direction
            t.sources[src].level = _num(rest[2], "V")
            t.digital, t.pw_type, t.pw_source = {}, "NONE", None
        elif key == "LOGIC":
            if query:
                return t.logic
            self._idle()
            t.logic = _choice(self._need(rest)[0], ("AND", "OR"), "logic")
        elif key == "DIG":
            rest = self._need(rest, 2)
            bit = _int(rest[0])
            if bit > 15:
                raise ExceptionPicoscope("digital bit must be 0..15")
            direction = _choice(rest[1], _DIG_DIRECTIONS, "direction")
            self._idle()
            if direction == "X":
                t.digital.pop(bit, None)
            else:
                t.digital[bit] = direction
        elif key == "PW":
            return self._cmd_trig_pw(rest)
        elif key == "DELAY":
            if query:
                return str(t.delay)
            self._idle()
            t.delay = _int(self._need(rest)[0])
        elif key == "AUTO":
            if query:
                return _fmt(t.auto)
            value = _num(self._need(rest)[0], "s")
            if value < 0:
                raise ExceptionPicoscope("auto trigger time must be >= 0")
            self._idle()
            t.auto = value
        elif key == "WITHINPRE":
            if query:
                return _fmt(t.within_pre)
            self._require_trigger_feature("WITHINPRE")
            self._idle()
            t.within_pre = _onoff(self._need(rest)[0])
        elif key == "EDGEDETECT":
            if query:
                return _fmt(t.edge_detect)
            self._require_trigger_feature("EDGEDETECT")
            self._idle()
            t.edge_detect = _onoff(self._need(rest)[0])
        elif key in ("CLEAR", "OFF"):
            self._idle()
            self.trig = _Trigger()
        else:
            raise ExceptionPicoscope(f"unknown parameter '{key}'")
        return None

    def _cmd_trig_source(self, src, rest):
        """TRG <src> DIR|LEVEL|LOWER|HYST|OFF: one analog trigger source.
        A source is created by its first setting.
        """
        t = self.trig
        key, query, rest = self._split_query(rest)
        if key == "OFF":
            self._idle()
            t.sources.pop(src, None)
            return None
        s = t.sources.get(src)
        if query:
            if s is None:
                return "OFF"
            value = {"DIR": s.direction, "LEVEL": _fmt(s.level),
                     "LOWER": _fmt(s.lower),
                     "HYST": "AUTO" if s.hyst is None else _fmt(s.hyst)}
            if key not in value:
                raise ExceptionPicoscope(f"unknown parameter '{key}'")
            return value[key]
        self._idle()
        s = t.sources.setdefault(src, _TrigSource())
        value = self._need(rest)[0]
        if key == "DIR":
            direction = _choice(value, _DIRECTIONS, "direction")
            if src == "EXT" and direction not in _EXT_DIRECTIONS:
                raise ExceptionNotSupported(
                    "EXT supports only RISING, FALLING and BOTH directions, "
                    "ABOVE/BELOW do not work on the EXT input")
            s.direction = direction
        elif key == "LEVEL":
            s.level = _num(value, "V")
        elif key == "LOWER":
            s.lower = _num(value, "V")
        elif key == "HYST":
            s.hyst = None if value.upper() == "AUTO" else abs(_num(value, "V"))
        else:
            raise ExceptionPicoscope(f"unknown parameter '{key}'")
        return None

    def _cmd_trig_pw(self, rest):
        """TRG PW TYPE|SOURCE|DIR|LEVEL|LOWER|UPPER: pulse-width qualifier.
        The limits are stored in seconds and converted to samples at ARM.
        The qualifier uses the LOWER threshold of the source (the main
        trigger uses the upper one, guide 4.58): LEVEL is its voltage,
        by default the LEVEL of the source.
        """
        t = self.trig
        key, query, rest = self._split_query(rest)
        if self._family and not _FAMILIES[self._family].pwq:
            raise ExceptionNotSupported(
                f"the {self._variant} has no pulse-width trigger "
                f"({self._family.lower()} driver)")
        if query:
            value = {"TYPE": t.pw_type, "SOURCE": t.pw_source or "NONE",
                     "DIR": t.pw_direction, "LOWER": _fmt(t.pw_lower),
                     "UPPER": _fmt(t.pw_upper),
                     "LEVEL": "AUTO" if t.pw_level is None
                     else _fmt(t.pw_level)}
            if key not in value:
                raise ExceptionPicoscope(f"unknown parameter '{key}'")
            return value[key]
        value = self._need(rest)[0]
        self._idle()
        if key == "TYPE":
            t.pw_type = _choice(value, _PW_TYPES, "pulse width type")
        elif key == "SOURCE":
            t.pw_source = _choice(value, _CH, "pulse width source")
        elif key == "DIR":
            t.pw_direction = _choice(value, _DIRECTIONS, "direction")
        elif key == "LEVEL":
            t.pw_level = None if value.upper() == "AUTO"                 else _num(value, "V")
        elif key in ("LOWER", "UPPER"):
            seconds = _num(value, "s")
            if seconds < 0:
                raise ExceptionPicoscope("pulse width must be >= 0")
            setattr(t, "pw_" + key.lower(), seconds)
        else:
            raise ExceptionPicoscope(f"unknown parameter '{key}'")
        return None

    def _require_trigger_feature(self, name):
        """TRG WITHINPRE and TRG EDGEDETECT exist in the ps5000a driver only."""
        if self._family and not _FAMILIES[self._family].extras:
            raise ExceptionNotSupported(
                f"T {name} is not available in the "
                f"{self._family.lower()} driver")

    def _trigger_summary(self) -> str:
        """Text of 'TRG?': LOGIC, sources as DIR,LEVEL,LOWER,HYST, digital
        conditions, pulse width, delay and auto trigger.
        """
        t = self.trig
        if not t.enabled:
            return "OFF"
        parts = [f"LOGIC={t.logic}"]
        for name, s in t.sources.items():
            hyst = "AUTO" if s.hyst is None else _fmt(s.hyst)
            parts.append(f"{name}={s.direction},{_fmt(s.level)},"
                         f"{_fmt(s.lower)},{hyst}")
        for bit, direction in sorted(t.digital.items()):
            parts.append(f"DIG{bit}={direction}")
        if t.pw_type != "NONE":
            parts.append(f"PW={t.pw_type},{t.pw_source},{t.pw_direction},"
                         f"{_fmt(t.pw_lower)},{_fmt(t.pw_upper)}")
        parts.append(f"DELAY={t.delay} AUTO={_fmt(t.auto)}")
        if t.within_pre:
            parts.append("WITHINPRE=ON")
        return " ".join(parts)

    def _counts(self, src, volts, with_offset=True, strict=False) -> int:
        """Convert a trigger voltage of `src` to ADC counts. A value outside
        the ADC range is clamped, or refused when `strict` (the trigger
        level, which the driver would reject as PICO_THRESHOLD_OUT_OF_RANGE).
        """
        if src == "EXT":
            full, maxadc, offset = _EXT_FULL_SCALE, _EXT_MAX_COUNTS, 0.0
        else:
            ch = self.channels[src]
            full, maxadc = ch.range_v, self._max_adc
            offset = ch.offset if with_offset else 0.0
        #> The trigger compares ADC counts, i.e. the signal after the analog
        #> offset was added; hence the offset is added to the threshold.
        #> Hysteresis is a difference of voltages, so it has no offset.
        counts = int(round((volts + offset) / full * maxadc))
        if strict and abs(counts) > maxadc:
            raise ExceptionPicoscope(
                f"trigger level {volts:g} V of {src} is outside the input "
                f"range (+-{full:g} V, analog offset {offset:g} V: the "
                f"level is compared after the offset is added)")
        return max(-32767, min(32767, counts))

    def _trig_spec(self, dt) -> dict:
        """Translate the trigger settings to driver structures (counts)."""
        t = self.trig
        spec = dict(props=[], directions=[], terms=[], digital=[], pwq=None,
                    delay=t.delay, auto_us=int(round(t.auto * 1e6)),
                    within_pre=t.within_pre, edge_detect=t.edge_detect)
        if not t.enabled:
            return spec
        for name, s in t.sources.items():
            if name != "EXT" and not self.channels[name].enabled:
                raise ExceptionPicoscope(f"trigger source {name} is disabled")
            #> AUTO hysteresis: 1 % of the full scale of the source.
            if s.hyst is None:
                hyst = int(0.01 * (_EXT_MAX_COUNTS if name == "EXT"
                                   else self._max_adc))
            else:
                hyst = abs(self._counts(name, s.hyst, with_offset=False))
            spec["props"].append((self._counts(name, s.level,
                                               strict=True), hyst,
                                  self._counts(name, s.lower), hyst,
                                  _CH[name]))
            value, window = _DIRECTIONS[s.direction]
            spec["directions"].append((_CH[name], value,
                                       _WINDOW if window else _LEVEL))
        analog = [_CH[n] for n in t.sources]
        if t.pw_type != "NONE":
            if t.pw_source not in t.sources:
                raise ExceptionPicoscope(
                    "TRG PW SOURCE must name a configured trigger source "
                    "(set its LEVEL first)")
            value, window = _DIRECTIONS[t.pw_direction]
            #> The guide (4.58) gives each channel two thresholds per
            #> direction (RISING / RISING_LOWER ...): the main trigger and
            #> the qualifier must not use the same one. The qualifier takes
            #> the lower one, set to pw_level (default: the trigger level).
            if not window:
                if value == 4:
                    raise ExceptionPicoscope(
                        "TRG PW DIR BOTH is not available (the qualifier "
                        "needs a direction with a lower threshold)")
                if value < 4:
                    value += 5
            pw_ch = _CH[t.pw_source]
            level = t.pw_level if t.pw_level is not None                 else t.sources[t.pw_source].level
            spec["props"] = [
                (p[0], p[1], self._counts(t.pw_source, level), p[3], p[4])
                if p[4] == pw_ch else p for p in spec["props"]]
            #> The driver counts pulse widths in sample intervals.
            lower = int(round(t.pw_lower / dt))
            upper = int(round(t.pw_upper / dt))
            spec["pwq"] = dict(type=_PW_TYPES[t.pw_type], lower=lower,
                               upper=upper,
                               conditions=[_CH[t.pw_source]],
                               directions=[(_CH[t.pw_source], value,
                                            _WINDOW if window else _LEVEL)])
            #> As in the Pico pulse-width examples: the pulse-width source is
            #> represented by PS5000A_PULSE_WIDTH_SOURCE in the conditions.
            analog = [c for c in analog if c != _CH[t.pw_source]]
            analog.append(_PULSE_WIDTH_SOURCE)
        ports = []
        if t.digital:
            if not self._mso and self._dev is not None:
                raise ExceptionNotSupported(
                    f"the {self._variant} has no digital inputs")
            spec["digital"] = [(bit, _DIG_DIRECTIONS[d])
                               for bit, d in sorted(t.digital.items())]
            if any(bit < 8 for bit in t.digital):
                ports.append(_PORT["D0"])
            if any(bit >= 8 for bit in t.digital):
                ports.append(_PORT["D1"])
        #> AND: all sources in one condition list (one driver call).
        #> OR: one condition list per source, each added with
        #> PS5000A_ADD (guide 4.68).
        terms = analog + ports
        if t.logic == "AND":
            spec["terms"] = [terms] if terms else []
        else:
            spec["terms"] = [[src] for src in terms]
        return spec

    # =========================================================================
    # Signal generator (G)
    # =========================================================================
    def _cmd_gen(self, args, summary):
        """GEN ... : signal generator. Every change is sent to the instrument
        at once (when open); FIRE and GATE only act on the running output.
        """
        g = self.gen
        if summary:
            sweep = "OFF" if g.sweep is None else \
                ",".join(_fmt(x) for x in g.sweep)
            return (f"{_fmt(g.enabled)} WAVE={g.wave} FREQ={_fmt(g.freq)} "
                    f"AMPL={_fmt(g.ampl)} OFFSET={_fmt(g.offset)} "
                    f"SWEEP={sweep} SHOTS={_cont(g.shots)} "
                    f"SWEEPS={_cont(g.sweeps)} "
                    f"TRIGGER={g.trig_source},{g.trig_type}")
        key, query, rest = self._split_query(args)
        if key in ("ON", "OFF"):
            g.enabled = key == "ON"
        elif key == "WAVE":
            if query:
                return g.wave
            wave = self._need(rest)[0].upper()
            if wave not in _WAVES and wave not in ("NOISE", "PRBS", "ARB"):
                raise ExceptionPicoscope(f"invalid waveform '{wave}'")
            if wave == "ARB" and g.arb is None:
                raise ExceptionPicoscope("load the waveform first (GEN ARB or "
                                        "set_awg)")
            g.wave = wave
        elif key in ("FREQ", "AMPL", "OFFSET", "EXTLEVEL"):
            attr = {"FREQ": "freq", "AMPL": "ampl", "OFFSET": "offset",
                    "EXTLEVEL": "ext_level"}[key]
            if query:
                return _fmt(getattr(g, attr))
            value = _num(self._need(rest)[0],
                         "Hz" if key == "FREQ" else "V")
            if key in ("FREQ", "AMPL") and value < 0:
                raise ExceptionPicoscope(f"{key} must be >= 0")
            setattr(g, attr, value)
        elif key == "SWEEP":
            if query:
                return "OFF" if g.sweep is None else \
                    " ".join(_fmt(x) for x in g.sweep)
            rest = self._need(rest)
            if rest[0].upper() == "OFF":
                g.sweep = None
            else:
                rest = self._need(rest, 4)
                g.sweep = (_num(rest[0], "Hz"), _num(rest[1], "Hz"),
                           _num(rest[2], "s"),
                           _choice(rest[3], _SWEEPS, "sweep type"))
        elif key in ("SHOTS", "SWEEPS"):
            if query:
                value = getattr(g, key.lower())
                return _cont(value)
            text = self._need(rest)[0]
            value = _CONTINUOUS_RUN if text.upper() == "CONT" else _int(text)
            setattr(g, key.lower(), value)
        elif key == "TRIGGER":
            if query:
                return f"{g.trig_source} {g.trig_type}"
            rest = self._need(rest)
            g.trig_source = _choice(rest[0], _GEN_TRIG_SOURCES,
                                    "generator trigger source")
            if len(rest) > 1:
                g.trig_type = _choice(rest[1], _GEN_TRIG_TYPES,
                                      "generator trigger type")
        elif key == "FIRE":
            self._require_open()
            self._dev.siggen_soft(1)
            return None
        elif key == "GATE":
            self._require_open()
            self._dev.siggen_soft(int(_onoff(self._need(rest)[0])))
            return None
        elif key == "ARB":
            values = [_num(v) for v in
                      " ".join(self._need(rest)).replace(",", " ").split()]
            return self.set_awg(values) and None
        else:
            raise ExceptionPicoscope(f"unknown parameter '{key}'")
        self._apply_generator()
        return None

    def _apply_generator(self):
        """Program the generator (or switch its output off)."""
        if self._dev is None:
            return
        g = self.gen
        if not g.enabled:
            #> The API has no "off": output 0 V DC (offset 0, amplitude 0)
            self._siggen_off()
            return
        offset_uv = int(round(g.offset * 1e6))
        pkpk_uv = int(round(g.ampl * 1e6))
        if g.sweep is None:
            f1, inc, dwell, sweep = g.freq, 0.0, 0.0, 0
        else:
            f1, inc, dwell, sweep = g.sweep[0], g.sweep[1], g.sweep[2], \
                _SWEEPS[g.sweep[3]]
        #> White noise and PRBS are "extra operations" of a built-in wave.
        op = {"NOISE": _OP_WHITENOISE, "PRBS": _OP_PRBS}.get(g.wave, _OP_OFF)
        ext = int(round(g.ext_level / _EXT_FULL_SCALE * _EXT_MAX_COUNTS))
        trig = (_GEN_TRIG_TYPES[g.trig_type],
                _GEN_TRIG_SOURCES[g.trig_source], ext)
        if g.wave == "ARB":
            vmin, vmax, lmin, lmax = self._dev.siggen_limits()
            if not lmin <= g.arb.size <= lmax:
                raise ExceptionPicoscope(
                    f"AWG length must be {lmin}..{lmax} samples")
            #> Map -1..+1 linearly onto the AWG sample range vmin..vmax;
            #> the output amplitude is then set by pkpk_uv and offset_uv.
            samples = np.round((g.arb + 1) / 2 * (vmax - vmin) + vmin)
            self._dev.siggen_arb(offset_uv, pkpk_uv, samples.astype(np.int16),
                                 g.freq, f1, inc, dwell, sweep, op, g.shots,
                                 g.sweeps, *trig)
        else:
            wave = _WAVES.get(g.wave, _WAVES["SINE"])
            self._dev.siggen_builtin(offset_uv, pkpk_uv, wave, g.freq, f1,
                                     inc, dwell, sweep, op, g.shots,
                                     g.sweeps, *trig)

    # =========================================================================
    # Capture control
    # =========================================================================
    def _find_timebase(self):
        """Return (timebase, interval) for the requested interval: the
        largest timebase whose interval does not exceed it (or the fastest
        one when the request is shorter than the minimum)."""
        a = self.acq
        dev = self._dev
        n = a.samples
        if a.tbindex is not None:
            info = dev.timebase(a.tbindex, n)
            if info is None:
                raise ExceptionPicoscope(
                    f"timebase {a.tbindex} is not available for {n} samples")
            return a.tbindex, info[0]
        #> Start from the fastest timebase for the enabled channels and
        #> resolution. If even that is slower than requested, use it.
        tb_min, _ = dev.min_timebase(self._flags(), _RESOLUTIONS[a.bits])
        info = dev.timebase(tb_min, n)
        if info is None:
            raise ExceptionPicoscope(
                f"{n} samples per record do not fit into the memory")
        if info[0] >= a.interval:
            return tb_min, info[0]
        #> Binary search: the interval grows monotonically with the timebase
        #> index, so about 32 GetTimebase2 calls are enough. The small
        #> tolerance accepts e.g. 1e-6 requested vs 1.0000001e-6 reported.
        lo, hi = tb_min, 2 ** 32 - 2
        while lo < hi:             # largest tb with interval <= request
            mid = (lo + hi + 1) // 2
            mid_info = dev.timebase(mid, n)
            if mid_info is not None and mid_info[0] <= a.interval * \
                    (1 + 1e-6):
                lo = mid
            else:
                hi = mid - 1
        return lo, dev.timebase(lo, n)[0]

    def _arm(self):
        """Send all settings to the instrument (ARM)."""
        self._require_open()
        self._idle()
        a = self.acq
        sources = self._sources()
        if not sources:
            raise ExceptionPicoscope("no channel or port is enabled")
        #> 15-bit resolution supports at most two analog channels and 16-bit
        #> resolution only one (guide 3.6, timebase tables); the driver fails
        #> with a less clear status, so check it here.
        n_analog = sum(1 for name in sources if name in _CHANNELS)
        limit = {15: 2, 16: 1}.get(a.bits)
        if limit is not None and n_analog > limit:
            raise ExceptionPicoscope(
                f"{a.bits}-bit resolution allows at most {limit} enabled "
                f"channel(s), {n_analog} are enabled")
        self._apply_all_channels()
        stream = a.mode == "STREAM"
        records = 1 if stream else a.records
        if a.ets != "OFF" and (stream or records > 1):
            raise ExceptionPicoscope("ETS works in single block mode only")
        if a.ets != "OFF" and self._family == "PS5000A" and [n for n in sources if n != "A"]:
            #> Measured on a 5443D: with channel D the driver answers
            #> PICO_TRIGGER_ERROR (0x2C) at RunBlock; channel A is accepted.
            raise ExceptionPicoscope("ETS works with channel A only, switch the other "
                     "channels off")
        if a.ds_mode == "AGGREGATE" and a.ets != "OFF":
            raise ExceptionPicoscope("ETS does not support aggregation")
        #> One segment per record; streaming and single block use one.
        self._dev.memory_segments(records)
        if not stream:
            self._dev.set_captures(records)
        if stream:
            tb, dt = None, a.interval
        else:
            tb, dt = self._find_timebase()
        ets_dt = 0.0
        if not stream:
            ets_dt = self._dev.set_ets(_ETS_MODES[a.ets], a.ets_cycles,
                                       a.ets_interleave)
        #> The trigger is sent last: pulse widths depend on the interval.
        self._dev.set_trigger(self._trig_spec(dt))
        #> Snapshot of everything needed to interpret the data later, so
        #> that settings changed after the run do not corrupt the scaling.
        self._run = dict(
            tb=tb, dt=dt, ets_dt=ets_dt, records=records, pre=a.pre,
            post=a.post, n=a.samples, sources=sources, stream=stream,
            ds_mode=a.ds_mode, ratio=a.ds_ratio, delay=self.trig.delay,
            max_adc=self._max_adc,
            channels={n: dict(range=c.range_v, offset=c.offset)
                      for n, c in self.channels.items()})
        return True

    def _run_capture(self, callback):
        """RUN / start(): arm and start a block, rapid block or streaming
        capture; returns at once. Streaming data are collected by a
        background thread (_stream_worker).
        """
        self._arm()
        a, r = self.acq, self._run
        self._abort.clear()
        self._data = None
        ratio_mode = _RATIO_MODES[a.ds_mode]
        if r["stream"]:
            with self._stream_lock:
                self._stream_data = {}
            self._stream_info = dict(samples=0, triggered_at=None,
                                     overflow=0)
            r["dt"] = self._dev.run_streaming(
                r["sources"], a.interval, a.pre, a.post, a.autostop,
                a.ds_ratio, ratio_mode, a.streambuf)
            self._state = "STREAMING"
            self._stream_thread = threading.Thread(
                target=self._stream_worker, name="Picoscope-stream",
                daemon=True)
            self._stream_thread.start()
        else:
            def _ready(status):
                if callback is not None:
                    callback(status)
            self._dev.run_block(r["pre"], r["post"], r["tb"],
                                _ready if callback is not None else None)
            self._state = "ARMED"
        return None

    def _stream_worker(self):
        """Background thread polling ps5000aGetStreamingLatestValues."""
        try:
            while not self._abort.is_set():
                #> The driver call needs the lock; the data are copied
                #> into self._stream_data under the separate stream lock.
                with self._lock:
                    chunks, autostop = self._dev.stream_poll()
                for chunk, overflow, trig_at in chunks:
                    with self._stream_lock:
                        n = 0
                        for name, (mx, mn) in chunk.items():
                            self._stream_data.setdefault(name, []).append(mx)
                            if mn is not None:
                                self._stream_data.setdefault(
                                    name + "_MIN", []).append(mn)
                            n = len(mx)
                        info = self._stream_info
                        if trig_at is not None and \
                                info["triggered_at"] is None:
                            info["triggered_at"] = info["samples"] + trig_at
                        info["samples"] += n
                        info["overflow"] |= overflow
                if autostop:
                    break
                #> Nothing new: sleep briefly, but wake at once on STOP.
                if not chunks:
                    self._abort.wait(0.002)
        except ExceptionPicoscope as exc:
            #> A thread cannot raise into the caller; keep the error.
            self._stream_info["error"] = str(exc)
        finally:
            if self._dev is not None:
                self._dev.stop()
            if self._state == "STREAMING":
                self._state = "IDLE"

    def _stop(self):
        """Interrupt any running operation (thread safe, no lock).

        Commands and WAIT of other threads do not continue before this
        method has finished (_stop_idle): ps5000aStop may take a moment, and a
        driver call made meanwhile fails with PICO_DRIVER_FUNCTION, while WAIT
        must not report ABORTED before the state is IDLE again.
        """
        with self._stop_count_lock:
            self._stop_count += 1
            self._stop_idle.clear()
        try:
            return self._stop_work()
        finally:
            with self._stop_count_lock:
                self._stop_count -= 1
                if self._stop_count == 0:
                    self._stop_idle.set()

    def _stop_work(self):
        """The work of _stop."""
        #> The event wakes WAIT, the streaming thread and a running data
        #> transfer; ps5000aStop aborts the capture in the instrument.
        self._abort.set()
        dev = self._dev
        if dev is None:
            return None
        dev.stop()
        thread = self._stream_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(2.0)
        self._stream_thread = None
        if self._state == "ARMED":
            #> Rapid block: the records completed before STOP stay valid
            #> and readable (guide, ps5000aStop / GetNoOfCaptures).
            if self._run and self._run["records"] > 1:
                with self._lock:
                    done = dev.n_captures()
                if done > 0:
                    self._run["records"] = done
                    self._state = "READY"
                    return None
            self._state = "IDLE"
        elif self._state == "STREAMING":
            self._state = "IDLE"
        return None

    def _wait(self, timeout):
        """Wait for the end of a block capture or of an autostop stream."""
        if self._state == "STREAMING":
            thread = self._stream_thread
            end = None if timeout is None else time.monotonic() + timeout
            try:
                while thread is not None and thread.is_alive():
                    if self._abort.is_set():
                        self._stop_idle.wait(5)
                        return "ABORTED"
                    if end is not None and time.monotonic() >= end:
                        return "TIMEOUT"
                    thread.join(0.01)
            except KeyboardInterrupt:
                #> Ctrl+C: stop streaming, then let the interrupt propagate.
                self._stop()
                raise
            return "ABORTED" if self._abort.is_set() else "READY"
        if self._state == "READY":
            return "READY"
        if self._state != "ARMED":
            raise ExceptionPicoscope("no capture is running")
        end = None if timeout is None else time.monotonic() + timeout
        try:
            while True:
                if self._abort.is_set():
                    self._stop_idle.wait(5)
                    return "ABORTED"
                #> Hold the lock only for the short IsReady call.
                with self._lock:
                    if self._state != "ARMED":
                        return "READY" if self._state == "READY" \
                            else "ABORTED"
                    if self._dev.is_ready():
                        self._state = "READY"
                        return "READY"
                if end is not None and time.monotonic() >= end:
                    return "TIMEOUT"
                #> 1 ms poll period; returns at once when STOP sets the event.
                self._abort.wait(0.001)
        except KeyboardInterrupt:
            #> Ctrl+C: stop the instrument, then let the interrupt propagate.
            self._stop()
            raise

    def _cmd_ready(self, args):
        """READY?: '1' when the capture is complete ('0' while streaming)."""
        if self._state == "ARMED" and self._dev.is_ready():
            self._state = "READY"
        if self._state == "STREAMING":
            return "0"
        return "1" if self._state == "READY" else "0"

    def _cmd_captures(self, args):
        """CAPTURES?: completed records (also during a rapid block run)."""
        self._require_open()
        if self._run is None:
            return "0"
        if self._state == "READY":
            return str(self._run["records"])
        return str(self._dev.n_captures()) if self._run["records"] > 1 \
            else "0"

    # =========================================================================
    # Data retrieval
    # =========================================================================
    def _fetch(self):
        """Transfer the data of the last capture from the driver (once)."""
        with self._lock:
            if self._data is not None:
                return
            if self._state == "ARMED" and self._dev.is_ready():
                self._state = "READY"
            if self._state != "READY":
                raise ExceptionPicoscope("no captured data available "
                                        f"(state {self._state})")
            r = self._run
            ratio_mode = _RATIO_MODES[r["ds_mode"]]
            ratio = r["ratio"] if ratio_mode else 1
            #> ETS: `ets` is the interleave factor, used for the time axis only.
            ets = self.acq.ets_interleave if self.acq.ets != "OFF" else 0
            #> A STOP issued before this point concerned the capture; only a
            #> STOP during the transfer below should abort it.
            self._abort.clear()
            try:
                raw, overflow, ets_times = self._dev.get_values(
                    r["sources"], r["n"], ratio, ratio_mode, r["records"],
                    self._abort, ets)
            except _Aborted:
                self._state = "IDLE"
                raise ExceptionPicoscope("data transfer aborted by STOP")
            n = next(iter(raw.values()))[0].shape[1]
            self._data = dict(raw=raw, overflow=overflow, ets_times=ets_times,
                              n=n, records=r["records"], pre=r["pre"],
                              dt=r["dt"], ratio=ratio, ds_mode=r["ds_mode"],
                              delay=r["delay"], max_adc=r["max_adc"],
                              channels=r["channels"])

    def _fetch_source(self, source):
        """(max, min) raw arrays of `source`, transferring data if needed."""
        self._fetch()
        source = source.upper()
        if source not in self._data["raw"]:
            raise ExceptionPicoscope(f"source {source} was not captured")
        return self._data["raw"][source]

    def _cmd_overflow(self, args):
        """OVERFLOW?: 'record:channels' items of records that exceeded
        the range (streaming: channels only), or NONE.
        """
        if self._state == "STREAMING" or (self._run and self._run["stream"]):
            bits = self._stream_info["overflow"]
            return ",".join(c for i, c in enumerate(_CHANNELS)
                            if bits & (1 << i)) or "NONE"
        self._fetch()
        out = []
        for rec, bits in enumerate(self._data["overflow"]):
            names = "".join(c for i, c in enumerate(_CHANNELS)
                            if int(bits) & (1 << i))
            if names:
                out.append(f"{rec}:{names}")
        return " ".join(out) if out else "NONE"

    def _cmd_trigtime(self, args):
        """TRIGTIME?: comma-separated trigger time offsets in seconds."""
        return ",".join(_fmt(float(x)) for x in self.get_trigger_times())

    def _cmd_data(self, args):
        """DATA? <src> [record]: one record as comma-separated text (volts
        for A-D, integers for the ports). Meant for short records; use
        get_float() for large data.
        """
        self._need(args)
        source = args[0].upper()
        record = _int(args[1]) if len(args) > 1 else 0
        if source in _CHANNELS:
            data = self.get_float(source)
        elif source in _PORT:
            data = self._fetch_source(source)[0] & 0xFF
        else:
            raise ExceptionPicoscope(f"invalid source '{source}'")
        if record >= data.shape[0]:
            raise ExceptionPicoscope(f"record {record} does not exist")
        return ",".join(_fmt(float(v)) if source in _CHANNELS else str(v)
                        for v in data[record])


# *****************************************************************************
# Command reference (HELP?)
# *****************************************************************************
_HELP = [
    ("<number>", "SI prefix + optional unit: 10us, 500mV (V and s: m = M = "
                 "milli), 1MHz, 100mHz, 10k samples."),
    ("OPEN [family] [serial]", "Open the first (or the selected) scope; the "
     "driver is found automatically, family PS2000A|PS3000A|PS4000A|PS5000A "
     "restricts the search."),
    ("OPEN SIM [variant]", "Simulated scope: 5443D (default), 2408B, 2204A, "
     "3404D MSO, 3206D, 4824A."),
    ("DEVICES?", "Connected unopened scopes as FAMILY:serial,..."),
    ("CLOSE", "Stop, switch the generator off and close the scope."),
    ("IDN?", "Model and serial number."),
    ("INFO?", "All GetUnitInfo values."),
    ("POWER?", "Power source: DC (adaptor), USB, USB2 (2-ch on USB 2.0)."),
    ("POWER DC|USB", "Confirm a power source change (ChangePowerSource)."),
    ("STATE?", "CLOSED, IDLE, ARMED, READY or STREAMING."),
    ("CAPS?", "Family, variant, channels, MSO, resolution, pulse width, "
              "trigger info, generator, simulator."),
    ("LED <count>|ON|STOP", "Flash the front LED (ON = indefinitely)."),
    ("RESET", "Restore default settings."),
    ("OSC RESET", "Same as RESET (also resets the X FACTOR scaling)."),
    ("HELP? [prefix]", "This list, optionally filtered by a prefix."),
    ("OSC BITS 8|12|14|15|16", "Resolution (ps5000a only; 15 bits: max 2 ch, "
                             "16 bits: 1 ch). Other series have a fixed one."),
    ("OSC INTERVAL <s>", "Requested sampling interval; the longest available "
                       "interval not exceeding it is used. Alias OSC TIMEBASE."),
    ("OSC INTERVAL?", "Actual interval after ARM/RUN, requested before."),
    ("OSC TBINDEX <n>", "Fixed ps5000a timebase index (overrides INTERVAL)."),
    ("OSC MININTERVAL?", "Fastest interval for the enabled channels."),
    ("OSC PRETRIGGER <n>", "Samples before the trigger."),
    ("OSC POSTTRIGGER <n>", "Samples after the trigger."),
    ("OSC SAMPLES?", "PRETRIGGER + POSTTRIGGER."),
    ("OSC RECORDS <n>", "Records per run (rapid block); 1 = block."),
    ("OSC MAXRECORDS?", "Maximum number of memory segments."),
    ("OSC MAXSAMPLES?", "Maximum samples per record for current settings."),
    ("OSC MODE BLOCK|STREAM", "Capture mode."),
    ("OSC DOWNSAMPLE NONE|AGGREGATE|DECIMATE|AVERAGE [ratio]",
     "Downsampling by the driver; AGGREGATE returns max and min."),
    ("OSC STREAMBUF <n>", "Streaming transfer buffer length."),
    ("OSC AUTOSTOP ON|OFF", "Streaming stops after PRE+POST samples."),
    ("OSC ETS OFF|FAST|SLOW [cycles] [interleave]",
     "Equivalent-time sampling (8 bits, channel A, edge trigger, block). "
     "The record keeps the sample count, the time step becomes 1/interleave "
     "of the interval; cycles must be >= interleave (default 20 10)."),
    ("OSC?", "Summary of the acquisition settings."),
    ("X ON|OFF", "Enable/disable channel X = A-D (A-H on 8-channel scopes)."),
    ("X COUPLING DC|AC", "Input coupling."),
    ("X RANGE <V>", "Smallest range +-10 mV..+-20 V covering the value."),
    ("X OFFSET <V>", "Analog offset (added before digitization)."),
    ("X OFFSETLIMITS?", "Allowed offset for the current range/coupling."),
    ("X BW FULL|20MHZ", "Bandwidth limiter."),
    ("X FACTOR <n>", "Output scale: returned volts are multiplied by n "
                     "(e.g. 10 for a 10:1 probe); default 1."),
    ("X?", "Summary of channel X."),
    ("ALL <channel command>", "The same command for every analog channel of "
                              "the model, e.g. ALL COUPLING DC, ALL OFF; A ON "
                              "(before OPEN: A-D). All or nothing."),
    ("ALL?, ALL <KEY>?", "Summary lines of all channels / one value per channel."),
    ("D0 ON|OFF, D1 ON|OFF", "MSO digital ports (D0 = bits 0-7, D1 = 8-15). "
                             "NOT TESTED."),
    ("D0 LEVEL <V>", "Logic threshold of the port (+-5 V). NOT TESTED."),
    ("TRG EDGE <src> RISING|FALLING|BOTH|ABOVE|BELOW <V>",
     "Simple edge/level trigger; clears other conditions. src = A-D, EXT. "
     "EXT accepts only RISING|FALLING|BOTH; on EXT, BOTH ignores the level "
     "(fires on every edge), use RISING or FALLING when the level matters."),
    ("TRG <src> DIR <dir>", "RISING, FALLING, BOTH, ABOVE, BELOW, *LOWER "
                          "variants, INSIDE, OUTSIDE, ENTER, EXIT, "
                          "ENTEROREXIT, POSITIVERUNT, NEGATIVERUNT."),
    ("TRG <src> LEVEL <V>", "Threshold (upper threshold of a window)."),
    ("TRG <src> LOWER <V>", "Lower threshold (window, runt, *LOWER)."),
    ("TRG <src> HYST <V>|AUTO", "Hysteresis (AUTO = 1 % of full scale)."),
    ("TRG <src> OFF", "Remove the source from the trigger."),
    ("TRG LOGIC AND|OR", "Combination of the trigger sources."),
    ("TRG DIG <bit> LOW|HIGH|RISING|FALLING|BOTH|X",
     "MSO digital condition (X removes it). NOT TESTED."),
    ("TRG PW TYPE NONE|LESS|GREATER|INSIDE|OUTSIDE", "Pulse-width qualifier."),
    ("TRG PW SOURCE <src>", "Source of the pulse-width qualifier."),
    ("TRG PW DIR <dir>", "Edge ending the pulse (e.g. FALLING)."),
    ("TRG PW LOWER <s>", "Lower pulse width limit."),
    ("TRG PW UPPER <s>", "Upper pulse width limit (INSIDE/OUTSIDE)."),
    ("TRG DELAY <samples>", "Post-trigger delay."),
    ("TRG AUTO <s>", "Auto trigger timeout; 0 = wait forever."),
    ("TRG WITHINPRE ON|OFF", "Trigger allowed within the pre-trigger samples."),
    ("TRG EDGEDETECT ON|OFF", "Output edge detection of the logic trigger."),
    ("TRG CLEAR, TRG OFF", "Remove all trigger conditions (free run)."),
    ("TRG?", "Summary of the trigger."),
    ("ARM", "Send all settings to the scope (prepare())."),
    ("RUN", "ARM and start the capture; returns at once (start())."),
    ("READY?", "1 when the block/all records are captured."),
    ("WAIT [timeout s]", "Wait for the capture: READY, TIMEOUT, ABORTED."),
    ("STOP", "Interrupt capture, streaming or data transfer."),
    ("CAPTURES?", "Number of captured records."),
    ("OVERFLOW?", "Records and channels that exceeded the range."),
    ("TRIGTIME?", "Trigger time offsets of the records in seconds."),
    ("DATA? <src> [record]", "Comma-separated data (volts; ports as ints)."),
    ("GEN ON|OFF", "Generator output on/off."),
    ("GEN WAVE <wave>", "SINE, SQUARE, TRIANGLE, RAMPUP, RAMPDOWN, SINC, "
                      "GAUSSIAN, HALFSINE, DC, NOISE, PRBS, ARB."),
    ("GEN FREQ <Hz>", "Frequency (PRBS: bit rate)."),
    ("GEN AMPL <Vpp>", "Peak-to-peak amplitude."),
    ("GEN OFFSET <V>", "Offset voltage."),
    ("GEN SWEEP <stop Hz> <step Hz> <dwell s> UP|DOWN|UPDOWN|DOWNUP",
     "Frequency sweep; GEN SWEEP OFF ends it."),
    ("GEN SHOTS <n>|CONT", "Cycles after a generator trigger."),
    ("GEN SWEEPS <n>|CONT", "Sweeps after a generator trigger."),
    ("GEN TRIGGER NONE|SCOPE|AUX|EXT|SOFT [RISING|FALLING|GATEHIGH|GATELOW]",
     "Generator trigger source and type."),
    ("GEN EXTLEVEL <V>", "Threshold of the EXT generator trigger."),
    ("GEN FIRE", "Software trigger of the generator."),
    ("GEN GATE ON|OFF", "Software gate of the generator."),
    ("GEN ARB <v1,v2,...>", "Arbitrary waveform (-1..+1); see set_awg()."),
    ("GEN?", "Summary of the generator."),
]


# *****************************************************************************
# Interactive console: python -m pypicocommands [SIM [variant]|serial]
# *****************************************************************************
def console(argv=None) -> None:
    """Interactive console (used by ``python -m pypicocommands``)."""
    scope = Picoscope(strict=False)
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print(scope.cmd("OPEN " + " ".join(argv)))
    print("PicoScope console; HELP? lists the commands, empty line ends.")
    try:
        while True:
            line = input("> ").strip()
            if not line:
                break
            print(scope.cmd(line))
    finally:
        scope.cmd("CLOSE")


if __name__ == "__main__":
    console(sys.argv[1:])
