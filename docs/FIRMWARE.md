# Firmware Source Boundary

[中文](FIRMWARE_ZH.md)

The repository contains a maintained ESP-Brookesia source project at
[`firmware/brookesia`](../firmware/brookesia/). It is a separate firmware/delivery
surface rather than a routine example.

## CI and change boundary

- Default ESP-IDF example CI discovers only `examples/esp-idf/`.
- `firmware/brookesia` is inventoried so maintainers can see its source and build
  configuration, but it is not silently added to the example matrix.
- Product workflows still publish a visible `firmware_touched` routing result;
  they skip example builds instead of treating the firmware change as docs-only.
- A `.bin`, `.zip`, or similar image/archive change also raises the explicit
  `release_review` flag.
- Do not change, repackage, or regenerate firmware source, binaries, or delivery
  archives as part of documentation or example-CI maintenance without an explicit
  firmware scope.
- Example-CI build outputs, when later requested, must remain separate from reviewed
  factory or delivery firmware.

This checkout currently has no positively identified checked-in factory `.bin` or
delivery `.zip` artifact under `firmware/`. Source and build instructions for a
future delivery surface are not included here yet and may be added later.

When firmware maintenance is authorized, record the target, ESP-IDF version,
component provenance, partition table, generated outputs, and validation evidence
separately from the first-party example matrix.
