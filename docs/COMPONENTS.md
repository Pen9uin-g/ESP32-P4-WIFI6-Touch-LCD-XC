# Component Ownership and Dependency Notes

[中文](COMPONENTS_ZH.md)

This page records why local component candidates are kept in their current
boundaries. A directory name alone is not treated as evidence that a component
can be removed.

## Registry-backed board support

Examples 07 through 12 and the maintained firmware use the managed
[`waveshare/esp32_p4_wifi6_touch_lcd_xc`](https://components.espressif.com/components/waveshare/esp32_p4_wifi6_touch_lcd_xc)
BSP pinned exactly to `3.0.1`. No vendored copy of that BSP remains in an
example; `bsp_extra` and unrelated local components remain local.

The official `3.0.1` BSP uses `GPIO_NUM_NC` for touch reset, whereas prior local
copies in examples 08 and 09 used GPIO23. This migration deliberately does not
invent a global GPIO override: the schematic evidence is insufficient. A touch
reset regression check on real hardware is required for every affected board.

The USB extend-screen example also pins `espressif/tinyusb` to `0.17.0~2`, the
exact release permitted by its `espressif/usb_device_uac` `1.2.0` dependency.
Keeping both versions exact prevents a future TinyUSB upload from silently
changing USB descriptors or P4 PHY behavior. The UAC component dependency is
conditional on the top-level `USB_DEVICE_UAC_COMPONENT` CMake option. Normal
builds leave it enabled; the CI vendor-only command disables both that option
and `CONFIG_UAC_AUDIO_ENABLE`, so it does not compile a component whose
descriptor types are disabled in the project TinyUSB configuration. The CMake
option is used because Kconfig-based manifest conditions require ESP-IDF 6.0
and this repository also validates ESP-IDF 5.5; see the Component Manager's
[Kconfig condition documentation](https://docs.espressif.com/projects/idf-component-manager/en/latest/reference/manifest_file.html#kconfig-options).

## Product-local or example-local components

| Component | Current reason to keep it local |
| --- | --- |
| `examples/esp-idf/05_sdmmc/components/sd_card` | Example-specific SD test helper and GPIO test routines |
| `examples/esp-idf/08_lvgl_demo_v9/components/bsp_extra` | Board/demo glue around audio and display integration |
| `examples/esp-idf/10_mp4_player/components/esp_extractor` | Espressif extractor integration with target-specific prebuilt libraries used by this example |
| `examples/esp-idf/11_esp_brookesia_phone/components/brookesia_app_squareline_demo` | Example application composition |
| `examples/esp-idf/12_usb_extend_screen/components/bsp_extra` | USB/display example-specific board glue |

The `firmware/brookesia/components/` tree is a separate maintained firmware
surface. Its BSP consumer is also pinned to `3.0.1`; its two revision profiles
are built separately from the unchanged example matrix.

When a reusable correction is needed in the shared Waveshare component
repository, request authorization for that upstream change before publishing a
new dependency release. Do not silently replace local board glue with a
component that has not been checked against the schematic and both display
variants.
