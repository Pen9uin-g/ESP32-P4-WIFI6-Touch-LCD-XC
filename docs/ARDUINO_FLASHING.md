# Arduino Segmented Flashing and Hardware CDC

[简体中文](ARDUINO_FLASHING_ZH.md)

## Scope

This guide applies to the 10 first-party sketches under
`examples/arduino/examples/` built with Arduino-ESP32 `3.3.11` and the exact
FQBN recorded in [the Arduino README](../examples/arduino/README.md). Select the
package whose 3.4C or 4C display variant matches the connected product.

These packages are hardware-test candidates, not factory firmware or evidence
that hardware-in-the-loop (HIL) testing passed.

## What the package contains

The packager reads the complete Arduino CLI build directory. It copies only the
bootloader, partition table, `boot_app0` when present, application, and any
other segment named by that build's generated `flash_args`. Offsets and flash
options are never inferred from the chip family, copied from another build, or
reconstructed from a merged image.

Each validated directory and ZIP contains:

- `manifest.json`, including the ordered segment offset, file, size and SHA-256;
- the normalized `flash_args` and its size and SHA-256 metadata;
- `SHA256SUMS`, covering the package metadata, helpers and payload files;
- `flash.sh` and `flash.bat`, which execute the exact segmented plan; and
- only the `bin/` payload files referenced by the real segment plan.

Raw `build.options.json`, expanded properties, ELF/map debug metadata and other
host-specific build records are not published. Under `build_inputs`, the
manifest records only the basename, size and SHA-256 of the raw build options,
`flash_args` and `compile_commands.json`; the validator re-hashes those exact
files in the private build directory.

The sanitized `build_identity` binds the product SHA, repository-relative
project and primary `.ino` path, sketch name, exact FQBN and screen define. It
also records basename/size/SHA-256 identities for the tracked primary source,
generated sketch translation unit and object, the SHA-256 of the ordered
compile-argument array, and the application basename, package path, offset,
size and SHA-256. Validation recomputes this identity from a clean source
checkout at the declared product SHA and the external build directory. It
matches the private build-options `sketchLocation` to the tracked project and
requires one matching compile entry, the real source include, translation unit,
object and application segment, plus the exact FQBN, screen define,
`ARDUINO_USB_MODE=1` and `ARDUINO_USB_CDC_ON_BOOT=1`. Raw compile arguments,
usernames, absolute work directories and tool-cache paths never enter the
public package.

The manifest also records the full product Git SHA, Arduino FQBN and core
version, flash capacity, `segmented_payload_total`, and the candidate BSP's
version, source SHA, source-tree hash and component-tree hash. Arduino sketches
do not link the managed ESP-IDF BSP, so the BSP relationship is explicitly
`reference-only`; the pins still bind an Arduino candidate to the same review
checkpoint as the ESP-IDF candidates.

Merged or whole-flash images are not published. A bootloader at offset `0x0`
is valid when the generated multi-segment plan requires it; a single merged
image written at `0x0` is not.

## Verify before flashing

Keep the package directory intact and run its checksum check from inside that
directory:

```sh
sha256sum -c SHA256SUMS
```

Also inspect `manifest.json` and confirm all of the following:

1. `product_variant`, `resolution` and `profile_id` match the board.
2. `product_git_sha` and every BSP pin match the candidate being tested.
3. `framework.version` is `3.3.11` and the FQBN is the expected ESP32-P4 FQBN.
4. `build_identity.project`, `sketch`, `screen_define`, `primary_source.path`
   and `application.source_basename` identify the intended sketch build.
5. The ordered `files` list and `portable_flash_command` describe multiple
   individual segments rather than a merged or whole-flash image.

CI validates the directory and then reopens the generated ZIP to repeat path,
hash, size, overlap, flash-capacity, privacy and no-merged checks. During the CI
check it also re-hashes the original build options outside the public package.
For both the directory and reopened ZIP, the validator reconstructs `flash.sh`
and `flash.bat` byte-for-byte from the validated segment plan. Either helper
being absent, a segment being removed, or any offset, segment filename, flash
mode/frequency/size option being changed makes validation fail with a nonzero
exit. Do not add, remove or replace files after validation.

## Flash the generated segment plan

Install the `esptool` Python package in the environment used for flashing.
Replace `PORT` with the upload port detected for the board. On Linux or macOS:

```sh
sh flash.sh PORT 921600
```

On Windows:

```bat
flash.bat PORT 921600
```

The helpers issue one `write_flash` command containing the real ordered
offset/file pairs recorded by Arduino CLI. They do not erase the device and do
not write a padded flash-size image. The copyable command with all resolved
segments is also available as `portable_flash_command` in `manifest.json`.

## Choose the correct USB connector

The tested FQBN uses `USBMode=hwcdc,CDCOnBoot=cdc`:

- **Type-C USB** connects the ESP32-P4 internal USB pins and carries sketch
  `Serial` through Hardware USB Serial/JTAG CDC.
- **Type-C UART** connects through the CH343P bridge to UART0. Supported upload
  flows can use that interface, but it does not carry sketch `Serial` output
  under the tested FQBN.

The first-party logging wrapper never waits for either connector or a serial
monitor. Hardware CDC uses a zero transmit timeout and drops a diagnostic line
when disconnected or back-pressured, so logging cannot hold up application,
display or touch startup.

## Required HIL checks

Run these checks separately on the 3.4C and 4C packages:

1. Close every serial monitor, disconnect Type-C USB, then power-cycle the
   board. Confirm the selected sketch enters its normal display and touch
   behavior without a host connection.
2. Connect Type-C USB while leaving the monitor closed. Exercise the UI and
   touch continuously; host backpressure must not introduce stalls.
3. Open the Hardware CDC monitor at `115200`. Confirm that opening it neither
   resets nor blocks the application. Startup lines may already have been
   dropped by design.
4. Close, unplug and reconnect Type-C USB while continuing to exercise the
   application. Display and touch must continue; later log lines may resume or
   be dropped without affecting the application.
5. For touch candidates, test cold start, software reset, repeated power cycles,
   corners, edges, dragging and multiple touch points. `Drawing_board` is the
   primary polling test; `LVGLV9_Arduino` adds continuous LVGL rendering.
6. If Type-C UART is used for upload, verify that upload/reset works as expected
   but do not treat absence of sketch logs on that connector as a failure.

Compilation, packaging and host-side tests cannot establish these physical
results. Record the package SHA-256 and exact product/BSP pins with every HIL
report.
