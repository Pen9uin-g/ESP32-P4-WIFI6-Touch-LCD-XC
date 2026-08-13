# I2S ES8311 Codec

[中文](README_ZH.md)

This ES8311 codec example supports ESP32-P4-WIFI6-Touch-LCD-XC 3.4C and 4C with
ESP-IDF `v5.5.5` and `v6.0.2`. On P4 it uses I2C SCL GPIO8/SDA GPIO7, I2S MCLK
GPIO13, BCLK GPIO12, WS GPIO10, DOUT GPIO9, DIN GPIO11, and PA enable GPIO53.

## Configuration and run

`menuconfig` selects music (the default) or echo mode; echo is available only
when BSP support is disabled. Music mode embeds the bundled `main/canon.pcm`.

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI compiles the shared/default configuration on both ESP-IDF lines. It does not
replace playback, microphone, or amplifier HIL testing.

See [Getting Started](../../../docs/GETTING_STARTED.md),
[Hardware Audit](../../../docs/HARDWARE.md), and [CI](../../../docs/CI.md).
