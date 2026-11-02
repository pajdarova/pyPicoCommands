"""Unit tests of pypicocommands.picoscope against the simulated instrument (OPEN SIM).

Run with ``python -m unittest discover tests`` from the project root (or with
pytest). Neither the hardware nor the Pico driver is needed; the tests check
the command parser, the number/unit parser, the state machine, the capture
modes and the interruption (STOP / WAIT timeout) logic. Behaviour of the real
driver calls is checked by the hardware test plan (HW_TEST_PLAN.md).
"""
import threading
import time
import unittest

import numpy as np

from pypicocommands.picoscope import ExceptionPicoscope, Picoscope, _int, _num


class TestNumbers(unittest.TestCase):
    """Number parsing: SI prefix honoured, unit optional and ignored."""

    def test_volts(self):
        for text in ("0.5", "500m", "500mV", "500mv", "500MV", "500M",
                     "5e-1", "5E-1V"):
            self.assertAlmostEqual(_num(text, "V"), 0.5, msg=text)
        self.assertAlmostEqual(_num("20uV", "V"), 20e-6)
        self.assertAlmostEqual(_num("20µV", "V"), 20e-6)
        self.assertAlmostEqual(_num("-1.5V", "V"), -1.5)

    def test_seconds(self):
        self.assertAlmostEqual(_num("10us", "s"), 10e-6)
        self.assertAlmostEqual(_num("10US", "s"), 10e-6)
        self.assertAlmostEqual(_num("10Ms", "s"), 10e-3)   # M = milli here
        self.assertAlmostEqual(_num("10ms", "s"), 10e-3)
        self.assertAlmostEqual(_num("2ns", "s"), 2e-9)
        self.assertAlmostEqual(_num("1s", "s"), 1.0)
        self.assertAlmostEqual(_num("3", "s"), 3.0)

    def test_frequency(self):
        self.assertAlmostEqual(_num("10kHz", "Hz"), 1e4)
        self.assertAlmostEqual(_num("10Khz", "Hz"), 1e4)
        self.assertAlmostEqual(_num("1MHz", "Hz"), 1e6)    # M = mega here
        self.assertAlmostEqual(_num("100mHz", "Hz"), 0.1)  # m = milli
        self.assertAlmostEqual(_num("1G", "Hz"), 1e9)
        self.assertAlmostEqual(_num("50HZ", "Hz"), 50.0)

    def test_counts(self):
        self.assertEqual(_int("10k"), 10000)
        self.assertEqual(_int("2M"), 2000000)
        self.assertEqual(_int("1000"), 1000)
        for bad in ("10m", "1.5", "-3", "10u"):
            with self.assertRaises(ExceptionPicoscope, msg=bad):
                _int(bad)

    def test_wrong_unit_or_prefix(self):
        for text, kind in (("1MHz", "V"), ("5mV", "s"), ("1k", "V"),
                           ("1us", "Hz"), ("5x", "V"), ("abc", "V"),
                           ("1kV", "V"), ("1MV", "s")):
            with self.assertRaises(ExceptionPicoscope, msg=text):
                _num(text, kind)


class SimTestCase(unittest.TestCase):
    def setUp(self):
        self.ps = Picoscope()
        self.ps.cmd("OPEN SIM")

    def tearDown(self):
        self.ps.cmd("CLOSE")


