#!/usr/bin/env python3
"""
Gateway Configuration Wizard — NiceGUI-based step-by-step bringup tool
for the MG100 BLE Gateway.  Wraps existing mcumgr_flash.py /
mcumgr_certificate_upload.py logic and adds EMnify SIM activation.
"""

import asyncio
import os
import re
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from time import sleep
from typing import Optional

import serial
import serial.tools.list_ports
from nicegui import ui, app

from register_sim import authenticate as emnify_authenticate_via_env
from register_sim import get_sim_id_for_iccid, activate_sim as emnify_activate_sim_api

USERS_FASTAPI_SCRIPTS = os.path.join(
    os.path.expanduser("~"),
    "git", "etoot", "lambda-functions", "users-fastapi", "lambda", "scripts",
)
CERT_OUTPUT_BASE = os.path.join(os.path.expanduser("~"), "Alon", "etoot", "mg100_certs")
AMAZON_ROOT_CA1_REF = os.path.join(CERT_OUTPUT_BASE, "354616090640025", "AmazonRootCA1.pem")
IOT_POLICY_NAME = "mg100"

EMNIFY_API_BASE = "https://cdn.emnify.net/api/v1"

CERTS_TO_UPLOAD = [
    ("AmazonRootCA1.pem", "/lfs/root_ca.pem"),
    (r".*-certificate\.pem\.crt$", "/lfs/client_cert.pem"),
    (r".*-private\.pem\.key$", "/lfs/client_key.pem"),
]

AWS_ENDPOINT = "a3t01gae6daupy-ats.iot.us-east-1.amazonaws.com"


@dataclass
class WizardState:
    gateway_id: str = ""
    serial_port: str = "/dev/ttyUSB0"
    image_path_1: str = ""
    image_path_2: str = ""
    cert_folder: str = ""
    sim_iccid: str = ""
    emnify_token: str = ""
    sensor_ids: str = ""
    timeout: int = 20
    retries: int = 3
    conntype: str = "serial"
    running: bool = False


state = WizardState()

# Thread-safe log buffer: background threads append here, UI timer drains it
_log_lines: list[str] = []
_log_pending: deque[str] = deque()
_log_lock = threading.Lock()


