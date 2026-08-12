#!/usr/bin/env python3
"""Package a successful first-party ESP-IDF or Arduino build for CI download.

The generated flash plan is read from the framework-generated argument file; no
flash offsets or input filenames are guessed by this helper.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath


class PackageError(RuntimeError):
    pass


FLASH_CAPACITY = 32 * 1024 * 1024
PROFILES = {"rev1_3", "rev3_x"}
FORBIDDEN_FLASH_TOKEN_RE = re.compile(
    r"(?i)(?:^|[^a-z0-9])(?:erase(?:[_-](?:flash|region))?|esp32c6)(?:$|[^a-z0-9])"
)


SDKCONFIG_NOT_SET_RE = re.compile(r"^# (CONFIG_[A-Z0-9_]+) is not set$")


def parse_sdkconfig(path: Path, profile_id: str, artifact_kind: str) -> dict[str, str | None]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PackageError(f"generated sdkconfig is missing: {exc}") from exc
    values: dict[str, str | None] = {}
    for raw_line in lines:
        line = raw_line.strip()
        not_set = SDKCONFIG_NOT_SET_RE.fullmatch(line)
        if not_set:
            values[not_set.group(1)] = None
        elif line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    if values.get("CONFIG_IDF_TARGET") != '"esp32p4"':
        raise PackageError("generated sdkconfig target is not esp32p4")
    enabled_minimums = {
        key for key, value in values.items()
        if key.startswith("CONFIG_ESP32P4_REV_MIN_") and value == "y"
    }
    expected_minimum = (
        "CONFIG_ESP32P4_REV_MIN_100"
        if profile_id == "rev1_3"
        else "CONFIG_ESP32P4_REV_MIN_300"
    )
    selector = values.get("CONFIG_ESP32P4_SELECTS_REV_LESS_V3")
    selector_matches = selector == "y" if profile_id == "rev1_3" else selector in {None, "n"}
    if not selector_matches or enabled_minimums != {expected_minimum}:
        raise PackageError(f"generated sdkconfig does not match {profile_id}")
    if artifact_kind == "maintained-firmware" and (
        values.get("CONFIG_ESPTOOLPY_FLASHSIZE_32MB") != "y"
        or values.get("CONFIG_ESPTOOLPY_FLASHSIZE") != '"32MB"'
        or values.get("CONFIG_ESPTOOLPY_FLASHSIZE_16MB") == "y"
    ):
        raise PackageError("maintained firmware generated sdkconfig must select 32MB flash")
    return values


def parse_build_options(path: Path, profile_id: str) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(f"generated Arduino build.options.json is invalid: {exc}") from exc
    values = " ".join(str(value) for value in data.values())
    if profile_id != "rev1_3" or "ChipVariant=prev3" not in values:
        raise PackageError("generated Arduino options do not match rev1_3 ChipVariant=prev3")


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


def reject_forbidden_flash_values(value: object) -> None:
    """Reject C6 or erase instructions anywhere in a generated flash plan."""
    if isinstance(value, dict):
        for key, item in value.items():
            reject_forbidden_flash_values(str(key))
            reject_forbidden_flash_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            reject_forbidden_flash_values(item)
    elif isinstance(value, str) and FORBIDDEN_FLASH_TOKEN_RE.search(value):
        raise PackageError("generated flash plan contains a forbidden C6 or erase token")


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
    reject_forbidden_flash_values(data)
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
    if any("erase" in token.lower() or "c6" in token.lower() for token in tokens):
        raise PackageError("Arduino flash_args must not contain erase or C6")
    command_indexes = [index for index, token in enumerate(tokens) if token in {"write_flash", "write-flash"}]
    if len(command_indexes) > 1:
        raise PackageError("Arduino flash_args must contain at most one write_flash command")
    if command_indexes:
        command_index = command_indexes[0]
        prefix = tokens[:command_index]
        if prefix == ["esptool.py", "--chip", "esp32p4"]:
            pass
        elif prefix == ["python", "-m", "esptool", "--chip", "esp32p4"]:
            pass
        else:
            raise PackageError("Arduino flash_args has an unsafe command prefix or target")
        tail = tokens[command_index + 1 :]
    else:
        if "--chip" in tokens or any(
            token.lower() in {"esptool", "esptool.py", "python", "write_flash", "write-flash"}
            for token in tokens
        ):
            raise PackageError("Arduino response-file flash_args contains a command or target")
        tail = list(tokens)
    options: list[str] = []
    option_aliases = {
        "--flash-mode": "--flash-mode", "--flash_mode": "--flash-mode",
        "--flash-freq": "--flash-freq", "--flash_freq": "--flash-freq",
        "--flash-size": "--flash-size", "--flash_size": "--flash-size",
    }
    seen_options: set[str] = set()
    while tail and tail[0].startswith("-"):
        raw_option = tail.pop(0)
        normalized_option = option_aliases.get(raw_option)
        if not normalized_option or normalized_option in seen_options:
            raise PackageError(f"Arduino flash_args has unsafe or duplicate option: {raw_option}")
        if not tail or tail[0].startswith("-"):
            raise PackageError("Arduino flash_args has incomplete flash option")
        value = tail.pop(0)
        if any(character in value for character in "\r\n"):
            raise PackageError("Arduino flash_args has an unsafe flash option value")
        seen_options.add(normalized_option)
        options.extend((normalized_option, value))
    if not tail or len(tail) % 2:
        raise PackageError("Arduino flash_args has incomplete offset/file pairs")
    entries: list[tuple[int, PurePosixPath]] = []
    seen: set[int] = set()
    seen_paths: set[PurePosixPath] = set()
    for raw_offset, raw_path in zip(tail[::2], tail[1::2]):
        current = offset(raw_offset)
        if current in seen:
            raise PackageError("Arduino flash_args has duplicate offsets")
        seen.add(current)
        relative = safe_relative(raw_path)
        if relative in seen_paths:
            raise PackageError("Arduino flash_args has duplicate file paths")
        seen_paths.add(relative)
        entries.append((current, relative))
    normalized = "write_flash " + " ".join(options + [item for entry in sorted(entries) for item in (f"0x{entry[0]:x}", entry[1].as_posix())])
    return sorted(entries), {"esptool_options": options}, [raw, normalized]


def write_helpers(output: Path, target: str, baud: str, files: list[dict[str, object]], settings: dict[str, object]) -> str:
    if target != "esp32p4":
        raise PackageError("only esp32p4 flash helpers are permitted")
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
    if args.mode == "esp-idf":
        parse_sdkconfig(Path(args.sdkconfig), args.profile_id, args.artifact_kind)
        plan, settings, original = idf_plan(build)
        if args.artifact_kind == "maintained-firmware" and str(settings.get("flash_size", "")).upper() != "32MB":
            raise PackageError("maintained firmware flasher settings must select 32MB flash")
    else:
        parse_build_options(Path(args.build_options), args.profile_id)
        plan, settings, original = arduino_plan(build)
    flash_files = []
    for flash_offset, relative in plan:
        item = stage(build, output, relative)
        item["offset"] = flash_offset
        if flash_offset + int(item["size"]) > FLASH_CAPACITY:
            raise PackageError("flash file exceeds 32 MiB capacity")
        flash_files.append(item)
    for previous, current in zip(flash_files, flash_files[1:]):
        if int(previous["offset"]) + int(previous["size"]) > int(current["offset"]):
            raise PackageError("flash files overlap")
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
        "schema": 2, "artifact_kind": args.artifact_kind, "source_type": args.mode,
        "product_variant": args.variant, "product_variant_id": args.variant_id,
        "product_label": args.product_label, "resolution": args.resolution, "scope": args.scope,
        "framework": {"name": "ESP-IDF" if args.mode == "esp-idf" else "Arduino-ESP32", "version": args.framework_version},
        "target": args.target, "project": args.project, "sketch": args.sketch if args.mode == "arduino" else None,
        "configuration": args.configuration, "profile_id": args.profile_id,
        "profile_compatibility": "ESP32-P4 silicon revision < 3.0" if args.profile_id == "rev1_3" else "ESP32-P4 silicon revision >= 3.0",
        "flash_capacity_bytes": FLASH_CAPACITY, "git_sha": args.git_sha, "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
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
    parser.add_argument("--product-label", required=True); parser.add_argument("--variant", required=True); parser.add_argument("--variant-id", required=True); parser.add_argument("--resolution", required=True); parser.add_argument("--configuration", required=True); parser.add_argument("--framework-version", required=True); parser.add_argument("--target", required=True); parser.add_argument("--project", required=True); parser.add_argument("--git-sha", required=True); parser.add_argument("--profile-id", required=True, choices=sorted(PROFILES)); parser.add_argument("--artifact-kind", choices=("ci-example", "maintained-firmware"), default="ci-example"); parser.add_argument("--sdkconfig"); parser.add_argument("--build-options"); parser.add_argument("--baud", default="921600"); parser.add_argument("--scope", default="first-party example"); parser.add_argument("--fqbn"); parser.add_argument("--sketch")
    args = parser.parse_args()
    try:
        if len(args.git_sha) != 40 or any(c not in "0123456789abcdef" for c in args.git_sha.lower()): raise PackageError("git SHA must be a full hexadecimal SHA")
        if args.target != "esp32p4": raise PackageError("only esp32p4 packages are permitted")
        if args.mode == "arduino" and (args.profile_id != "rev1_3" or not args.fqbn or not args.sketch or not args.build_options): raise PackageError("Arduino artifacts require rev1_3 FQBN, sketch, and build options")
        if args.mode == "esp-idf" and not args.sdkconfig: raise PackageError("ESP-IDF artifacts require generated sdkconfig")
        if not args.baud.isdigit() or int(args.baud) <= 0: raise PackageError("baud must be a positive integer")
        package(args); return 0
    except PackageError as exc:
        print(f"artifact packaging failed: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
