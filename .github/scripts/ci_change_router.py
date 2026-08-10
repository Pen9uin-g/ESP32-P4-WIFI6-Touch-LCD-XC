#!/usr/bin/env python3
"""Classify repository changes and emit the complete product CI route.

This script is the single source of truth for the ESP-IDF and Arduino build
matrices.  It deliberately keeps the maintained ``firmware/`` tree outside the
example matrices while making that decision visible to policy jobs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


IDF_ROOT = Path("examples/esp-idf")
ARDUINO_ROOT = Path("examples/arduino/examples")
ARDUINO_LIBRARY_ROOT = "examples/arduino/libraries"
DEFAULT_IDF_VERSIONS = ("v5.5.5", "v6.0.2")
SCREEN_VARIANTS = (
    {"screen": "3.4C", "variant_id": "3_4c", "screen_define": "SCREEN_3INCH_4_DSI", "resolution": "800x800"},
    {"screen": "4C", "variant_id": "4c", "screen_define": "SCREEN_4INCH_DSI", "resolution": "720x720"},
)
USB_PROJECT = "examples/esp-idf/12_usb_extend_screen"
PHONE_PROJECT = "examples/esp-idf/11_esp_brookesia_phone"
DISPLAY_PROJECTS = {
    f"examples/esp-idf/{name}"
    for name in (
        "07_Displaycolorbar", "08_lvgl_demo_v9", "09_video_lcd_display",
        "10_mp4_player", "11_esp_brookesia_phone", "12_usb_extend_screen",
    )
}
DISPLAY_BASE_DEFAULTS = {
    "examples/esp-idf/07_Displaycolorbar": ("sdkconfig.defaults", "sdkconfig.defaults.esp32p4"),
    USB_PROJECT: ("sdkconfig.defaults", "sdkconfig.defaults.esp32p4"),
}

GLOBAL_BOTH_PATHS = {
    ".github/scripts/ci_change_router.py",
    ".github/scripts/package_build_artifact.py",
}
# Keep the legacy classifier paths as routing inputs so their deletion or a
# later rename still selects the matrix whose behavior changed.
IDF_GLOBAL_PATHS = {
    ".github/scripts/discover_esp_idf_projects.py",
    ".github/workflows/esp-idf-projects.yml",
}
ARDUINO_GLOBAL_PATHS = {
    ".github/scripts/discover_arduino_sketches.py",
    ".github/workflows/arduino-projects.yml",
}
POLICY_PATHS = {
    ".gitignore",
    "LICENSE",
    ".github/workflows/documentation.yml",
    ".github/scripts/audit_markdown.py",
    ".github/scripts/ci-routing-audit-config.json",
    ".github/scripts/markdown-audit-config.json",
    ".github/scripts/repo_self_check.py",
}
POLICY_PREFIXES = (
    ".github/ISSUE_TEMPLATE/",
    ".github/PULL_REQUEST_TEMPLATE/",
    ".github/tests/",
    "assets/",
    "docs/",
    "hardware/",
)
RELEASE_SUFFIXES = (
    ".a",
    ".bin",
    ".elf",
    ".gz",
    ".img",
    ".map",
    ".tar",
    ".uf2",
    ".xz",
    ".zip",
)
STATUS_RE = re.compile(r"^[ACDMRTUXB][0-9]*$")
SAFE_ITEM_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class RoutingError(RuntimeError):
    """An operational error that must not be interpreted as a no-build route."""


@dataclass(frozen=True)
class Change:
    status: str
    paths: tuple[str, ...]


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip("/")


def is_idf_project(path: Path) -> bool:
    return (path / "CMakeLists.txt").is_file() and (path / "main").is_dir()


def list_idf_projects() -> list[str]:
    if not IDF_ROOT.is_dir():
        return []
    return sorted(
        path.as_posix()
        for path in IDF_ROOT.iterdir()
        if path.is_dir() and is_idf_project(path)
    )


def list_arduino_sketches() -> list[str]:
    if not ARDUINO_ROOT.is_dir():
        return []
    return sorted(
        path.as_posix()
        for path in ARDUINO_ROOT.iterdir()
        if path.is_dir() and (path / f"{path.name}.ino").is_file()
    )


def validate_inventory(items: set[str], kind: str) -> None:
    unsafe = sorted(item for item in items if not SAFE_ITEM_NAME_RE.fullmatch(Path(item).name))
    if unsafe:
        raise RoutingError(
            f"unsafe {kind} directory name(s): " + ", ".join(unsafe)
        )


def parse_name_status_z(payload: str) -> list[Change]:
    fields = payload.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    changes: list[Change] = []
    index = 0
    while index < len(fields):
        status_token = fields[index]
        index += 1
        if not STATUS_RE.fullmatch(status_token):
            raise RoutingError(f"invalid git status token: {status_token!r}")
        path_count = 2 if status_token[0] in {"R", "C"} else 1
        if index + path_count > len(fields):
            raise RoutingError(f"incomplete git name-status record: {status_token}")
        paths = tuple(normalize_path(path) for path in fields[index:index + path_count])
        index += path_count
        if any(not path for path in paths):
            raise RoutingError(f"empty path in git name-status record: {status_token}")
        changes.append(Change(status_token, paths))
    return changes


def parse_changed_file(path: Path) -> list[Change]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RoutingError(f"cannot read changed-file list {path}: {exc}") from exc
    changes: list[Change] = []
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        fields = raw_line.split("\t")
        if STATUS_RE.fullmatch(fields[0]):
            status = fields.pop(0)
        else:
            status = "M"
        expected = 2 if status[0] in {"R", "C"} else 1
        if len(fields) != expected:
            raise RoutingError(
                f"{path}:{line_number}: status {status} expects {expected} path(s)"
            )
        normalized = tuple(normalize_path(value) for value in fields)
        if any(not value for value in normalized):
            raise RoutingError(f"{path}:{line_number}: empty changed path")
        changes.append(Change(status, normalized))
    return changes


def git_changes(base_ref: str | None, head_ref: str) -> list[Change]:
    if base_ref:
        args = ["diff", "--name-status", "-z", "--find-renames", f"{base_ref}...{head_ref}"]
    else:
        args = [
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-status",
            "-z",
            "--find-renames",
            "-r",
            head_ref,
        ]
    try:
        result = subprocess.run(
            ["git", *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise RoutingError(f"git is unavailable: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or f"git exited with {result.returncode}"
        raise RoutingError(f"cannot classify changes: {detail}")
    return parse_name_status_z(result.stdout)


def path_is_documentation(path: str) -> bool:
    if path.lower().endswith(".md"):
        return True
    if path in POLICY_PATHS:
        return True
    if path.startswith(POLICY_PREFIXES):
        return True
    return path in {
        ".github/CODEOWNERS",
        ".github/pull_request_template.md",
        ".github/pull_request_template_ZH.md",
    }


def path_is_release_artifact(path: str) -> bool:
    return path.lower().endswith(RELEASE_SUFFIXES)


def containing_item(path: str, known_items: set[str]) -> str | None:
    candidates = [
        item for item in known_items if path == item or path.startswith(item + "/")
    ]
    if not candidates:
        return None
    return max(candidates, key=len)


def route_changes(
    changes: list[Change],
    known_idf: set[str],
    known_arduino: set[str],
) -> dict[str, object]:
    selected_idf: set[str] = set()
    selected_arduino: set[str] = set()
    firmware_paths: set[str] = set()
    release_paths: set[str] = set()
    unknown_paths: set[str] = set()
    all_paths = sorted({path for change in changes for path in change.paths})

    for path in all_paths:
        if path_is_release_artifact(path):
            release_paths.add(path)

        if path == "firmware" or path.startswith("firmware/"):
            firmware_paths.add(path)
            continue
        if path_is_documentation(path):
            continue
        if path in GLOBAL_BOTH_PATHS:
            selected_idf.update(known_idf)
            selected_arduino.update(known_arduino)
            continue
        if path in IDF_GLOBAL_PATHS or path == "config" or path.startswith("config/"):
            selected_idf.update(known_idf)
            continue
        if path in ARDUINO_GLOBAL_PATHS:
            selected_arduino.update(known_arduino)
            continue
        if path == ARDUINO_LIBRARY_ROOT or path.startswith(ARDUINO_LIBRARY_ROOT + "/"):
            selected_arduino.update(known_arduino)
            continue

        project = containing_item(path, known_idf)
        if project:
            selected_idf.add(project)
            continue
        if path == IDF_ROOT.as_posix() or path.startswith(IDF_ROOT.as_posix() + "/"):
            # A deleted project cannot be present in the current inventory.  In
            # that case the safe route is the complete ESP-IDF matrix.
            selected_idf.update(known_idf)
            continue

        sketch = containing_item(path, known_arduino)
        if sketch:
            selected_arduino.add(sketch)
            continue
        if path == ARDUINO_ROOT.as_posix() or path.startswith(ARDUINO_ROOT.as_posix() + "/"):
            selected_arduino.update(known_arduino)
            continue

        unknown_paths.add(path)
        selected_idf.update(known_idf)
        selected_arduino.update(known_arduino)

    docs_only = bool(all_paths) and not firmware_paths and not release_paths and all(
        path_is_documentation(path) for path in all_paths
    )
    return {
        "changed_paths": all_paths,
        "idf_projects": sorted(selected_idf),
        "arduino_sketches": sorted(selected_arduino),
        "docs_only": docs_only,
        "firmware_paths": sorted(firmware_paths),
        "release_paths": sorted(release_paths),
        "unknown_paths": sorted(unknown_paths),
    }


def normalize_selection(value: str, known_items: set[str], kind: str) -> list[str]:
    value = normalize_path(value)
    if not value or value == "all":
        return sorted(known_items)
    if value in known_items:
        return [value]
    matches = sorted(item for item in known_items if Path(item).name == value)
    if len(matches) == 1:
        return matches
    known = "\n".join(f"  {item}" for item in sorted(known_items))
    raise RoutingError(f"unknown {kind}: {value}\nKnown {kind}s:\n{known}")


def idf_matrix(projects: list[str]) -> dict[str, list[dict[str, str]]]:
    include: list[dict[str, str]] = []
    for project in projects:
        variants = SCREEN_VARIANTS if project in DISPLAY_PROJECTS else ({"screen": "shared", "variant_id": "shared", "resolution": "n/a"},)
        configurations = ("default", "vendor-only") if project == USB_PROJECT else ("default",)
        for variant in variants:
            for configuration in configurations:
                defaults = list(DISPLAY_BASE_DEFAULTS.get(project, ("sdkconfig.defaults",)))
                if project in DISPLAY_PROJECTS:
                    # Project 11 already records 3.4C in its default file, but an
                    # explicit overlay keeps the matrix contract uniform.
                    defaults.append("sdkconfig.ci.3_4c" if variant["screen"] == "3.4C" else "sdkconfig.ci.4c")
                vendor_only = configuration == "vendor-only"
                if vendor_only:
                    defaults.append("sdkconfig.ci.vendor-only")
                command_parts = []
                if vendor_only:
                    command_parts.append('-D "USB_DEVICE_UAC_COMPONENT=OFF"')
                command_parts.append('-D "SDKCONFIG_DEFAULTS=' + ";".join(defaults) + '"')
                command_parts.append("build")
                command = "idf.py " + " ".join(command_parts)
                for idf_version in DEFAULT_IDF_VERSIONS:
                    artifact_key = "-".join((
                        "xc", variant["variant_id"], "esp-idf",
                        "v" + idf_version.lstrip("v").replace(".", "-"),
                        Path(project).name, configuration,
                    ))
                    include.append(
                        {
                            "project": project,
                            "project_name": Path(project).name,
                            "idf_version": idf_version,
                            "configuration": configuration,
                            "variant": variant["screen"],
                            "variant_id": variant["variant_id"],
                            "resolution": variant["resolution"],
                            "artifact_key": artifact_key,
                            "command": command,
                        }
                    )
    return {"include": include}


def arduino_matrix(sketches: list[str]) -> dict[str, list[dict[str, str]]]:
    return {
        "include": [
            {
                "sketch": sketch,
                "sketch_name": Path(sketch).name,
                **variant,
                "configuration": "default",
                "variant": variant["screen"],
                "artifact_key": "-".join((
                    "xc", variant["variant_id"], "arduino", "3-3-11",
                    Path(sketch).name, "default",
                )),
            }
            for sketch in sketches
            for variant in SCREEN_VARIANTS
        ]
    }


def github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"{name}={value}\n")


def emit_route(route: dict[str, object]) -> None:
    idf_projects = list(route["idf_projects"])
    arduino_sketches = list(route["arduino_sketches"])
    route["idf_matrix"] = idf_matrix(idf_projects)
    route["arduino_matrix"] = arduino_matrix(arduino_sketches)
    route["has_idf"] = bool(idf_projects)
    route["has_arduino"] = bool(arduino_sketches)
    route["firmware_touched"] = bool(route["firmware_paths"])
    route["release_review"] = bool(route["release_paths"])

    compact = lambda value: json.dumps(value, separators=(",", ":"))
    outputs = {
        "idf_matrix": compact(route["idf_matrix"]),
        "has_idf": str(route["has_idf"]).lower(),
        "idf_projects": ",".join(idf_projects),
        "arduino_matrix": compact(route["arduino_matrix"]),
        "has_arduino": str(route["has_arduino"]).lower(),
        "arduino_sketches": ",".join(arduino_sketches),
        "docs_only": str(route["docs_only"]).lower(),
        "firmware_touched": str(route["firmware_touched"]).lower(),
        "release_review": str(route["release_review"]).lower(),
        "unknown_paths": compact(route["unknown_paths"]),
        "route": compact(route),
    }
    for name, value in outputs.items():
        github_output(name, value)
    print(compact(route))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--changed-files-from", type=Path)
    parser.add_argument("--manual-idf")
    parser.add_argument("--manual-arduino")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--strict-unknown", action="store_true")
    args = parser.parse_args()

    try:
        known_idf = set(list_idf_projects())
        known_arduino = set(list_arduino_sketches())
        validate_inventory(known_idf, "ESP-IDF project")
        validate_inventory(known_arduino, "Arduino sketch")
        manual_mode = args.manual_idf is not None or args.manual_arduino is not None
        if args.all and (manual_mode or args.changed_files_from):
            raise RoutingError("--all cannot be combined with manual or changed-file input")
        if args.changed_files_from and manual_mode:
            raise RoutingError("--changed-files-from cannot be combined with manual selection")

        if args.all:
            route = route_changes([], known_idf, known_arduino)
            route["idf_projects"] = sorted(known_idf)
            route["arduino_sketches"] = sorted(known_arduino)
        elif manual_mode:
            route = route_changes([], known_idf, known_arduino)
            if args.manual_idf is not None:
                route["idf_projects"] = normalize_selection(
                    args.manual_idf, known_idf, "ESP-IDF project"
                )
            if args.manual_arduino is not None:
                route["arduino_sketches"] = normalize_selection(
                    args.manual_arduino, known_arduino, "Arduino sketch"
                )
        else:
            changes = (
                parse_changed_file(args.changed_files_from)
                if args.changed_files_from
                else git_changes(args.base_ref, args.head_ref)
            )
            if not changes:
                raise RoutingError(
                    "change classification produced an empty diff; refusing a silent no-build result"
                )
            route = route_changes(changes, known_idf, known_arduino)

        emit_route(route)
        if args.strict_unknown and route["unknown_paths"]:
            print(
                "Unclassified paths require an explicit routing rule: "
                + ", ".join(route["unknown_paths"]),
                file=sys.stderr,
            )
            return 3
        return 0
    except RoutingError as exc:
        print(f"CI change routing failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
