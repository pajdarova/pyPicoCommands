# Hardware test plan: pypicocommands (PicoScope 2000, 3000, 4000, 5000)

`pypicocommands` was written and tested against simulated models
(`python -m unittest discover tests`) and checked against the installed
driver DLLs (every function it binds exists in `ps2000a`, `ps3000a`,
`ps4000a` and `ps5000a`, except the ones the series does not have). No
instrument other than a 5443D was available while it was written, so **the
ps2000a, ps3000a and ps4000a paths have never talked to a real instrument**.
This plan is done at the place where the instruments are.

Instruments of the department (quote 9/2024): 4x PicoScope 2408B (ps2000a),
2x 5443D (ps5000a), 1x 4824A (ps4000a); a 3000-series scope delivered with
the deposition device (ps3000a if it is a 3000A/B/D; model still to be
confirmed - a 3000E needs the psospa driver, which this module does not
have).

Run the steps in the console

    python -m pypicocommands                 # then: OPEN, commands, ...

or from a script with `Picoscope().cmd(...)`. Record OK / FAIL and a note.
Close PicoScope 7 before every test: the driver cannot open a unit that
another program holds.

Items marked **VERIFY** rely on an assumption that could not be checked
without hardware.

## 0. Installation and detection

| # | Action | Expected |
|---|--------|----------|
| 0.1 | PicoSDK (64 bit) installed | `C:\Program Files\Pico Technology\SDK\lib\ps2000a.dll` ... `ps5000a.dll` exist |
| 0.2 | `python -m pypicocommands.identify` (no instrument opened) | lists the drivers found and `DEVICES?` of every connected instrument as `FAMILY:serial` |
| 0.3 | connect one instrument, `DEVICES?` | one entry with the right family (2408B `PS2000A`, 3000 `PS3000A`, 4824A `PS4000A`, 5443D `PS5000A`) |
| 0.4 | `OPEN`, `IDN?`, `CAPS?` | the right VARIANT; `CHANNELS=4` (2408B, 5443D, 3x04), `8` (4824A), 2 for 3x0 2-channel models; `MSO=ON` only with digital inputs; `BITS=8` (2000, 3000), `12` (4000), `8,12,14,15,16` (5000) |
| 0.5 | two instruments of different series connected, `OPEN <serial of the second>` | the second one is opened whichever driver serves it |
| 0.6 | `OPEN PS3000A` with only a 2408B connected | error "no PicoScope found" |

## 1. Common steps (every series)

Wiring: AWG / generator output to channel A (BNC T-piece also to B). Models
without a generator: use the probe compensation output or a function
generator instead and skip the `G` steps.

| # | Commands | Expected |
|---|----------|----------|
| 1.1 | `A ON; A RANGE 2; A COUPLING DC; B OFF; OSC MININTERVAL?` | the fastest interval of the model (2408B/3000D 1 ns for one channel, 4824A 12.5 ns) |
| 1.2 | `GEN WAVE SINE; GEN FREQ 1kHz; GEN AMPL 1; GEN ON; OSC INTERVAL 10us; OSC PRETRIGGER 100; OSC POSTTRIGGER 900; TRG EDGE A RISING 0; RUN; WAIT 5` | `READY`; `get_float("A")` 1000 samples, about 0.5 V amplitude, trigger at index 100 |
| 1.3 | `OSC INTERVAL?` after 1.2 | not larger than 10 us and the next timebase would exceed it (the search of `_find_timebase`) |
| 1.4 | `OSC TBINDEX 0; A ON; B ON; C ON; RUN` | refused (timebase 0 not available with 3-4 channels), `STATE?` = `IDLE`, the unit stays open |
| 1.5 | `A RANGE 20; A RANGE 5` and the smallest range of the model | accepted ranges follow the model; a range it lacks gives `Not supported` (2000/3000: no +-10 mV) **VERIFY** |
| 1.6 | `TRG AUTO 100m; TRG EDGE A RISING 5; RUN; WAIT 1` | finishes by the auto trigger after about 100 ms (ps2000a/3000a/4000a: rounded up to whole ms) |
| 1.7 | `OSC RECORDS 10; OSC PRETRIGGER 0; OSC POSTTRIGGER 500; RUN; WAIT 5; CAPTURES?` | `10`; `get_float("A")` shape (10, 500) |
| 1.8 | `OSC MODE STREAM; OSC INTERVAL 10us; OSC PRETRIGGER 0; OSC POSTTRIGGER 50k; OSC AUTOSTOP ON; RUN` and `get_stream()` in a loop | data arrive, stream ends by itself |
| 1.9 | `A FACTOR 10; get_float` after a capture | values 10x larger; `A FACTOR?` = `10`; `OSC RESET` (or `RESET`) returns it to `1` |
| 1.10 | `RUN` then `STOP` from another thread while `WAIT 60` runs | `WAIT` returns `ABORTED` |
| 1.11 | `CLOSE`; `OPEN` again | works; the generator output is 0 V after CLOSE |
| 1.12 | `RESET` | all settings default; OPEN's 0 V generator attempt does not make OPEN fail on a model without a generator |

## 2. PicoScope 2408B (ps2000a)

