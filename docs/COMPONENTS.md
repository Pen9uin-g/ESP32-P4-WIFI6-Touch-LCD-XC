# Component Ownership and Dependency Notes

[中文](COMPONENTS_ZH.md)

This page records why local component candidates are kept in their current
boundaries. A directory name alone is not treated as evidence that a component
can be removed.

## Registry-backed board support

The ESP-IDF examples declare Waveshare's
`waveshare/esp32_p4_wifi6_touch_lcd_xc` component and related Espressif/LVGL
components in manifests. The checked-in `waveshare__esp32_p4_wifi6_touch_lcd_xc`
directories are registry-shaped BSP sources with board headers and a manifest;
they are kept consistently across the affected examples for the current matrix.
A future conversion to downloaded managed components must first compare the
component version, supported IDF lines, generated configuration, and board
behavior for both display variants.

## Product-local or example-local components

| Component | Current reason to keep it local |
| --- | --- |
| `examples/esp-idf/05_sdmmc/components/sd_card` | Example-specific SD test helper and GPIO test routines |
| `examples/esp-idf/08_lvgl_demo_v9/components/bsp_extra` | Board/demo glue around audio and display integration |
| `examples/esp-idf/10_mp4_player/components/esp_extractor` | Espressif extractor integration with target-specific prebuilt libraries used by this example |
| `examples/esp-idf/11_esp_brookesia_phone/components/brookesia_app_squareline_demo` | Example application composition |
| `examples/esp-idf/12_usb_extend_screen/components/bsp_extra` | USB/display example-specific board glue |

The `firmware/brookesia/components/` tree is a separate maintained firmware
surface. It is inventoried but not changed or added to default example CI by
this repository workflow.

When a reusable correction is needed in the shared Waveshare component
repository, request authorization for that upstream change before publishing a
new dependency release. Do not silently replace local board glue with a
component that has not been checked against the schematic and both display
variants.
