# Continuous Integration

GitHub Actions performs the repository checks and product builds for this
repository. The workflows intentionally separate documentation validation from
firmware compilation so a documentation-only change does not consume product
build jobs.

## Workflows

| Workflow | Purpose |
| --- | --- |
| [ESP-IDF projects](../.github/workflows/esp-idf-projects.yml) | Repository self-check, ESP-IDF project discovery, and ESP32-P4 builds |
| [Arduino projects](../.github/workflows/arduino-projects.yml) | First-party Arduino sketch discovery and ESP32-P4 builds |

Both workflows run on relevant pull requests, on matching pushes to `main`, and
through manual dispatch from the GitHub Actions page.

## Repository Self-Check

The ESP-IDF workflow runs:

```bash
python .github/scripts/repo_self_check.py
```

It verifies that:

- Repository-level documentation, product artwork, CI workflows, and helper
  scripts exist.
- Generated ESP-IDF outputs are ignored.
- Every discovered ESP-IDF project has the minimum expected structure.
- Every first-party Arduino sketch has a same-named `.ino` file.
- The ESP-IDF example index includes every discovered project.

Changes limited to `README*.md`, `docs/**`, or `assets/**` run this self-check
but do not select ESP-IDF or Arduino product builds.

## ESP-IDF Build Discovery

The discovery helper runs:

```bash
python .github/scripts/discover_esp_idf_projects.py
```

A buildable ESP-IDF project contains both `CMakeLists.txt` and `main/`. The
current project roots are:

- `examples/esp-idf/`
- `firmware/` (including supported capitalization variants)

For pull requests and pushes, only affected projects are selected. Changes to
the ESP-IDF workflow, its discovery helper, or shared files under `config/`
select all 13 projects.

Each selected project is built with:

| Setting | Value |
| --- | --- |
| ESP-IDF | `v5.5.5`, `v6.0.2` |
| Target | `esp32p4` |
| GitHub Action | `espressif/esp-idf-ci-action@v1` |

Manual runs accept `project=all`, a directory name such as
`02_HelloWorld`, or a full path such as
`examples/esp-idf/02_HelloWorld`.

## Arduino Build Discovery

The Arduino helper runs:

```bash
python .github/scripts/discover_arduino_sketches.py
```

Only direct children matching
`examples/arduino/examples/<name>/<name>.ino` are first-party sketches.
Examples bundled inside third-party libraries are never discovered.

For pull requests and pushes, only affected sketches are selected. A change to
the Arduino workflow, its discovery helper, or any bundled library under
`examples/arduino/libraries/` selects all 5 first-party sketches. Manual runs
accept `sketch=all`, a sketch name, or a full sketch path.

Each selected sketch is compiled twice:

| Setting | Value |
| --- | --- |
| Arduino-ESP32 | `3.3.11` |
| Board | Generic ESP32-P4, pre-v3 silicon, 32 MB flash, PSRAM enabled |
| Display variants | 3.4C (`SCREEN_3INCH_4_DSI`), 4C (`SCREEN_4INCH_DSI`) |
| Bundled libraries | `examples/arduino/libraries/` |

The workflow uses the repository copies of Arduino GFX, LVGL, and the board
display/touch helpers. It does not substitute newer online library versions.
