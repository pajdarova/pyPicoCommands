"""pypicocommands.identify - list the PicoScope drivers and instruments of this computer.

Read-only: it loads the driver libraries (ps2000a, ps3000a, ps4000a,
ps5000a) and asks each for the connected units (``EnumerateUnits``). It
opens nothing, so it cannot disturb a running measurement, but an
instrument held by PicoScope 7 is not listed (the driver cannot see it).

With ``--open`` each found unit is also opened, its model, serial number,
firmware, power source and capabilities are printed and the unit is closed
again. Opening changes nothing in the instrument settings.

    python -m pypicocommands.identify            # drivers and serial numbers
    python -m pypicocommands.identify --open     # plus model and capabilities

Run it first on a new computer: it tells which series the department has
and which driver serves them (the answer shows which driver series the
module has to use).
"""
import sys

from .picoscope import (_FAMILIES, _FAMILY_ORDER, ExceptionPicoscope,
                        Picoscope, _HwBackend)


def main(open_units: bool) -> int:
    """Print the report; returns the number of instruments found."""
    total = 0
    for key in _FAMILY_ORDER:
        try:
            backend = _HwBackend(key)
        except ExceptionPicoscope as exc:
            print(f"{key}: driver not available ({exc})")
            continue
        serials = backend.enumerate()
        print(f"{key}: driver loaded, {len(serials)} unit(s) "
              f"{', '.join(serials)}")
        total += len(serials)
        if not open_units:
            continue
        for serial in serials:
            scope = Picoscope(strict=False)
            answer = scope.cmd(f"OPEN {key} {serial}")
            if answer != "OK":
                print(f"   {serial}: {answer}")
                continue
            try:
                print(f"   {scope.cmd('IDN?')}")
                print(f"   {scope.cmd('CAPS?')}")
                print(f"   POWER={scope.cmd('POWER?')} "
                      f"{scope.cmd('INFO?')}")
            finally:
                scope.cmd("CLOSE")
    if total == 0:
        print("No instrument found. Is it connected and closed in "
              "PicoScope 7?")
    return total


if __name__ == "__main__":
    main("--open" in sys.argv[1:])
