"""Flash an MG100 over its UART with mcumgr and swap to the new image.

Sequence: upload to slot 1 -> mark for test -> reset -> wait for the swapped
image to come up -> confirm. Every step is verified against the image's
MCUboot SHA-256, read from the image file itself, and every mcumgr call has a
bounded wall-clock time.

Why the care: SMP runs over the shell UART, and a gateway does not always
answer. It is silent while it reboots (the image swap itself takes a minute or
two), and firmware <= 7.1.0 resets on its own every few minutes when it cannot
register on the network, staying unresponsive for up to five minutes while it
waits for the forced watchdog reset. The previous version of this script gave
`image list` a 10000 s timeout, so one unanswered request hung the whole flash.
Here a step that gets no answer is retried until a deadline long enough to
ride out such a window, the shell log is silenced before every request
(`log halt` does not survive a reboot), and nothing is assumed to have worked
until the device reports it.
"""

import argparse
import os
import re
import struct
import subprocess
import sys
import time

import serial

from mcumgr_bin import McumgrNotFound, mcumgr_path
from mg100_port import PortNotFound, resolve_port
from send_serial_command_to_device import execute_command_over_serial

# Higher MTUs do not work over the MG100 UART.
SERIAL_MTU = 1024

MCUBOOT_IMAGE_MAGIC = 0x96F3B83D
MCUBOOT_TLV_INFO_MAGIC = 0x6907
MCUBOOT_TLV_PROT_INFO_MAGIC = 0x6908
MCUBOOT_TLV_SHA256 = 0x10

PROBE_TIMEOUT_S = 5          # per SMP attempt while waiting for the device
PROBE_INTERVAL_S = 2
READY_DEADLINE_S = 6 * 60    # rides out a forced-watchdog window (300 s) + boot
PROGRESS_EVERY_S = 30
UPLOAD_ATTEMPTS = 3
UPLOAD_WALL_CLOCK_S = 30 * 60
SWAP_DEADLINE_S = 5 * 60     # reset + MCUboot swap + boot
SWAP_GRACE_S = 30            # time the device may still answer before it resets


class FlashError(RuntimeError):
    """A flash step failed; the message says which one and why."""


def str2bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def local_image_hash(image_path: str):
    """Return the MCUboot SHA-256 (hex) stored in the image's TLV area.

    This is the value `mcumgr image list` reports as `hash`. Returns None if
    the file is not an MCUboot image or carries no SHA-256 TLV.
    """
    with open(image_path, "rb") as image_file:
        data = image_file.read()
    if len(data) < 32:
        return None
    magic, _, hdr_size, _, img_size, _ = struct.unpack_from("<IIHHII", data, 0)
    if magic != MCUBOOT_IMAGE_MAGIC:
        return None
    offset = hdr_size + img_size
    try:
        tlv_magic, tlv_total = struct.unpack_from("<HH", data, offset)
        if tlv_magic == MCUBOOT_TLV_PROT_INFO_MAGIC:
            offset += tlv_total
            tlv_magic, tlv_total = struct.unpack_from("<HH", data, offset)
        if tlv_magic != MCUBOOT_TLV_INFO_MAGIC:
            return None
        end = offset + tlv_total
        offset += 4
        while offset + 4 <= end:
            tlv_type, tlv_len = struct.unpack_from("<HH", data, offset)
            offset += 4
            if tlv_type == MCUBOOT_TLV_SHA256:
                return data[offset:offset + tlv_len].hex()
            offset += tlv_len
    except struct.error:
        return None
    return None


def parse_image_list(text: str) -> dict:
    """Parse `mcumgr image list` output into {slot: {version, hash, flags}}."""
    slots = {}
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r"image=\d+\s+slot=(\d+)", line)
        if match:
            current = {"version": "", "hash": "", "flags": set()}
            slots[int(match.group(1))] = current
            continue
        if current is None or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "version":
            current["version"] = value
        elif key == "hash":
            current["hash"] = value.lower()
        elif key == "flags":
            current["flags"] = set(value.split())
    return slots


