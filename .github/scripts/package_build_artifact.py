#!/usr/bin/env python3
"""Package a successful first-party ESP-IDF or Arduino build for CI download.

The generated flash plan is read from the framework-generated argument file; no
flash offsets or input filenames are guessed by this helper.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath


class PackageError(RuntimeError):
    pass


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value.replace("\\", "/"))
    windows_path = PureWindowsPath(value)
    if (
        not value
        or path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in path.parts
        or path == PurePosixPath(".")
    ):
        raise PackageError(f"unsafe generated file path: {value!r}")
    return path


def offset(value: str) -> int:
    try:
        result = int(value, 0)
    except ValueError as exc:
        raise PackageError(f"invalid flash offset: {value!r}") from exc
    if result < 0:
        raise PackageError(f"invalid flash offset: {value!r}")
    return result


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(build: Path, output: Path, source: PurePosixPath) -> dict[str, object]:
    build_root = build.resolve()
    input_path = (build_root / Path(*source.parts)).resolve()
    try:
        input_path.relative_to(build_root)
    except ValueError as exc:
        raise PackageError(f"unsafe generated file path: {source.as_posix()!r}") from exc
    if not input_path.is_file():
        raise PackageError(f"generated file is missing: {source.as_posix()}")
    destination = output / "bin" / Path(*source.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_path, destination)
    return {"path": (Path("bin") / Path(*source.parts)).as_posix(), "size": destination.stat().st_size, "sha256": digest(destination)}


def idf_plan(build: Path) -> tuple[list[tuple[int, PurePosixPath]], dict[str, object], list[str]]:
    args_path = build / "flasher_args.json"
    try:
        data = json.loads(args_path.read_text(encoding="utf-8"))
        files = data["flash_files"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise PackageError(f"invalid ESP-IDF flasher_args.json: {exc}") from exc
    if not isinstance(files, dict) or not files:
        raise PackageError("flasher_args.json has no flash_files")
    entries: list[tuple[int, PurePosixPath]] = []
    seen: set[int] = set()
    for raw_offset, raw_path in files.items():
        current = offset(str(raw_offset))
        if current in seen or not isinstance(raw_path, str):
            raise PackageError("duplicate offset or invalid flash file in flasher_args.json")
        seen.add(current)
        entries.append((current, safe_relative(raw_path)))
    settings = data.get("flash_settings", {})
    if not isinstance(settings, dict):
        raise PackageError("flasher_args.json flash_settings must be an object")
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return sorted(entries), settings, [raw]


def arduino_plan(build: Path) -> tuple[list[tuple[int, PurePosixPath]], dict[str, object], list[str]]:
    args_path = build / "flash_args"
    try:
        raw = args_path.read_text(encoding="utf-8").strip()
        tokens = shlex.split(raw)
    except (OSError, ValueError) as exc:
        raise PackageError(f"invalid Arduino flash_args: {exc}") from exc
    command_indexes = [index for index, token in enumerate(tokens) if token in {"write_flash", "write-flash"}]
    if len(command_indexes) > 1:
        raise PackageError("Arduino flash_args has multiple write_flash commands")
    tail = tokens[command_indexes[0] + 1 :] if command_indexes else tokens
    options: list[str] = []
    while tail and tail[0].startswith("-"):
        options.append(tail.pop(0))
        if not tail or tail[0].startswith("-"):
            raise PackageError("Arduino flash_args has incomplete flash option")
        options.append(tail.pop(0))
    if not tail or len(tail) % 2:
        raise PackageError("Arduino flash_args has incomplete offset/file pairs")
    entries: list[tuple[int, PurePosixPath]] = []
    seen: set[int] = set()
    for raw_offset, raw_path in zip(tail[::2], tail[1::2]):
        current = offset(raw_offset)
        if current in seen:
            raise PackageError("Arduino flash_args has duplicate offsets")
        seen.add(current)
        entries.append((current, safe_relative(raw_path)))
    normalized = " ".join(options + [item for entry in sorted(entries) for item in (f"0x{entry[0]:x}", entry[1].as_posix())])
    return sorted(entries), {"esptool_options": options}, [raw, normalized]


def write_helpers(output: Path, target: str, baud: str, files: list[dict[str, object]], settings: dict[str, object]) -> str:
    options = settings.get("esptool_options", [])
    if not isinstance(options, list) or not all(isinstance(item, str) for item in options):
        options = []
    if not options:
        for key in ("flash_mode", "flash_freq", "flash_size"):
            value = settings.get(key)
            if isinstance(value, str) and value:
                options.extend((f"--{key}", value))
    pairs = " ".join(f"0x{int(item['offset']):x} {item['path']}" for item in files)
    command = f"python -m esptool --chip {target} --port {{port}} --baud {{baud}} write_flash {' '.join(options)} {pairs}".replace("  ", " ")
    (output / "flash.sh").write_text("#!/usr/bin/env sh\nset -eu\nport=${1:?usage: flash.sh PORT [BAUD]}\nbaud=${2:-" + baud + "}\n" + command.replace("{port}", '"$port"').replace("{baud}", '"$baud"') + "\n", encoding="utf-8")
    (output / "flash.bat").write_text("@echo off\r\nset PORT=%~1\r\nif \"%PORT%\"==\"\" (echo Usage: flash.bat PORT [BAUD] & exit /b 2)\r\nset BAUD=%~2\r\nif \"%BAUD%\"==\"\" set BAUD=" + baud + "\r\n" + command.replace("{port}", "%PORT%").replace("{baud}", "%BAUD%") + "\r\n", encoding="utf-8")
    return command


def package(args: argparse.Namespace) -> None:
    build, output = args.build_dir.resolve(), args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise PackageError(f"output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    plan, settings, original = idf_plan(build) if args.mode == "esp-idf" else arduino_plan(build)
    flash_files = []
    for flash_offset, relative in plan:
        item = stage(build, output, relative)
        item["offset"] = flash_offset
        flash_files.append(item)
    extra: list[dict[str, object]] = []
    for candidate in sorted(build.glob("*.elf")) + sorted(build.glob("*.map")) + [build / "sdkconfig"]:
        if candidate.is_file():
            rel = safe_relative(candidate.relative_to(build).as_posix())
            extra.append(stage(build, output, rel))
    merged_candidates = sorted(candidate for candidate in build.glob("*.merged.bin") if candidate.is_file())
    if (build / "merged.bin").is_file():
        merged_candidates.append(build / "merged.bin")
    merged_candidates.sort()
    if len(merged_candidates) > 1:
        raise PackageError("ambiguous merged image candidates")
    merged_meta = None
    if merged_candidates:
        merged_meta = stage(build, output, safe_relative(merged_candidates[0].relative_to(build).as_posix()))
    args_name = "flasher_args.json" if args.mode == "esp-idf" else "flash_args"
    normalized_args = original[0] if args.mode == "esp-idf" else original[1]
    (output / args_name).write_text(normalized_args + "\n", encoding="utf-8")
    command = write_helpers(output, args.target, str(args.baud), flash_files, settings)
    manifest = {
        "schema": 1, "artifact_kind": "ci-example", "source_type": args.mode,
        "product_variant": args.variant, "product_variant_id": args.variant_id,
        "product_label": args.product_label, "resolution": args.resolution, "scope": args.scope,
        "framework": {"name": "ESP-IDF" if args.mode == "esp-idf" else "Arduino-ESP32", "version": args.framework_version},
        "target": args.target, "project": args.project, "sketch": args.sketch if args.mode == "arduino" else None,
        "configuration": args.configuration, "git_sha": args.git_sha, "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "baud": int(args.baud), "fqbn": args.fqbn if args.mode == "arduino" else None,
        "flash_settings": settings, "files": flash_files, "debug_files": extra,
        "original_flash_args": original, "portable_flash_command": command, "merged_image": merged_meta,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checks = [(path, digest(path)) for path in sorted(output.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
    (output / "SHA256SUMS").write_text("".join(f"{value}  {path.relative_to(output).as_posix()}\n" for path, value in checks), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("esp-idf", "arduino")); parser.add_argument("--build-dir", type=Path, required=True); parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--product-label", required=True); parser.add_argument("--variant", required=True); parser.add_argument("--variant-id", required=True); parser.add_argument("--resolution", required=True); parser.add_argument("--configuration", required=True); parser.add_argument("--framework-version", required=True); parser.add_argument("--target", required=True); parser.add_argument("--project", required=True); parser.add_argument("--git-sha", required=True); parser.add_argument("--baud", default="921600"); parser.add_argument("--scope", default="first-party example"); parser.add_argument("--fqbn"); parser.add_argument("--sketch")
    args = parser.parse_args()
    try:
        if len(args.git_sha) != 40 or any(c not in "0123456789abcdef" for c in args.git_sha.lower()): raise PackageError("git SHA must be a full hexadecimal SHA")
        if args.mode == "arduino" and (not args.fqbn or not args.sketch): raise PackageError("Arduino artifacts require FQBN and sketch metadata")
        if not args.baud.isdigit() or int(args.baud) <= 0: raise PackageError("baud must be a positive integer")
        package(args); return 0
    except PackageError as exc:
        print(f"artifact packaging failed: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
