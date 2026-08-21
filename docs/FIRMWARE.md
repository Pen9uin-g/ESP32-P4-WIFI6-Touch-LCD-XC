# Firmware Source Boundary

[中文](FIRMWARE_ZH.md)

[`firmware/brookesia`](../firmware/brookesia/) is the maintained ESP-Brookesia
delivery-source project for this board family. It is based on the LCD-X firmware
source layout and adapted for the XC board; it is not a routine example under
`examples/`.

## Supported build profiles

The firmware is built only for ESP32-P4 rev3.x and 32 MB flash. Its two display
profiles are independent builds:

| Profile | Display | Expected FactoryOnly combine-bin name |
| --- | --- | --- |
| `3_4c` | 3.4C, 800 × 800 | `ESP32-P4-WIFI6-Touch-LCD-3.4C-FactoryOnly-260821.bin` |
| `4c` | 4C, 720 × 720 | `ESP32-P4-WIFI6-Touch-LCD-4C-FactoryOnly-260821.bin` |

There is no firmware `rev1_3` build profile. ESP32-P4 pre-v3 uses the legacy
PLL_F20M DSI PHY reference, while rev3.x uses XTAL. The XC firmware and managed
BSP leave `.phy_clk_src` at `0`, allowing ESP-IDF to choose from the active
silicon profile. The DPI pixel clock remains 80 MHz; both XC displays use two
DSI lanes at 1,500 Mbps per lane.

## Build and combine flow

Use the checked-in defaults in this order: `sdkconfig.defaults`,
`sdkconfig.defaults.rev3_x`, and the selected display file
(`sdkconfig.defaults.3_4c` or `sdkconfig.defaults.4c`). Build each profile in a
separate directory; never reuse a generated `sdkconfig`, `managed_components/`,
or `dependencies.lock` from another profile.

```bash
cd firmware/brookesia
idf.py -B build-3_4c-rev3_x \
  -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.rev3_x;sdkconfig.defaults.3_4c" build
idf.py -B build-4c-rev3_x \
  -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.rev3_x;sdkconfig.defaults.4c" build
```

After a successful build, run `esptool merge_bin` from the corresponding build
directory with that directory's generated `flash_args`. The two output names in
the table above are the required FactoryOnly naming convention. A combined image
must come from its own successful profile build, never from a copied or padded
whole-flash image.

## Dependencies and hardware contract

The board BSP dependency is the published registry component
[`waveshare/esp32_p4_wifi6_touch_lcd_xc`](https://components.espressif.com/components/waveshare/esp32_p4_wifi6_touch_lcd_xc)
at exactly `3.0.1`. Do not replace it with an unpublished version, a Git URL, or
a local path in a component manifest: such inputs are not accepted by Component
Registry packaging.

GT911-compatible touch is intentionally polling-only. The software leaves INT
and RST unconfigured, probes `0x5D` then `0x14`, and initializes the address
that responds. It must not install a touch ISR or drive the address/reset strap.

## CI and validation boundary

The maintained-firmware workflow is separate from the default example matrix.
When firmware source is routed, it is expected to build the two rev3.x display
profiles above; it does not add firmware source to the normal ESP-IDF or Arduino
example discovery.

This local maintenance task compiles source and prepares profile-specific
combine-bin outputs only. It does not flash a board or establish display,
touch, audio, camera, Wi-Fi, or other hardware-in-the-loop results. Treat every
compiled image as a test candidate until the corresponding physical board checks
are recorded.