def describe(slots: dict) -> str:
    if not slots:
        return "(no images reported)"
    return "; ".join(
        f"slot{slot}: {info['version'] or '?'} "
        f"[{' '.join(sorted(info['flags'])) or '-'}] {info['hash'][:12]}"
        for slot, info in sorted(slots.items()))


class Flasher:
    def __init__(self, conntype, connstring, timeout, retries):
        self.conntype = conntype
        self.port = connstring
        self.connstring = f"{connstring},mtu={SERIAL_MTU}"
        self.timeout = int(timeout)
        self.retries = int(retries)
        try:
            self.mcumgr = mcumgr_path()
        except McumgrNotFound as exc:
            raise FlashError(str(exc)) from exc
        if conntype == "serial" and not os.path.exists(connstring):
            raise FlashError(f"serial device not found: {connstring}")
        self._last_serial_error = None

    # -- primitives ---------------------------------------------------------
    def _base_cmd(self, timeout, retries):
        return [self.mcumgr, "-t", str(timeout), "-r", str(retries),
                "--conntype", self.conntype, "--connstring", self.connstring]

    def run(self, args, timeout=None, retries=None):
        """Run one mcumgr command. Never blocks longer than its own budget."""
        timeout = self.timeout if timeout is None else timeout
        retries = self.retries if retries is None else retries
        wall_clock = timeout * (retries + 1) + 10
        try:
            proc = subprocess.run(self._base_cmd(timeout, retries) + list(args),
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, errors="replace", timeout=wall_clock)
            return proc.returncode, proc.stdout
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            return 124, output + f"\n(mcumgr killed after {wall_clock}s)"

    def shell(self, command, quiet=True):
        """Send a shell command; a busy or missing port is reported, not fatal."""
        try:
            return execute_command_over_serial(command, device=self.port,
                                               read_timeout=1, quiet=quiet)
        except (serial.SerialException, OSError) as exc:
            if str(exc) != self._last_serial_error:   # say it once, not per probe
                print(f"  serial: '{command}' not sent ({exc})")
                self._last_serial_error = str(exc)
            return ""

    def images(self, deadline_s, accept=None, reject=None, what="device"):
        """Wait until the device answers `image list` (and `accept` holds).

        The shell is silenced before every probe because `log halt` does not
        survive a reboot. `reject` can fail fast with a reason.
        """
        start = time.monotonic()
        last_output, last_slots = "", {}
        next_progress = PROGRESS_EVERY_S
        while True:
            self.shell("log halt")
            rc, output = self.run(["image", "list"],
                                  timeout=min(self.timeout, PROBE_TIMEOUT_S),
                                  retries=1)
            if rc == 0:
                slots = parse_image_list(output)
                if slots:
                    last_slots = slots
                    elapsed = time.monotonic() - start
                    if elapsed >= PROGRESS_EVERY_S and next_progress > PROGRESS_EVERY_S:
                        print(f"  device answered after {elapsed:.0f}s")
                        next_progress = PROGRESS_EVERY_S  # report once per silence
                    if reject is not None:
                        reason = reject(slots, elapsed)
                        if reason:
                            raise FlashError(f"{reason} ({describe(slots)})")
                    if accept is None or accept(slots):
                        return slots
            last_output = output
            waited = time.monotonic() - start
            if waited >= next_progress:
                print(f"  still waiting for {what} ({waited:.0f}s of {deadline_s}s)")
                next_progress += PROGRESS_EVERY_S
            if time.monotonic() - start > deadline_s:
                state = describe(last_slots) if last_slots else \
                    (last_output.strip().splitlines() or ["no reply"])[-1]
                raise FlashError(
                    f"timed out after {deadline_s}s waiting for {what}: {state}")
            time.sleep(PROBE_INTERVAL_S)

    def upload(self, image_path):
        """Upload with progress lines and a wall-clock limit. Returns success."""
        cmd = self._base_cmd(self.timeout, self.retries) + ["image", "upload", image_path]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        os.set_blocking(proc.stdout.fileno(), False)
        start = time.monotonic()
        tail = ""
        next_mark = 10
        while True:
            chunk = proc.stdout.read(4096)
            if chunk:
                tail = (tail + chunk.decode(errors="replace"))[-4096:]
                percents = re.findall(r"(\d+(?:\.\d+)?)%", tail)
                if percents and float(percents[-1]) >= next_mark:
                    done = float(percents[-1])
                    print(f"  upload {done:5.1f}%  ({time.monotonic() - start:4.0f}s)")
                    next_mark = (int(done) // 10 + 1) * 10
            elif proc.poll() is not None:
                break
            else:
                time.sleep(0.2)
            if time.monotonic() - start > UPLOAD_WALL_CLOCK_S:
                proc.kill()
                proc.wait()
                print(f"  upload killed after {UPLOAD_WALL_CLOCK_S}s")
                return False
        if proc.returncode != 0:
            lines = [l.strip() for l in re.split(r"[\r\n]", tail) if l.strip()]
            print(f"  upload ended with code {proc.returncode}: "
                  f"{lines[-1] if lines else 'no output'}")
        return proc.returncode == 0

    # -- the sequence -------------------------------------------------------
    def flash(self, image_path, target_hash):
        def is_running(slots):
            slot0 = slots.get(0, {})
            if target_hash:
                return slot0.get("hash") == target_hash and "active" in slot0.get("flags", ())
            return "active" in slot0.get("flags", ())

        def is_uploaded(slots):
            slot1 = slots.get(1)
            if slot1 is None or not slot1["hash"]:
                return False
            if target_hash:
                return slot1["hash"] == target_hash
            return slot1["hash"] != slots.get(0, {}).get("hash")

        print("[1/5] waiting for the device to answer SMP ...")
        slots = self.images(READY_DEADLINE_S, what="the device to answer SMP")
        print(f"  {describe(slots)}")

        new_hash = target_hash
        if target_hash and is_running(slots):
            print("  this image is already running; nothing to upload")
        else:
            print("[2/5] uploading image to slot 1 ...")
            for attempt in range(1, UPLOAD_ATTEMPTS + 1):
                if target_hash and is_uploaded(slots):
                    print("  slot 1 already holds this image")
                    break
                ok = self.upload(image_path)
                slots = self.images(READY_DEADLINE_S,
                                    what="the device to answer after the upload")
                if is_uploaded(slots) and (ok or target_hash):
                    print(f"  upload verified: {describe(slots)}")
                    break
                print(f"  attempt {attempt}/{UPLOAD_ATTEMPTS} did not land "
                      f"({describe(slots)})")
            else:
                raise FlashError("upload failed: slot 1 does not hold the new image")

            new_hash = target_hash or slots[1]["hash"]

            print("[3/5] marking the new image for test and resetting ...")
            self.shell("log halt")
            rc, output = self.run(["image", "test", new_hash])
            pending = parse_image_list(output).get(1, {}).get("flags", set())
            if rc != 0 or "pending" not in pending:
                slots = self.images(READY_DEADLINE_S, what="image test to register")
                if "pending" not in slots.get(1, {}).get("flags", set()):
                    raise FlashError(f"image test was not accepted ({describe(slots)})")
            self.shell("log halt")
            self.run(["reset"], retries=1)   # the reply is lost if it resets fast

            print("[4/5] waiting for the swap and boot ...")

            def swap_failed(slots, elapsed):
                slot1_flags = slots.get(1, {}).get("flags", set())
                if elapsed > SWAP_GRACE_S and not is_running(slots) \
                        and "pending" not in slot1_flags:
                    return "device came back on the old image; MCUboot rejected or reverted the new one"
                return None

            def swapped(slots):
                return slots.get(0, {}).get("hash") == new_hash \
                    and "active" in slots[0]["flags"]

            slots = self.images(SWAP_DEADLINE_S, accept=swapped, reject=swap_failed,
                                what="the new image to boot")
            print(f"  {describe(slots)}")

        print("[5/5] confirming ...")

        def confirmed(slots):
            slot0 = slots.get(0, {})
            return slot0.get("hash") == new_hash \
                and "confirmed" in slot0.get("flags", set())

        def reverted(slots, _elapsed):
            # An unconfirmed test image is swapped back out on the next reset.
            if slots.get(0, {}).get("hash") != new_hash:
                return "device reset before the image was confirmed and reverted to the old image"
            return None

        if not confirmed(slots):
            self.shell("log halt")
            self.run(["image", "confirm"])
            slots = self.images(READY_DEADLINE_S, accept=confirmed, reject=reverted,
                                what="the confirmation to register")
        print(f"  {describe(slots)}")
        return slots


def read_from_serial_device(port, baudrate=115200, timeout=1):
    """Print device output until interrupted; also saved to <epoch>_mg100.log."""
    try:
        with serial.Serial(port, baudrate, timeout=timeout) as ser, \
                open(f"{time.time()}_mg100.log", "w+") as log_file:
            while True:
                line = ser.readline().decode(errors="replace").strip()
                if line:
                    print(line)
                    log_file.write(line + "\n")
    except KeyboardInterrupt:
        print("\nExiting...")
    except serial.SerialException as exc:
        print(f"Error: {exc}")


def main(image_path, timeout, retries, conntype, connstring,
         set_commission: bool = True, no_monitor: bool = False) -> int:
    if not os.path.isfile(image_path):
        print(f"FAILED: image not found: {image_path}")
        return 1

    target_hash = local_image_hash(image_path)
    if target_hash:
        print(f"image {image_path}\n  MCUboot hash {target_hash}")
    else:
        print(f"image {image_path}\n  no MCUboot SHA-256 found in the file; "
              "steps will be verified by slot state only")

    if conntype == "serial":
        try:
            detected = resolve_port(connstring)
        except PortNotFound as exc:
            print(f"FAILED: {exc}")
            return 1
        if detected != connstring:
            print(f"serial port {detected} (auto-detected)")
        connstring = detected

    try:
        flasher = Flasher(conntype, connstring, timeout, retries)
    except FlashError as exc:
        print(f"FAILED: {exc}")
        return 1

    was_commissioned = "true" in flasher.shell("attr get commissioned").lower()
    flasher.shell("attr set commissioned 0")
    ok = False
    try:
        flasher.flash(image_path, target_hash)
        ok = True
    except FlashError as exc:
        print(f"FAILED: {exc}")
    finally:
        # A failed flash must not leave a working gateway decommissioned.
        restore = set_commission if ok else was_commissioned
        if restore:
            flasher.shell("log halt")
            print("setting commissioned to 1")
            flasher.shell("attr set commissioned 1")

    if not ok:
        return 1
    print("flash complete")

    if no_monitor:
        print("--no_monitor set; skipping post-flash serial read loop")
        return 0

    flasher.shell("log go")
    read_from_serial_device(port=connstring, baudrate=115200, timeout=3)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Flash MG100 FW')
    parser.add_argument('-t', '--timeout', type=int, default=20,
                        help='mcumgr timeout per attempt, in seconds')
    parser.add_argument('-r', '--retries', type=int, default=3,
                        help='mcumgr retries per command')
    parser.add_argument('-ct', '--conntype', type=str,
                        help='the connection type', default='serial')
    parser.add_argument('-cs', '--connstring', type=str,
                        help='serial device, e.g. /dev/ttyUSB0; "auto" (the default) '
                             'finds the MG100 cable', default='auto')
    parser.add_argument('--image_path', type=str,
                        help='path to .bin image',
                        default=os.path.join('build', 'mg100', 'aws', 'zephyr', 'app_update.bin'))
    parser.add_argument('--set_commission', type=str2bool, default=True,
                        help='set the commissioned flag to true after a successful flash '
                             '(true/false).')
    parser.add_argument('--no_monitor', action='store_true',
                        help='skip the post-flash serial read loop (useful when called '
                             'from a wrapper).')

    args = parser.parse_args()
    # python ./scripts/mcumgr_flash.py --image_path ./build/mg100/aws/zephyr/app_update.bin
    sys.exit(main(**args.__dict__))
