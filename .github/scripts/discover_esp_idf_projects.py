#!/usr/bin/env python3
"""Discover ESP-IDF projects that should be built by CI."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path


GLOBAL_PROJECT_PATTERNS = (
    ".github/workflows/esp-idf-projects.yml",
    ".github/scripts/discover_esp_idf_projects.py",
    "config/**",
)
DEFAULT_IDF_VERSIONS = ("v5.5.5", "v6.0.2")


def run_git(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_project(path: Path) -> bool:
    return (path / "CMakeLists.txt").is_file() and (path / "main").is_dir()


def discover_roots() -> list[Path]:
    """Return only the first-party example roots used by default CI.

    Projects under ``firmware/`` are maintained delivery/source surfaces.  They
    are inventoried by the repository modernization workflow, but are not part
    of the example matrix unless a future maintainer adds an explicit,
    separately named firmware workflow.
    """

    root = Path("examples/esp-idf")
    return [root] if root.is_dir() else []


def list_projects() -> list[str]:
    projects: list[str] = []
    for root in discover_roots():
        if is_project(root):
            projects.append(root.as_posix())
        for path in root.iterdir():
            if path.is_dir() and is_project(path):
                projects.append(path.as_posix())
    return sorted(dict.fromkeys(projects))


def normalize_project(value: str, known_projects: set[str]) -> str:
    value = value.strip().strip("/")
    if not value or value == "all":
        return value

    normalized = Path(value).as_posix()
    if normalized in known_projects:
        return normalized

    matches = [project for project in known_projects if Path(project).name == value]
    if len(matches) == 1:
        return matches[0]

    return normalized


def discover_from_paths(paths: list[str], known_projects: set[str]) -> list[str]:
    selected: set[str] = set()
    roots = discover_roots()

    for changed_path in paths:
        changed_path = changed_path.strip().strip("/")
        if any(fnmatch.fnmatch(changed_path, pattern) for pattern in GLOBAL_PROJECT_PATTERNS):
            selected.update(known_projects)
            continue

        for project in known_projects:
            if changed_path == project or changed_path.startswith(project + "/"):
                selected.add(project)
                break
        else:
            for root in roots:
                root_path = root.as_posix()
                if changed_path == root_path or changed_path.startswith(root_path + "/"):
                    selected.update(known_projects)
                    break

    return sorted(selected)


def discover_changed_projects(base_ref: str | None, head_ref: str, known_projects: set[str]) -> list[str]:
    if base_ref:
        diff_args = ["diff", "--name-only", f"{base_ref}...{head_ref}"]
    else:
        diff_args = ["diff-tree", "--no-commit-id", "--name-only", "-r", head_ref]

    return discover_from_paths(run_git(diff_args), known_projects)


def github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def versions_for_project(project: str) -> tuple[str, ...]:
    return DEFAULT_IDF_VERSIONS


def build_matrix(selected: list[str]) -> dict[str, list[dict[str, str]]]:
    return {
        "include": [
            {"project": project, "idf_version": idf_version}
            for project in selected
            for idf_version in versions_for_project(project)
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--project", default="")
    args = parser.parse_args()

    known_projects = set(list_projects())
    requested_project = normalize_project(args.project, known_projects)

    if requested_project == "all":
        selected = sorted(known_projects)
    elif requested_project:
        if requested_project not in known_projects:
            print(f"Unknown ESP-IDF project: {args.project}", file=sys.stderr)
            print("Known projects:", file=sys.stderr)
            for project in sorted(known_projects):
                print(f"  {project}", file=sys.stderr)
            return 1
        selected = [requested_project]
    else:
        selected = discover_changed_projects(args.base_ref, args.head_ref, known_projects)

    matrix = build_matrix(selected)
    matrix_json = json.dumps(matrix, separators=(",", ":"))
    has_projects = "true" if selected else "false"

    github_output("matrix", matrix_json)
    github_output("has_projects", has_projects)
    github_output("projects", ",".join(selected))

    print(matrix_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
