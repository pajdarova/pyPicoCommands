# pypicocommands manual

How to drive a PicoScope with short text commands. The examples use the
oscilloscope on the bench: replace `OPEN` with `OPEN SIM` (see
[Trying it without an instrument](#trying-it-without-an-instrument)) to run
them with no hardware.

Contents

1. [Quick start](#1-quick-start)
2. [The command language](#2-the-command-language)
3. [Recipes](#3-recipes)
4. [Differences between the series](#4-differences-between-the-series)
5. [Known limits and pitfalls](#5-known-limits-and-pitfalls)
6. [Troubleshooting](#6-troubleshooting)
7. [Command reference by group](#7-command-reference-by-group)
   (instrument and control, `OSC`, channels, `TRG`, capture and data, `GEN`)

---

## 1. Quick start

```bash
pip install pypicocommands
```

PicoSDK (or PicoScope 7) must be installed: it provides the driver DLLs.
Close PicoScope 7 before using the instrument from Python; the driver cannot
open a unit that another program holds.

```python
from pypicocommands import Picoscope

ps = Picoscope()
ps.cmd("OPEN")                                    # finds the scope and loads its driver
print(ps.cmd("IDN?"))                             # e.g. "5443D JY064/0018"

ps.cmd("A ON; A RANGE 2; A COUPLING DC; B OFF; C OFF; D OFF")
ps.cmd("OSC INTERVAL 10us; OSC PRETRIGGER 100; OSC POSTTRIGGER 900")
ps.cmd("TRG EDGE A RISING 0.5; TRG AUTO 100ms")   # trigger at +0.5 V, free-run after 100 ms
ps.cmd("RUN")                                     # returns at once
print(ps.cmd("WAIT 5"))                           # READY, TIMEOUT or ABORTED

volts = ps.get_float("A")                         # shape (records, samples), in volts
t = ps.get_time()                                 # seconds, 0 = trigger
ps.cmd("CLOSE")
```

`Picoscope` also works as a context manager (`with Picoscope() as ps:`); the
instrument is closed at the end of the block.

### Trying it without an instrument

`OPEN SIM` opens a simulated scope: no driver and no hardware needed. The
variants are `5443D` (default), `2408B`, `2204A`, `3404D MSO`, `3206D` and
`4824A`, for example `OPEN SIM 4824A`. The simulator produces a test signal,
so it is good for checking the flow of a script, not the physics.

### Interactive console

```bash
python -m pypicocommands            # then type: OPEN, A ON, ...
python -m pypicocommands SIM        # the same with the simulator
python -m pypicocommands.identify   # list drivers and connected scopes (opens nothing)
```

---

## 2. The command language

* Several commands in one string, separated by `;` or new lines, run left to
  right. Keywords are case insensitive.
* A query ends with `?`: `A RANGE?`, `OSC INTERVAL?`. Summary queries (`A?`,
  `OSC?`, `TRG?`, `GEN?`) return `KEY=value` pairs.
* Setting commands return `OK`; queries return only the value. Several
  queries in one string are joined with `"; "`: `ps.cmd("A RANGE 2; A RANGE?; OSC BITS?")`
  gives `"2; 8"` (the `OK` of the setting is dropped).
* Numbers take SI prefixes and an optional unit, which is checked loosely:
  `500m`, `500mV`, `0.5` are the same voltage; `10us`, `10u`, `1e-5` the same
  time. Frequencies are case sensitive (`m` milli, `M` mega): `100mHz`,
  `10kHz`, `1MHz`. Counts accept `k`, `M`: `OSC POSTTRIGGER 2M`.
* You may enter settings before `OPEN`; they are sent when the scope opens.
  With an open scope, channel and generator settings are sent at once, while
  the trigger, timebase and memory are sent by `ARM` or `RUN`.
* Errors raise `ExceptionPicoscope` (a command the model cannot do raises its
  subclass `ExceptionNotSupported`). With `Picoscope(strict=False)` the
  response is `"ERR <reason>"` instead, which suits a socket or serial link.
  Commands before the failing one in the same string stay executed.

```python
from pypicocommands import Picoscope, ExceptionPicoscope, ExceptionNotSupported

ps = Picoscope()
ps.cmd("OPEN")
try:
    ps.cmd("OSC BITS 16")
except ExceptionNotSupported as exc:       # e.g. on a PicoScope 4000
    print("not available here:", exc)
except ExceptionPicoscope as exc:          # anything else the module refuses
    print("error:", exc)
```

### Channels

`A` to `D` are the analog inputs (`A` to `H` on 8-channel scopes such as the
4824A). Each channel has `ON`/`OFF`, `COUPLING DC|AC`, `RANGE <V>`, `OFFSET
<V>`, `BW FULL|20MHZ` and `FACTOR <n>`. `RANGE 1.5` selects the smallest range
that covers the value (here ±2 V). `FACTOR 10` multiplies the returned volts,
e.g. for a 10:1 probe; ranges, offsets and trigger levels stay in input volts.

`ALL` gives the same channel command to every analog channel of the model:

```python
ps.cmd("ALL COUPLING DC; ALL RANGE 5")      # all channels
ps.cmd("ALL OFF; A ON")                     # only A
print(ps.cmd("ALL RANGE?"))                 # "5 5 5 5" (one value per channel)
```

`ALL` is all or nothing: if the driver rejects it for one channel, the
channels already changed are restored.

---

## 3. Recipes

Each recipe assumes `ps = Picoscope()` and `ps.cmd("OPEN")` (or `OPEN SIM`).

### 3.1 One capture, saved to a file

```python
import numpy as np

ps.cmd("ALL OFF; A ON; A RANGE 2")
ps.cmd("OSC INTERVAL 1us; OSC PRETRIGGER 200; OSC POSTTRIGGER 1800")
ps.cmd("TRG EDGE A RISING 0; TRG AUTO 500ms")
ps.cmd("RUN")
if ps.cmd("WAIT 5") == "READY":
    t = ps.get_time()
    v = ps.get_float("A")[0]               # first (only) record
    np.savetxt("capture.csv", np.c_[t, v], delimiter=",", header="t_s,A_V")
print(ps.cmd("OSC INTERVAL?"))             # the interval actually used
```

`OSC INTERVAL` is a request: the longest interval the scope offers that does
not exceed it is used, and `OSC INTERVAL?` after `RUN` tells which. Time 0 is
the trigger, so `PRETRIGGER` samples have negative times.

`TRG AUTO <time>` makes the scope capture anyway after that time without a
trigger; `TRG AUTO 0` waits forever.

### 3.2 Many records at once (rapid block)

```python
ps.cmd("OSC RECORDS 50; OSC INTERVAL 100ns; OSC PRETRIGGER 0; OSC POSTTRIGGER 500")
ps.cmd("TRG EDGE A RISING 0.3; TRG AUTO 1")
ps.cmd("RUN")
ps.cmd("WAIT 30")
data = ps.get_float("A")                   # shape (50, 500)
print(ps.cmd("CAPTURES?"))                 # records captured
dt = ps.get_trigger_times()                # trigger time of each record, seconds
print(ps.cmd("OVERFLOW?"))                 # records and channels that exceeded the range
```

If you `STOP` a rapid capture early, the records completed so far stay
readable. `OSC MAXRECORDS?` and `OSC MAXSAMPLES?` tell the limits for the
current settings.

### 3.3 Triggers

A simple edge trigger on a channel or the external input:

```python
ps.cmd("TRG EDGE A RISING 0.5")            # RISING, FALLING, BOTH, ABOVE, BELOW
ps.cmd("TRG EDGE EXT RISING 1.0")          # external input, ±5 V
ps.cmd("TRG DELAY 30")                     # shift the trigger point by 30 samples
```

A trigger from several sources. `TRG <src> DIR` and `LEVEL` describe one
source; `TRG LOGIC` combines them:

```python
ps.cmd("TRG CLEAR")
ps.cmd("TRG A DIR RISING; TRG A LEVEL 0.3")
ps.cmd("TRG B DIR FALLING; TRG B LEVEL 0")
ps.cmd("TRG LOGIC AND")                    # both conditions at once; OR for either
```

Window triggers use the upper level (`LEVEL`) and the lower level (`LOWER`):

```python
ps.cmd("TRG CLEAR; TRG A DIR ENTER; TRG A LEVEL 0.5; TRG A LOWER -0.5")
```

Directions are `RISING`, `FALLING`, `BOTH`, `ABOVE`, `BELOW`, the window
directions `INSIDE`, `OUTSIDE`, `ENTER`, `EXIT`, `ENTEROREXIT` and the runt
directions `POSITIVERUNT`, `NEGATIVERUNT`. Hysteresis: `TRG A HYST 0.05` (or
`AUTO`). `TRG CLEAR` removes all conditions (free run).

Trigger levels are compared with the signal **after the analog offset is
added**, so a level outside the input range is refused with a message that
says so.

### 3.4 Measuring the delay from a trigger

```python
ps.cmd("OSC PRETRIGGER 100; OSC POSTTRIGGER 900; OSC INTERVAL 1us")
ps.cmd("TRG EDGE EXT RISING 0.5; TRG DELAY 200")   # start 200 samples after the trigger
```

`TRG DELAY` is in samples. With a positive delay the capture starts after the
trigger; `get_time()` stays relative to the trigger.

### 3.5 Streaming

Streaming has no memory limit: data arrive in chunks while the scope runs.

```python
import time
import numpy as np

ps.cmd("ALL OFF; A ON; A RANGE 2")
ps.cmd("OSC MODE STREAM; OSC INTERVAL 10us")
ps.cmd("OSC PRETRIGGER 0; OSC POSTTRIGGER 500k; OSC AUTOSTOP ON")
ps.cmd("TRG CLEAR")
ps.cmd("RUN")

chunks = []
while ps.cmd("STATE?") == "STREAMING":
    got = ps.get_stream()                  # data since the previous call
    if "A" in got:
        chunks.append(got["A"])
    time.sleep(0.05)
last = ps.get_stream()                     # whatever came after the last poll
if "A" in last:
    chunks.append(last["A"])
volts = np.concatenate(chunks)
ps.cmd("OSC MODE BLOCK")
```

With `AUTOSTOP ON` streaming ends after `PRETRIGGER + POSTTRIGGER` samples;
otherwise stop it with `STOP`. `OSC DOWNSAMPLE AGGREGATE 100` returns the
maximum and minimum of every 100 samples (the minima appear under keys such
as `A_MIN`).

### 3.6 Signal generator

```python
ps.cmd("GEN WAVE SINE; GEN FREQ 10kHz; GEN AMPL 1; GEN OFFSET 0; GEN ON")
print(ps.cmd("GEN?"))
ps.cmd("GEN OFF")
```

`GEN AMPL` is the peak-to-peak amplitude. Waveforms: `SINE`, `SQUARE`,
`TRIANGLE`, `RAMPUP`, `RAMPDOWN`, `SINC`, `GAUSSIAN`, `HALFSINE`, `DC`,
`NOISE`, `PRBS` (the frequency is then the bit rate) and `ARB`.

A burst of three cycles started by software:

```python
ps.cmd("GEN WAVE SINE; GEN FREQ 1kHz; GEN AMPL 1")
ps.cmd("GEN SHOTS 3; GEN TRIGGER SOFT RISING; GEN ON")
ps.cmd("GEN FIRE")                         # one burst per FIRE
ps.cmd("GEN SHOTS 0; GEN TRIGGER NONE")    # back to continuous
```

A frequency sweep: `GEN SWEEP <stop Hz> <step Hz> <dwell s> UP|DOWN|UPDOWN|DOWNUP`,
ended by `GEN SWEEP OFF`. An arbitrary waveform, either as numbers between
-1 and +1 in a command or from Python:

```python
import numpy as np

ps.cmd("GEN ARB " + ",".join(f"{x:.4f}" for x in np.sin(np.linspace(0, 6.28318, 256))))
ps.cmd("GEN FREQ 1kHz; GEN ON")
ps.set_awg(np.sign(np.sin(np.linspace(0, 6.28318, 64))))   # same thing, from an array
```

The generator has a limited amplitude (4 Vpp measured on a 5443D) and its
output is not switched off by `STOP`; `GEN OFF` or `CLOSE` does that.

### 3.7 Equivalent-time sampling (ETS)

ETS rebuilds a fast **repetitive** signal from many triggers, with a time step
much finer than the real sampling interval. It needs a stable edge trigger and
works with channel A only (a limit measured on the 5443D).

```python
ps.cmd("ALL OFF; A ON; A RANGE 1")
ps.cmd("OSC INTERVAL 10ns; OSC PRETRIGGER 100; OSC POSTTRIGGER 400")
ps.cmd("TRG EDGE A RISING 0; TRG AUTO 0")
ps.cmd("OSC ETS FAST 20 10")               # mode, cycles, interleave (cycles >= interleave)
ps.cmd("RUN; WAIT 5")
v = ps.get_float("A")[0]
t = ps.get_time()                          # irregular ETS sample times, about 1/10 of the interval apart
ps.cmd("OSC ETS OFF")
```

The record keeps the requested number of samples; the time step becomes
`interval / interleave`. Use `OSC ETS OFF` afterwards.

### 3.8 Resolution and downsampling (5000 series)

```python
ps.cmd("OSC BITS 12")                      # 8, 12, 14, 15, 16 on ps5000a
print(ps.cmd("OSC MININTERVAL?"))          # fastest interval for the enabled channels
ps.cmd("OSC DOWNSAMPLE AVERAGE 10")        # NONE, AGGREGATE, DECIMATE, AVERAGE
```

More bits means a slower fastest interval and fewer usable channels (15 bits:
2 channels, 16 bits: 1 channel). The 2000 and 3000 series are 8-bit, the 4000
series is 12-bit; `OSC BITS` then accepts only that value.

### 3.9 Stopping from another thread (for example a GUI button)

```python
import threading

ps.cmd("TRG EDGE A RISING 1.9; TRG AUTO 0")       # never fires
ps.cmd("RUN")
threading.Timer(2.0, lambda: ps.cmd("STOP")).start()
print(ps.cmd("WAIT 60"))                          # ABORTED after about 2 s
```

`STOP` can be called from any thread at any time. `WAIT` returns `READY`,
`TIMEOUT` (the capture keeps running, so you may call `WAIT` again) or
`ABORTED`. `Ctrl+C` during `WAIT` stops the instrument.

### 3.10 Probes, scaling and reset

```python
ps.cmd("A FACTOR 10")      # 10:1 probe: get_float() now returns 10x the input volts
ps.cmd("RESET")            # all settings back to defaults (also OSC RESET), FACTOR included
```

### 3.11 Several scopes, or one of several

```python
print(ps.cmd("DEVICES?"))          # e.g. "PS5000A:JY064/0018,PS2000A:ABC12/0001"
ps.cmd("OPEN JY064/0018")          # open that serial number
ps.cmd("OPEN PS2000A")             # first scope served by the ps2000a driver
```

Use one `Picoscope()` object per instrument.

---

## 4. Differences between the series

`CAPS?` summarizes what the opened model can do. The module checks what it
knows from the driver API; what depends on the model is decided by the driver,
and its "not supported" answers become `ExceptionNotSupported`.

| Feature | 2000 (ps2000a) | 3000 (ps3000a) | 4000 (ps4000a) | 5000 (ps5000a) |
|---------|----------------|----------------|----------------|----------------|
| Resolution | 8 bit | 8 bit | 12 bit | 8-16 bit (`OSC BITS`) |
| Channels | 2 or 4 | 2 or 4 | 2, 4 or 8 | 2 or 4 |
| Digital inputs (MSO) | on MSO models | on MSO models | - | on MSO models |
| Pulse-width trigger | yes | yes | no | yes |
| `TRG WITHINPRE`, `TRG EDGEDETECT` | no | no | no | yes |
| Trigger information | no | yes | no | yes |
| `TRG AUTO` resolution | ms | ms | ms | µs |
| Verified on hardware | **no** | **no** | **no** | yes (5443D) |

On 8-channel scopes the channels are `A` to `H` and `G` is the channel G; the
generator is always `GEN`. Not supported at all: the 3000E and 5000E series
(driver `psospa`), the 6000 series and the selectable resolution of the 4444.

---

## 5. Known limits and pitfalls

* **External trigger.** `RISING` and `FALLING` honour the level. `BOTH` fires
  on every edge whatever the level is. `ABOVE` and `BELOW` are refused on EXT
  because the hardware fires at any level. A level just outside the signal
  swing fires only now and then (hysteresis and overshoot).
* **Pulse-width qualifier** (`TRG PW ...`). On a 5443D it did not discriminate
  the pulse width in tests; treat it as unverified.
* **ETS** works with channel A only, in single block mode, with an edge
  trigger and no aggregation.
* **Window triggers** `ENTER`, `EXIT` and `ENTEROREXIT` need real crossings of
  the window; a signal that stays inside will not trigger.
* **Order of trigger commands.** The module applies the trigger at `ARM`/`RUN`
  and sends the directions of all sources before their thresholds, as the
  driver requires, so the order of your `TRG` commands does not matter.
* **Analog offset and trigger level.** The level is compared after the offset
  is added; a level outside the range is an error, not clipped.
* **Generator** output is not stopped by `STOP`. Use `GEN OFF` or `CLOSE`.
* **Instrument held by another program.** A unit open in PicoScope 7 is not
  listed by `DEVICES?` and cannot be opened.
* **`OPEN` cannot be interrupted**; it takes a few seconds.
* **Digital (MSO) inputs** `D0`, `D1` and `TRG DIG` are not tested on
  hardware.
* **Series 2000, 3000 and 4000** are implemented from the driver headers and
  tested on the simulator only; see `docs/HW_TEST_PLAN.md` for the checklist.

---

## 6. Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `driver not available` | PicoSDK/PicoScope 7 not installed, or the DLLs are in an unusual place: set the environment variable `PICO_SDK_DIR` to the folder with the DLLs. |
| `OPEN` finds no instrument | The scope is not connected, is open in PicoScope 7, or needs power (a 4-channel scope on USB 2.0 may need the DC adaptor): see `POWER?`. |
| `PICO_POWER_SUPPLY_NOT_CONNECTED` / `PICO_POWER_SUPPLY_UNDERVOLTAGE` | Connect or replace the power supply and confirm with `POWER DC` or `POWER USB`. |
| `a capture is running, use STOP first` | Settings that change the capture cannot be changed while it runs: `STOP` first. |
| `PICO_TOO_MANY_SAMPLES`, `PICO_INVALID_TIMEBASE` | The request exceeds the scope's memory or fastest interval: lower `PRETRIGGER + POSTTRIGGER` or raise `OSC INTERVAL`. `OSC MAXSAMPLES?` and `OSC MININTERVAL?` tell the limits. |
| `trigger level ... is outside the input range` | Level plus offset beyond the range: check `A RANGE?` and `A OFFSET?`. |
| `Not supported: ...` | The model cannot do it; `CAPS?` shows the family and features. |
| `ETS works with channel A only` | Switch the other channels off: `ALL OFF; A ON`. |
| `WAIT` returns `TIMEOUT` | No trigger yet; use `TRG AUTO <time>` for a fallback or `WAIT` again. |

Driver errors appear as `ps5000aRunBlock failed: PICO_...` (the function and
the PicoStatus name); the codes are listed in `PicoStatus.h` of the PicoSDK.

---

## 7. Command reference by group

All commands of one group together. `<x>` is a value, `a|b` means "one of",
`[x]` is optional. Every setting command that has a value can be queried with
a `?` after the key (`OSC INTERVAL?`, `A RANGE?`, `TRG AUTO?`, `GEN FREQ?`);
the group summary (`OSC?`, `A?`, `TRG?`, `GEN?`) shows everything at once.
`HELP` prints the one-line version of this list and `HELP? <prefix>` filters
it (`HELP? GEN`).

Settings that change the capture (most `OSC`, channel and `TRG` settings)
are refused with `a capture is running, use STOP first` while a capture runs.
Changing one after a capture discards the data of that capture.

### 7.1 Instrument and control

- `OPEN [serial]`, `OPEN <family> [serial]`, `OPEN SIM [variant]`: open the
  first instrument found, the one with that serial number, the first one of a
  driver family (`PS2000A`, `PS3000A`, `PS4000A`, `PS5000A`), or a simulated
  instrument. Sends all settings stored so far.
- `CLOSE`: stops, sets the generator output to 0 V and closes the instrument.
- `DEVICES?`: connected instruments that are not open, `FAMILY:serial,...`
  (`NONE` when there is none).
- `IDN?`: `<model> <serial>`, e.g. `5443D JY064/0018`. `INFO?`: all unit
  information strings.
- `CAPS?`: what the model can do, e.g. `FAMILY=PS5000A VARIANT=5443D
  CHANNELS=4 MSO=OFF BITS=8,12,14,15,16 PULSEWIDTH=ON TRIGINFO=ON
  GENERATOR=ON SIM=OFF`.
- `STATE?`: `CLOSED`, `IDLE`, `ARMED` (waiting for the trigger), `READY`
  (data available) or `STREAMING`.
- `POWER?`: power source `DC`, `USB` or `USB2`. `POWER DC|USB`: confirm a
  change of the power source after the driver asked for it.
- `LED <count>|ON|STOP`: flash the front LED, `ON` without end.
- `RESET`: all settings back to the defaults (also `OSC RESET`).
- `HELP`, `HELP? [prefix]`: command list.

### 7.2 Acquisition: `OSC`

Defaults: 8 bits, `INTERVAL` 1 µs, `PRETRIGGER` 100, `POSTTRIGGER` 1000,
`RECORDS` 1, block mode, no downsampling, `STREAMBUF` 100000, `AUTOSTOP` off,
ETS off. `OSC?` returns e.g. `BITS=8 INTERVAL=1e-06 PRETRIGGER=100
POSTTRIGGER=1000 RECORDS=1 MODE=BLOCK DOWNSAMPLE=NONE,1 ETS=OFF
STREAMBUF=100000 AUTOSTOP=OFF`.

**Resolution**
- `OSC BITS 8|12|14|15|16`: resolution. Selectable on the 5000 series only
  (15 bits: at most 2 channels, 16 bits: 1 channel); the other series have a
  fixed resolution and refuse any other value as not supported.

**Timebase**
- `OSC INTERVAL <s>` (alias `OSC TIMEBASE`): requested sampling interval. The
  longest interval the scope offers that does not exceed it is used.
  `OSC INTERVAL?` gives the interval actually used after `ARM`/`RUN`, the
  requested one before.
- `OSC TBINDEX <n>`: set the driver's timebase index directly (overrides
  `OSC INTERVAL`); `OSC TBINDEX?` gives the index of the last run.
- `OSC MININTERVAL?`: the fastest interval for the enabled channels and the
  resolution.

**Record length and number**
- `OSC PRETRIGGER <n>`, `OSC POSTTRIGGER <n>`: samples before and after the
  trigger. `OSC SAMPLES?` is their sum (the length of one record).
- `OSC RECORDS <n>`: records per run (rapid block); 1 is a single block.
- `OSC MAXSAMPLES?`: the most samples per record that fit into the memory for
  the current settings. `OSC MAXRECORDS?`: the most records (memory segments).

**Mode and data reduction**
- `OSC MODE BLOCK|STREAM`: block capture (the default) or streaming.
- `OSC DOWNSAMPLE NONE|AGGREGATE|DECIMATE|AVERAGE [ratio]`: reduction by the
  driver. `AGGREGATE` returns the maximum and the minimum of every `ratio`
  samples. `OSC DOWNSAMPLE?` gives mode and ratio.
- `OSC STREAMBUF <n>`: length of the streaming transfer buffer in samples.
- `OSC AUTOSTOP ON|OFF`: streaming ends after `PRETRIGGER + POSTTRIGGER`
  samples.

**Equivalent-time sampling**
- `OSC ETS OFF|FAST|SLOW [cycles] [interleave]`: ETS for repetitive signals.
  Defaults for cycles and interleave: 20 and 10; `cycles` must be at least
  `interleave`. Channel A only, block mode, edge trigger (recipe 3.7).
  `OSC ETS?` gives mode, cycles, interleave.

**Reset**
- `OSC RESET`: the same as `RESET`.

### 7.3 Channels: `A` to `H`, `ALL`, `D0`/`D1`

`A` to `D` on most scopes, `A` to `H` on 8-channel models; a channel the
model does not have raises `ExceptionNotSupported`. Defaults: only `A` is on,
DC coupling, ±5 V range, offset 0, full bandwidth, `FACTOR` 1. `A?` returns
e.g. `ON COUPLING=DC RANGE=5 OFFSET=0 BW=FULL FACTOR=1`.

- `X ON|OFF`: enable or disable the channel (`X` is `A`...`H`).
- `X COUPLING DC|AC`: input coupling. After switching to AC the signal needs
  about a second to settle.
- `X RANGE <V>`: the smallest input range that covers `<V>`: ±10 mV, 20 mV,
  50 mV, 100 mV, 200 mV, 500 mV, 1 V, 2 V, 5 V, 10 V, 20 V (50, 100 and 200 V
  on models that have them). `A RANGE 1.5` selects ±2 V. A range the model
  lacks is refused as not supported.
- `X OFFSET <V>`: analog offset. It shifts the window of the input range; the
  returned volts are corrected, so they still show the input voltage.
  `X OFFSETLIMITS?` gives the allowed minimum and maximum for the current
  range and coupling. Trigger levels are compared after the offset is added.
- `X BW FULL|20MHZ`: bandwidth limiter (models that have one).
- `X FACTOR <n>`: output scale. The volts returned by `get_float`, `DATA?` and
  `get_stream` are multiplied by `n` (for example 10 for a 10:1 probe). Ranges,
  offsets and trigger levels stay in input volts. `n` must not be zero.
- `X?`: summary of the channel.
- `ALL <channel command>`: the same channel command for every analog channel
  of the model (`ALL COUPLING DC`, `ALL RANGE 2`, `ALL OFF`). `ALL?` gives one
  summary line per channel, `ALL <KEY>?` one value per channel. All or
  nothing.
- `D0 ON|OFF`, `D1 ON|OFF`, `D0 LEVEL <V>`, `D1 LEVEL <V>`: digital ports of
  MSO models (`D0` is bits 0-7, `D1` bits 8-15) and their logic threshold
  (default 1.5 V). Not tested on hardware.

### 7.4 Trigger: `TRG`

Nothing is triggered until a source is set (`TRG?` returns `OFF`, the scope
runs free). Defaults of a source: `RISING`, level 0 V, lower level 0 V,
hysteresis `AUTO` (1 % of the full scale). `LOGIC` `AND`, `DELAY` 0, `AUTO`
0 (wait forever). `TRG?` returns e.g. `LOGIC=AND A=RISING,0.5,0,AUTO DELAY=0
AUTO=0`. The trigger is sent to the scope by `ARM`/`RUN`.

**Quick setup**
- `TRG EDGE <src> RISING|FALLING|BOTH|ABOVE|BELOW <V>`: clears the trigger and
  sets one source. `<src>` is `A`...`H` or `EXT` (the external input, ±5 V;
  only `RISING`, `FALLING` and `BOTH` work there).

**Sources, one at a time** (`<src>` is `A`...`H` or `EXT`; the first setting
creates the source)
- `TRG <src> DIR <direction>`: what triggers (table below).
- `TRG <src> LEVEL <V>`: threshold; the upper threshold of a window.
- `TRG <src> LOWER <V>`: lower threshold of a window or runt, and the
  threshold of the `...LOWER` directions.
- `TRG <src> HYST <V>|AUTO`: hysteresis.
- `TRG <src> OFF`: remove the source from the trigger.

| Direction | Triggers when |
|-----------|---------------|
| `RISING`, `FALLING`, `BOTH` | the signal crosses `LEVEL` upward, downward or either way |
| `ABOVE`, `BELOW` | the signal is above or below `LEVEL` (a state; on EXT they are refused) |
| `ABOVELOWER`, `BELOWLOWER`, `RISINGLOWER`, `FALLINGLOWER` | as above, but against `LOWER` |
| `INSIDE`, `OUTSIDE` | the signal is inside or outside the window `LOWER`..`LEVEL` (a state) |
| `ENTER`, `EXIT`, `ENTEROREXIT` | the signal enters or leaves the window, or either |
| `POSITIVERUNT`, `NEGATIVERUNT` | a pulse that crosses one threshold but not the other |

**Combining**
- `TRG LOGIC AND|OR`: all sources at once, or any of them.
- `TRG CLEAR` (or `TRG OFF`): remove every condition (free run).

**Timing**
- `TRG DELAY <samples>`: shift the trigger point by that many samples after
  the trigger.
- `TRG AUTO <s>`: capture anyway after this time without a trigger; 0 waits
  forever. The 2000, 3000 and 4000 series round it up to whole milliseconds.

**Pulse-width qualifier** (not in the 4000 series; unreliable on the 5443D,
see section 5)
- `TRG PW TYPE NONE|LESS|GREATER|INSIDE|OUTSIDE`: how the pulse width is
  judged against the limits.
- `TRG PW SOURCE <src>`: channel of the pulse. `TRG PW DIR <direction>`: edge
  that ends the pulse (default `FALLING`). `TRG PW LEVEL <V>|AUTO`: threshold
  (`AUTO` uses the `LEVEL` of the source).
- `TRG PW LOWER <s>`, `TRG PW UPPER <s>`: the pulse width limits in seconds.

**Digital and extras**
- `TRG DIG <bit> LOW|HIGH|RISING|FALLING|BOTH|X`: condition on a digital
  input, bit 0-15; `X` removes it. MSO only, not tested on hardware.
- `TRG WITHINPRE ON|OFF`: allow a trigger within the pre-trigger samples.
  `TRG EDGEDETECT ON|OFF`: edge detection of the logic trigger output. Both
  exist in the 5000 series only.

### 7.5 Running a capture and reading it

- `ARM`: send all settings to the scope without starting.
- `RUN`: `ARM` and start; returns at once.
- `WAIT [timeout]`: wait for the end of the capture and return `READY`,
  `TIMEOUT` or `ABORTED`. Without a timeout it waits as long as it takes.
- `STOP`: interrupt a capture, streaming or a data transfer (any thread).
- `READY?`: `1` when the capture is complete, `0` otherwise (always `0` while
  streaming).
- `CAPTURES?`: records captured so far (also during a rapid block run).
- `OVERFLOW?`: `<record>:<channels>` of every record that exceeded the input
  range, e.g. `0:A 3:AB`, or `NONE`; while streaming the channels only.
- `TRIGTIME?`: trigger time offsets of the records in seconds, comma
  separated. In Python `get_trigger_times()`.
- `DATA? <src> [record]`: one record of channel `<src>` as comma separated
  volts (`D0`/`D1`: integers). For short records only; use `get_float` for
  large data.

### 7.6 Signal generator: `GEN`

Defaults: off, `SINE`, 1 kHz, 1 Vpp, offset 0, no sweep, `SHOTS` 0, `SWEEPS`
0, trigger `NONE RISING`. `GEN?` returns e.g. `OFF WAVE=SINE FREQ=1000
AMPL=1 OFFSET=0 SWEEP=OFF SHOTS=0 SWEEPS=0 TRIGGER=NONE,RISING`. Every
change is sent to the scope at once. What the model cannot do raises
`ExceptionNotSupported`.

**Output**
- `GEN ON|OFF`: start or stop the output (off means 0 V DC).
- `GEN WAVE <wave>`: `SINE`, `SQUARE`, `TRIANGLE`, `RAMPUP`, `RAMPDOWN`,
  `SINC`, `GAUSSIAN`, `HALFSINE`, `DC`, `NOISE`, `PRBS`, `ARB`.
- `GEN FREQ <Hz>`: frequency (for `PRBS` the bit rate).
- `GEN AMPL <Vpp>`: peak-to-peak amplitude. `GEN OFFSET <V>`: offset voltage.
- `GEN ARB <v1,v2,...>`: load an arbitrary waveform, values from -1 to +1,
  and select it. `GEN WAVE ARB` before loading one is an error.

**Sweep**
- `GEN SWEEP <stop Hz> <step Hz> <dwell s> UP|DOWN|UPDOWN|DOWNUP`: sweep from
  `GEN FREQ` to the stop frequency. `GEN SWEEP OFF` ends it.

**Bursts and triggering**
- `GEN SHOTS <n>|CONT`: number of cycles after each generator trigger.
  `GEN SWEEPS <n>|CONT`: the same for sweeps. 0 or `CONT` means continuous.
- `GEN TRIGGER NONE|SCOPE|AUX|EXT|SOFT [RISING|FALLING|GATEHIGH|GATELOW]`:
  what starts a burst and how.
- `GEN EXTLEVEL <V>`: threshold of the external generator trigger.
- `GEN FIRE`: software trigger (with `GEN TRIGGER SOFT`).
- `GEN GATE ON|OFF`: software gate (with `GEN TRIGGER SOFT GATEHIGH` or
  `GATELOW`).

### 7.7 Python methods besides `cmd()`

| Method | Purpose |
|--------|---------|
| `get_float(source, minimum=False)` | Volts, array (records, samples). `minimum=True` gives the minima of aggregated data. |
| `get_int(source)`, `get_min(source)` | Raw ADC counts. |
| `get_time()` | Time axis in seconds, 0 = trigger (ETS: driver times). |
| `get_trigger_times()` | Trigger time of each record, seconds. |
| `get_trigger_info()` | Trigger information per record (3000 and 5000 series). |
| `get_stream(volts=True)` | Streaming data since the previous call, dict source to array. |
| `get_digital()` | MSO digital inputs as integers. Not tested on hardware. |
| `set_awg(samples)` | Arbitrary waveform from an array of -1..+1. |
| `prepare()`, `start(callback=None)`, `wait(timeout)`, `stop()`, `ready()` | The same as `ARM`, `RUN`, `WAIT`, `STOP`, `READY?`. |
| `set_timebase(interval)`, `set_preposttrigger(pre, post)` | Convenience setters. |
| `help(prefix="")` | The command list. |