class TestCommands(SimTestCase):
    def test_identity(self):
        self.assertEqual(self.ps.cmd("IDN?"), "5443D SIM0001")
        self.assertIn("VARIANT=5443D", self.ps.cmd("INFO?"))
        self.assertEqual(self.ps.cmd("STATE?"), "IDLE")

    def test_caps_and_family(self):
        caps = self.ps.cmd("CAPS?")
        self.assertIn("FAMILY=PS5000A", caps)
        self.assertIn("SIM=ON", caps)
        ps = Picoscope()
        ps.cmd("OPEN ps5000a SIM")         # family keyword, any case
        try:
            self.assertEqual(ps.cmd("IDN?"), "5443D SIM0001")
        finally:
            ps.cmd("CLOSE")
        for family in ("PSOSPA", "PS6000A"):
            with self.assertRaises(ExceptionPicoscope):
                Picoscope().cmd(f"OPEN {family}")

    def test_case_insensitive(self):
        self.assertEqual(self.ps.cmd("a range 2v; A RANGE?"), "2")
        self.assertEqual(self.ps.cmd("a Range?"), "2")
        self.assertEqual(self.ps.cmd("osc bits 12; osc bits?"), "12")
        self.assertEqual(self.ps.cmd("state?"), "IDLE")

    def test_multiple_queries(self):
        self.assertEqual(self.ps.cmd("A RANGE 500mV; A RANGE?; OSC BITS?"),
                         "0.5; 8")
        self.assertEqual(self.ps.cmd("A RANGE 1\nA RANGE?"), "1")

    def test_range_rounds_up(self):
        self.ps.cmd("A RANGE 1.2V")
        self.assertEqual(self.ps.cmd("A RANGE?"), "2")
        self.ps.cmd("A RANGE 10m")
        self.assertEqual(self.ps.cmd("A RANGE?"), "0.01")

    def test_interval_units(self):
        self.ps.cmd("OSC INTERVAL 1us")
        self.assertAlmostEqual(float(self.ps.cmd("OSC INTERVAL?")), 1e-6)
        self.ps.cmd("OSC PRETRIGGER 1k; OSC POSTTRIGGER 2k")
        self.assertEqual(self.ps.cmd("OSC SAMPLES?"), "3000")

    def test_errors_strict(self):
        with self.assertRaises(ExceptionPicoscope):
            self.ps.cmd("A NONSENSE 1")
        with self.assertRaises(ExceptionPicoscope):
            self.ps.cmd("A RANGE 1MHz")
        with self.assertRaises(ExceptionPicoscope):
            self.ps.cmd("XYZ")

    def test_errors_not_strict(self):
        ps = Picoscope(strict=False)
        ps.cmd("OPEN SIM")
        try:
            answer = ps.cmd("A RANGE 2; A RANGE?; A FOO; A RANGE 5")
            # Answers of the preceding queries come first, then the error.
            self.assertEqual(answer, "2; ERR A FOO: unknown parameter 'FOO'")
            # Commands before the failing one stay executed, the rest not.
            self.assertEqual(ps.cmd("A RANGE?"), "2")
        finally:
            ps.cmd("CLOSE")

    def test_settings_before_open(self):
        ps = Picoscope()
        ps.cmd("A RANGE 1; OSC BITS 12")
        ps.cmd("OPEN SIM")
        try:
            self.assertEqual(ps.cmd("A RANGE?; OSC BITS?"), "1; 12")
        finally:
            ps.cmd("CLOSE")

    def test_help(self):
        self.assertIn("OSC INTERVAL", self.ps.cmd("HELP?"))
        self.assertTrue(all(line.startswith("T")
                            for line in self.ps.cmd("HELP? TRG").splitlines()))

    def test_reset(self):
        self.ps.cmd("A RANGE 1; RESET")
        self.assertEqual(self.ps.cmd("A RANGE?"), "5")

    def test_ext_trigger_directions(self):
        # measured on a 5443D: ABOVE/BELOW fire at any level on EXT
        self.ps.cmd("TRG EDGE EXT RISING 0.5; TRG EXT DIR BOTH")
        self.assertEqual(self.ps.cmd("TRG EXT DIR?"), "BOTH")
        for text in ("TRG EDGE EXT ABOVE 1", "TRG EXT DIR BELOW",
                     "TRG EXT DIR INSIDE"):
            with self.assertRaises(ExceptionPicoscope, msg=text):
                self.ps.cmd(text)
        self.assertEqual(self.ps.cmd("TRG EXT DIR?"), "BOTH")   # unchanged

    def test_trigger_level_beyond_range_with_offset(self):
        # measured on a 5443D: level 0 V + offset 2.4 V is beyond the +-2 V
        # range and the driver answers PICO_THRESHOLD_OUT_OF_RANGE
        self.ps.cmd("A RANGE 2; A OFFSET 2.4; TRG EDGE A RISING 0")
        with self.assertRaises(ExceptionPicoscope) as cm:
            self.ps.cmd("ARM")
        self.assertIn("outside the input range", str(cm.exception))
        self.ps.cmd("A OFFSET 0; ARM")

    def test_o_reset(self):
        self.ps.cmd("A RANGE 1; B ON; B FACTOR 10; OSC BITS 12; OSC RESET")
        self.assertEqual(self.ps.cmd("A RANGE?; B FACTOR?; OSC BITS?; B?"),
                         "5; 1; 8; OFF COUPLING=DC RANGE=5 OFFSET=0 BW=FULL "
                         "FACTOR=1")

    def test_factor_setting(self):
        self.assertEqual(self.ps.cmd("A FACTOR?"), "1")
        self.ps.cmd("a factor 10")
        self.assertEqual(self.ps.cmd("A FACTOR?"), "10")
        self.assertEqual(self.ps.cmd("B FACTOR?"), "1")
        self.assertIn("FACTOR=10", self.ps.cmd("A?"))
        for bad in ("A FACTOR 0", "A FACTOR", "A FACTOR x"):
            with self.assertRaises(ExceptionPicoscope, msg=bad):
                self.ps.cmd(bad)
        self.assertEqual(self.ps.cmd("A FACTOR?"), "10")

    def test_factor_scales_output(self):
        self.ps.cmd("TRG AUTO 10ms; RUN")
        self.ps.cmd("WAIT 5")
        plain = self.ps.get_float("A")
        raw = self.ps.get_int("A")
        # FACTOR may be changed after the capture, data stay cached.
        self.ps.cmd("A FACTOR 10")
        self.assertEqual(self.ps.cmd("STATE?"), "READY")
        np.testing.assert_allclose(self.ps.get_float("A"), plain * 10)
        np.testing.assert_array_equal(self.ps.get_int("A"), raw)


