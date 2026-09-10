# Building the etoot MG100 gateway firmware

Laird deleted the `Pinnacle-100-Firmware-Manifest` repo this app used to be built
from, and the original Linux build box is gone. This directory recreates the build
environment in Docker so the firmware can be rebuilt on any machine (arm64 or
x86_64) with nothing installed on the host but Docker.

```bash
build_env/build.sh --pristine            # first run: builds the image, fetches the
                                         # west workspace into ~/git/etoot-gw-fw (~1 GB), builds
build_env/build.sh                       # incremental rebuild
build_env/build.sh --pristine --package  # also writes build/etoot_mg100_gw_fw_v<ver>.zip
```

Output: `build/mg100/aws/zephyr/app_update.bin` (mcumgr / wizard image),
`merged.hex` (full image incl. MCUboot, for SWD), `zephyr.elf` (symbols).

Upload the zip to `s3://etoot-devices/firmware/mg100/` and it appears in the
Gateway Config Wizard's firmware dropdown (it looks for
`build/mg100/aws/zephyr/app_update.bin` inside each zip).

## What is pinned, and why

| Component | Pin | Evidence |
|---|---|---|
| Toolchain | Ubuntu 22.04, Zephyr SDK 0.14.2, CMake 3.22, Python 3.10 | `CMakeCache.txt` inside the fleet's 7.0.7 zip |
| `sdk-nrf` | LairdCP tag `v1.7.0` (== upstream NCS v1.7.0) | `ncs_version.h` = 1.7.0 in the 7.0.7 zip |
| `zephyr` | LairdCP branch `laird/ncs_1.7.0` @ `a68516e8` (2022-06-30) | last commit before the Laird v6.4.1 tag. **Do not use tag `v1.7.0` — that is Zephyr RTOS 1.7.0 from 2017.** |
| `zephyr_lib`, `attributes` | heads of Laird's `mg100/GA5` branches | our app tree is Laird v6.4.1 (GA5 line): snake_case attribute IDs, `modules/lib/laird_connect` layout |
| `zephyr_framework` | `0b628d9f` (2022-01-20) | last commit before it started depending on a private `cmake_functions` module |
| `zephyr_boards` | `d513dc2e` (2022-03-01) | parent of "MG100: optimizations", which removed SPI/I2C/LIS2DH from `mg100_defconfig`; the fleet's `.config` still has them (movement sensor, SD card) |

With these pins the generated `zephyr/.config` differs from the fleet's 7.0.7 build
only in the symbols we changed on purpose, and `partitions.yml` is identical.

## Memory

The nRF52840 is full. The 7.0.7 image linked with **440 bytes** of SRAM to spare;
v7.1.0 recovered ~30 KB by taking `CONFIG_BT_MAX_CONN` back from 13 to Laird's 3
(the app only ever holds one BLE connection at a time). Check the `SRAM:` line at
the end of every build before shipping.
