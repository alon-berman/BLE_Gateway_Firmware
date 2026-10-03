"""Upload the AWS IoT credentials to an MG100 over the serial cable.

Files written on the device (LittleFS):
  AmazonRootCA1.pem                      -> /lfs/root_ca.pem
  deviceId-<IMEI>-certificate.pem.crt    -> /lfs/client_cert.pem
  deviceId-<IMEI>-private.pem.key        -> /lfs/client_key.pem

Every upload is read back with `mcumgr fs download` and compared byte for
byte. The sequence stops at the first failure and leaves the gateway
decommissioned (commissioned=0), so it keeps waiting instead of trying to
connect with missing files. Only after all three files verify does it set the
endpoint, set commissioned=1 and reset the gateway.

CLI:
  python scripts/mcumgr_certificate_upload.py --cert_folder ~/Alon/etoot/mg100_certs/<IMEI>
Exit code 0 only when every file was uploaded and verified.
"""
import argparse
import filecmp
import os
import re
import subprocess
import sys
import tempfile
from time import sleep
from typing import Callable, Optional

from mcumgr_bin import McumgrNotFound, mcumgr_path
from mg100_port import resolve_port
from root_ca import ROOT_CA_NAME, ensure_root_ca
from send_serial_command_to_device import execute_command_over_serial

AWS_ENDPOINT = "a3t01gae6daupy-ats.iot.us-east-1.amazonaws.com"

CERTS_TO_UPLOAD = [
    (ROOT_CA_NAME, "/lfs/root_ca.pem"),
    (r".*-certificate\.pem\.crt$", "/lfs/client_cert.pem"),
    (r".*-private\.pem\.key$", "/lfs/client_key.pem"),
]

Runner = Callable[[list, str], int]          # run(cmd, label) -> exit code
SerialCmd = Callable[[str, str], None]        # serial_cmd(command, port)


def find_first_file_by_pattern(pattern: str, dir_path: str) -> Optional[str]:
    for root, _dirs, files in os.walk(dir_path):
        for name in files:
            if re.search(pattern, name):
                return os.path.abspath(os.path.join(root, name))
    return None


def _default_run(cmd: list, label: str) -> int:
    print(f"▶ {label}")
    return subprocess.run(cmd).returncode


def _default_serial(command: str, port: str) -> None:
    execute_command_over_serial(command, device=port, quiet=True)


def upload_certificates(cert_folder: str, port: str, *, timeout: int = 20, retries: int = 3,
                        conntype: str = "serial", log: Callable[[str], None] = print,
                        run: Runner = _default_run, serial_cmd: SerialCmd = _default_serial,
                        settle_s: float = 3.0) -> bool:
    """Upload and verify the three credential files. Returns True on success."""
    cert_folder = os.path.expanduser(cert_folder)
    if not os.path.isdir(cert_folder):
        log(f"✗ Certificate folder not found: {cert_folder}")
        return False
    try:
        mcumgr = mcumgr_path()
    except McumgrNotFound as exc:
        log(f"✗ {exc}")
        return False
    try:
        ensure_root_ca(cert_folder)
    except (OSError, ValueError) as exc:
        log(f"✗ Root CA: {exc}")
        return False

    files = []
    for pattern, dest in CERTS_TO_UPLOAD:
        path = find_first_file_by_pattern(pattern, cert_folder)
        if not path:
            log(f"✗ No file matching '{pattern}' in {cert_folder}; nothing was written to the device")
            return False
        files.append((path, dest))

    base = [mcumgr, "-t", str(int(timeout)), "-r", str(int(retries)),
            "--conntype", conntype, "--connstring", port]
    log(f"Uploading credentials over {port} with {mcumgr}")
    serial_cmd("log halt", port)
    serial_cmd("attr set commissioned 0", port)

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for path, dest in files:
            name = os.path.basename(path)
            rc = run(base + ["fs", "upload", path, dest], f"upload {name} → {dest}")
            if rc != 0:
                log(f"✗ upload of {name} failed (mcumgr exit code {rc})")
                ok = False
                break
            sleep(settle_s)
            readback = os.path.join(tmp, name)
            rc = run(base + ["fs", "download", dest, readback], f"read back {dest}")
            if rc != 0 or not os.path.isfile(readback) or not filecmp.cmp(path, readback, shallow=False):
                log(f"✗ {dest} on the device does not match {name}")
                ok = False
                break
            log(f"✓ {dest} verified ({os.path.getsize(path)} bytes)")

    if not ok:
        log("✗ Stopped. The gateway stays decommissioned (commissioned=0); fix the problem and run the upload again.")
        serial_cmd("log go", port)
        return False

    serial_cmd(f"attr set endpoint {AWS_ENDPOINT}", port)
    serial_cmd("attr set commissioned 1", port)
    serial_cmd("log go", port)
    rc = run(base[:-1] + [f"{port},mtu=1024", "reset"], "reset to apply the credentials")
    if rc != 0:
        log(f"⚠ reset returned {rc}; the credentials are on the device, power-cycle it with the button")
    else:
        log("✓ Credentials uploaded and verified; the gateway is rebooting")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload AWS IoT credentials to an MG100")
    parser.add_argument("-t", "--timeout", type=int, default=20, help="mcumgr timeout per attempt, seconds")
    parser.add_argument("-r", "--retries", type=int, default=3, help="mcumgr retries per command")
    parser.add_argument("-ct", "--conntype", type=str, default="serial", help="the connection type")
    parser.add_argument("-cs", "--connstring", type=str, default="auto",
                        help='serial device; "auto" (the default) finds the MG100 cable')
    parser.add_argument("--cert_folder", type=str, required=True,
                        help="folder holding deviceId-<IMEI>-certificate.pem.crt and -private.pem.key "
                             "(AmazonRootCA1.pem is added from the repo when missing)")
    args = parser.parse_args()
    port = resolve_port(args.connstring)
    done = upload_certificates(args.cert_folder, port, timeout=args.timeout, retries=args.retries,
                               conntype=args.conntype)
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