| # | Commands | Expected |
|---|----------|----------|
| 2.1 | `CAPS?` | `FAMILY=PS2000A ... BITS=8 PULSEWIDTH=ON TRIGINFO=OFF GENERATOR=ON` |
| 2.2 | `POWER?` | `USB` (no `CurrentPowerSource` in this driver) |
| 2.3 | `A BW 20MHZ` | `Not supported: the ps2000a driver has no SetBandwidthFilter` |
| 2.4 | `POWER DC` | `Not supported` |
| 2.5 | `TRG WITHINPRE ON`, `TRG EDGEDETECT OFF`, `OSC BITS 12`, `D0 ON` | `Not supported` |
| 2.6 | trigger variants: `TRG EDGE A FALLING 0`, `TRG A DIR ABOVE; TRG A LEVEL 0.3`, `TRG LOGIC AND; TRG A DIR RISING; TRG B DIR RISING; TRG B LEVEL 0`, window `TRG A DIR INSIDE; TRG A LEVEL 0.5; TRG A LOWER -0.5` | each triggers as described; the V1 condition structure (ps2000a: 8 states incl. digital) is accepted **VERIFY** |
| 2.7 | pulse width: `TRG EDGE A RISING 0; TRG PW SOURCE A; TRG PW TYPE GREATER; TRG PW DIR RISING; TRG PW LOWER 20us` with a 10 kHz square wave | triggers only on pulses wider than 20 us **VERIFY** |
| 2.8 | ETS: `OSC ETS FAST` with a repetitive signal | accepted or `Not supported` (model dependent) **VERIFY** |
| 2.9 | AWG: `GEN ARB 0,1,0,-1; GEN FREQ 1kHz; GEN ON` | output frequency right; **VERIFY** the dwell unit (`_Family.awg_tick`, assumed 50 ns for ps2000a) with `GEN SWEEP` |
| 2.10 | `get_trigger_info()` after rapid block | `Not supported` (no `GetTriggerInfoBulk`) |
| 2.11 | MSO variants only: `D0 ON; D0 LEVEL 1.5; DATA? D0`, `TRG DIG 3 RISING` | digital data readable; `TRG DIG` gives `Not supported` (not implemented for ps2000a/3000a) |

## 3. PicoScope 3000 series (ps3000a)

| # | Commands | Expected |
|---|----------|----------|
| 3.1 | `CAPS?` | `FAMILY=PS3000A ... BITS=8 PULSEWIDTH=ON TRIGINFO=ON`; `MSO=ON` only for MSO models; `GENERATOR` per model |
| 3.2 | `POWER?`; `OPEN` without the DC adaptor (3000D only) | `DC`; with USB power `USB` (ChangePowerSource) and fewer usable channels **VERIFY** |
| 3.3 | `A BW 20MHZ` | accepted or `Not supported` (model dependent) **VERIFY** |
| 3.4 | trigger tests of 2.6 and 2.7 | as 2000; ps3000a uses `SetTriggerChannelConditionsV2` and `SetPulseWidthQualifierV2` **VERIFY** |
| 3.5 | `OSC RECORDS 5; ... RUN; WAIT 5; get_trigger_info()` | per record trigger index and time stamps |
| 3.6 | `OSC INTERVAL 1n` with one channel and with four channels | 1 ns (1 channel), 4 ns (3-4 channels) on a 3000D **VERIFY** the table |
| 3.7 | AWG as 2.9 | **VERIFY** the dwell unit |
| 3.8 | MSO: `D0 ON; D1 ON; DATA? D0` | digital data (NOT TESTED in this project) |

## 4. PicoScope 4824A (ps4000a)

| # | Commands | Expected |
|---|----------|----------|
| 4.1 | `CAPS?` | `FAMILY=PS4000A ... CHANNELS=8 BITS=12 PULSEWIDTH=OFF TRIGINFO=OFF` |
| 4.2 | `E ON; F ON; H ON; H RANGE 5; RUN; WAIT 5; get_float("H")` | channels E-H work (driver codes 4-7); EXT trigger code is 8 **VERIFY** (`TRG EXT LEVEL 1; TRG EDGE EXT RISING 1`) |
| 4.3 | `G ON; G RANGE 2`; `GEN ON; GEN FREQ 1kHz` | `G` is only channel G (8-channel scopes); the generator command is `GEN` on every model |
| 4.4 | `A RANGE 50`; `A RANGE 100` | 50 V accepted on the 4824A; 100 V `Not supported` **VERIFY** the limits of the model |
| 4.5 | `OSC BITS?`; `OSC BITS 8` | `12`; `Not supported` |
| 4.6 | `OSC MININTERVAL?` | 12.5 ns for any channel count **VERIFY** (`(timebase + 1) / 80 MHz` assumed only in the simulator; the real value comes from GetTimebase2) |
| 4.7 | `TRG PW TYPE GREATER` | `Not supported` (no pulse-width function in ps4000a) |
| 4.8 | `TRG EDGE A RISING 0; TRG B ...` multi-source AND / OR (`TRG LOGIC OR`) | conditions array form (`SetTriggerChannelConditions`, direction array without mode) accepted **VERIFY** |
| 4.9 | `get_trigger_info()` | `Not supported` |
| 4.10 | generator: `GEN ON` | works, or `Not supported` if the 4824A has none (then `CAPS?` shows `GENERATOR=OFF`) **VERIFY** |
| 4.11 | `A BW 20MHZ` | accepted or `Not supported` **VERIFY** |
| 4.12 | `POWER?`, USB-only operation | state reported; channel limits **VERIFY** |

## 5. PicoScope 5443D (ps5000a) - regression of the common module

The 5443D was verified on hardware (see `design_and_hardware_notes.md`); repeat
the relevant steps of sections 1-3 on it after every larger change. Open items
that remain: offset sign, EXT scaling, the pulse-width qualifier, downsampled
POSTTRIGGER and the CONT constant.

Extra: `OPEN SIM 2408B` (and the other simulated models) must keep working
with no instrument connected.

## 6. Not tested / not implemented

* Digital triggers (`TRG DIG`) of ps2000a / ps3000a MSO models: refused with
  `Not supported`.
* 3000E / 5000E (psospa), 6000 series, old ps2000/ps3000/ps4000/ps5000
  drivers, 4444 (selectable resolution in ps4000a).
* MSO digital inputs on any model (never tested in this project).
