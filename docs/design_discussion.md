> Imported from the Experiment-Skeleton-System project. Paths and module names (Independent_Modules/..., Picoscope_5000D, Picoscope_pyPicoSDK, picoscope_common.py) refer to that repository; the code now lives in `src/pypicocommands/picoscope.py`.

# Brainstorm: common PicoScope 3000/4000/5000 module (2026-10-27)

Status: discussion only, no code yet (Andrea's explicit wish). Analysis doc:
https://claude.ai/artifact/4rLcvBnQ25tBs1XpruHDEx

Goal (Andrea): one module that behaves like Picoscope_5000D, detects the
device on OPEN, loads the matching driver, and returns a "Not supported"
error for anything the instrument cannot do. The department has 3000, 4000
and 5000 series; exact models unknown (colleague only named the series).

Facts (wrappers in Picoscope_5000D/picosdk-python-wrappers + Pico pages):
- Driver per model: ps3000a = 3000A/B/D/MSO; ps4000a = 4224A/4424A/4824A,
  4823, 4824, 4444, 4225A/4425A; ps5000a = 5000A/B/D(+MSO); older ps3000
  (3204-3206, 3223/3224, 3423-3425), ps4000 (4223/4224/4226/4227/4423/4424,
  4262), ps5000 (5203/5204); psospa = 3000E/5000E. 4224 != 4224A.
- A drivers share the API shape. Differences: ps3000a RunBlock/GetTimebase2
  have `oversample`, siggen uses float, only ConditionsV2; ps4000a no V2
  trigger structs, ranges via PICO_CONNECT_PROBE_RANGE, up to 8 channels;
  only ps5000a has GetMinimumTimebaseStateless, SetAutoTriggerMicroSeconds,
  flexible resolution. ps4000a 4444: SetDeviceResolution 12/14 bit.
- Timebase: 3000D/4ch: 1/2/4 ns for tb 0-2 (1/2/4 channels), then
  (n-2)/125 MHz; 4000A/4824: 12.5 ns*(n+1); 4444: tb0 = 2.5 ns (Pico page
  inconsistent, verify).
- EnumerateUnits exists in ps3000a/ps4000a/ps5000a/ps4000 (not ps5000).

Proposal (awaiting Andrea's answers):
- New module (working name Independent_Modules/Picoscope), own ctypes, no
  pyPicoSDK dependency (pyPicoSDK has no ps3000a/ps4000); common command
  layer + one backend per driver + per-model capability table; OPEN
  enumerates all installed drivers, VARIANT -> capabilities; CAPS? query;
  ExceptionNotSupported subclass. Picoscope_5000D stays frozen until the new
  module matches it on the 5443D.
- First: HW test of 5000D, then a read-only pico_identify.py script to list
  department models.

Update 2026-11-02 - department instruments (from the supplier quote, 10/2024):
- 4x PicoScope 2408B (4 ch, 100 MHz) -> **ps2000a** driver. Not covered in the
  brainstorm above (it listed 3000/4000/5000 only; the colleague's "3000" was
  probably wrong or refers to other units) - the 2000 series must be added.
- 2x PicoScope 5443D (4 ch, 100 MHz) -> ps5000a (the module already tested on it).
- 1x PicoScope 4824A (8 ch, 20 MHz, USB 3) -> ps4000a (channels A-H).
- Consequence: the common module needs ps2000a, ps4000a and ps5000a backends
  (ps3000a only if 3000-series units turn out to exist). The pico_identify.py
  step is still useful to confirm what is actually installed.
- New commands X FACTOR and OSC RESET were added to both existing modules; the
  common module must keep them.

Update 2026-11-02 (2): a 3000-series PicoScope exists too (delivered with the
deposition device), exact model unknown. Andrea wants all series covered in the
common module from the start: ps2000a (2408B), ps3000a (3000 A/B/D/MSO, or
psospa if it is a 3000E), ps4000a (4824A), ps5000a (5443D).

Update 2026-11-02 (3): decision taken - the common module was built (see
picoscope_common_module.md): new `Independent_Modules/Picoscope_Common/`, own
ctypes, one backend per driver family (ps2000a, ps3000a, ps4000a, ps5000a),
OPEN detection, ExceptionNotSupported. Hardware verification is pending
(instruments are at the work place).