class TestCapture(SimTestCase):
    def test_block(self):
        self.ps.cmd("OSC INTERVAL 1us; OSC PRETRIGGER 100; OSC POSTTRIGGER 900; "
                    "TRG EDGE A RISING 0; TRG AUTO 100ms")
        self.ps.cmd("RUN")
        self.assertEqual(self.ps.cmd("WAIT 5s"), "READY")
        self.assertEqual(self.ps.cmd("READY?"), "1")
        data = self.ps.get_float("A")
        self.assertEqual(data.shape, (1, 1000))
        # The simulator feeds 1 Vpp: the amplitude must be about 0.5 V.
        self.assertAlmostEqual(float(np.max(data)), 0.5, delta=0.05)
        t = self.ps.get_time()
        self.assertEqual(t.size, 1000)
        self.assertAlmostEqual(t[100], 0.0, delta=1e-9)
        text = self.ps.cmd("DATA? A")
        self.assertEqual(len(text.split(",")), 1000)

    def test_offset_is_removed(self):
        self.ps.cmd("A RANGE 2; A OFFSET 300mV; TRG AUTO 10ms")
        self.ps.cmd("RUN")
        self.ps.cmd("WAIT 5")
        self.assertAlmostEqual(float(np.mean(self.ps.get_float("A"))), 0.0,
                               delta=0.05)

    def test_rapid_block(self):
        self.ps.cmd("OSC RECORDS 5; OSC PRETRIGGER 0; OSC POSTTRIGGER 500; "
                    "TRG AUTO 10ms")
        self.ps.cmd("RUN")
        self.assertEqual(self.ps.cmd("WAIT 5"), "READY")
        self.assertEqual(self.ps.cmd("CAPTURES?"), "5")
        self.assertEqual(self.ps.get_float("A").shape, (5, 500))
        self.assertEqual(len(self.ps.cmd("DATA? A 3").split(",")), 500)

    def test_two_channels(self):
        self.ps.cmd("B ON; TRG AUTO 10ms; RUN")
        self.ps.cmd("WAIT 5")
        self.assertEqual(self.ps.get_float("A").shape,
                         self.ps.get_float("B").shape)
        with self.assertRaises(ExceptionPicoscope):
            self.ps.get_float("C")          # not enabled

    def test_aggregate(self):
        self.ps.cmd("OSC DOWNSAMPLE AGGREGATE 10; OSC POSTTRIGGER 1000; "
                    "OSC PRETRIGGER 0; TRG AUTO 10ms; RUN")
        self.ps.cmd("WAIT 5")
        mx = self.ps.get_float("A")
        mn = self.ps.get_float("A", minimum=True)
        self.assertEqual(mx.shape, (1, 100))
        self.assertTrue(np.all(mx >= mn))

    def test_wait_timeout_and_stop(self):
        # A level the 1 Vpp signal never reaches and no auto trigger:
        # the capture never finishes.
        self.ps.cmd("TRG EDGE A RISING 3V; TRG AUTO 0")
        self.ps.cmd("RUN")
        self.assertEqual(self.ps.cmd("STATE?"), "ARMED")
        t0 = time.monotonic()
        self.assertEqual(self.ps.cmd("WAIT 200ms"), "TIMEOUT")
        self.assertLess(time.monotonic() - t0, 2.0)
        self.assertEqual(self.ps.cmd("STOP"), "OK")
        self.assertEqual(self.ps.cmd("STATE?"), "IDLE")

    def test_wait_aborted_only_after_stop_finished(self):
        # real ps5000aStop takes a moment: WAIT must not report ABORTED, and
        # no other command may run, before the stop is complete
        self.ps.cmd("TRG EDGE A RISING 5; TRG AUTO 0; RUN")
        real_stop = self.ps._dev.stop

        def slow_stop():
            time.sleep(0.3)
            real_stop()
        self.ps._dev.stop = slow_stop
        threading.Timer(0.1, lambda: self.ps.cmd("STOP")).start()
        self.assertEqual(self.ps.cmd("WAIT 5"), "ABORTED")
        self.assertEqual(self.ps.cmd("STATE?"), "IDLE")
        self.ps.cmd("TRG CLEAR")             # no "capture is running"

    def test_stop_from_other_thread(self):
        self.ps.cmd("TRG EDGE A RISING 3V; TRG AUTO 0; RUN")
        threading.Timer(0.2, self.ps.stop).start()
        t0 = time.monotonic()
        self.assertEqual(self.ps.cmd("WAIT 10"), "ABORTED")
        self.assertLess(time.monotonic() - t0, 3.0)

    def test_settings_locked_while_armed(self):
        self.ps.cmd("TRG EDGE A RISING 3V; TRG AUTO 0; RUN")
        try:
            with self.assertRaises(ExceptionPicoscope):
                self.ps.cmd("A RANGE 1")
        finally:
            self.ps.cmd("STOP")

    def test_resolution_channel_limit(self):
        self.ps.cmd("OSC BITS 16; B ON; TRG AUTO 10ms")
        with self.assertRaisesRegex(ExceptionPicoscope, "at most 1"):
            self.ps.cmd("RUN")
        self.ps.cmd("B OFF; RUN")
        self.assertEqual(self.ps.cmd("WAIT 5"), "READY")

    def test_no_digital_inputs(self):
        # The simulated 5443D has no MSO ports; this is all that can be
        # tested of the digital features without an MSO instrument.
        with self.assertRaises(ExceptionPicoscope):
            self.ps.cmd("D0 ON")
        self.ps.cmd("TRG DIG 3 HIGH")
        with self.assertRaises(ExceptionPicoscope):
            self.ps.cmd("RUN")

    def test_ets(self):
        self.ps.cmd("OSC ETS FAST 20 4; TRG EDGE A RISING 0; TRG AUTO 10ms; RUN")
        self.assertEqual(self.ps.cmd("WAIT 5"), "READY")
        self.assertEqual(self.ps.get_time().size,
                         self.ps.get_float("A").shape[1])
        self.ps.cmd("OSC RECORDS 3")
        with self.assertRaises(ExceptionPicoscope):
            self.ps.cmd("RUN")              # ETS needs single block mode

    def test_trigger_window_logic(self):
        self.ps.cmd("B ON; TRG A DIR INSIDE; TRG A LEVEL 400mV; TRG A LOWER -400mV;"
                    " TRG B DIR FALLING; TRG B LEVEL 0; TRG LOGIC OR; TRG AUTO 10ms")
        self.assertIn("LOGIC=OR", self.ps.cmd("TRG?"))
        self.ps.cmd("TRG PW TYPE GREATER; TRG PW SOURCE A; TRG PW DIR FALLING; "
                    "TRG PW LOWER 10us")
        self.assertIn("PW=GREATER,A,FALLING,1e-05", self.ps.cmd("TRG?"))
        self.ps.cmd("RUN")
        self.assertEqual(self.ps.cmd("WAIT 5"), "READY")

    def test_streaming(self):
        self.ps.cmd("OSC MODE STREAM; OSC INTERVAL 10us; TRG OFF")
        self.ps.cmd("RUN")
        self.assertEqual(self.ps.cmd("STATE?"), "STREAMING")
        time.sleep(0.3)
        self.ps.cmd("STOP")
        stream = self.ps.get_stream()
        self.assertIn("A", stream)
        self.assertGreater(len(stream["A"]), 0)

    def test_streaming_autostop(self):
        self.ps.cmd("OSC MODE STREAM; OSC INTERVAL 10us; OSC PRETRIGGER 0; "
                    "OSC POSTTRIGGER 5k; OSC AUTOSTOP ON")
        self.ps.cmd("RUN")
        self.assertEqual(self.ps.cmd("WAIT 5"), "READY")
        self.assertEqual(len(self.ps.get_stream()["A"]), 5000)