def emit_log(msg: str):
    """Append a log line. Safe to call from any thread."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _log_lock:
        _log_lines.append(line)
        _log_pending.append(line)


def get_serial_ports() -> list[str]:
    return [p.device for p in serial.tools.list_ports.comports()] or ["/dev/ttyUSB0"]


def find_first_file_by_pattern(pattern: str, dir_path: str) -> Optional[str]:
    for root, _dirs, files in os.walk(dir_path):
        for f in files:
            if re.search(pattern, f):
                return os.path.abspath(os.path.join(root, f))
    return None


def run_cmd(cmd: list[str], label: str = "") -> tuple[int, str]:
    """Run a subprocess, streaming output to the log buffer.

    Reads raw bytes in small chunks so that carriage-return based progress
    bars (like mcumgr upload) are captured.
    """
    emit_log(f"▶ {label or ' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        output_lines = []
        buf = ""
        while True:
            chunk = proc.stdout.read(256)
            if not chunk:
                break
            buf += chunk.decode(errors="replace")
            while "\n" in buf or "\r" in buf:
                idx_n = buf.find("\n")
                idx_r = buf.find("\r")
                if idx_n == -1:
                    idx = idx_r
                elif idx_r == -1:
                    idx = idx_n
                else:
                    idx = min(idx_n, idx_r)
                segment = buf[:idx].rstrip()
                buf = buf[idx + 1:]
                if segment:
                    emit_log(segment)
                    output_lines.append(segment)
        remainder = buf.strip()
        if remainder:
            emit_log(remainder)
            output_lines.append(remainder)
        proc.wait()
        emit_log(f"✓ Exit code: {proc.returncode}")
        return proc.returncode, "\n".join(output_lines)
    except FileNotFoundError:
        emit_log(f"✗ Command not found: {cmd[0]}")
        return -1, ""
    except Exception as e:
        emit_log(f"✗ Error: {e}")
        return -1, str(e)


def serial_command(command: str, device: str = "/dev/ttyUSB0") -> str:
    emit_log(f"Serial → {command}")
    try:
        ser = serial.Serial(device, 115200, timeout=2)
        if ser.isOpen():
            ser.write((command + "\n").encode())
            sleep(1)
            output = ser.read(4096).decode(errors="replace")
            ser.close()
            if output.strip():
                emit_log(output.strip())
            return output
        else:
            emit_log(f"✗ Failed to open {device}")
            return ""
    except Exception as e:
        emit_log(f"✗ Serial error: {e}")
        return ""


def extract_hash(output: str) -> Optional[str]:
    image_count = 0
    for line in output.splitlines():
        if "hash" in line:
            image_count += 1
            if image_count > 1:
                h = line.split(":")[1].strip()
                emit_log(f"Found image hash: {h}")
                return h
    return None


# ---------------------------------------------------------------------------
#  EMnify helpers
# ---------------------------------------------------------------------------
def emnify_authenticate(app_token: str) -> Optional[str]:
    import requests

    emit_log("Authenticating with EMnify…")
    if app_token:
        os.environ["EMNIFY_APPLICATION_TOKEN"] = app_token

    try:
        token = emnify_authenticate_via_env()
        if token:
            emit_log("✓ EMnify authentication successful")
            return token
        emit_log("✗ EMnify auth returned None — trying direct API call…")
    except Exception as e:
        emit_log(f"✗ register_sim.authenticate() failed: {e} — trying direct…")

    effective_token = app_token or os.environ.get("EMNIFY_APPLICATION_TOKEN", "")
    if not effective_token:
        emit_log("✗ No application token available")
        return None
    try:
        resp = requests.post(
            f"{EMNIFY_API_BASE}/authenticate",
            json={"application_token": effective_token},
            timeout=15,
        )
        emit_log(f"  EMnify responded with status {resp.status_code}")
        if resp.status_code != 200:
            emit_log(f"  Response body: {resp.text[:500]}")
            return None
        auth = resp.json().get("auth_token")
        if auth:
            emit_log("✓ EMnify authentication successful (direct)")
            return auth
        emit_log(f"✗ No auth_token in response: {resp.text[:300]}")
        return None
    except Exception as e:
        emit_log(f"✗ EMnify direct auth also failed: {e}")
        return None


def emnify_find_sim(auth_token: str, iccid: str) -> Optional[int]:
    from register_sim import SimIdNotFoundException

    emit_log(f"Looking up SIM with ICCID {iccid}…")
    try:
        sim_id = get_sim_id_for_iccid(auth_token, iccid)
        emit_log(f"✓ Found SIM id={sim_id}")
        return sim_id
    except SimIdNotFoundException:
        emit_log("✗ No SIM found with that ICCID")
        return None
    except Exception as e:
        emit_log(f"✗ SIM lookup failed: {e}")
        return None


def emnify_activate_sim(auth_token: str, sim_id: int) -> bool:
    emit_log(f"Activating SIM id={sim_id}…")
    try:
        emnify_activate_sim_api(auth_token, str(sim_id))
        emit_log("✓ SIM activated successfully")
        return True
    except Exception as e:
        emit_log(f"✗ Activation failed: {e}")
        return False


def emnify_create_endpoint(auth_token: str, name: str, sim_id: int) -> bool:
    import requests

    emit_log(f"Creating EMnify endpoint '{name}' with SIM {sim_id}…")
    try:
        resp = requests.post(
            f"{EMNIFY_API_BASE}/endpoint",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
            },
            json={
                "name": name,
                "sim": {"id": sim_id, "activate": True},
                "service_profile": {"id": 1},
                "tariff_profile": {"id": 1},
                "status": {"id": 0},
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            emit_log(f"✓ Endpoint '{name}' created")
            return True
        emit_log(f"✗ Endpoint creation returned {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        emit_log(f"✗ Endpoint creation failed: {e}")
        return False


# ---------------------------------------------------------------------------
#  Task runners — all blocking work happens in threads; the UI polls the log
# ---------------------------------------------------------------------------
def _run_flash_blocking(image_path: str, label: str):
    connstring_mtu = f"{state.serial_port},mtu=1024"
    connstring_raw = state.serial_port
    t, r, ct = str(state.timeout), str(state.retries), state.conntype

    emit_log(f"── {label} ──")
    serial_command("attr set commissioned 0", device=connstring_raw)
    serial_command("log halt", device=connstring_raw)
    sleep(3)

    emit_log("Listing current images…")
    run_cmd(
        ["mcumgr", "-t", t, "-r", r, "--conntype", ct, "--connstring", connstring_mtu, "image", "list", "-t", "10000"],
        "image list",
    )

    emit_log("Uploading image…")
    run_cmd(
        ["mcumgr", "-t", t, "-r", r, "--conntype", ct, "--connstring", connstring_mtu, "image", "upload", image_path],
        "image upload",
    )
    sleep(5)

    emit_log("Listing images after upload…")
    _rc, output = run_cmd(
        ["mcumgr", "-t", t, "-r", r, "--conntype", ct, "--connstring", connstring_mtu, "image", "list", "-t", "10000"],
        "image list (post-upload)",
    )
    image_hash = extract_hash(output)
    if not image_hash:
        emit_log("✗ Could not extract image hash — aborting flash")
        return

    emit_log("Testing (switching) image…")
    run_cmd(
        ["mcumgr", "-t", t, "-r", r, "--conntype", ct, "--connstring", connstring_mtu, "image", "test", image_hash],
        "image test",
    )

    emit_log("Resetting device…")
    run_cmd(
        ["mcumgr", "-t", t, "-r", r, "--conntype", ct, "--connstring", connstring_mtu, "reset"],
        "reset",
    )

    emit_log("Waiting 105 s for device to boot with new image…")
    for i in range(105):
        sleep(1)
        if i % 15 == 0:
            emit_log(f"  …{105 - i}s remaining")

    emit_log("Confirming image…")
    run_cmd(
        ["mcumgr", "-t", t, "-r", r, "--conntype", ct, "--connstring", connstring_mtu, "image", "confirm"],
        "image confirm",
    )
    serial_command("attr set commissioned 1", device=connstring_raw)
    emit_log(f"✓ {label} complete")


def _create_certs_blocking() -> Optional[str]:
    """Create AWS IoT Thing + certs using the same logic as
    add_mg_100_gateway_thing.py.  Returns the output directory on success."""
    import shutil

    gw = state.gateway_id.strip()
    if not gw:
        emit_log("✗ Gateway ID is required to create certificates")
        return None

    thing_name = f"deviceId-{gw}"
    output_dir = os.path.join(CERT_OUTPUT_BASE, gw)

    emit_log(f"── Create AWS IoT Thing & Certificates ──")
    emit_log(f"Thing name: {thing_name}")
    emit_log(f"Output dir: {output_dir}")

    try:
        import boto3
    except ImportError:
        emit_log("✗ boto3 is not installed — run: pip install boto3")
        return None

    try:
        iot_client = boto3.client("iot", region_name="us-east-1")
        s3_client = boto3.client("s3", region_name="us-east-1")

        emit_log(f"Creating IoT Thing '{thing_name}'…")
        iot_client.create_thing(thingName=thing_name)
        emit_log(f"✓ Thing '{thing_name}' created")

        emit_log("Creating keys and certificate…")
        resp = iot_client.create_keys_and_certificate(setAsActive=True)
        certificate_pem = resp["certificatePem"]
        private_key = resp["keyPair"]["PrivateKey"]
        certificate_arn = resp["certificateArn"]
        certificate_id = resp["certificateId"]
        emit_log(f"✓ Certificate created: {certificate_id[:16]}…")

        emit_log("Attaching certificate to thing…")
        iot_client.attach_thing_principal(thingName=thing_name, principal=certificate_arn)
        emit_log("✓ Certificate attached")

        emit_log(f"Attaching policy '{IOT_POLICY_NAME}'…")
        iot_client.attach_policy(policyName=IOT_POLICY_NAME, target=certificate_arn)
        emit_log(f"✓ Policy '{IOT_POLICY_NAME}' attached")

        bucket_name = "etoot-devices"
        cert_s3_key = f"certificates/mg100/{thing_name}/{thing_name}-certificate.pem.crt"
        key_s3_key = f"certificates/mg100/{thing_name}/{thing_name}-private.pem.key"
        emit_log(f"Uploading to S3 bucket '{bucket_name}'…")
        s3_client.put_object(Bucket=bucket_name, Key=cert_s3_key, Body=certificate_pem)
        s3_client.put_object(Bucket=bucket_name, Key=key_s3_key, Body=private_key)
        emit_log("✓ Uploaded to S3")

        os.makedirs(output_dir, exist_ok=True)
        cert_path = os.path.join(output_dir, f"{thing_name}-certificate.pem.crt")
        key_path = os.path.join(output_dir, f"{thing_name}-private.pem.key")
        with open(cert_path, "w") as f:
            f.write(certificate_pem)
        with open(key_path, "w") as f:
            f.write(private_key)
        emit_log(f"✓ Saved cert → {cert_path}")
        emit_log(f"✓ Saved key  → {key_path}")

        if os.path.isfile(AMAZON_ROOT_CA1_REF):
            shutil.copy(AMAZON_ROOT_CA1_REF, output_dir)
            emit_log(f"✓ Copied AmazonRootCA1.pem → {output_dir}")
        else:
            emit_log(f"⚠ AmazonRootCA1.pem not found at {AMAZON_ROOT_CA1_REF} — copy it manually")

        emit_log(f"✓ Certificates ready in {output_dir}")
        return output_dir

    except Exception as e:
        emit_log(f"✗ Certificate creation failed: {e}")
        return None


def _run_cert_upload_blocking():
    connstring_mtu = f"{state.serial_port},mtu=1024"
    connstring_raw = state.serial_port
    t, r, ct = str(state.timeout), str(state.retries), state.conntype

    emit_log("── Certificate Upload ──")
    serial_command("log halt", device=connstring_raw)
    serial_command("attr set commissioned 0", device=connstring_raw)

    for file_pattern, dest_path in CERTS_TO_UPLOAD:
        abs_path = find_first_file_by_pattern(file_pattern, state.cert_folder)
        if not abs_path:
            emit_log(f"✗ File matching '{file_pattern}' not found in {state.cert_folder}")
            continue
        run_cmd(
            ["mcumgr", "-t", t, "-r", r, "--conntype", ct, "--connstring", connstring_mtu, "fs", "upload", abs_path, dest_path],
            f"upload {os.path.basename(abs_path)} → {dest_path}",
        )
        sleep(3)

    serial_command(f"attr set endpoint {AWS_ENDPOINT}", device=connstring_raw)
    serial_command("attr set commissioned 1", device=connstring_raw)
    serial_command("log go", device=connstring_raw)
    emit_log("✓ Certificate upload complete")


def _run_emnify_blocking():
    emit_log("── EMnify SIM Activation ──")
    auth = emnify_authenticate(state.emnify_token)
    if not auth:
        return

    sim_id = emnify_find_sim(auth, state.sim_iccid)
    if sim_id is None:
        return

    emnify_activate_sim(auth, sim_id)

    if state.gateway_id:
        emnify_create_endpoint(auth, state.gateway_id, sim_id)

    emit_log("✓ EMnify step complete")


# ---------------------------------------------------------------------------
#  Live serial monitor
# ---------------------------------------------------------------------------
_monitor_stop = threading.Event()


def _serial_monitor_thread():
    try:
        with serial.Serial(state.serial_port, 115200, timeout=1) as ser:
            while not _monitor_stop.is_set():
                line = ser.readline().decode(errors="replace").strip()
                if line:
                    emit_log(line)
    except Exception as e:
        emit_log(f"Monitor error: {e}")


def start_serial_monitor():
    _monitor_stop.clear()
    t = threading.Thread(target=_serial_monitor_thread, daemon=True)
    t.start()
    emit_log("Serial monitor started — streaming device output…")


def stop_serial_monitor():
    _monitor_stop.set()
    emit_log("Serial monitor stopped")


# ---------------------------------------------------------------------------
#  Async wrappers that run blocking work in a thread
# ---------------------------------------------------------------------------
async def _run_in_thread(fn, *args):
    state.running = True
    try:
        await asyncio.get_event_loop().run_in_executor(None, fn, *args)
    finally:
        state.running = False


# ---------------------------------------------------------------------------
#  UI
# ---------------------------------------------------------------------------
@ui.page("/")
def index():
    ui.colors(primary="#1976D2", secondary="#424242", accent="#82B1FF")

    with ui.header().classes("items-center justify-between bg-primary text-white"):
        ui.label("MG100 Gateway Configuration Wizard").classes("text-h5 font-bold")
        ui.label("eToot").classes("text-subtitle1 opacity-80")

    with ui.splitter(value=70).classes("w-full h-[calc(100vh-64px)]") as splitter:
        with splitter.before:
            with ui.stepper().props("vertical animated header-nav").classes("w-full") as stepper:
                _build_step_welcome(stepper)
                _build_step_hardware(stepper)
                _build_step_sim_replace(stepper)
                _build_step_emnify(stepper)
                _build_step_flash1(stepper)
                _build_step_flash2(stepper)
                _build_step_certs(stepper)
                _build_step_sensors(stepper)
                _build_step_verify(stepper)
                _build_step_done(stepper)

        with splitter.after:
            with ui.column().classes("w-full h-full p-2 gap-0"):
                ui.label("Log Output").classes("text-h6 text-grey-8 mb-1")
                log_widget = ui.log(max_lines=2000).classes(
                    "w-full flex-grow font-mono text-xs bg-grey-10 text-green-4 rounded"
                )
                # Replay any lines already in the buffer (e.g. after page refresh)
                with _log_lock:
                    for line in _log_lines:
                        log_widget.push(line)

                # Timer drains pending log lines into this client's widget
                def _drain_logs():
                    with _log_lock:
                        while _log_pending:
                            log_widget.push(_log_pending.popleft())

                ui.timer(0.3, _drain_logs)

                with ui.row().classes("w-full mt-1 gap-2"):
                    ui.button("Clear", icon="delete_sweep", on_click=lambda: log_widget.clear()).props("flat dense color=grey")

                    def _copy():
                        with _log_lock:
                            text = "\n".join(_log_lines)
                        ui.run_javascript(f"navigator.clipboard.writeText({text!r})")

                    ui.button("Copy", icon="content_copy", on_click=_copy).props("flat dense color=grey")


def _nav_buttons(stepper, on_next=None, next_label="Next", show_run=False, run_label="Run", run_handler=None):
    with ui.stepper_navigation():
        ui.button("Back", on_click=stepper.previous).props("flat")
        if show_run and run_handler:
            ui.button(run_label, icon="play_arrow", on_click=run_handler).props("color=positive")
        ui.button(next_label, on_click=on_next or stepper.next).props("color=primary")


# ── Steps ──


def _build_step_welcome(stepper):
    with ui.step("Welcome"):
        ui.markdown("""
