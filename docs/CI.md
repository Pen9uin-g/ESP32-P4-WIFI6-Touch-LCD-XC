# Continuous Integration

[中文](CI_ZH.md)

GitHub Actions is the build authority for this repository. Maintainers may run
the Python policy checks locally, but product compilation evidence comes from
Actions after the change is committed and pushed.

## Workflows

| Workflow | Purpose |
| --- | --- |
| [Documentation and repository policy](../.github/workflows/documentation.yml) | Always-visible unit, Markdown, structure, and routing-policy checks |
| [ESP-IDF projects](../.github/workflows/esp-idf-projects.yml) | Conditional ESP32-P4 builds for first-party ESP-IDF examples |
| [Arduino projects](../.github/workflows/arduino-projects.yml) | Conditional ESP32-P4 builds for first-party Arduino sketches |

All three workflows start on every pull request and on pushes to `main`. The
product workflows always expose their routing result, while their expensive
build jobs run only when the route selects a product project. A newer pull
request commit cancels an obsolete in-progress run. Pull-request jobs check out
and build the exact head SHA rather than GitHub's synthetic merge commit.

## Static policy gate

The policy workflow runs:

```bash
python -m unittest discover -s .github/tests -p "test_*.py"
python .github/scripts/repo_self_check.py
python .github/scripts/audit_markdown.py . --all --config .github/scripts/markdown-audit-config.json
```

On pull requests, the Markdown command uses the base SHA instead of `--all`.
The self-check verifies required documentation and workflows, generated-output
ignore rules, all 12 direct ESP-IDF projects, all 5 direct Arduino sketches,
and the example index.

For every first-party English/Chinese Markdown companion pair, the local policy
gate requires reciprocal language links near the top of both pages. Internal
links also stay in the reader's language when the destination companion exists;
an explicit bilingual language chooser may link to both targets together.

## Complete change routing

Both product workflows and the policy workflow use one classifier:

```bash
python .github/scripts/ci_change_router.py --base-ref <base-sha> --head-ref <head-sha>
```

The classifier reads `git diff --name-status -z --find-renames`. Deletions and
both sides of a rename therefore retain their original build impact. An invalid
ref or an unexpectedly empty diff is an operational failure, never a silent
green no-build result. The policy workflow adds `--strict-unknown`, so a new
unclassified path must receive an explicit rule even though the router's safe
fallback selects both complete product matrices.

| Changed path | Product route |
| --- | --- |
| `examples/esp-idf/<project>/**` source/configuration | That ESP-IDF project |
| `examples/arduino/examples/<sketch>/**` source | That Arduino sketch |
| `examples/arduino/libraries/**` | All first-party Arduino sketches |
| Product workflow or shared router | Corresponding complete matrix |
| First-party Markdown, `docs/**`, `assets/**`, `hardware/**`, policy-only files | Policy checks only |
| `firmware/**` | Visible `firmware_touched` result; no inferred example build |
| Firmware/archive images such as `.bin` or `.zip` | Firmware result plus explicit release-review flag |
| Unknown non-documentation path | Both complete matrices and strict policy failure |

`firmware/brookesia` is a separately maintained delivery/source surface. It is
inventoried, but it is not treated as another example and does not gain an
unverified build command merely because its directory contains an ESP-IDF
project.

## ESP-IDF matrix

A first-party ESP-IDF project contains both `CMakeLists.txt` and `main/` and is
a direct child of `examples/esp-idf/`. Every selected project builds with:

| Setting | Value |
| --- | --- |
| ESP-IDF | `v5.5.5`, `v6.0.2` |
| Target | `esp32p4` |
| GitHub Action | `espressif/esp-idf-ci-action@v1` |

The complete route contains 40 jobs: projects 01–06 use the shared/default
configuration (6 × 2); display projects 07–11 build explicit 3.4C (800×800)
and 4C (720×720) variants (5 × 2 × 2); and
`12_usb_extend_screen` builds both display variants with both `default` and
CI-only `vendor-only` configurations (2 × 2 × 2). Vendor-only keeps the screen
choice orthogonal while disabling HID touch/UAC audio and omitting the managed
UAC component during dependency resolution.

Manual runs accept `project=all`, a directory name such as `02_HelloWorld`, or
a full project path.

## Arduino matrix

Only direct children matching
`examples/arduino/examples/<name>/<name>.ino` are first-party sketches.
Examples bundled inside third-party libraries are not discovered. Each selected
sketch builds for both displays:

| Setting | Value |
| --- | --- |
| Arduino-ESP32 | `3.3.11` |
| Board | Generic ESP32-P4, pre-v3 silicon, 32 MB flash, PSRAM enabled |
| Display variants | 3.4C (`SCREEN_3INCH_4_DSI`), 4C (`SCREEN_4INCH_DSI`) |
| Bundled libraries | `examples/arduino/libraries/` |

A complete route is 5 sketches times 2 display variants, or 10 build jobs.
Manual runs accept `sketch=all`, a sketch name, or a full sketch path.

## Downloadable example artifacts

After a successful product build, Actions uploads one artifact named with its
project/sketch, variant, configuration, framework and short exact SHA. Download
it from the workflow run's **Artifacts** section. It contains only generated
first-party example outputs: `manifest.json`, `SHA256SUMS`, `flash.sh`,
`flash.bat`, safe-path `bin/` files referenced by the framework flash plan, and
available ELF/map/sdkconfig debug files. Arduino packages also retain
`merged.bin` when the core generated it.

The manifest records the full commit SHA, target, display/resolution,
configuration, framework, flash settings and ordered offsets. The flash helpers
require a port and accept an optional baud rate; they do not erase flash.
Artifacts are example-build diagnostics, not hardware validation or factory
firmware. Releases remain manual/deferred, and the separately maintained
`firmware/` delivery surface remains separate.
