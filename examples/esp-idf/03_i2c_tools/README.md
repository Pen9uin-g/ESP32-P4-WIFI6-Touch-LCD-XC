# I2C Tools

[中文](README_ZH.md)

This console example configures and probes the board's shared I2C bus: SDA is
GPIO7 and SCL is GPIO8. It supports ESP32-P4-WIFI6-Touch-LCD-XC 3.4C and 4C
with ESP-IDF `v5.5.5` and `v6.0.2`.

## Configuration and run

No external client is supplied. Connect only compatible I2C hardware to the
shared bus, then use `menuconfig` to adjust the documented I2C GPIO defaults or
console history option if needed.

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

At the `i2c-tools>` prompt, `help` lists commands; `i2cconfig`, `i2cdetect`,
`i2cget`, `i2cset`, and experimental `i2cdump` are registered by this project.
CI compiles its shared/default configuration on both ESP-IDF lines, not attached
I2C devices.

See [Getting Started](../../../docs/GETTING_STARTED.md),
[Hardware Audit](../../../docs/HARDWARE.md), and [CI](../../../docs/CI.md).