### Welcome to the MG100 Gateway Configuration Wizard

This wizard will walk you through the **complete bringup process** for a new gateway:

1. **Hardware setup** — connect USB, verify serial port
2. **SIM replacement** — physical swap instructions
3. **EMnify activation** — activate SIM via API
4. **Firmware flashing** — upload image 1 & 2 via mcumgr
5. **Certificate upload** — provision AWS IoT certs
6. **Sensor list update** — register BLE sensors
7. **Verification** — live serial monitor

> Make sure `mcumgr` is installed and accessible in your PATH.
""")
        with ui.row().classes("gap-4 mt-4"):
            ui.input("Gateway ID (IMEI)", placeholder="e.g. 354616090640025").classes("w-64").bind_value(state, "gateway_id")
            port_input = ui.input("Serial Port", value=state.serial_port, placeholder="/dev/ttyUSB0").classes("w-64")
            port_input.bind_value(state, "serial_port")

            detected = get_serial_ports()
            port_label = ui.label(f"Detected: {', '.join(detected) if detected else 'none'}").classes("text-xs text-grey-6 self-center")

            def _refresh_ports():
                ports = get_serial_ports()
                port_label.text = f"Detected: {', '.join(ports) if ports else 'none'}"
                if ports and not state.serial_port:
                    state.serial_port = ports[0]
                    port_input.value = ports[0]

            ui.button("Refresh ports", icon="refresh", on_click=_refresh_ports).props("flat dense")

        _nav_buttons(stepper, next_label="Start →")


def _build_step_hardware(stepper):
    with ui.step("Hardware Setup"):
        ui.markdown("""
