# Project Structure

[中文](PROJECT_STRUCTURE_ZH.md)

This repository is organized as a board package with first-party examples,
maintained firmware source, schematics, and repository-level documentation.

## Top Level

| Path | Purpose |
| --- | --- |
| `README.md` | Project overview and quick start |
| `examples/` | ESP-IDF and Arduino examples |
| `firmware/` | Board firmware applications and related components |
| `hardware/` | Board schematic and hardware reference files |
| `docs/` | Repository-level documentation |
| `.github/` | CI workflow and helper scripts |
| `LICENSE` | Apache license text |

## ESP-IDF Example Projects

Buildable ESP-IDF projects are expected to contain:

| File or directory | Purpose |
| --- | --- |
| `CMakeLists.txt` | ESP-IDF project entry point |
| `main/` | Application source component |
| `main/CMakeLists.txt` | Main component build definition |
| `main/idf_component.yml` | Managed dependencies, when needed |
| `components/` | Project-local components |
| `sdkconfig.defaults` | Default project configuration |
| `sdkconfig.ci*` | Optional CI-oriented configuration overlays |
| `partitions.csv` | Optional custom partition table |
| `README.md` | Project-specific setup and hardware notes |

Generated directories such as `build/`, `managed_components/`,
`dependencies.lock`, and local `sdkconfig` files should not be committed.

The ESP-IDF examples under `examples/esp-idf/` are the default product build
surface. The `firmware/` tree is maintained separately and remains outside the
default example matrix. Its dedicated workflow builds only the rev3.x `3_4c`
and `4c` display profiles; see [Firmware Source Boundary](FIRMWARE.md).

## Example Documentation

Every hardware-facing example should document:

- Supported board and required peripherals.
- ESP-IDF or Arduino-ESP32 version expectations.
- Required jumpers, cables, modules, SD card contents, or test media.
- Required `menuconfig` options or Arduino board settings.
- Build, flash, and monitor commands.
- Known limitations and troubleshooting notes.

Update [examples/README.md](../examples/README.md) when adding, renaming, or
removing projects.

## CI Expectations

The CI helper scripts discover only first-party buildable ESP-IDF examples
under:

- `examples/esp-idf/`

New example directories should be independently buildable with:

```bash
idf.py set-target esp32p4
idf.py build
```

Repository policy and Markdown checks run in a separate always-visible
workflow. Documentation-only changes do not start the expensive example
matrix.
