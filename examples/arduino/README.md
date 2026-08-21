# ESP32-P4 Arduino Support

[中文](README_ZH.md)

## Arduino-ESP32 core

### CI-tested stable release

[Arduino-ESP32 3.3.11](https://github.com/espressif/arduino-esp32/releases/tag/3.3.11)
is the exact release used by this repository. Use that version to reproduce CI
and flash-package results; evaluate later releases separately before changing
the compatibility matrix.

### CI-Tested Configuration

GitHub Actions compiles the ten first-party sketches with Arduino-ESP32
`3.3.11`. The CI board configuration is:

```text
esp32:esp32:esp32p4:ChipVariant=postv3,PSRAM=enabled,FlashSize=32M,FlashMode=qio,FlashFreq=80,PartitionScheme=app13M_data7M_32MB,USBMode=hwcdc,CDCOnBoot=cdc,UploadMode=default,UploadSpeed=921600
```

This selects post-v3 ESP32-P4 silicon at the board-supported frequency, enables
the onboard 32 MB PSRAM and 32 MB flash, and provides a 13 MB application
partition for the larger graphics examples. For confirmed pre-v3 silicon,
replace `ChipVariant=postv3` with `ChipVariant=prev3` explicitly; that build is
not part of the default CI matrix, and its binary is not interchangeable with
the `rev3_x` build.

### Arduino IDE setup

Install the **ESP32 by Espressif Systems** board package at exactly `3.3.11`,
then copy all four direct entries from this repository's
`examples/arduino/libraries/` directory into your Arduino sketchbook's
`libraries/` directory:

| Repository entry | Sketchbook destination |
| --- | --- |
| `displays/` | `libraries/displays/` |
| `GFX_Library_for_Arduino/` | `libraries/GFX_Library_for_Arduino/` |
| `lvgl/` | `libraries/lvgl/` |
| `lv_conf.h` | `libraries/lv_conf.h` |

Copy the **contents** of the repository `libraries/` directory; do not copy
the parent directory itself. In particular, do not create
`libraries/libraries/`. The four entries above are the complete bundled
dependency set for these sketches; do not replace them with unrelated upstream
libraries.

`ESP_Video`, `SD_MMC`, `FS`, `Wire`, and `I2S` are supplied by the installed
Arduino-ESP32 3.3.11 core, so they are not copied from this repository.

`displays_config.h` defaults to the 3.4C panel:
`CURRENT_SCREEN` is `SCREEN_3INCH_4_DSI`. To build for the 4C panel in the
Arduino IDE, change that default in `libraries/displays/displays_config.h` to
`SCREEN_4INCH_DSI`. CI uses the equivalent `CURRENT_SCREEN` build macro and
compiles both panels.

For the matching Arduino-ESP32 3.3.11 **Tools** menu configuration, select:

| Tools menu | Selection |
| --- | --- |
| Board | `ESP32P4 Dev Module` |
| Chip Variant | `v3.00 or newer` |
| PSRAM | `Enabled` |
| Flash Size | `32MB (256Mb)` |
| Flash Mode | `QIO` |
| Flash Frequency | `80MHz` |
| Partition Scheme | `32M Flash (13MB APP/6.75MB SPIFFS)` |
| USB Mode | `Hardware CDC and JTAG` |
| CDC On Boot | `Enabled` |
| Upload Speed | `921600` |
| Upload Mode | `UART0 / Hardware CDC` (default; use the USB-UART bridge for UART0 upload) |

These selections are the Arduino IDE names for the CI FQBN above.

### USB ports and non-blocking logs

The CI FQBN selects `USBMode=hwcdc,CDCOnBoot=cdc`. Consequently, sketch
`Serial` output uses the ESP32-P4 Hardware USB Serial/JTAG CDC interface on the
board's **Type-C USB** connector. The separate **Type-C UART** connector passes
through the CH343P USB-to-UART bridge to UART0 and can be used by supported
upload flows, but it does not carry these sketch logs under the CI FQBN.

First-party sketches never wait for a serial monitor. If Hardware CDC is not
connected or the host is not accepting data, diagnostic lines are dropped
without delaying display, touch, or application startup.

Every sketch is compiled for both product displays:

| Product | CI definition |
| --- | --- |
| ESP32-P4-WIFI6-Touch-LCD-3.4C | `CURRENT_SCREEN=SCREEN_3INCH_4_DSI` |
| ESP32-P4-WIFI6-Touch-LCD-4C | `CURRENT_SCREEN=SCREEN_4INCH_DSI` |

### First-party sketches

The Arduino examples are numbered to keep the documentation, CI discovery, and
IDE sketch names aligned:

| Sketch | Purpose |
| --- | --- |
| `01_HelloWorld` | Basic DSI display startup and text output |
| `02_AsciiTable` | Display character table |
| `03_Drawing_board` | GT911-compatible polling touch drawing board |
| `04_LVGLV9_Arduino` | LVGL v9 display and touch example |
| `05_GFX_ESPWiFiAnalyzer` | Nearby Wi-Fi scan visualization |
| `06_Camera_Preview` | OV5647 MIPI-CSI preview on the selected XC display |
| `07_Camera_ISP_Tuning` | OV5647 preview with serial ISP/3A controls |
| `08_SD_Card` | SDIO microSD read/write check |
| `09_Audio_Playback` | ES8311 speaker playback |
| `10_Mic_Record` | ES7210 microphone PCM capture |

The camera, storage, and audio examples use the XC board peripheral pins. They
compile without the optional camera, card, or audio hardware connected, but
their runtime functions require the corresponding hardware.

### MIPI-DSI clock source

The bundled Arduino_GFX DSI panel leaves `phy_clk_src` at `0`, matching the
released BSP and letting the ESP-IDF revision profile select the correct PHY
clock source. The default CI configuration uses `ChipVariant=postv3`; do not
flash a pre-v3 build to a rev3.x board or vice versa.

### Touch behavior

The official controller is GT9271, and the Arduino library uses a
GT911-compatible API. The driver intentionally leaves both RST and INT
unconfigured, installs no interrupt handler, probes `0x5D` then `0x14`, and
polls touch data. Although the schematic routes RST through R62 to GPIO23, INT
only reaches TP2; avoiding software reset/address-strapping keeps the polling
path independent of those signals. Compilation does not confirm the responding
address, coordinates, or release events; verify them on real hardware.

### Documentation

See [segmented flashing and Hardware CDC validation](../../docs/ARDUINO_FLASHING.md)
for package verification, flashing, connector selection, and the required HIL
checks. The [Arduino-ESP32 documentation](https://docs.espressif.com/projects/arduino-esp32/en/latest/)
currently describes the pinned `3.3.11` core.

## Other Dependencies

### [lvgl v9.3.0](https://github.com/lvgl/lvgl)

<p align="center">
  <img src="https://lvgl.io/github-assets/logo-colored.png" width=300px>
</p>

  <h1 align="center">Light and Versatile Graphics Library</h1>
  <br>
<div align="center">
  <img src="https://lvgl.io/github-assets/smartwatch-demo.gif">
  &nbsp;
  <img border="1px" src="https://lvgl.io/github-assets/widgets-demo.gif">
</div>

### [Arduino_GFX v1.6.0](https://github.com/moononournation/Arduino_GFX)

Arduino GFX provides the encapsulated ESP32-P4 MIPI DSI function

## Special points to pay attention

### I2C Drivers

In libraries, we provide a way to wrap i2c_master.h ourselves and then provide some basic functions. The main reason is that after the esp-idf update, arduino-esp32 v3.2.0 uses a new version of i2c_master driver also known as i2c driver_ng, which is not compatible with some older libraries, including but not limited to some sensor libraries, touch libraries, and extended IO libraries.