class TestGenerator(SimTestCase):
    def test_builtin(self):
        self.ps.cmd("GEN WAVE SINE; GEN FREQ 10kHz; GEN AMPL 2V; GEN OFFSET 0; GEN ON")
        self.assertAlmostEqual(float(self.ps.cmd("GEN FREQ?")), 1e4)
        summary = self.ps.cmd("GEN?")
        self.assertIn("SINE", summary)
        # The simulated input sees the generator: amplitude 1 V.
        self.ps.cmd("A RANGE 2; TRG AUTO 10ms; RUN")
        self.ps.cmd("WAIT 5")
        self.assertAlmostEqual(float(np.max(self.ps.get_float("A"))), 1.0,
                               delta=0.1)
        self.ps.cmd("GEN OFF")

    def test_frequency_prefixes(self):
        self.ps.cmd("GEN FREQ 1MHz")
        self.assertAlmostEqual(float(self.ps.cmd("GEN FREQ?")), 1e6)
        self.ps.cmd("GEN FREQ 500mHz")
        self.assertAlmostEqual(float(self.ps.cmd("GEN FREQ?")), 0.5)

    def test_sweep(self):
        self.ps.cmd("GEN FREQ 1kHz; GEN SWEEP 10kHz 100Hz 1ms UP")
        self.assertEqual(self.ps.cmd("GEN SWEEP?"), "10000 100 0.001 UP")
        self.ps.cmd("GEN SWEEP OFF")
        self.assertEqual(self.ps.cmd("GEN SWEEP?"), "OFF")

    def test_continuous_shots(self):
        self.ps.cmd("GEN TRIGGER SOFT RISING; GEN SHOTS CONT")
        self.assertEqual(self.ps.cmd("GEN SHOTS?"), "CONT")
        self.assertIn("SHOTS=CONT", self.ps.cmd("GEN?"))

    def test_arb(self):
        self.ps.cmd("GEN ARB 0, 0.5, 1, 0.5, 0, -0.5, -1, -0.5; GEN ON")
        self.assertIn("ARB", self.ps.cmd("GEN?"))
        with self.assertRaises(ExceptionPicoscope):
            self.ps.set_awg([0, 2])


