#!/usr/bin/env python3
"""Run the repository's lightweight Markdown and scope policy gate.

The full Waveshare modernization skill remains the authoritative deep audit
used by maintainers.  This repository-local gate keeps the most important
checks reproducible in GitHub Actions without depending on a developer's
local skill installation: first-party language pairing, local links, homepage
symmetry, public-text hygiene, and docs-only scope classification.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


FIRST_PARTY = {
    "first_party_customer",
    "first_party_maintainer",
    "first_party_wrapper",
}
UPSTREAM = {"managed_component", "third_party", "embedded_upstream"}
DEFAULT_CONFIG = {
    "classification_rules": [
        {"category": "managed_component", "patterns": ["managed_components/**", "**/managed_components/**"]},
        {"category": "third_party", "patterns": [
            "third_party/**", "**/third_party/**", "third-party/**", "**/third-party/**",
            "vendor/**", "**/vendor/**", "external/**", "**/external/**",
        ]},
        {"category": "embedded_upstream", "patterns": [
            "upstream/**", "**/upstream/**", "submodules/**", "**/submodules/**",
            "libraries/**", "**/libraries/**", "**/components/waveshare__*/**",
        ]},
        {"category": "first_party_wrapper", "patterns": [
            "wrappers/**", "**/wrappers/**", "overrides/**", "**/overrides/**",
            "**/bsp_extra/**",
        ]},
    ],
    "pair_exempt_patterns": [],
    "language_link_exempt_patterns": [],
    "docs_only_allowed_patterns": [],
}
VALID_CATEGORIES = FIRST_PARTY | UPSTREAM | {"unknown"}
QUICK_LINK_ICONS = "🌐📚📦🚀🧩🔧"
H2_ICON_RE = re.compile(r"^##\s+([^\s]+)")
LOCAL_PATH_RE = re.compile(r"(?:\[[^\]]*\]\(|!\[[^\]]*\]\(|href=[\"']|src=[\"'])([^)\"']+)", re.IGNORECASE)
WINDOWS_PATH_RE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\[A-Za-z0-9_.-]+[\\/])")
SERIAL_RE = re.compile(r"\bCOM\d+\b", re.IGNORECASE)
TOKEN_RE = re.compile(r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,})\b")


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def normalized(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def load_config(path: Path | None) -> dict:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if path is None:
        return config
    user = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(user, dict):
        raise ValueError("audit config must be a JSON object")
    for key, value in user.items():
        if key not in config:
            raise ValueError(f"unknown audit config key: {key}")
        if key == "classification_rules":
            if not isinstance(value, list):
                raise ValueError("classification_rules must be a list")
            rules = []
            for rule in value:
                if not isinstance(rule, dict) or set(rule) != {"category", "patterns"}:
                    raise ValueError("each classification rule needs category and patterns")
                if rule["category"] not in VALID_CATEGORIES or not isinstance(rule["patterns"], list):
                    raise ValueError("invalid classification rule")
                rules.append(rule)
            config[key] = rules + config[key]
        else:
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"{key} must be a list of strings")
            config[key] = config[key] + value
    return config


def classify(path: str, config: dict) -> str:
    for rule in config["classification_rules"]:
        if matches(path, rule["patterns"]):
            return rule["category"]
    return "first_party_customer"


def parse_name_status_z(payload: str) -> list[str]:
    """Return both sides of rename/copy records from git name-status output."""

    fields = payload.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    paths: list[str] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        count = 2 if status[:1] in {"R", "C"} else 1
        if not status or index + count > len(fields):
            raise ValueError(f"invalid git name-status record: {status!r}")
        paths.extend(normalized(path) for path in fields[index:index + count])
        index += count
    return sorted(set(paths))


def changed_paths(root: Path, scope: str, base: str | None) -> list[str]:
    if scope == "all":
        output = run_git(root, "ls-files", "*.md")
        return sorted({normalized(line) for line in output.splitlines() if line.strip()})
    if scope == "base":
        return changed_status_paths(root, scope, base)

    output = run_git(root, "status", "--porcelain=v1")
    selected: set[str] = set()
    for line in output.splitlines():
        if len(line) < 4:
            continue
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        selected.add(normalized(value.strip('"')))
    return sorted(selected)


def changed_status_paths(root: Path, scope: str, base: str | None) -> list[str]:
    if scope == "all":
        return []
    if scope == "base":
        output = run_git(
            root,
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            f"{base}...HEAD",
        )
        return parse_name_status_z(output)
    return changed_paths(root, scope, base)


def is_markdown(path: str) -> bool:
    return path.lower().endswith(".md")


def read_text(root: Path, path: str) -> str:
    return (root / Path(path)).read_text(encoding="utf-8")


def expected_companion(path: str) -> str:
    if path.endswith("_ZH.md"):
        return path[:-6] + ".md"
    return path[:-3] + "_ZH.md"


def local_link_target(raw: str) -> str | None:
    target = urllib.parse.unquote(raw.strip())
    if not target or target.startswith(("#", "/", "\\")):
        return None
    parsed = urllib.parse.urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    return parsed.path


def check_links(root: Path, path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for match in LOCAL_PATH_RE.finditer(text):
        raw = match.group(1)
        target = local_link_target(raw)
        if target is None:
            continue
        candidate = (root / Path(path).parent / Path(target)).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            findings.append(Finding("error", "RELATIVE_LINK_ESCAPE", path, f"local link escapes repository: {raw}"))
            continue
        if not candidate.exists():
            findings.append(Finding("error", "RELATIVE_LINK_MISSING", path, f"local link target does not exist: {raw}"))
    return findings


def quick_icons(text: str) -> list[str]:
    header = text.split("\n---", 1)[0]
    return re.findall(f"[{QUICK_LINK_ICONS}]", header)


def h2_icons(text: str) -> list[str]:
    icons: list[str] = []
    for line in text.splitlines():
        if line.startswith("###"):
            continue
        match = H2_ICON_RE.match(line)
        if match:
            icons.append(match.group(1)[0])
    return icons


def check_homepage(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    english = root / "README.md"
    chinese = root / "README_ZH.md"
    if not english.is_file() or not chinese.is_file():
        return findings
    english_text = english.read_text(encoding="utf-8")
    chinese_text = chinese.read_text(encoding="utf-8")
    if quick_icons(english_text) != quick_icons(chinese_text):
        findings.append(Finding(
            "error", "HOMEPAGE_QUICK_LINK_ASYMMETRY", "README.md",
            f"README.md and README_ZH.md quick-link icons differ: {quick_icons(english_text)} != {quick_icons(chinese_text)}",
        ))
    if h2_icons(english_text) != h2_icons(chinese_text):
        findings.append(Finding(
            "error", "HOMEPAGE_H2_ASYMMETRY", "README.md",
            f"README.md and README_ZH.md primary-section icons differ: {h2_icons(english_text)} != {h2_icons(chinese_text)}",
        ))
    return findings


def check_public_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for pattern, code, message in (
        (WINDOWS_PATH_RE, "LOCAL_ABSOLUTE_PATH", "public Markdown contains a machine-specific absolute path"),
        (SERIAL_RE, "ACTUAL_SERIAL_PORT", "public Markdown contains a concrete serial-port identifier"),
        (TOKEN_RE, "CREDENTIAL_OR_TOKEN", "public Markdown contains a credential-shaped token"),
    ):
        if pattern.search(text):
            findings.append(Finding("error", code, path, message))
    return findings


def docs_only_findings(root: Path, paths: list[str], config: dict) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if is_markdown(path) or matches(path, config["docs_only_allowed_patterns"]):
            continue
        findings.append(Finding("error", "DOCS_ONLY_SCOPE", path, "documentation-only scope contains a non-documentation file"))
    return findings


def deleted_pair_findings(root: Path, paths: list[str], config: dict) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        candidate = root / Path(path)
        if not is_markdown(path) or candidate.exists():
            continue
        if classify(path, config) not in FIRST_PARTY or matches(
            path, config["pair_exempt_patterns"]
        ):
            continue
        counterpart = expected_companion(path)
        if (root / Path(counterpart)).is_file():
            findings.append(
                Finding(
                    "error",
                    "BILINGUAL_PAIR_ORPHANED",
                    path,
                    f"deleting or renaming this page leaves its companion orphaned: {counterpart}",
                )
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--base")
    scope.add_argument("--working-tree", action="store_true")
    scope.add_argument("--all", action="store_true")
    parser.add_argument("--expect-docs-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    root = args.repo.resolve()
    selected_scope = "all" if args.all else "base" if args.base else "working-tree"
    try:
        config = load_config(args.config.resolve() if args.config else None)
        paths = changed_paths(root, selected_scope, args.base)
        status_paths = changed_status_paths(root, selected_scope, args.base)
    except (OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as exc:
        print(f"Markdown audit incomplete: {exc}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    if args.expect_docs_only:
        findings.extend(docs_only_findings(root, status_paths or paths, config))
    findings.extend(deleted_pair_findings(root, paths, config))

    selected_markdown = [path for path in paths if is_markdown(path) and (root / Path(path)).is_file()]
    classifications = {path: classify(path, config) for path in selected_markdown}
    for path in selected_markdown:
        category = classifications[path]
        if category in FIRST_PARTY and not matches(path, config["pair_exempt_patterns"]):
            counterpart = expected_companion(path)
            if not (root / Path(counterpart)).is_file():
                severity = "warning" if selected_scope == "all" else "error"
                findings.append(Finding(severity, "BILINGUAL_PAIR_MISSING", path, f"first-party Markdown has no companion: {counterpart}"))
            elif path.endswith("_ZH.md"):
                text = read_text(root, path)
                if not re.search(r"(?:English|英文|English Version|English version)", text[:1200], re.IGNORECASE):
                    findings.append(Finding("warning", "BILINGUAL_NAVIGATION_MISSING", path, "Chinese page has no nearby English navigation entry"))
        if category in FIRST_PARTY:
            text = read_text(root, path)
            findings.extend(check_links(root, path, text))
            findings.extend(check_public_text(path, text))
        elif category == "unknown":
            findings.append(Finding("warning", "MARKDOWN_OWNERSHIP_UNKNOWN", path, "Markdown ownership is not classified"))

    findings.extend(check_homepage(root))

    print(f"Markdown audit: {root.name}")
    print(f"Scope: {selected_scope}, selected_markdown={len(selected_markdown)}, docs_only={args.expect_docs_only}")
    counts: dict[str, int] = {}
    for category in classifications.values():
        counts[category] = counts.get(category, 0) + 1
    if counts:
        print("Classification: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    for finding in findings:
        print(f"[{finding.severity.upper()}] {finding.code} {finding.path}: {finding.message}")
    errors = sum(finding.severity == "error" for finding in findings)
    warnings = sum(finding.severity == "warning" for finding in findings)
    print(f"Summary: errors={errors} warnings={warnings}")
    if errors or (warnings and args.strict):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
