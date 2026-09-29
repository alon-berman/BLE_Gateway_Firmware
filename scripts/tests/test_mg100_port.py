"""Hardware-free tests for mg100_port.py.

Run with `python -m pytest scripts/tests` or `python scripts/tests/test_mg100_port.py`.
"""

import errno
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import serial  # noqa: E402

import mg100_port as mp  # noqa: E402


def port(device, vid=0x0403, product="LC231X", serial_number="FT000001"):
    return SimpleNamespace(device=device, vid=vid, pid=0x6015, product=product,
                           description=product, serial_number=serial_number)


class FakeSerial:
    """Answers `attr get name` with a per-device reply; some devices are busy."""
    replies = {}
    busy = set()

    def __init__(self, device, *args, **kwargs):
        if device in self.busy:
            raise serial.SerialException(errno.EBUSY, f"could not open port {device}: Resource busy")
        self.device = device
        self.sent = b""
        self.pending = b""

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.sent += data
        self.pending = self.replies.get(self.device, "").encode()

    def read(self, n):
        out, self.pending = self.pending[:n], self.pending[n:]
        return out

    def close(self):
        pass


def install(ports, replies=None, busy=()):
    mp.serial.tools.list_ports.comports = lambda: ports
    FakeSerial.replies = replies or {}
    FakeSerial.busy = set(busy)
    mp.serial.Serial = FakeSerial


def test_single_adapter_is_used_without_touching_it():
    install([port("/dev/cu.usbserial-A"), port("/dev/cu.Bluetooth", vid=None, product="")])
    assert mp.find_mg100_port() == "/dev/cu.usbserial-A"


def test_no_adapter_raises():
    install([port("/dev/cu.Bluetooth", vid=None, product="")])
    try:
        mp.find_mg100_port()
    except mp.PortNotFound as exc:
        assert "no FTDI" in str(exc)
    else:
        raise AssertionError("expected PortNotFound")


def test_probe_picks_the_one_that_answers_as_mg100():
    install([port("/dev/cu.usbserial-A"), port("/dev/cu.usbserial-B", serial_number="FT000002")],
            replies={"/dev/cu.usbserial-B": "[140] name                          'MG100-0668356'\r\nuart:~$ "})
    mp.PROBE_SECONDS = 0.2
    assert mp.find_mg100_port() == "/dev/cu.usbserial-B"


def test_busy_port_is_reported_and_not_written():
    install([port("/dev/cu.usbserial-A")], busy={"/dev/cu.usbserial-A"})
    c = mp.probe(mp.candidate_ports()[0], seconds=0.1)
    assert c.status == "busy"


def test_laird_cable_wins_over_other_ftdi_when_nothing_answers():
    install([port("/dev/cu.usbserial-A", product="FT232R USB UART"), port("/dev/cu.usbserial-B")])
    mp.PROBE_SECONDS = 0.1
    assert mp.find_mg100_port() == "/dev/cu.usbserial-B"


def test_two_laird_cables_and_no_answer_is_ambiguous():
    install([port("/dev/cu.usbserial-A"), port("/dev/cu.usbserial-B", serial_number="FT000002")])
    mp.PROBE_SECONDS = 0.1
    try:
        mp.find_mg100_port()
    except mp.PortNotFound as exc:
        assert "several adapters" in str(exc)
    else:
        raise AssertionError("expected PortNotFound")


def test_resolve_port_passes_explicit_paths_through():
    install([])
    assert mp.resolve_port("/dev/ttyUSB3") == "/dev/ttyUSB3"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