# *****************************************************************************
# Several oscilloscope series (simulated models)
# *****************************************************************************
from pypicocommands.picoscope import ExceptionNotSupported


class ModelTestCase(unittest.TestCase):
    """Base class: opens the simulated model in `model`."""
    model = "5443D"

    def setUp(self):
        self.ps = Picoscope()
        self.ps.cmd(f"OPEN SIM {self.model}")

    def tearDown(self):
        self.ps.cmd("CLOSE")

    def capture(self, source="A"):
        self.ps.cmd("TRG AUTO 10ms; RUN")
        self.assertEqual(self.ps.cmd("WAIT 5"), "READY")
        return self.ps.get_float(source)


class TestSeries2000(ModelTestCase):
    model = "2408B"

    def test_identity_and_caps(self):
        self.assertEqual(self.ps.cmd("IDN?"), "2408B SIM0001")
        caps = self.ps.cmd("CAPS?")
        for item in ("FAMILY=PS2000A", "CHANNELS=4", "MSO=OFF", "BITS=8",
                     "PULSEWIDTH=ON", "TRIGINFO=OFF", "SIM=ON"):
            self.assertIn(item, caps)

    def test_fixed_resolution(self):
        self.assertEqual(self.ps.cmd("OSC BITS?"), "8")
        self.ps.cmd("OSC BITS 8")
        with self.assertRaises(ExceptionNotSupported):
            self.ps.cmd("OSC BITS 12")

    def test_missing_functions(self):
        # no bandwidth limiter, no power source function, no trigger info
        with self.assertRaises(ExceptionNotSupported):
            self.ps.cmd("A BW 20MHZ")
        self.assertEqual(self.ps.cmd("A BW?"), "FULL")
        with self.assertRaises(ExceptionNotSupported):
            self.ps.cmd("POWER DC")
        self.assertEqual(self.ps.cmd("POWER?"), "USB")
        self.ps.cmd("OSC RECORDS 3; OSC PRETRIGGER 0; OSC POSTTRIGGER 100")
        self.ps.cmd("TRG AUTO 10ms; RUN; WAIT 5")
        with self.assertRaises(ExceptionNotSupported):
            self.ps.get_trigger_info()

    def test_not_supported_features(self):
        for text in ("TRG WITHINPRE ON", "TRG EDGEDETECT OFF", "D0 ON",
                     "A RANGE 50", "E ON"):
            with self.assertRaises(ExceptionNotSupported, msg=text):
                self.ps.cmd(text)

    def test_range_below_minimum(self):
        # the 2000 series has no +-10 mV range, the driver refuses it
        with self.assertRaises(ExceptionNotSupported):
            self.ps.cmd("A RANGE 10m")
        self.assertEqual(self.ps.cmd("A RANGE?"), "5")     # old value kept

    def test_capture(self):
        self.ps.cmd("OSC INTERVAL 1us; OSC PRETRIGGER 100; OSC POSTTRIGGER 900")
        data = self.capture()
        self.assertEqual(data.shape, (1, 1000))
        self.assertAlmostEqual(float(np.max(data)), 0.5, delta=0.05)
        # timebase 0 on this series is 1 ns (formula 2^tb ns)
        self.ps.cmd("OSC INTERVAL 1n")
        self.assertAlmostEqual(float(self.ps.cmd("OSC MININTERVAL?")), 1e-9,
                               delta=1e-12)

    def test_trigger_still_works(self):
        self.ps.cmd("TRG EDGE A RISING 0.1; TRG PW TYPE GREATER; "
                    "TRG PW SOURCE A; TRG PW LOWER 1us")
        self.ps.cmd("TRG AUTO 10ms")
        self.ps.cmd("RUN")
        self.assertEqual(self.ps.cmd("WAIT 5"), "READY")

    def test_no_generator_model(self):
        ps = Picoscope()
        ps.cmd("OPEN SIM 2204A")
        try:
            # opening works (the 0 V output attempt reveals the missing
            # generator), only using the generator fails
            self.assertIn("GENERATOR=OFF", ps.cmd("CAPS?"))
            ps.cmd("RESET")
            with self.assertRaises(ExceptionNotSupported):
                ps.cmd("GEN ON")
        finally:
            ps.cmd("CLOSE")

    def test_not_supported_text_mode(self):
        ps = Picoscope(strict=False)
        ps.cmd("OPEN SIM 2408B")
        try:
            self.assertEqual(
                ps.cmd("A BW?; A BW 20MHZ; A BW?"),
                "FULL; ERR A BW 20MHZ: Not supported: the ps2000a driver "
                "has no SetBandwidthFilter")
        finally:
            ps.cmd("CLOSE")