### Physical Connections

Please complete the following before proceeding:
""")
        for label in [
            "Gateway is powered on",
            "USB cable connected between gateway and this PC",
            "Serial port detected (check dropdown on previous page)",
            "Gateway ID (IMEI) noted from device label",
        ]:
            ui.checkbox(label)

        ui.separator()
        ui.markdown("> **Tip:** Run `dmesg | tail` to verify the USB device appeared.")

        _nav_buttons(stepper)


def _build_step_sim_replace(stepper):
    with ui.step("SIM Replacement"):
        ui.markdown("""
### Replace the SIM Card

1. **Power off** the gateway (or leave on if hot-swap supported)
2. **Open** the SIM tray on the MG100
3. **Remove** the existing SIM card
4. **Insert** the new **EMnify** SIM card
5. **Note the ICCID** printed on the SIM (without the trailing Luhn digit)
6. **Close** the SIM tray
""")
        with ui.image("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/Sim_cards.jpg/320px-Sim_cards.jpg").classes("w-48 rounded shadow mt-2"):
            pass

        ui.input("SIM ICCID (without Luhn digit)", placeholder="e.g. 8988307...").classes("w-80 mt-4").bind_value(state, "sim_iccid")

        _nav_buttons(stepper)


def _build_step_emnify(stepper):
    with ui.step("EMnify SIM Activation"):
        env_token = os.environ.get("EMNIFY_APPLICATION_TOKEN", "")
        if env_token and not state.emnify_token:
            state.emnify_token = env_token

        ui.markdown("""
