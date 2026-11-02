#!/usr/bin/python3
"""Apply the AC820 GT911 pinctrl correction through Linux device-tree only.

PS MIO registers are read for verification, never written by this program.
Run before applications open GPIO/I2C devices. Requires Python standard library.
"""

import argparse
import fcntl
import logging
import mmap
import os
from pathlib import Path
import re
import signal
import struct
import sys
import time


LOG = logging.getLogger("ac820-touch-pinctrl")
OVERLAY = Path("/sys/kernel/config/device-tree/overlays/ac820_gt911_pads")
DTBO = Path("/usr/local/share/ac820-touch/gt911_pads_fix.dtbo")
PLATFORM = Path("/sys/bus/platform/devices")
DEVICE_NAMES = ("e0004000.i2c", "e000a000.gpio")
EXPECTED = {0: 0x0600, 50: 0x1240, 51: 0x1240}
SLCR_BASE = 0xF8000000
MIO_OFFSET = 0x0700


def read_mio():
    """Read the three MIO registers using a strictly read-only mapping."""
    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, mmap.PAGESIZE, flags=mmap.MAP_SHARED,
                       prot=mmap.PROT_READ, offset=SLCR_BASE) as registers:
            return {pin: struct.unpack_from("<I", registers,
                                            MIO_OFFSET + 4 * pin)[0]
                    for pin in EXPECTED}
    finally:
        os.close(fd)


def format_mio(values):
    return ", ".join("MIO{}=0x{:04x}".format(pin, values[pin])
                     for pin in sorted(values))


def overlay_status():
    if not OVERLAY.exists():
        return None
    return (OVERLAY / "status").read_text().strip()


def require_gpio_idle():
    # Fail closed if debugfs cannot prove that consumers are absent.
    debug = Path("/sys/kernel/debug/gpio").read_text()
    consumers = [line.strip() for line in debug.splitlines()
                 if re.match(r"\s*gpio-\d+\b", line)]
    exports = sorted(str(path) for path in
                     Path("/sys/class/gpio").glob("gpio[0-9]*"))
    if consumers or exports:
        raise RuntimeError("GPIO is in use; stop applications and release GPIO "
                           "before retrying. Consumers: {}; exports: {}".format(
                               consumers, exports))


def bound_drivers():
    result = []
    for name in DEVICE_NAMES:
        link = PLATFORM / name / "driver"
        if not link.is_symlink():
            raise RuntimeError("{} is not bound to a platform driver".format(name))
        driver = link.resolve(strict=True)
        for control in ("unbind", "bind"):
            if not (driver / control).is_file():
                raise RuntimeError("Missing driver control: {}".format(driver / control))
        result.append((driver, name))
    return result


def rebind_all(detached):
    """Attempt every rebind even when a preceding one fails."""
    failures = []
    for driver, name in reversed(detached):
        try:
            (driver / "bind").write_text(name)
            time.sleep(0.05)
            if (PLATFORM / name / "driver").resolve(strict=True) != driver:
                raise RuntimeError("driver did not reattach")
            LOG.info("Rebound %s", name)
        except Exception as exc:
            failures.append("{}: {}".format(name, exc))
            LOG.error("Rebind failed for %s: %s", name, exc)
    return failures


def apply_fix(check_only=False):
    status = overlay_status()
    current = read_mio()
    LOG.info("Overlay status: %s; %s", status or "absent", format_mio(current))

    # This path must precede GPIO checks: restarting this service during a
    # correctly configured, active notebook must have no hardware side effects.
    if status == "applied" and current == EXPECTED:
        LOG.info("Touch pinctrl is already correct; no changes needed")
        return
    if check_only:
        raise RuntimeError("Touch pinctrl check failed; expected applied overlay and "
                           + format_mio(EXPECTED))
    if status not in (None, "applied"):
        raise RuntimeError("Existing overlay has status {!r}; inspect it before "
                           "retrying".format(status))

    blob = DTBO.read_bytes()
    if len(blob) < 40 or blob[:4] != b"\xd0\x0d\xfe\xed":
        raise RuntimeError("Invalid or truncated DTBO: {}".format(DTBO))
    if not OVERLAY.parent.is_dir():
        raise RuntimeError("Device-tree configfs is unavailable")
    drivers = bound_drivers()
    require_gpio_idle()
    detached = []
    operation_error = None
    try:
        for driver, name in drivers:
            (driver / "unbind").write_text(name)
            detached.append((driver, name))
            LOG.info("Detached %s", name)
        if status is None:
            OVERLAY.mkdir()
            (OVERLAY / "dtbo").write_bytes(blob)
            if overlay_status() != "applied":
                raise RuntimeError("Device-tree overlay did not become applied")
            LOG.info("Applied %s", DTBO)
        else:
            LOG.info("Overlay already applied; reprobe its GPIO and I2C consumers")
    except BaseException as exc:
        operation_error = exc
    finally:
        rebind_failures = rebind_all(detached)

    if rebind_failures:
        raise RuntimeError("Failed to rebind all devices: " + "; ".join(rebind_failures)) from operation_error
    if operation_error is not None:
        raise operation_error
    current = read_mio()
    if overlay_status() != "applied" or current != EXPECTED:
        raise RuntimeError("Pinctrl verification failed: " + format_mio(current))
    LOG.info("Touch pinctrl verified: %s", format_mio(current))


def interrupted(signum, _frame):
    raise RuntimeError("Interrupted by signal {}".format(signum))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the overlay and MIO registers without changing hardware")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(levelname)s: %(message)s")
    try:
        if os.geteuid() != 0:
            raise RuntimeError("Run as root (read-only /dev/mem verification requires it)")
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        with open("/run/ac820-touch-pinctrl.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            apply_fix(check_only=args.check)
    except Exception as exc:
        LOG.error("Touch pinctrl setup failed: %s. Camera/Jupyter services may continue.", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
