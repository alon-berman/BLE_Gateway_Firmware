# Install script for directory: /home/bermanalon/git/pinnacle-100/zephyr

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/usr/local")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "TRUE")
endif()

# Set default install directory permissions.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/home/bermanalon/zephyr-sdk-0.14.2/arm-zephyr-eabi/bin/arm-zephyr-eabi-objdump")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for each subdirectory.
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/zephyr/arch/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/zephyr/lib/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/zephyr/soc/arm/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/zephyr/boards/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/zephyr/subsys/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/zephyr/drivers/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/attributes/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/framework/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/memfault-firmware-sdk/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/nrf/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/zephyr_lib/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/mcuboot/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/trusted-firmware-m/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/cjson/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/openthread/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/pelion-dm/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/cddl-gen/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/cmsis/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/fatfs/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/hal_nordic/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/libmetal/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/littlefs/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/lvgl/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/mbedtls/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/mcumgr/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/mipi-sys-t/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/nrf_hw_models/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/open-amp/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/segger/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/tinycbor/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/tinycrypt/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/nrfxlib/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/modules/connectedhomeip/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/zephyr/kernel/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/zephyr/cmake/flash/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/zephyr/cmake/usage/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/mcuboot/zephyr/cmake/reports/cmake_install.cmake")

endif()

