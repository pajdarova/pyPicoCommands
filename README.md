# pypicocommands

Control PicoScope 2000, 3000, 4000 and 5000 series oscilloscopes with short
text commands from Python. The `Picoscope` class detects the
connected instrument on `OPEN`, loads the matching PicoSDK driver (ps2000a,
ps3000a, ps4000a or ps5000a) through `ctypes`, and rejects commands the
model cannot do with `ExceptionNotSupported`.

```python
from pypicocommands import Picoscope

ps = Picoscope()
ps.cmd("OPEN; A ON; A RANGE 2; A COUPLING DC; B OFF")
ps.cmd("OSC INTERVAL 10n; OSC PRETRIGGER 200; OSC POSTTRIGGER 2000")
ps.cmd("TRG EDGE A RISING 0.5; TRG AUTO 100m")
ps.cmd("RUN")
print(ps.cmd("WAIT 5"))        # READY, TIMEOUT or ABORTED
volts = ps.get_float("A")      # ndarray (records, samples) in volts
t = ps.get_time()              # seconds, 0 = trigger
ps.cmd("CLOSE")
```

Command groups: `OSC` (acquisition), `TRG` (trigger), `GEN` (signal
generator), channel commands `A ...` to `H ...`. Send `HELP` for the full list.
`OPEN SIM [variant]` opens a simulated instrument, no hardware or driver needed.

## Install

```bash
pip install pypicocommands      # once published; until then: pip install .
```

## Requirements

- Python 3.10+, `numpy`
- PicoSDK or PicoScope 7 installed (the driver DLLs; set `PICO_SDK_DIR` if they
  are in a non-standard place). Not needed for `OPEN SIM`.

## Tests and tools

```bash
python -m unittest discover tests          # 68 tests, run on the simulator
python -m pypicocommands.identify [--open] # list drivers and connected units
python -m pypicocommands [SIM]             # interactive command console
```

## Status

| Series | Driver | Status |
|--------|--------|--------|
| 5000 | ps5000a | tested on hardware (5443D) |
| 2000 | ps2000a | not yet tested on hardware |
| 3000 | ps3000a | not yet tested on hardware |
| 4000 | ps4000a | not yet tested on hardware |

See `docs/HW_TEST_PLAN.md` for the checklist to verify the other families and
`docs/design_and_hardware_notes.md` for design decisions, measured driver
behavior and known problems (e.g. the pulse-width qualifier on the 5443D).

Not supported: 3000E/5000E (psospa), 6000 series, 4444 selectable resolution.

## License

MIT, see `LICENSE`.

This package does not include the PicoSDK drivers; install PicoSDK or
PicoScope 7 from Pico Technology.
