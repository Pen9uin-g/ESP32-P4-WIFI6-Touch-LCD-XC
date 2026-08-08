# The following five lines of boilerplate have to be in your project's
# CMakeLists in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

# Component Manager Kconfig dependency rules require ESP-IDF 6.0 or newer.
# Mirror this cache option into the environment so the same manifest can omit
# usb_device_uac on the supported ESP-IDF 5.5 and 6.0 lines. Normal builds keep
# UAC enabled; the CI vendor-only command explicitly disables it.
option(USB_DEVICE_UAC_COMPONENT "Include the managed USB UAC component" ON)
if(USB_DEVICE_UAC_COMPONENT)
    set(ENV{USB_DEVICE_UAC_COMPONENT} "enabled")
else()
    set(ENV{USB_DEVICE_UAC_COMPONENT} "disabled")
endif()

add_compile_options(-Wno-ignored-qualifiers)
project(usb_touch_screen)

