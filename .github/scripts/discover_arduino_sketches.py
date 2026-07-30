#!/usr/bin/env python3
"""Discover first-party Arduino sketches that should be built by CI."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path


SKETCH_ROOT = Path("examples/arduino/examples")
BUILD_ALL_PATTERNS = (
    ".github/workflows/arduino-projects.yml",
    ".github/scripts/discover_arduino_sketches.py",
    "examples/arduino/libraries/**",
)
SCREEN_VARIANTS = (
    {"screen": "3.4C", "screen_define": "SCREEN_3INCH_4_DSI"},
    {"screen": "4C", "screen_define": "SCREEN_4INCH_DSI"},
)


def run_git(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def list_sketches() -> list[str]:
    if not SKETCH_ROOT.is_dir():
        return []

    sketches: list[str] = []
    for path in SKETCH_ROOT.iterdir():
        if path.is_dir() and (path / f"{path.name}.ino").is_file():
            sketches.append(path.as_posix())
    return sorted(sketches)


def normalize_sketch(value: str, known_sketches: set[str]) -> str:
    value = value.strip().strip("/")
    if not value or value == "all":
        return value

    normalized = Path(value).as_posix()
    if normalized in known_sketches:
        return normalized

    matches = [sketch for sketch in known_sketches if Path(sketch).name == value]
    if len(matches) == 1:
        return matches[0]

    return normalized


def discover_from_paths(paths: list[str], known_sketches: set[str]) -> list[str]:
    selected: set[str] = set()

    for changed_path in paths:
        changed_path = changed_path.strip().strip("/")
        if any(fnmatch.fnmatch(changed_path, pattern) for pattern in BUILD_ALL_PATTERNS):
            selected.update(known_sketches)
            continue

        for sketch in known_sketches:
            if changed_path == sketch or changed_path.startswith(sketch + "/"):
                selected.add(sketch)
                break

    return sorted(selected)


def discover_changed_sketches(
    base_ref: str | None,
    head_ref: str,
    known_sketches: set[str],
) -> list[str]:
    if base_ref:
        diff_args = ["diff", "--name-only", f"{base_ref}...{head_ref}"]
    else:
        diff_args = ["diff-tree", "--no-commit-id", "--name-only", "-r", head_ref]

    return discover_from_paths(run_git(diff_args), known_sketches)


def build_matrix(selected: list[str]) -> dict[str, list[dict[str, str]]]:
    return {
        "include": [
            {
                "sketch": sketch,
                "sketch_name": Path(sketch).name,
                **screen,
            }
            for sketch in selected
            for screen in SCREEN_VARIANTS
        ]
    }


def github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--sketch", default="")
    args = parser.parse_args()

    known_sketches = set(list_sketches())
    requested_sketch = normalize_sketch(args.sketch, known_sketches)

    if requested_sketch == "all":
        selected = sorted(known_sketches)
    elif requested_sketch:
        if requested_sketch not in known_sketches:
            print(f"Unknown Arduino sketch: {args.sketch}", file=sys.stderr)
            print("Known sketches:", file=sys.stderr)
            for sketch in sorted(known_sketches):
                print(f"  {sketch}", file=sys.stderr)
            return 1
        selected = [requested_sketch]
    else:
        selected = discover_changed_sketches(
            args.base_ref,
            args.head_ref,
            known_sketches,
        )

    matrix_json = json.dumps(build_matrix(selected), separators=(",", ":"))
    has_sketches = "true" if selected else "false"

    github_output("matrix", matrix_json)
    github_output("has_sketches", has_sketches)
    github_output("sketches", ",".join(selected))

    print(matrix_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
