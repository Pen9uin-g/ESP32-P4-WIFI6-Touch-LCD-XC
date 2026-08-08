# Component Ownership and Dependency Notes

[中文](COMPONENTS_ZH.md)

This page records why local component candidates are kept in their current
boundaries. A directory name alone is not treated as evidence that a component
can be removed.

## Registry-backed board support

Examples 07 through 12 carry registry-shaped local copies of Waveshare's
`waveshare/esp32_p4_wifi6_touch_lcd_xc` BSP at version `2.0.0`. Their first-party
manifests now require that exact version instead of a floating wildcard, so a
future registry release cannot silently replace the checked-in source.

The six copies are not interchangeable cache output. Examples 08 and 09 carry
the board-specific `GPIO23` GT911 reset definition while the other four leave
the touch-reset GPIO unconnected, and two copies have a semantically equivalent
CMake dependency ordering difference. They remain local until those differences
are either upstreamed or proven unnecessary.

The [Component Registry](https://components.espressif.com/components/waveshare/esp32_p4_wifi6_touch_lcd_xc)
currently advertises `3.0.1`, a semver-major change from the local `2.0.0`
snapshot, with an additional dependency. A future managed-component migration
must compare exported APIs, Kconfig, GPIO23 behavior, both ESP-IDF lines, P4
revision requirements, and both display variants before changing the boundary.

The USB extend-screen example also pins `espressif/tinyusb` to `0.19.0~3`.
That is the registry release exercised by the current CI baseline; keeping it
exact prevents a future TinyUSB upload from silently changing USB descriptors
or P4 PHY behavior. Its existing `espressif/usb_device_uac` dependency remains
at `1.2.0`.

## Product-local or example-local components

| Component | Current reason to keep it local |
| --- | --- |
| `examples/esp-idf/05_sdmmc/components/sd_card` | Example-specific SD test helper and GPIO test routines |
| `examples/esp-idf/08_lvgl_demo_v9/components/bsp_extra` | Board/demo glue around audio and display integration |
| `examples/esp-idf/10_mp4_player/components/esp_extractor` | Espressif extractor integration with target-specific prebuilt libraries used by this example |
| `examples/esp-idf/11_esp_brookesia_phone/components/brookesia_app_squareline_demo` | Example application composition |
| `examples/esp-idf/12_usb_extend_screen/components/bsp_extra` | USB/display example-specific board glue |

The `firmware/brookesia/components/` tree is a separate maintained firmware
surface. It is inventoried but is not changed, repinned, or added to default
example CI by this repository workflow.

When a reusable correction is needed in the shared Waveshare component
repository, request authorization for that upstream change before publishing a
new dependency release. Do not silently replace local board glue with a
component that has not been checked against the schematic and both display
variants.
