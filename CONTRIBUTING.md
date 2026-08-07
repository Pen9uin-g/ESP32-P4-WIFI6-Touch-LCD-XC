# Contributing

[中文](CONTRIBUTING_ZH.md)

Thank you for improving the ESP32-P4-WIFI6-Touch-LCD-XC examples and
documentation.

## Before opening a pull request

- Keep changes scoped to the affected first-party example or documentation
  surface.
- Do not add generated `build/`, `managed_components/`, `dependencies.lock`, or
  local `sdkconfig` output.
- Keep bundled library and embedded-upstream source boundaries intact.
- Do not change `firmware/` source or delivery artifacts as part of routine
  example/CI work without explicit maintainer direction.
- For board-facing changes, compare the repository schematic, BSP headers,
  Arduino configuration, and example source before changing pins or display
  settings.
- Add or update the English and Simplified Chinese Markdown companions for
  first-party human-readable documentation.

## Validation

Run the repository checks relevant to the change:

```bash
python .github/scripts/repo_self_check.py
python .github/scripts/audit_markdown.py . --working-tree --config .github/scripts/markdown-audit-config.json
python .github/scripts/discover_esp_idf_projects.py --project all
python .github/scripts/discover_arduino_sketches.py --sketch all
```

For source changes, use the ESP-IDF and Arduino workflows or equivalent local
toolchains. In a pull request description, record the examples, framework
versions, target, hardware/reference audit status, component impact, and any
firmware artifact impact.