class TestSeries3000(ModelTestCase):
    model = "3404D MSO"

    def test_digital_inputs_exist(self):
        self.assertIn("MSO=ON", self.ps.cmd("CAPS?"))
        self.ps.cmd("D0 ON; D0 LEVEL 1.5")
        self.assertEqual(self.ps.cmd("D0?"), "ON LEVEL=1.5")

    def test_trigger_info_and_fixed_resolution(self):
        self.assertIn("TRIGINFO=ON", self.ps.cmd("CAPS?"))
        with self.assertRaises(ExceptionNotSupported):
            self.ps.cmd("OSC BITS 16")

    def test_reset_keeps_fixed_resolution(self):
        self.ps.cmd("RESET")
        self.assertEqual(self.ps.cmd("OSC BITS?"), "8")

    def test_capture(self):
        data = self.capture()
        self.assertEqual(data.shape, (1, 1100))


class TestSeries4000(ModelTestCase):
    model = "4824A"

    def test_eight_channels(self):
        self.assertIn("CHANNELS=8", self.ps.cmd("CAPS?"))
        self.ps.cmd("E ON; H ON; H RANGE 50")
        self.assertEqual(self.ps.cmd("H RANGE?"), "50")
        self.assertEqual(self.ps.cmd("E?").split()[0], "ON")

    def test_twelve_bit_fixed(self):
        self.assertEqual(self.ps.cmd("OSC BITS?"), "12")
        with self.assertRaises(ExceptionNotSupported):
            self.ps.cmd("OSC BITS 8")

    def test_channel_g_and_generator_command(self):
        # G is channel G (8-channel scope); the generator is GEN only
        self.ps.cmd("G ON; G RANGE 2")
        self.assertEqual(self.ps.cmd("G RANGE?"), "2")
        self.ps.cmd("GEN ON; GEN FREQ 2kHz")
        self.assertEqual(self.ps.cmd("GEN FREQ?"), "2000")

    def test_g_is_not_the_generator(self):
        # on a 4-channel scope there is no channel G and no short generator
        ps = Picoscope()
        ps.cmd("OPEN SIM 2408B")
        try:
            for text in ("G FREQ 1kHz", "G ON", "G?"):
                with self.assertRaises(ExceptionNotSupported, msg=text):
                    ps.cmd(text)
        finally:
            ps.cmd("CLOSE")

    def test_no_pulse_width_trigger(self):
        self.assertIn("PULSEWIDTH=OFF", self.ps.cmd("CAPS?"))
        with self.assertRaises(ExceptionNotSupported):
            self.ps.cmd("TRG PW TYPE GREATER")

    def test_range_above_maximum(self):
        with self.assertRaises(ExceptionNotSupported):
            self.ps.cmd("A RANGE 100")

    def test_timebase_formula(self):
        self.ps.cmd("A ON")
        # 80 MHz clock: timebase 0 = 12.5 ns, interval (tb + 1) / 80 MHz
        self.assertAlmostEqual(float(self.ps.cmd("OSC MININTERVAL?")), 12.5e-9,
                               delta=1e-12)
        self.ps.cmd("OSC INTERVAL 1us")
        self.capture()
        self.assertAlmostEqual(float(self.ps.cmd("OSC INTERVAL?")), 1e-6,
                               delta=1e-7)

    def test_capture_of_channel_h(self):
        self.ps.cmd("H ON")
        data = self.capture("H")
        self.assertEqual(data.shape, (1, 1100))

    def test_no_trigger_info(self):
        self.ps.cmd("OSC RECORDS 2; OSC PRETRIGGER 0; OSC POSTTRIGGER 50")
        self.ps.cmd("TRG AUTO 10ms; RUN; WAIT 5")
        with self.assertRaises(ExceptionNotSupported):
            self.ps.get_trigger_info()


