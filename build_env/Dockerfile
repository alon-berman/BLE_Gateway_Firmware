# Build environment for the etoot MG100 gateway firmware (BLE_Gateway_Firmware fork).
# Matches the toolchain recorded in the fleet's 7.0.7 build (CMakeCache in the S3 zips):
#   nRF Connect SDK 1.7.0 (LairdCP forks), Zephyr 2.6.99, Zephyr SDK 0.14.2, CMake 3.22, Python 3.10.
# Host-arch agnostic: the Zephyr SDK ships linux-aarch64 and linux-x86_64 builds.
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG ZSDK_VERSION=0.14.2

RUN apt-get update && apt-get install -y --no-install-recommends \
        git cmake ninja-build gperf ccache dfu-util device-tree-compiler wget curl ca-certificates \
        python3 python3-dev python3-pip python3-setuptools python3-tk python3-wheel python3-venv \
        xz-utils file make gcc g++ libsdl2-dev libmagic1 zip unzip \
    && rm -rf /var/lib/apt/lists/*

# Zephyr SDK (minimal) + arm-zephyr-eabi toolchain + host tools, for the container's own arch.
RUN set -eux; \
    arch="$(uname -m)"; \
    wget -q "https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZSDK_VERSION}/zephyr-sdk-${ZSDK_VERSION}_linux-${arch}_minimal.tar.gz" -O /tmp/zsdk.tar.gz; \
    tar -xf /tmp/zsdk.tar.gz -C /opt; rm /tmp/zsdk.tar.gz; \
    cd "/opt/zephyr-sdk-${ZSDK_VERSION}"; \
    ./setup.sh -t arm-zephyr-eabi -h -c

ENV ZEPHYR_SDK_INSTALL_DIR=/opt/zephyr-sdk-${ZSDK_VERSION} \
    ZEPHYR_TOOLCHAIN_VARIANT=zephyr \
    PATH=/root/.local/bin:$PATH

# west + the python deps NCS 1.7 expects (zephyr + nrf + mcuboot requirement files are
# installed from the checked-out workspace by build.sh on first run; this is the bootstrap).
RUN pip3 install --no-cache-dir "west==0.14.0" "pyelftools>=0.26" "intelhex" "click" \
        "cryptography" "cbor>=1.0.0" "cbor2" "pyyaml" "packaging" "pykwalify" "psutil" "anytree" "colorama" \
        "ply" "gcovr" "imgtool>=1.7.0" "canopen" "progress" "junit2html" "python-magic" "lpc_checksum" "tabulate"

WORKDIR /work/etoot-gw-fw
