#!/usr/bin/env bash
# Build the etoot MG100 gateway firmware in a Docker container (see README.md).
#
#   build_env/build.sh                              # incremental build
#   build_env/build.sh --pristine                   # full rebuild
#   build_env/build.sh --pristine -- -DCONFIG_X=y   # extra CMake/Kconfig args after --
#   build_env/build.sh --package                    # build + write the S3-layout zip
#
# Layout (mirrors the original Linux build box, /home/bermanalon/git/etoot-gw-fw):
#   $WORKSPACE (default ~/git/etoot-gw-fw)   west workspace   -> /work/etoot-gw-fw
#   this repo                                bind-mounted     -> /work/etoot-gw-fw/ble_gateway_firmware
# Output: build/mg100/aws/zephyr/app_update.bin (+ merged.hex, zephyr.elf) under this repo.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="${WORKSPACE:-$HOME/git/etoot-gw-fw}"
IMAGE="etoot-gw-fw-builder"
BOARD="${BOARD:-mg100}"
BUILD_DIR="ble_gateway_firmware/build/${BOARD}/aws"

if [ -z "${INSIDE_BUILDER:-}" ]; then
    # ---- host side ----------------------------------------------------------
    mkdir -p "$WORKSPACE/manifest"
    cp "$REPO/build_env/west.yml" "$WORKSPACE/manifest/west.yml"
    if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
        docker build -t "$IMAGE" "$REPO/build_env"
    fi
    TTY=""; [ -t 0 ] && TTY="-it"
    exec docker run --rm $TTY \
        -e INSIDE_BUILDER=1 \
        -v "$WORKSPACE":/work/etoot-gw-fw \
        -v "$REPO":/work/etoot-gw-fw/ble_gateway_firmware \
        -w /work/etoot-gw-fw \
        "$IMAGE" bash /work/etoot-gw-fw/ble_gateway_firmware/build_env/build.sh "$@"
fi

# ---- container side ---------------------------------------------------------
cd /work/etoot-gw-fw

if [ ! -d .west ]; then
    west init -l manifest
fi
if [ ! -d zephyr/.git ]; then
    # first run: narrow, shallow fetch of every pinned project (~1 GB)
    west update --narrow -o=--depth=1
fi

# Python deps NCS 1.7 wants, in a venv on the workspace so they persist across runs.
if [ ! -x .venv/bin/python ]; then
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install --no-cache-dir -q \
        -r zephyr/scripts/requirements-base.txt \
        -r nrf/scripts/requirements-base.txt \
        -r bootloader/mcuboot/scripts/requirements.txt || true
fi
export PATH="/work/etoot-gw-fw/.venv/bin:$PATH"
export ZEPHYR_BASE=/work/etoot-gw-fw/zephyr
west zephyr-export >/dev/null

PRISTINE=""; PACKAGE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --pristine) PRISTINE="--pristine"; shift ;;
        --package)  PACKAGE=1; shift ;;
        --)         shift; break ;;
        *)          break ;;
    esac
done

west build $PRISTINE -b "$BOARD" -d "$BUILD_DIR" ble_gateway_firmware/app -- "$@"

echo
echo "== artefacts =="
ls -la "$BUILD_DIR"/zephyr/app_update.bin "$BUILD_DIR"/zephyr/merged.hex "$BUILD_DIR"/zephyr/zephyr.elf
imgtool verify "$BUILD_DIR"/zephyr/app_update.bin

if [ -n "$PACKAGE" ]; then
    # Same layout the gateway_config_wizard expects inside each S3 zip:
    #   build/mg100/aws/zephyr/app_update.bin
    ver=$(grep -o 'CONFIG_MCUBOOT_IMAGE_VERSION="[^"]*"' "$BUILD_DIR"/zephyr/.config | cut -d'"' -f2)
    app_ver=${ver%%+*}
    name="${PACKAGE_NAME:-etoot_mg100_gw_fw_v${app_ver}}"
    out="ble_gateway_firmware/build/${name}.zip"
    rm -f "$out"
    tmp=$(mktemp -d); mkdir -p "$tmp/build/${BOARD}/aws/zephyr" "$tmp/build/${BOARD}/aws/mcuboot/zephyr"
    cp "$BUILD_DIR"/zephyr/{app_update.bin,merged.hex,zephyr.hex,zephyr.elf,.config} "$tmp/build/${BOARD}/aws/zephyr/"
    cp "$BUILD_DIR"/mcuboot/zephyr/.config "$tmp/build/${BOARD}/aws/mcuboot/zephyr/"
    cp "$BUILD_DIR"/partitions.yml "$BUILD_DIR"/generated_app_version.conf "$tmp/build/${BOARD}/aws/"
    [ -f "ble_gateway_firmware/build/BUILD_INFO.md" ] && cp ble_gateway_firmware/build/BUILD_INFO.md "$tmp/build/"
    ( cd "$tmp" && zip -q -r "/work/etoot-gw-fw/$out" build )
    rm -rf "$tmp"
    echo "== package =="; ls -la "$out"
fi
