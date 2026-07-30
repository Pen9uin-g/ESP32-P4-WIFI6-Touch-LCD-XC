# Troubleshooting

Use this checklist when an example does not build, flash, or run as expected.

## Build Issues

- Confirm ESP-IDF is active and supports ESP32-P4.
- Run `idf.py --version` and compare it with the version documented by the
  example. CI currently tests ESP-IDF `v5.5.5` and `v6.0.2`.
- Remove generated build outputs if configuration changed significantly:
  `build/`, `managed_components/`, `dependencies.lock`, and local `sdkconfig`.
- Run `idf.py set-target esp32p4` before the first build in a project.
- Check `main/idf_component.yml` for managed components that require network
  access during the first build.

## Flash And Monitor Issues

- Verify the USB-UART port and use it with `idf.py -p PORT flash monitor`.
- Hold or press the board boot/reset controls only when the serial tool cannot
  enter download mode automatically.
- Try a data-capable USB-C cable and a direct USB port on the host.
- Confirm the board is powered and the power switch is enabled.

## Display And Touch Issues

- Rebuild the exact example intended for the display interface.
- Confirm any FPC cable is fully seated and oriented correctly.
- Check `menuconfig` display, touch, LVGL, and frame buffer options.
- For video or LVGL examples, reduce resolution, color depth, or frame rate if
  artifacts suggest memory bandwidth pressure.

## Storage And Media Issues

- Confirm the SD card is formatted and mounted by the example.
- Match filenames in `menuconfig` exactly, including case and extension.
- Use media formats documented by the example. Video examples may support only
  specific container, codec, and alignment combinations.

## Wi-Fi Issues

- Confirm credentials were set in `menuconfig` or the example-specific config.
- Check that the Wi-Fi remote or hosted components required by the project were
  downloaded successfully.
- Keep serial logs from boot through connection failure when opening an issue.