class TestOpen(unittest.TestCase):
    def test_default_models_per_family(self):
        for family, variant in (("PS2000A", "2408B"), ("PS3000A", "3206D"),
                                ("PS4000A", "4824A"), ("PS5000A", "5443D")):
            ps = Picoscope()
            ps.cmd(f"OPEN {family} SIM")
            try:
                self.assertTrue(ps.cmd("IDN?").startswith(variant))
            finally:
                ps.cmd("CLOSE")

    def test_unknown_simulated_model(self):
        ps = Picoscope()
        with self.assertRaises(ExceptionPicoscope):
            ps.cmd("OPEN SIM 9999X")
        self.assertEqual(ps.cmd("STATE?"), "CLOSED")

    def test_fixed_resolution_conflict_at_open(self):
        ps = Picoscope()
        ps.cmd("OSC BITS 12")
        with self.assertRaises(ExceptionNotSupported):
            ps.cmd("OPEN SIM 2408B")
        self.assertEqual(ps.cmd("STATE?"), "CLOSED")
        ps.cmd("OPEN SIM 4824A")           # 12 bits agrees with the 4824A
        try:
            self.assertEqual(ps.cmd("OSC BITS?"), "12")
        finally:
            ps.cmd("CLOSE")

    def test_channel_beyond_the_model(self):
        ps = Picoscope()
        ps.cmd("E ON")                     # accepted before OPEN ...
        ps.cmd("OPEN SIM 2408B")           # ... and dropped at OPEN
        try:
            with self.assertRaises(ExceptionNotSupported):
                ps.cmd("E?")
            with self.assertRaises(ExceptionNotSupported):
                ps.cmd("TRG EDGE E RISING 0")
        finally:
            ps.cmd("CLOSE")

    def test_devices_without_driver_is_a_list(self):
        # whatever is connected, the answer is NONE or FAMILY:serial items
        text = Picoscope().cmd("DEVICES?")
        self.assertTrue(text == "NONE" or all(":" in p
                                              for p in text.split(",")))


