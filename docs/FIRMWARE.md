# Firmware Source Boundary

[中文](FIRMWARE_ZH.md)

The repository contains a maintained ESP-Brookesia source project at
[`firmware/brookesia`](../firmware/brookesia/). It is a separate firmware/delivery
surface rather than a routine example.

## CI and change boundary

- Default ESP-IDF example CI discovers only `examples/esp-idf/`.
- `firmware/brookesia` has its own `maintained-firmware.yml` route and exactly two
  ESP-IDF `v5.5.5` artifacts: `rev1_3` and `rev3_x`. It is not added to the
  unchanged 40 ESP-IDF plus 10 Arduino example jobs.
- The maintained firmware keeps the 3.4C display default and uses 32 MB flash.
  `rev1_3` is the default profile; `rev1_3` and `rev3_x` binaries are incompatible.
- The ESP32-C6 Hosted image remains a runtime dependency, not a C6 flash image
  in these P4 artifacts.
- Product workflows still publish a visible `firmware_touched` routing result;
  they skip example builds instead of treating the firmware change as docs-only.
- A `.bin`, `.zip`, or similar image/archive change also raises the explicit
  `release_review` flag.
- Do not change, repackage, or regenerate firmware source, binaries, or delivery
  archives as part of documentation or example-CI maintenance without an explicit
  firmware scope.
- Downloadable example-CI artifacts are generated after successful example builds.
  They remain separate from reviewed factory or delivery firmware; Releases are
  manual/deferred rather than an automated artifact publication path.

## Flash current CI artifacts

`Flash-CI-Firmware.cmd` downloads and flashes only the exact-HEAD successful
Actions artifact selected by the XC CI router. It requires Git, GitHub CLI,
Python with `esptool`, an open non-draft PR whose head equals the clean local
HEAD, a successful and complete 52-artifact set from all product build workflows
for that SHA, and an explicit serial port.

```text
Flash-CI-Firmware.cmd -SelfTest
Flash-CI-Firmware.cmd -ListOnly
Flash-CI-Firmware.cmd -Port COMx
```

The first two commands are offline local checks: they do not contact GitHub,
inspect serial hardware, or flash a device. Normal mode requires `-Port COMx`;
the GUI displays that explicit port and asks for confirmation before writing.
For Arduino entries, the downloader requires exactly one schema-3 segmented ZIP.
It safely expands that ZIP only after rejecting unsafe, duplicate, colliding, or
linked entries, then verifies the exact `SHA256SUMS` file set. The manifest,
canonical `flash_args`, segment sizes and hashes, Flash capacity, FQBN, product
SHA, and reference-only BSP version/source/tree/component-tree pins must all
match the selected exact-HEAD workflow identity. The CI producer and validator
also recompute a canonical build identity from a clean source worktree at that
product SHA: the repository-relative project and tracked primary sketch, actual
`sketchLocation`, generated translation unit and object, compile FQBN/USB/screen
definitions, source include, and application segment must agree. Raw
`build.options.json` and `compile_commands.json` stay outside the ZIP; only their
basenames, sizes, and SHA-256 digests are published. Merged and whole-flash
images are rejected. A
bootloader at offset `0x0` remains valid as part of a real multi-segment plan; a
single-file plan at `0x0` is rejected. See the
[Arduino segmented flashing guide](ARDUINO_FLASHING.md) for package contents and
manual commands.

The packager and validator each derive their trusted repository root from their
own checked-in script location. `--source-root` must resolve to that same Git
top-level worktree (the workflow passes its own `GITHUB_WORKSPACE`). A script
from one checkout therefore rejects a different checkout even when the other
checkout reports a self-consistent SHA and build metadata.

Schema-3 ZIP entries use fixed timestamps and the manifest contains no
wall-clock generation field, so packaging the same verified inputs twice is
byte-for-byte reproducible. The package regression suite also rewrites a valid
ZIP with five independent mutations for each helper (`flash.sh` and
`flash.bat`): removing the helper, removing one segment pair, changing an
offset, changing a filename, and changing a flash option. All ten cases must be
rejected by the ZIP validator after checksum metadata is recomputed.

`-SelfTest` also creates a temporary synthetic schema-3 package and ZIP locally.
It checks the legal offset-`0x0` multi-segment case and negative BSP, canonical
build-identity, checksum, whole-flash, traversal, duplicate-entry, and symlink
cases without using the network or a serial device.

The GUI never erases flash. It persists the exact SHA, manual PASS progress,
selected port, and logs under the current user's local application-data
directory; verified-write state does not carry across sessions. A successful CI artifact
and `Hash of data verified` prove neither display, touch, audio, USB, nor other
hardware behavior; confirm each item manually before marking it PASS.

Silicon revision selection cannot confirm PCB or electrical revision. Compile
success, CI success, and a verified write do not replace HIL testing. Touch
HIL still requires checking the responding `0x5D`/`0x14` address, coordinates,
release events, and polling on real hardware.

This checkout currently has no positively identified checked-in factory `.bin` or
delivery `.zip` artifact under `firmware/`. Source and build instructions for a
future delivery surface are not included here yet and may be added later.

When firmware maintenance is authorized, record the target, ESP-IDF version,
component provenance, partition table, generated outputs, and validation evidence
separately from the first-party example matrix.
