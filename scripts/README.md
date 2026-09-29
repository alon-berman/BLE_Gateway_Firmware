[![Laird Connectivity](https://lairdcp.github.io/assets/images/site/logo-rgb-sm.png)](https://www.lairdconnect.com/)

> **WARNING:** This is a Zephyr-based repository, **DO NOT** `git clone` this repo. To clone and build the project properly, please see the instructions in the [Pinnacle 100 Firmware Manifest](https://github.com/LairdCP/Pinnacle-100-Firmware-Manifest) repository for Pinnacle 100/MG100 or [BL5340 Firmware Manifest](https://github.com/LairdCP/BL5340_Firmware_Manifest) repository for BL5340.

### To evaluate the OOB demo, download pre-built firmware images [here for Pinnacle 100/MG100](https://github.com/LairdCP/Pinnacle-100-Firmware-Manifest/releases) or [here for BL5340](https://github.com/LairdCP/BL5340_Firmware_Manifest/releases). You do not need to build the application if no customizations are necessary.

# BLE Gateway Firmware

Documentation for the BLE Gateway Firmware is [HERE!](https://lairdcp.github.io/guides/ble-gateway-firmware/1.0/Introduction.html)


# List images command

`(.venv) bermanalon@pop-os:~/git/etoot-gw-fw/ble_gateway_firmware/scripts$ mcumgr image list --conntype serial --connstring /dev/ttyUSB0 -t 20 -r 3 `

# Flashing a gateway over serial

```
python scripts/mcumgr_flash.py --image_path build/mg100/aws/zephyr/app_update.bin --no_monitor
```

The serial port is found automatically (see below). Pass `-cs /dev/ttyUSB0` or
similar to choose one yourself.

`mcumgr` must be on `PATH` or in `~/go/bin`. The script exits `0` only when the
new image is running **and** confirmed; any failure exits `1` with the step
that failed, so wrappers such as `gateway_config_wizard.py` can trust the code.

What it does, and verifies at each step against the image's MCUboot SHA-256
(read from the `.bin` itself, the same value `mcumgr image list` shows):

1. Waits for the device to answer SMP, up to 6 minutes. A gateway on firmware
   7.1.0 or older can be unresponsive for up to 5 minutes while it waits for a
   forced watchdog reset.
2. Uploads to slot 1, up to 3 attempts. Skipped if slot 1 already holds the
   image, or if the image is already running.
3. Marks the image for test and resets.
4. Waits for the swapped image to boot, up to 5 minutes. Fails fast if the
   device comes back on the old image.
5. Confirms, and checks the confirmed image is the new one.

`commissioned` is cleared during the flash and set back afterwards. If the
flash fails it is restored to whatever it was before, so a failed flash does
not leave a working gateway decommissioned.

Hardware-free tests: `python scripts/tests/test_mcumgr_flash.py`
(or `python -m pytest scripts/tests`).

# Finding the gateway's serial port

The MG100 console is reached through Laird's USB-to-serial cable, an FTDI chip
that reports the product name `LC231X`. `mg100_port.py` finds it:

```
python scripts/mg100_port.py          # list adapters and what answers on each
python scripts/mg100_port.py --pick   # print the one port to use, or exit 1
```

- **One adapter plugged in:** it is used without writing anything to it.
- **Several adapters:** each free port is asked for its `name` attribute, and
  the single one that answers as an MG100 is used. A port held by another
  program, such as a running flash, is reported as busy and is not written to.
- **Still ambiguous:** the scripts stop and list the ports, so you can pass one.

`mcumgr_flash.py`, `mcumgr_certificate_upload.py` and
`send_serial_command_to_device.py` default to `auto`. The wizard fills its
Serial Port field on start, and its "Detect gateway" button re-detects and shows
the gateway's name. On macOS use the `/dev/cu.usbserial-...` device, which is
the one detection returns.

Hardware-free tests: `python scripts/tests/test_mg100_port.py`.