### Activate SIM on EMnify

Enter your EMnify **Application Token** (create one at [EMnify Portal → Integrations](https://portal.emnify.com)),
or set the `EMNIFY_APPLICATION_TOKEN` environment variable before launching the wizard.

This step reuses `register_sim.py` — the same flow as the CLI script.

The wizard will:
- Authenticate with the EMnify API
- Look up the SIM by ICCID
- Activate the SIM
- Create a device endpoint named after the Gateway ID
""")
        ui.input("EMnify Application Token", password=True, password_toggle_button=True).classes("w-full mt-2").bind_value(state, "emnify_token")
        if env_token:
            ui.label("(Pre-filled from EMNIFY_APPLICATION_TOKEN env var)").classes("text-xs text-grey-6")

        ui.separator()
        with ui.row().classes("gap-2 items-center"):
            ui.label("ICCID:").classes("font-bold")
            ui.label().bind_text_from(state, "sim_iccid")
            ui.label("  |  Gateway:").classes("font-bold")
            ui.label().bind_text_from(state, "gateway_id")

        async def _run():
            if not state.emnify_token:
                ui.notify("Please enter the EMnify token", type="warning")
                return
            if not state.sim_iccid:
                ui.notify("Please enter the SIM ICCID", type="warning")
                return
            await _run_in_thread(_run_emnify_blocking)
            ui.notify("EMnify activation complete", type="positive")

        _nav_buttons(stepper, show_run=True, run_label="Activate SIM", run_handler=_run)


def _build_step_flash1(stepper):
    with ui.step("Flash Firmware Image 1"):
        ui.markdown("""
### Flash Primary Firmware Image

Select the **first** firmware `.bin` file to upload via mcumgr.
This is typically the latest release candidate.
""")
        ui.input(
            "Image path (.bin)",
            placeholder="/path/to/app_update.bin",
        ).classes("w-full").bind_value(state, "image_path_1")

        with ui.row().classes("gap-2 mt-2"):
            ui.label("Timeout (s):")
            ui.number(value=20, min=5, max=120).classes("w-20").bind_value(state, "timeout")
            ui.label("Retries:")
            ui.number(value=3, min=1, max=10).classes("w-20").bind_value(state, "retries")

        async def _run():
            path = state.image_path_1.strip()
            path = os.path.expanduser(path)
            emit_log(f"Checking image path: '{path}'")
            if not path or not os.path.isfile(path):
                emit_log(f"✗ File not found: '{path}'")
                ui.notify(f"Invalid image path: {path}", type="negative")
                return
            state.image_path_1 = path
            await _run_in_thread(_run_flash_blocking, path, "Flash Image 1")
            ui.notify("Flash image 1 complete", type="positive")

        _nav_buttons(stepper, show_run=True, run_label="Flash Image 1", run_handler=_run)


def _build_step_flash2(stepper):
    with ui.step("Flash Firmware Image 2"):
        ui.markdown("""
### Flash Secondary Firmware Image

Select the **second** firmware `.bin` file (e.g. a different release candidate).
This step is optional — skip if only one image is needed.
""")
        ui.input(
            "Image path (.bin)",
            placeholder="/path/to/app_update.bin (optional)",
        ).classes("w-full").bind_value(state, "image_path_2")

        async def _run():
            path = state.image_path_2.strip()
            path = os.path.expanduser(path)
            emit_log(f"Checking image path: '{path}'")
            if not path or not os.path.isfile(path):
                emit_log(f"✗ File not found: '{path}'")
                ui.notify(f"Invalid image path: {path}", type="negative")
                return
            state.image_path_2 = path
            await _run_in_thread(_run_flash_blocking, path, "Flash Image 2")
            ui.notify("Flash image 2 complete", type="positive")

        _nav_buttons(stepper, show_run=True, run_label="Flash Image 2", run_handler=_run)


def _build_step_certs(stepper):
    with ui.step("Certificates"):
        ui.markdown("""
### Create & Upload AWS IoT Certificates

**Option A** — Create new certificates automatically:
- Creates an AWS IoT Thing (`deviceId-<Gateway ID>`)
- Generates certificate + private key
- Attaches the `mg100` policy
- Uploads to S3 and saves locally
- Then uploads all certs to the device via mcumgr

**Option B** — Use an existing certificate folder (if already created).

> Requires valid AWS credentials (`aws configure` or env vars).
""")
        cert_input = ui.input(
            "Certificate folder (auto-filled on create, or enter manually)",
            placeholder=f"~/Alon/etoot/mg100_certs/<GATEWAY_ID>",
        ).classes("w-full").bind_value(state, "cert_folder")

        async def _create_and_upload():
            if not state.gateway_id.strip():
                ui.notify("Gateway ID is required", type="warning")
                return

            def _do_all():
                out = _create_certs_blocking()
                if out:
                    state.cert_folder = out
                    _run_cert_upload_blocking()

            await _run_in_thread(_do_all)
            cert_input.value = state.cert_folder
            ui.notify("Certificates created & uploaded", type="positive")

        async def _upload_existing():
            folder = os.path.expanduser(state.cert_folder.strip())
            if not os.path.isdir(folder):
                ui.notify("Certificate folder not found", type="negative")
                return
            state.cert_folder = folder
            await _run_in_thread(_run_cert_upload_blocking)
            ui.notify("Certificates uploaded", type="positive")

        with ui.stepper_navigation():
            ui.button("Back", on_click=stepper.previous).props("flat")
            ui.button("Create & Upload", icon="add_circle", on_click=_create_and_upload).props("color=positive")
            ui.button("Upload Existing", icon="upload_file", on_click=_upload_existing).props("color=accent outlined")
            ui.button("Next", on_click=stepper.next).props("color=primary")


def _build_step_sensors(stepper):
    with ui.step("Update Sensors List"):
        ui.markdown("""
### Register BLE Sensor MAC Addresses

Enter the BLE MAC addresses of the sensors assigned to this gateway,
**space-separated**.

> This calls `update_sensors_list.py` from the users-fastapi repo with
> the prefix `deviceId-<GATEWAY_ID>`.
""")
        ui.textarea(
            "Sensor MAC addresses (space-separated)",
            placeholder="D98827F159FA D47B1B13780B E2F76EDF7F8C ...",
        ).classes("w-full font-mono").bind_value(state, "sensor_ids")

        async def _run():
            macs = state.sensor_ids.split()
            if not macs:
                ui.notify("Enter at least one sensor MAC", type="warning")
                return
            device_arg = f"deviceId-{state.gateway_id}"
            cmd = ["python3", "update_sensors_list.py", device_arg] + macs
            emit_log(f"Would run: {' '.join(cmd)}")
            emit_log("(Run this in the users-fastapi repo directory)")
            ui.notify("Sensor command logged — run it in users-fastapi repo", type="info")

        _nav_buttons(stepper, show_run=True, run_label="Generate Command", run_handler=_run)


def _build_step_verify(stepper):
    with ui.step("Verify & Monitor"):
        ui.markdown("""
### Live Serial Monitor

Open a live serial monitor to verify the gateway is booting correctly
and connecting to AWS IoT.
""")
        with ui.row().classes("gap-2"):
            ui.button("Start Monitor", icon="monitor_heart", on_click=start_serial_monitor).props("color=positive")
            ui.button("Stop Monitor", icon="stop", on_click=stop_serial_monitor).props("color=negative outlined")

        _nav_buttons(stepper)


def _build_step_done(stepper):
    with ui.step("Done"):
        ui.markdown("""
### Configuration Complete!

**Post-installation checklist:**
- [ ] Upload PEM files to shared Drive
- [ ] Create client folder in Drive with:
  - Signed contract
  - Videos of installed sensors
  - Diagram of installation
  - Accepted price quote
- [ ] Share folder with customer
""")
        with ui.row().classes("gap-4 mt-4"):
            ui.label("Gateway:").classes("font-bold")
            ui.label().bind_text_from(state, "gateway_id")
            ui.label("ICCID:").classes("font-bold")
            ui.label().bind_text_from(state, "sim_iccid")

        with ui.stepper_navigation():
            ui.button("Back", on_click=stepper.previous).props("flat")
            ui.button("Restart", icon="replay", on_click=lambda: stepper.set_value("Welcome")).props("color=secondary")


ui.run(title="MG100 Gateway Wizard", port=8080, reload=False)
