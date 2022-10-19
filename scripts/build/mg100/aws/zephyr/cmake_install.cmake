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
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/zephyr/arch/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/zephyr/lib/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/zephyr/soc/arm/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/zephyr/boards/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/zephyr/subsys/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/zephyr/drivers/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/attributes/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/framework/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/memfault-firmware-sdk/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/nrf/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/zephyr_lib/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/mcuboot/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/trusted-firmware-m/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/cjson/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/openthread/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/pelion-dm/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/cddl-gen/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/cmsis/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/fatfs/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/hal_nordic/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/libmetal/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/littlefs/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/lvgl/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/mbedtls/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/mcumgr/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/mipi-sys-t/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/nrf_hw_models/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/open-amp/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/segger/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/tinycbor/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/tinycrypt/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/nrfxlib/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/modules/connectedhomeip/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/zephyr/kernel/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/zephyr/cmake/flash/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/zephyr/cmake/usage/cmake_install.cmake")
  include("/home/bermanalon/git/pinnacle-100/ble_gateway_firmware/build/mg100/aws/zephyr/cmake/reports/cmake_install.cmake")

endif()