if __name__ == "__main__":
    unittest.main()


class TestAllChannels(unittest.TestCase):
    """ALL <channel command>: the same command for every analog channel."""

    def open(self, model="5443D"):
        ps = Picoscope()
        ps.cmd(f"OPEN SIM {model}")
        self.addCleanup(ps.cmd, "CLOSE")
        return ps

    def test_sets_every_channel(self):
        ps = self.open()
        ps.cmd("ALL COUPLING AC; ALL RANGE 2; ALL OFFSET 0.1; ALL FACTOR 10; ALL BW 20MHZ")
        for ch in "ABCD":
            self.assertEqual(ps.cmd(f"{ch} COUPLING?"), "AC")
            self.assertEqual(ps.cmd(f"{ch} RANGE?"), "2")
            self.assertEqual(ps.cmd(f"{ch} FACTOR?"), "10")
        self.assertEqual(ps.cmd("ALL COUPLING?"), "AC AC AC AC")

    def test_all_off_then_one_on(self):
        ps = self.open()
        ps.cmd("ALL OFF; A ON")
        self.assertEqual(ps.cmd("A?").split()[0], "ON")
        for ch in "BCD":
            self.assertEqual(ps.cmd(f"{ch}?").split()[0], "OFF")

    def test_summary_lines(self):
        ps = self.open()
        lines = ps.cmd("ALL?").splitlines()
        self.assertEqual([ln[:2] for ln in lines], ["A:", "B:", "C:", "D:"])

    def test_covers_the_channels_of_the_model(self):
        ps = self.open("4824A")
        ps.cmd("ALL ON; ALL RANGE 5")
        self.assertEqual(ps.cmd("ALL RANGE?"), "5 5 5 5 5 5 5 5")
        ps2 = self.open("2408B")
        self.assertEqual(len(ps2.cmd("ALL RANGE?").split()), 4)

    def test_before_open_means_a_to_d(self):
        ps = Picoscope()
        ps.cmd("ALL COUPLING AC")
        self.assertEqual(ps.cmd("ALL COUPLING?"), "AC AC AC AC")

    def test_errors_leave_nothing_half_done(self):
        ps = self.open()
        with self.assertRaises(ExceptionPicoscope):
            ps.cmd("ALL RANGE nonsense")
        with self.assertRaises(ExceptionPicoscope):
            ps.cmd("ALL")
        self.assertEqual(ps.cmd("ALL RANGE?"), "5 5 5 5")

    def test_rollback_when_the_driver_rejects_one_channel(self):
        ps = self.open()
        original = ps._apply_channel
        calls = []

        def failing(name):
            calls.append(name)
            if name == "C" and calls.count("C") == 1:
                raise ExceptionPicoscope("driver rejected C")
            return original(name)
        ps._apply_channel = failing
        with self.assertRaises(ExceptionPicoscope):
            ps.cmd("ALL RANGE 1")
        ps._apply_channel = original
        self.assertEqual(ps.cmd("ALL RANGE?"), "5 5 5 5")
