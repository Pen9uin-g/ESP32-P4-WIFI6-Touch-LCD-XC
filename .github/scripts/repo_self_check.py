#!/usr/bin/env python3
"""Lightweight repository structure checks for CI."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOTS = (
    Path("examples/esp-idf"),
)
ARDUINO_SKETCH_ROOT = Path("examples/arduino/examples")

REQUIRED_FILES = (
    Path("README.md"),
    Path("README_ZH.md"),
    Path("assets/ESP32-P4-WIFI6-Touch-LCD-XC.jpg"),
    Path("docs/GETTING_STARTED.md"),
    Path("docs/PROJECT_STRUCTURE.md"),
    Path("docs/CI.md"),
    Path("docs/TROUBLESHOOTING.md"),
    Path("examples/README.md"),
    Path("examples/arduino/README.md"),
    Path(".github/scripts/audit_markdown.py"),
    Path(".github/scripts/ci_change_router.py"),
    Path(".github/scripts/package_build_artifact.py"),
    Path(".github/scripts/ci-routing-audit-config.json"),
    Path(".github/scripts/markdown-audit-config.json"),
    Path(".github/scripts/repo_self_check.py"),
    Path(".github/tests/test_audit_markdown.py"),
    Path(".github/tests/test_ci_change_router.py"),
    Path(".github/tests/test_package_build_artifact.py"),
    Path(".github/ISSUE_TEMPLATE/bug_report.md"),
    Path(".github/ISSUE_TEMPLATE/bug_report_ZH.md"),
    Path(".github/pull_request_template.md"),
    Path(".github/pull_request_template_ZH.md"),
    Path(".github/workflows/arduino-projects.yml"),
    Path(".github/workflows/documentation.yml"),
    Path(".github/workflows/esp-idf-projects.yml"),
    Path("CONTRIBUTING.md"),
    Path("CONTRIBUTING_ZH.md"),
    Path("SUPPORT.md"),
    Path("SUPPORT_ZH.md"),
    Path("docs/CI_ZH.md"),
    Path("docs/COMPONENTS.md"),
    Path("docs/COMPONENTS_ZH.md"),
    Path("docs/FIRMWARE.md"),
    Path("docs/FIRMWARE_ZH.md"),
    Path("docs/GETTING_STARTED_ZH.md"),
    Path("docs/HARDWARE.md"),
    Path("docs/HARDWARE_ZH.md"),
    Path("docs/PROJECT_STRUCTURE_ZH.md"),
    Path("docs/TROUBLESHOOTING_ZH.md"),
    Path("examples/README_ZH.md"),
    Path("examples/arduino/README_ZH.md"),
    Path("examples/esp-idf/09_video_lcd_display/README_ZH.md"),
    Path("examples/esp-idf/10_mp4_player/README_ZH.md"),
    Path("examples/esp-idf/11_esp_brookesia_phone/README_ZH.md"),
    Path("examples/esp-idf/11_esp_brookesia_phone/sdkconfig.ci.4c"),
    Path("examples/esp-idf/11_esp_brookesia_phone/sdkconfig.ci.3_4c"),
    Path("examples/esp-idf/12_usb_extend_screen/sdkconfig.ci.vendor-only"),
)

REQUIRED_GITIGNORE_PATTERNS = {
    "**/build",
    "**/managed_components",
    "**/dependencies.lock",
    "**/sdkconfig",
    "**/sdkconfig.old",
    "**/__pycache__",
    "**/*.pyc",
}


def is_project(path: Path) -> bool:
    return (path / "CMakeLists.txt").is_file() and (path / "main").is_dir()


def list_projects() -> list[Path]:
    projects: list[Path] = []
    for root in PROJECT_ROOTS:
        if not root.exists():
            continue
        for path in root.iterdir():
            if path.is_dir() and is_project(path):
                projects.append(path)
    return sorted(projects, key=lambda item: item.as_posix())


def check_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        if not path.is_file():
            errors.append(f"Missing required file: {path.as_posix()}")


def check_gitignore(errors: list[str]) -> None:
    gitignore = Path(".gitignore")
    if not gitignore.is_file():
        errors.append("Missing .gitignore")
        return

    patterns = {
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    missing = sorted(REQUIRED_GITIGNORE_PATTERNS - patterns)
    for pattern in missing:
        errors.append(f".gitignore missing generated-output pattern: {pattern}")


def check_projects(errors: list[str]) -> list[Path]:
    projects = list_projects()
    if not projects:
        errors.append("No ESP-IDF projects discovered")
        return projects

    names: dict[str, Path] = {}
    for project in projects:
        name = project.name
        if name in names:
            errors.append(
                "Duplicate ESP-IDF project directory name: "
                f"{name} ({names[name].as_posix()} and {project.as_posix()})"
            )
        names[name] = project

        if not (project / "main" / "CMakeLists.txt").is_file():
            errors.append(f"Missing main/CMakeLists.txt: {project.as_posix()}")

    return projects


def check_example_index(projects: list[Path], errors: list[str]) -> None:
    index = Path("examples/README.md")
    if not index.is_file():
        return

    content = index.read_text(encoding="utf-8")
    for project in projects:
        project_text = project.as_posix()
        if project_text not in content:
            errors.append(f"examples/README.md does not mention {project_text}")


def check_arduino_sketches(errors: list[str]) -> list[Path]:
    if not ARDUINO_SKETCH_ROOT.is_dir():
        errors.append(
            f"Missing Arduino sketch root: {ARDUINO_SKETCH_ROOT.as_posix()}"
        )
        return []

    sketch_dirs = sorted(
        (path for path in ARDUINO_SKETCH_ROOT.iterdir() if path.is_dir()),
        key=lambda item: item.as_posix(),
    )
    if not sketch_dirs:
        errors.append("No first-party Arduino sketches discovered")
        return []

    sketches: list[Path] = []
    for sketch_dir in sketch_dirs:
        source = sketch_dir / f"{sketch_dir.name}.ino"
        if not source.is_file():
            errors.append(
                "Arduino sketch source must match its directory name: "
                f"{source.as_posix()}"
            )
            continue
        sketches.append(sketch_dir)

    return sketches


def main() -> int:
    errors: list[str] = []

    check_required_files(errors)
    check_gitignore(errors)
    projects = check_projects(errors)
    check_example_index(projects, errors)
    sketches = check_arduino_sketches(errors)

    if errors:
        print("Repository self-check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Repository self-check passed "
        f"({len(projects)} ESP-IDF projects, {len(sketches)} Arduino sketches)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
