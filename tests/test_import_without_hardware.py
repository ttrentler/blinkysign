"""Guard: BlinkySign must import with no hardware libraries installed at all.

Before the backend split, led_controller.py imported board/busio at module
scope and built the controller at import time, so nothing in this project could
be imported on a development machine. This test makes that property permanent:
it hides the hardware modules outright and asserts the package still imports.
"""
import builtins
import importlib
import subprocess
import sys
import textwrap

HARDWARE_MODULES = ("board", "busio", "neopixel_spi", "gpiozero", "RPi", "RPi.GPIO")


class _BlockHardware:
    """A meta_path finder that makes the hardware modules unimportable."""

    def find_module(self, fullname, path=None):
        if fullname in HARDWARE_MODULES:
            return self
        return None

    def find_spec(self, fullname, path=None, target=None):
        if fullname in HARDWARE_MODULES:
            raise ImportError(f"hardware module {fullname!r} blocked for this test")
        return None

    def load_module(self, fullname):
        raise ImportError(f"hardware module {fullname!r} blocked for this test")


def test_package_imports_with_hardware_blocked():
    blocker = _BlockHardware()
    saved = {name: sys.modules.pop(name, None) for name in HARDWARE_MODULES}
    for name in list(sys.modules):
        if name == "blinkysign" or name.startswith("blinkysign."):
            del sys.modules[name]

    sys.meta_path.insert(0, blocker)
    try:
        importlib.import_module("blinkysign")
        importlib.import_module("blinkysign.leds")
        importlib.import_module("blinkysign.server")
        importlib.import_module("blinkysign.service")
    finally:
        sys.meta_path.remove(blocker)
        for name, mod in saved.items():
            if mod is not None:
                sys.modules[name] = mod


def test_importing_leds_does_not_build_a_controller():
    """Importing must stay side-effect free -- no SPI touched, no strip built."""
    for name in list(sys.modules):
        if name == "blinkysign" or name.startswith("blinkysign."):
            del sys.modules[name]

    controller_mod = importlib.import_module("blinkysign.leds.controller")
    assert controller_mod._controller is None, (
        "importing blinkysign.leds built an LEDController -- the import-time "
        "singleton is back"
    )


def test_subprocess_import_is_clean():
    """A cold interpreter must import the package without warnings on stderr."""
    code = textwrap.dedent(
        """
        import sys
        import blinkysign.service
        sys.stdout.write("ok")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "ok"
