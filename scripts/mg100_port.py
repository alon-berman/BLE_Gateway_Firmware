"""Find the serial port of an MG100 gateway's console.

The MG100 console is reached through Laird's USB-to-UART cable, an FTDI FT231X
that reports USB vendor 0x0403, product 0x6015 and the product name "LC231X".
Other FTDI adapters are accepted as a fallback. On macOS each adapter appears
twice, as /dev/cu.usbserial-XXXX and /dev/tty.usbserial-XXXX; pyserial lists
the cu device, which is the right one to open.

When more than one adapter is plugged in, each free port is asked for its
`name` attribute (for example 'MG100-0668356'). A port held by another program,
such as a running flash, is reported as busy and never written to.

Command line:

    python scripts/mg100_port.py          # list adapters and what answers on each
    python scripts/mg100_port.py --pick   # print the one port to use, or exit 1

Other scripts accept "auto" wherever they take a serial port.
"""

import argparse
import errno
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional

import serial
import serial.tools.list_ports

AUTO = "auto"
FTDI_VID = 0x0403
LAIRD_PRODUCTS = {"LC231X"}
BAUDRATE = 115200
PROBE_SECONDS = 2.5
NAME_RE = re.compile(r"\]\s+name\s+'([^']*)'")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class PortNotFound(Exception):
    """No MG100 port, or more than one and no way to choose."""


@dataclass
class Candidate:
    device: str
    product: str
    serial_number: str
    laird_cable: bool
    status: str = "not probed"   # not probed | mg100 | busy | no answer | error
    gateway_name: str = ""

    def describe(self) -> str:
        what = f"{self.product or 'USB serial'} {self.serial_number or ''}".strip()
        if self.status == "mg100":
            return f"{self.device}  ({what}, gateway {self.gateway_name})"
        return f"{self.device}  ({what}, {self.status})"


def candidate_ports() -> list:
    """FTDI serial adapters, Laird cables first."""
    found = []
    for p in serial.tools.list_ports.comports():
        if p.vid != FTDI_VID:
            continue
        product = p.product or p.description or ""
        found.append(Candidate(device=p.device, product=product,
                               serial_number=p.serial_number or "",
                               laird_cable=product in LAIRD_PRODUCTS))
    found.sort(key=lambda c: (not c.laird_cable, c.device))
    return found


def probe(candidate: Candidate, seconds: Optional[float] = None) -> Candidate:
    """Ask the device on this port for its name. Never writes to a busy port."""
    seconds = PROBE_SECONDS if seconds is None else seconds
    try:
        ser = serial.Serial(candidate.device, BAUDRATE, timeout=0.2, exclusive=True)
    except serial.SerialException as exc:
        busy = getattr(exc, "errno", None) in (errno.EBUSY, errno.EAGAIN) or \
            "busy" in str(exc).lower() or "lock" in str(exc).lower()
        candidate.status = "busy" if busy else "error"
        return candidate
    try:
        ser.reset_input_buffer()
        ser.write(b"\nattr get name\n")
        deadline = time.monotonic() + seconds
        text = ""
        while time.monotonic() < deadline:
            text += ANSI_RE.sub("", ser.read(512).decode(errors="replace"))
            match = NAME_RE.search(text)
            if match:
                candidate.status = "mg100"
                candidate.gateway_name = match.group(1)
                return candidate
        candidate.status = "no answer"
        return candidate
    finally:
        ser.close()


def find_mg100_port(probe_ports: bool = True) -> str:
    """Return the one serial port an MG100 console is on, or raise PortNotFound.

    One adapter: returned without touching the device. Several: each free port
    is probed and the single one that answers as an MG100 wins; failing that,
    a single Laird cable wins.
    """
    candidates = candidate_ports()
    if not candidates:
        raise PortNotFound("no FTDI USB-serial adapter found; is the gateway cable plugged in?")
    if len(candidates) == 1:
        return candidates[0].device
    if probe_ports:
        answered = [c for c in (probe(c) for c in candidates) if c.status == "mg100"]
        if len(answered) == 1:
            return answered[0].device
    laird = [c for c in candidates if c.laird_cable]
    if len(laird) == 1:
        return laird[0].device
    listing = "; ".join(c.describe() for c in candidates)
    raise PortNotFound(f"several adapters found, pass one explicitly: {listing}")


def resolve_port(value: Optional[str]) -> str:
    """Pass an explicit port through; detect one for "", None or "auto"."""
    if value and value.strip().lower() != AUTO:
        return value.strip()
    return find_mg100_port()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pick", action="store_true",
                        help="print only the port to use; exit 1 if there is none or it is ambiguous")
    parser.add_argument("--no-probe", action="store_true",
                        help="do not write to any port; choose by USB identity only")
    args = parser.parse_args()
    if args.pick:
        try:
            print(find_mg100_port(probe_ports=not args.no_probe))
            return 0
        except PortNotFound as exc:
            print(exc, file=sys.stderr)
            return 1
    candidates = candidate_ports()
    if not candidates:
        print("no FTDI USB-serial adapter found")
        return 1
    for c in candidates:
        if not args.no_probe:
            probe(c)
        print(c.describe())
    return 0


if __name__ == "__main__":
    sys.exit(main())
