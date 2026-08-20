#!/usr/bin/env python3
"""Package a successful first-party ESP-IDF or Arduino build for CI download.

The generated flash plan is read from the framework-generated argument file; no
flash offsets or input filenames are guessed by this helper. Arduino artifacts
publish only the individual files named by Arduino-ESP32's ``flash_args``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath


class PackageError(RuntimeError):
    pass


FLASH_CAPACITY = 32 * 1024 * 1024
ARDUINO_SEGMENT_BYTES_LIMIT = FLASH_CAPACITY // 2
ARDUINO_CORE_VERSION = "3.3.11"
PROFILES = {"rev1_3", "rev3_x"}
TRUSTED_REPO_ROOT = Path(__file__).resolve().parents[2]
FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
BSP_VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
FLASH_SIZE_RE = re.compile(r"([1-9][0-9]*)([KMG])B?", re.IGNORECASE)
ARDUINO_PROFILE_CHIP_VARIANTS = {
    "rev1_3": "prev3",
    "rev3_x": "postv3",
}
REQUIRED_ARDUINO_SELECTIONS = {
    "PSRAM": "enabled",
    "FlashSize": "32M",
    "FlashMode": "qio",
    "FlashFreq": "80",
    "PartitionScheme": "app13M_data7M_32MB",
    "USBMode": "hwcdc",
    "CDCOnBoot": "cdc",
    "UploadMode": "default",
    "UploadSpeed": "921600",
}
EXPECTED_SCREEN_DEFINES = {
    "3_4c": "CURRENT_SCREEN=SCREEN_3INCH_4_DSI",
    "4c": "CURRENT_SCREEN=SCREEN_4INCH_DSI",
}
FORBIDDEN_FLASH_TOKEN_RE = re.compile(
    r"(?i)(?:^|[^a-z0-9])(?:erase(?:[_-](?:flash|region))?|esp32c6)(?:$|[^a-z0-9])"
)
PRIVATE_PUBLIC_TEXT_RE = re.compile(
    r"(?i)(?:/(?:home|tmp|var/tmp|private/tmp|users)/|[a-z]:[\\/]|\\\\[^\\\s]+\\|"
    r"(?:^|[/\\])[^/\\\s]*(?:cache|workdir|workspace)[^/\\\s]*(?:[/\\]|$))"
)
POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![:A-Za-z0-9_.-])/(?:[^/\s'\"<>]+/)+[^/\s'\"<>]*")
FORBIDDEN_PUBLIC_IMAGE_TEXT_RE = re.compile(
    r"(?i)(?:[a-z0-9_.-]*\.merged\.bin|(?:^|[/\\\s'\"])(?:merged\.bin|whole[-_]?flash\.bin)(?:$|[/\\\s'\"]))"
)
SDKCONFIG_NOT_SET_RE = re.compile(r"^# (CONFIG_[A-Z0-9_]+) is not set$")


def validate_full_sha(value: str, label: str) -> str:
    normalized = value.lower()
    if not FULL_SHA_RE.fullmatch(normalized):
        raise PackageError(f"{label} must be a full hexadecimal SHA")
    return normalized


def validate_bsp_version(value: str) -> str:
    if not BSP_VERSION_RE.fullmatch(value):
        raise PackageError("BSP version must be a stable semantic version")
    return value


def unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PackageError(f"generated JSON contains a duplicate key: {key!r}")
        result[key] = value
    return result


def parse_flash_size(value: str) -> int:
    match = FLASH_SIZE_RE.fullmatch(value)
    if not match:
        raise PackageError(f"invalid generated flash size: {value!r}")
    scale = {"K": 1024, "M": 1024**2, "G": 1024**3}[match.group(2).upper()]
    return int(match.group(1)) * scale


def parse_fqbn_selections(
    value: str, profile_id: str | None = None
) -> dict[str, str]:
    prefix, separator, raw_options = value.partition(":esp32p4:")
    if prefix != "esp32:esp32" or not separator or not raw_options:
        raise PackageError("generated Arduino FQBN is not an esp32p4 FQBN")
    selections: dict[str, str] = {}
    for item in raw_options.split(","):
        key, separator, option_value = item.partition("=")
        if not separator or not key or not option_value or key in selections:
            raise PackageError("generated Arduino FQBN has invalid or duplicate selections")
        selections[key] = option_value
    if selections.get("ChipVariant") not in set(ARDUINO_PROFILE_CHIP_VARIANTS.values()):
        raise PackageError("generated Arduino FQBN must select a supported ChipVariant")
    for key, required in REQUIRED_ARDUINO_SELECTIONS.items():
        if selections.get(key) != required:
            raise PackageError(f"generated Arduino FQBN must select {key}={required}")
    if set(selections) != {"ChipVariant", *REQUIRED_ARDUINO_SELECTIONS}:
        raise PackageError("generated Arduino FQBN contains unsupported extra selections")
    if profile_id:
        expected_chip_variant = ARDUINO_PROFILE_CHIP_VARIANTS.get(profile_id)
        if not expected_chip_variant:
            raise PackageError(f"unsupported Arduino silicon profile: {profile_id}")
        if selections["ChipVariant"] != expected_chip_variant:
            raise PackageError(
                f"generated Arduino FQBN must select ChipVariant={expected_chip_variant} "
                f"for {profile_id}"
            )
    return selections


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
        key
        for key, value in values.items()
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


def parse_build_options(
    path: Path,
    profile_id: str,
    expected_fqbn: str,
    expected_framework_version: str,
) -> dict[str, object]:
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=unique_json_object
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(f"generated Arduino build.options.json is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise PackageError("generated Arduino build.options.json must be an object")
    if expected_framework_version != ARDUINO_CORE_VERSION:
        raise PackageError(f"Arduino artifacts require Arduino-ESP32 {ARDUINO_CORE_VERSION}")
    actual_fqbn = data.get("fqbn")
    if not isinstance(actual_fqbn, str) or actual_fqbn != expected_fqbn:
        raise PackageError("generated Arduino FQBN does not match the requested FQBN")
    parse_fqbn_selections(actual_fqbn, profile_id)
    raw_hardware_folders = data.get("hardwareFolders")
    if not isinstance(raw_hardware_folders, str) or not raw_hardware_folders:
        raise PackageError("generated Arduino options do not identify the installed core")
    hardware_folders = [item.strip().replace("\\", "/") for item in raw_hardware_folders.split(",")]
    if not hardware_folders or any(
        not item.endswith(f"/esp32/hardware/esp32/{ARDUINO_CORE_VERSION}")
        for item in hardware_folders
    ):
        raise PackageError(f"generated Arduino build did not use Arduino-ESP32 {ARDUINO_CORE_VERSION}")
    return data


def safe_relative(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    windows_path = PureWindowsPath(value)
    if (
        not value
        or any(ord(character) < 32 for character in value)
        or any(character in value for character in ':&|<>^%!()')
        or path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in path.parts
        or path == PurePosixPath(".")
        or normalized != path.as_posix()
    ):
        raise PackageError(f"unsafe generated file path: {value!r}")
    return path


def path_key(path: PurePosixPath) -> str:
    """Return a cross-platform collision key for a safe artifact path."""
    return path.as_posix().casefold()


def is_forbidden_published_image(value: str | PurePosixPath) -> bool:
    name = PurePosixPath(str(value).replace("\\", "/")).name.casefold()
    return (
        name == "merged.bin"
        or name.endswith(".merged.bin")
        or name in {"whole-flash.bin", "whole_flash.bin", "wholeflash.bin"}
    )


def offset(value: str) -> int:
    try:
        result = int(value, 0)
    except ValueError as exc:
        raise PackageError(f"invalid flash offset: {value!r}") from exc
    if result < 0:
        raise PackageError(f"invalid flash offset: {value!r}")
    return result


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def external_file_identity(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    if not payload:
        raise PackageError(f"generated build input is empty: {path.name}")
    return {"basename": path.name, "size": len(payload), "sha256": digest_bytes(payload)}


def git_output(source_root: Path, arguments: list[str], label: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source_root), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise PackageError(f"unable to validate Arduino source Git identity: {label}") from exc
    if result.returncode:
        raise PackageError(f"unable to validate Arduino source Git identity: {label}")
    return result.stdout.strip()


def git_blob(source_root: Path, object_name: str, label: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(source_root), "show", object_name],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise PackageError(f"unable to validate Arduino source Git identity: {label}") from exc
    if result.returncode:
        raise PackageError(f"unable to validate Arduino source Git identity: {label}")
    return result.stdout


def validate_source_root(path: Path, expected_sha: str) -> Path:
    if path.is_symlink():
        raise PackageError("Arduino source root must not be a symlink")
    root = path.resolve()
    if not root.is_dir():
        raise PackageError("Arduino source root is missing")
    if root != TRUSTED_REPO_ROOT:
        raise PackageError(
            "Arduino source root does not match the packaging script's trusted repository root"
        )
    top_level = Path(git_output(root, ["rev-parse", "--show-toplevel"], "top level")).resolve()
    if top_level != root:
        raise PackageError("Arduino source root must be the Git worktree root")
    head = git_output(root, ["rev-parse", "HEAD"], "HEAD").lower()
    if head != expected_sha:
        raise PackageError("Arduino source root HEAD does not match the product Git SHA")
    if git_output(root, ["status", "--porcelain=v1", "--untracked-files=all"], "status"):
        raise PackageError("Arduino source root must be clean for exact-SHA packaging")
    return root


def resolved_regular_child(root: Path, relative: PurePosixPath, label: str) -> Path:
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise PackageError(f"{label} must not be a symlink")
    resolved = root.joinpath(*relative.parts).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PackageError(f"{label} escapes its declared root") from exc
    if not resolved.is_file():
        raise PackageError(f"{label} is missing")
    return resolved


def resolve_compile_path(value: str, directory: Path, label: str) -> Path:
    if not value or any(ord(character) < 32 for character in value):
        raise PackageError(f"Arduino compile_commands {label} is invalid")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = directory / candidate
    return candidate.resolve()


def parse_compile_identity(
    build: Path,
    sketch: str,
    expected_screen_define: str,
    expected_fqbn: str,
    expected_source_location: Path,
) -> dict[str, object]:
    compile_commands_path = build / "compile_commands.json"
    if compile_commands_path.is_symlink() or not compile_commands_path.is_file():
        raise PackageError("generated Arduino compile_commands.json is missing or unsafe")
    try:
        entries = json.loads(
            compile_commands_path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_json_object,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"generated Arduino compile_commands.json is invalid: {exc}") from exc
    if not isinstance(entries, list) or not entries:
        raise PackageError("generated Arduino compile_commands.json must be a non-empty array")
    translation_relative = PurePosixPath("sketch", f"{sketch}.ino.cpp")
    object_relative = PurePosixPath("sketch", f"{sketch}.ino.cpp.o")
    translation_unit = resolved_regular_child(
        build, translation_relative, "generated Arduino sketch translation unit"
    )
    object_file = resolved_regular_child(
        build, object_relative, "generated Arduino sketch object"
    )
    matching_entries: list[tuple[dict[str, object], Path]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise PackageError("generated Arduino compile_commands entry must be an object")
        directory_value = entry.get("directory")
        file_value = entry.get("file")
        if not isinstance(directory_value, str) or not isinstance(file_value, str):
            raise PackageError("generated Arduino compile_commands entry lacks directory/file")
        directory = Path(directory_value).resolve()
        if resolve_compile_path(file_value, directory, "file") == translation_unit:
            matching_entries.append((entry, directory))
    if len(matching_entries) != 1:
        raise PackageError("generated Arduino compile_commands must contain one sketch entry")
    entry, directory = matching_entries[0]
    arguments = entry.get("arguments")
    if (
        not isinstance(arguments, list)
        or not arguments
        or not all(isinstance(argument, str) and argument for argument in arguments)
    ):
        raise PackageError("generated Arduino sketch compile entry must use an argument array")
    output_indexes = [index for index, argument in enumerate(arguments) if argument == "-o"]
    if len(output_indexes) != 1 or output_indexes[0] + 1 >= len(arguments):
        raise PackageError("generated Arduino sketch compile entry has no unique object output")
    output_path = resolve_compile_path(
        arguments[output_indexes[0] + 1], directory, "object output"
    )
    if output_path != object_file:
        raise PackageError("generated Arduino sketch compile object does not match the build path")
    source_arguments = [
        argument
        for argument in arguments
        if not argument.startswith("-")
        and resolve_compile_path(argument, directory, "source argument") == translation_unit
    ]
    if len(source_arguments) != 1:
        raise PackageError("generated Arduino sketch compile entry has no unique translation input")
    screen_arguments = [
        argument[2:]
        for argument in arguments
        if argument.startswith("-DCURRENT_SCREEN=")
    ]
    if screen_arguments != [expected_screen_define]:
        raise PackageError("generated Arduino sketch compile screen identity is inconsistent")
    required_compile_definitions = (
        f'-DARDUINO_FQBN="{expected_fqbn}"',
        "-DARDUINO_USB_MODE=1",
        "-DARDUINO_USB_CDC_ON_BOOT=1",
    )
    if any(arguments.count(definition) != 1 for definition in required_compile_definitions):
        raise PackageError("generated Arduino sketch compile FQBN/USB identity is inconsistent")
    source_include_arguments = [
        argument
        for argument in arguments
        if argument.startswith("-I")
        and len(argument) > 2
        and resolve_compile_path(argument[2:], directory, "source include")
        == expected_source_location
    ]
    if len(source_include_arguments) != 1:
        raise PackageError("generated Arduino sketch compile source identity is inconsistent")
    return {
        "compile_commands": external_file_identity(compile_commands_path),
        "translation_unit": external_file_identity(translation_unit),
        "object": external_file_identity(object_file),
        "compile_arguments_sha256": digest_bytes(
            json.dumps(arguments, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ),
    }


def arduino_build_identity(
    *,
    build: Path,
    source_root_path: Path,
    build_options: dict[str, object],
    product_sha: str,
    project: str,
    sketch: str,
    fqbn: str,
    variant_id: str,
    plan: list[tuple[int, PurePosixPath]],
    flash_files: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    source_root = validate_source_root(source_root_path, product_sha)
    project_path = safe_relative(project)
    sketch_path = safe_relative(sketch)
    if len(sketch_path.parts) != 1 or sketch_path.suffix:
        raise PackageError("Arduino sketch identity must be one directory name without a suffix")
    expected_location = source_root.joinpath(*project_path.parts)
    raw_location = build_options.get("sketchLocation")
    if not isinstance(raw_location, str) or not raw_location or not Path(raw_location).is_absolute():
        raise PackageError("generated Arduino build options lack an absolute sketchLocation")
    actual_location = Path(raw_location).resolve()
    if actual_location != expected_location.resolve():
        raise PackageError("generated Arduino sketchLocation does not match --project")
    try:
        actual_project = actual_location.relative_to(source_root).as_posix()
    except ValueError as exc:
        raise PackageError("generated Arduino sketchLocation escapes the source root") from exc
    if actual_project != project_path.as_posix() or actual_location.name != sketch:
        raise PackageError("generated Arduino project/sketch identity is inconsistent")
    primary_relative = PurePosixPath(*project_path.parts, f"{sketch}.ino")
    primary_source = resolved_regular_child(
        source_root, primary_relative, "tracked Arduino primary sketch"
    )
    tracked = git_output(
        source_root,
        ["ls-files", "--error-unmatch", "--", primary_relative.as_posix()],
        "tracked primary sketch",
    )
    if tracked != primary_relative.as_posix():
        raise PackageError("Arduino primary sketch is not uniquely tracked at product HEAD")
    if git_blob(
        source_root,
        f"{product_sha}:{primary_relative.as_posix()}",
        "primary sketch blob",
    ) != primary_source.read_bytes():
        raise PackageError("Arduino primary sketch bytes do not match product HEAD")
    expected_screen_define = EXPECTED_SCREEN_DEFINES.get(variant_id)
    if not expected_screen_define:
        raise PackageError("Arduino variant has no supported compile identity")
    custom_properties = build_options.get("customBuildProperties")
    if not isinstance(custom_properties, str):
        raise PackageError("generated Arduino build options lack customBuildProperties")
    property_screen_defines = re.findall(
        r"(?<!\S)-D(CURRENT_SCREEN=[A-Za-z0-9_]+)(?!\S)", custom_properties
    )
    if property_screen_defines != [expected_screen_define]:
        raise PackageError("generated Arduino build options screen identity is inconsistent")
    compile_identity = parse_compile_identity(
        build, sketch, expected_screen_define, fqbn, actual_location
    )
    expected_application = PurePosixPath(f"{sketch}.ino.bin")
    application_matches = [
        (entry, metadata)
        for entry, metadata in zip(plan, flash_files)
        if entry[1] == expected_application
    ]
    if len(application_matches) != 1:
        raise PackageError("generated Arduino flash_args must name one sketch application output")
    (application_offset, application_source), application_segment = application_matches[0]
    primary_identity = external_file_identity(primary_source)
    primary_identity["path"] = primary_relative.as_posix()
    application_identity = {
        "source_basename": application_source.name,
        "path": application_segment["path"],
        "offset": application_offset,
        "size": application_segment["size"],
        "sha256": application_segment["sha256"],
    }
    identity = {
        "product_git_sha": product_sha,
        "project": actual_project,
        "sketch": sketch,
        "fqbn": fqbn,
        "screen_define": expected_screen_define,
        "primary_source": primary_identity,
        "translation_unit": compile_identity["translation_unit"],
        "object": compile_identity["object"],
        "compile_arguments_sha256": compile_identity["compile_arguments_sha256"],
        "application": application_identity,
    }
    return identity, compile_identity["compile_commands"]


def contains_private_public_text(text: str) -> bool:
    without_allowed_shebang = text.replace("/usr/bin/env", "")
    return bool(
        PRIVATE_PUBLIC_TEXT_RE.search(text)
        or POSIX_ABSOLUTE_PATH_RE.search(without_allowed_shebang)
    )


def reject_private_public_text(output: Path) -> None:
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        if path.suffix.casefold() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise PackageError(f"public metadata is not UTF-8 text: {path.name}") from exc
        if contains_private_public_text(text):
            raise PackageError(f"public metadata contains a private build path: {path.name}")
        if FORBIDDEN_PUBLIC_IMAGE_TEXT_RE.search(text):
            raise PackageError(f"public metadata references a merged or whole-flash image: {path.name}")


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
    unresolved_input = build_root.joinpath(*source.parts)
    cursor = build_root
    for part in source.parts:
        cursor /= part
        if cursor.is_symlink():
            raise PackageError(f"unsafe generated file path: {source.as_posix()!r}")
    input_path = unresolved_input.resolve()
    try:
        input_path.relative_to(build_root)
    except ValueError as exc:
        raise PackageError(f"unsafe generated file path: {source.as_posix()!r}") from exc
    if not input_path.is_file():
        raise PackageError(f"generated file is missing: {source.as_posix()}")
    destination = output / "bin" / Path(*source.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_path, destination)
    size = destination.stat().st_size
    if size <= 0:
        raise PackageError(f"generated flash file is empty: {source.as_posix()}")
    return {
        "path": (Path("bin") / Path(*source.parts)).as_posix(),
        "size": size,
        "sha256": digest(destination),
    }


def parse_idf_flasher_args(raw: str) -> tuple[list[tuple[int, PurePosixPath]], dict[str, object], str]:
    try:
        data = json.loads(raw, object_pairs_hook=unique_json_object)
        files = data["flash_files"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise PackageError(f"invalid ESP-IDF flasher_args.json: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(files, dict) or not files:
        raise PackageError("flasher_args.json has no flash_files")
    reject_forbidden_flash_values(data)
    entries: list[tuple[int, PurePosixPath]] = []
    seen_offsets: set[int] = set()
    seen_paths: set[str] = set()
    for raw_offset, raw_path in files.items():
        current = offset(str(raw_offset))
        if current in seen_offsets or not isinstance(raw_path, str):
            raise PackageError("duplicate offset or invalid flash file in flasher_args.json")
        relative = safe_relative(raw_path)
        key = path_key(relative)
        if key in seen_paths:
            raise PackageError("duplicate flash file path in flasher_args.json")
        if is_forbidden_published_image(relative):
            raise PackageError("generated flash plan references a merged or whole-flash image")
        seen_offsets.add(current)
        seen_paths.add(key)
        entries.append((current, relative))
    settings = data.get("flash_settings", {})
    if not isinstance(settings, dict):
        raise PackageError("flasher_args.json flash_settings must be an object")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return sorted(entries), settings, canonical


def idf_plan(build: Path) -> tuple[list[tuple[int, PurePosixPath]], dict[str, object], list[str]]:
    try:
        raw = (build / "flasher_args.json").read_text(encoding="utf-8")
    except OSError as exc:
        raise PackageError(f"invalid ESP-IDF flasher_args.json: {exc}") from exc
    entries, settings, canonical = parse_idf_flasher_args(raw)
    return entries, settings, [canonical]


def parse_arduino_flash_args(raw: str) -> tuple[list[tuple[int, PurePosixPath]], dict[str, object], str]:
    try:
        tokens = shlex.split(raw.strip())
    except ValueError as exc:
        raise PackageError(f"invalid Arduino flash_args: {exc}") from exc
    if any("erase" in token.lower() or "c6" in token.lower() for token in tokens):
        raise PackageError("Arduino flash_args must not contain erase or C6")
    command_indexes = [
        index for index, token in enumerate(tokens) if token in {"write_flash", "write-flash"}
    ]
    if len(command_indexes) > 1:
        raise PackageError("Arduino flash_args must contain at most one write_flash command")
    if command_indexes:
        command_index = command_indexes[0]
        prefix = tokens[:command_index]
        if not prefix:
            pass
        elif prefix == ["esptool.py", "--chip", "esp32p4"]:
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
        "--flash-mode": "--flash-mode",
        "--flash_mode": "--flash-mode",
        "--flash-freq": "--flash-freq",
        "--flash_freq": "--flash-freq",
        "--flash-size": "--flash-size",
        "--flash_size": "--flash-size",
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
        if any(ord(character) < 32 for character in value):
            raise PackageError("Arduino flash_args has an unsafe flash option value")
        if normalized_option == "--flash-mode" and not re.fullmatch(r"[A-Za-z0-9]+", value):
            raise PackageError("Arduino flash_args has an invalid flash mode")
        if normalized_option == "--flash-freq" and not re.fullmatch(r"[1-9][0-9]*[KkMm]?", value):
            raise PackageError("Arduino flash_args has an invalid flash frequency")
        if normalized_option == "--flash-size":
            parse_flash_size(value)
        seen_options.add(normalized_option)
        options.extend((normalized_option, value))
    if not tail or len(tail) % 2:
        raise PackageError("Arduino flash_args has incomplete offset/file pairs")
    entries: list[tuple[int, PurePosixPath]] = []
    seen_offsets: set[int] = set()
    seen_paths: set[str] = set()
    for raw_offset, raw_path in zip(tail[::2], tail[1::2]):
        current = offset(raw_offset)
        if current in seen_offsets:
            raise PackageError("Arduino flash_args has duplicate offsets")
        relative = safe_relative(raw_path)
        key = path_key(relative)
        if key in seen_paths:
            raise PackageError("Arduino flash_args has duplicate file paths")
        if is_forbidden_published_image(relative):
            raise PackageError("Arduino flash_args references a merged or whole-flash image")
        seen_offsets.add(current)
        seen_paths.add(key)
        entries.append((current, relative))
    entries.sort()
    if len(entries) == 1 and entries[0][0] == 0:
        raise PackageError("Arduino flash_args must not describe a single whole-flash image at offset 0x0")
    normalized_parts = options + [
        item
        for entry in entries
        for item in (f"0x{entry[0]:x}", entry[1].as_posix())
    ]
    normalized = "write_flash " + shlex.join(normalized_parts)
    return entries, {"esptool_options": options}, normalized


def arduino_plan(build: Path) -> tuple[list[tuple[int, PurePosixPath]], dict[str, object], list[str]]:
    try:
        raw = (build / "flash_args").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PackageError(f"invalid Arduino flash_args: {exc}") from exc
    entries, settings, normalized = parse_arduino_flash_args(raw)
    return entries, settings, [raw, normalized]


def esptool_options(settings: dict[str, object]) -> list[str]:
    options = settings.get("esptool_options", [])
    if options and isinstance(options, list) and all(isinstance(item, str) for item in options):
        return list(options)
    options = []
    for key in ("flash_mode", "flash_freq", "flash_size"):
        value = settings.get(key)
        if isinstance(value, str) and value:
            options.extend((f"--{key}", value))
    return options


def arduino_flash_capacity(settings: dict[str, object], fqbn: str) -> int:
    options = esptool_options(settings)
    if len(options) != 6 or set(options[::2]) != {"--flash-mode", "--flash-freq", "--flash-size"}:
        raise PackageError("Arduino flash_args must declare mode, frequency, and size exactly once")
    option_size = options[options.index("--flash-size") + 1]
    plan_capacity = parse_flash_size(option_size)
    fqbn_capacity = parse_flash_size(parse_fqbn_selections(fqbn)["FlashSize"])
    if plan_capacity != fqbn_capacity:
        raise PackageError("Arduino flash_args and generated FQBN disagree on flash size")
    if plan_capacity != FLASH_CAPACITY:
        raise PackageError("Arduino artifact must use the generated 32 MiB flash configuration")
    return plan_capacity


def flash_helper_contents(
    target: str,
    baud: str,
    files: list[dict[str, object]],
    settings: dict[str, object],
) -> tuple[str, str, str]:
    if target != "esp32p4":
        raise PackageError("only esp32p4 flash helpers are permitted")
    common = ["python", "-m", "esptool", "--chip", target]
    tail = ["write_flash", *esptool_options(settings)]
    for item in files:
        tail.extend((f"0x{int(item['offset']):x}", str(item["path"])))
    portable = shlex.join([*common, "--port", "PORT", "--baud", baud, *tail])
    posix_command = shlex.join(
        [*common, "--port", "__PORT__", "--baud", "__BAUD__", *tail]
    ).replace("__PORT__", '"$port"').replace("__BAUD__", '"$baud"')
    shell = (
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        "port=${1:?usage: flash.sh PORT [BAUD]}\n"
        f"baud=${{2:-{baud}}}\n"
        f"{posix_command}\n"
    )
    windows_command = subprocess.list2cmdline(
        [*common, "--port", "%PORT%", "--baud", "%BAUD%", *tail]
    )
    batch = (
        "@echo off\r\n"
        "set PORT=%~1\r\n"
        'if "%PORT%"=="" (echo Usage: flash.bat PORT [BAUD] & exit /b 2)\r\n'
        "set BAUD=%~2\r\n"
        f'if "%BAUD%"=="" set BAUD={baud}\r\n'
        f"{windows_command}\r\n"
    )
    return portable, shell, batch


def write_helpers(
    output: Path,
    target: str,
    baud: str,
    files: list[dict[str, object]],
    settings: dict[str, object],
) -> str:
    command, shell, batch = flash_helper_contents(target, baud, files, settings)
    (output / "flash.sh").write_text(shell, encoding="utf-8")
    (output / "flash.sh").chmod(0o755)
    (output / "flash.bat").write_text(batch, encoding="utf-8")
    return command


def create_deterministic_zip(source: Path, destination: Path) -> None:
    """Archive a validated directory without timestamps, symlinks, or extra roots."""
    if destination.exists():
        raise PackageError(f"ZIP output already exists: {destination}")
    try:
        destination.relative_to(source)
    except ValueError:
        pass
    else:
        raise PackageError("ZIP output must not be inside the artifact directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        destination,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            if path.is_symlink():
                raise PackageError("artifact directory contains a symlink")
            relative = safe_relative(path.relative_to(source).as_posix()).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o755 if relative == "flash.sh" else 0o644
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits |= 0x800
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def validate_flash_ranges(
    files: list[dict[str, object]], mode: str, flash_capacity: int
) -> int:
    for item in files:
        current_offset = int(item["offset"])
        current_size = int(item["size"])
        if current_offset >= flash_capacity or current_offset + current_size > flash_capacity:
            raise PackageError("flash file exceeds 32 MiB capacity")
    for previous, current in zip(files, files[1:]):
        if int(previous["offset"]) + int(previous["size"]) > int(current["offset"]):
            raise PackageError("flash files overlap")
    total = sum(int(item["size"]) for item in files)
    if mode == "arduino" and total >= ARDUINO_SEGMENT_BYTES_LIMIT:
        raise PackageError("Arduino flash segment bytes must remain below the 16 MiB safety ceiling")
    return total


def bind_segment(item: dict[str, object], args: argparse.Namespace) -> None:
    item.update(
        {
            "target": args.target,
            "fqbn": args.fqbn if args.mode == "arduino" else None,
            "product_git_sha": args.git_sha,
            "bsp_git_sha": args.bsp_sha,
            "bsp_source_tree": args.bsp_source_tree,
            "bsp_component_tree": args.bsp_component_tree,
            "bsp_version": args.bsp_version,
            "bsp_linked": False if args.mode == "arduino" else None,
        }
    )


def package(args: argparse.Namespace) -> None:
    if args.build_dir.is_symlink() or args.output_dir.is_symlink():
        raise PackageError("build and output directories must not be symlinks")
    build, output = args.build_dir.resolve(), args.output_dir.resolve()
    if not build.is_dir():
        raise PackageError(f"build directory is missing: {build}")
    try:
        output.relative_to(build)
    except ValueError:
        pass
    else:
        raise PackageError("output directory must not be inside the build directory")
    if output.exists() and any(output.iterdir()):
        raise PackageError(f"output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    if args.mode == "esp-idf":
        parse_sdkconfig(Path(args.sdkconfig), args.profile_id, args.artifact_kind)
        plan, settings, original = idf_plan(build)
        flash_capacity = FLASH_CAPACITY
        if (
            args.artifact_kind == "maintained-firmware"
            and str(settings.get("flash_size", "")).upper() != "32MB"
        ):
            raise PackageError("maintained firmware flasher settings must select 32MB flash")
    else:
        raw_build_options_path = Path(args.build_options)
        if raw_build_options_path.is_symlink():
            raise PackageError("Arduino build options must not be a symlink")
        build_options_path = raw_build_options_path.resolve()
        if build_options_path != build / "build.options.json":
            raise PackageError("Arduino build options must be the generated build-path build.options.json")
        build_options_data = parse_build_options(
            build_options_path,
            args.profile_id,
            args.fqbn,
            args.framework_version,
        )
        plan, settings, original = arduino_plan(build)
        flash_capacity = arduino_flash_capacity(settings, args.fqbn)
        build_inputs = {
            "build_options": external_file_identity(build_options_path),
            "flash_args": external_file_identity(build / "flash_args"),
        }
    flash_files: list[dict[str, object]] = []
    for flash_offset, relative in plan:
        item = stage(build, output, relative)
        item["offset"] = flash_offset
        bind_segment(item, args)
        flash_files.append(item)
    total_segment_bytes = validate_flash_ranges(flash_files, args.mode, flash_capacity)
    if args.mode == "arduino":
        build_identity, compile_commands_identity = arduino_build_identity(
            build=build,
            source_root_path=Path(args.source_root),
            build_options=build_options_data,
            product_sha=args.git_sha,
            project=args.project,
            sketch=args.sketch,
            fqbn=args.fqbn,
            variant_id=args.variant_id,
            plan=plan,
            flash_files=flash_files,
        )
        build_inputs["compile_commands"] = compile_commands_identity
    extra: list[dict[str, object]] = []
    debug_candidates = (
        sorted(build.glob("*.elf")) + sorted(build.glob("*.map")) + [build / "sdkconfig"]
        if args.mode == "esp-idf"
        else []
    )
    for candidate in debug_candidates:
        if candidate.is_file():
            rel = safe_relative(candidate.relative_to(build).as_posix())
            extra.append(stage(build, output, rel))
    merged_meta = None
    if args.mode == "esp-idf":
        merged_candidates = sorted(
            candidate for candidate in build.glob("*.merged.bin") if candidate.is_file()
        )
        if (build / "merged.bin").is_file():
            merged_candidates.append(build / "merged.bin")
        merged_candidates.sort()
        if len(merged_candidates) > 1:
            raise PackageError("ambiguous merged image candidates")
        if merged_candidates:
            merged_meta = stage(
                build,
                output,
                safe_relative(merged_candidates[0].relative_to(build).as_posix()),
            )
    args_name = "flasher_args.json" if args.mode == "esp-idf" else "flash_args"
    normalized_args = original[0] if args.mode == "esp-idf" else original[1]
    (output / args_name).write_text(normalized_args + "\n", encoding="utf-8")
    flash_args_path = output / args_name
    flash_args_metadata = {
        "path": args_name,
        "size": flash_args_path.stat().st_size,
        "sha256": digest(flash_args_path),
    }
    command = write_helpers(output, args.target, str(args.baud), flash_files, settings)
    bsp_linked = False if args.mode == "arduino" else None
    bsp_relationship = "reference-only" if args.mode == "arduino" else "not-declared"
    manifest: dict[str, object] = {
        "schema": 3,
        "artifact_kind": args.artifact_kind,
        "source_type": args.mode,
        "product_variant": args.variant,
        "product_variant_id": args.variant_id,
        "product_label": args.product_label,
        "resolution": args.resolution,
        "scope": args.scope,
        "framework": {
            "name": "ESP-IDF" if args.mode == "esp-idf" else "Arduino-ESP32",
            "version": args.framework_version,
        },
        "target": args.target,
        "project": args.project,
        "sketch": args.sketch if args.mode == "arduino" else None,
        "configuration": args.configuration,
        "profile_id": args.profile_id,
        "profile_compatibility": (
            "ESP32-P4 silicon revision < 3.0"
            if args.profile_id == "rev1_3"
            else "ESP32-P4 silicon revision >= 3.0"
        ),
        "flash_capacity_bytes": flash_capacity,
        "flash_size": "32MiB",
        "flash_size_bytes": flash_capacity,
        "segment_count": len(flash_files),
        "total_segment_bytes": total_segment_bytes,
        "segmented_payload_total": total_segment_bytes,
        "git_sha": args.git_sha,
        "product_git_sha": args.git_sha,
        "bsp_git_sha": args.bsp_sha,
        "bsp_source_tree": args.bsp_source_tree,
        "bsp_component_tree": args.bsp_component_tree,
        "bsp_version": args.bsp_version,
        "bsp_linked": bsp_linked,
        "bsp_relationship": bsp_relationship,
        "bsp": {
            "source_sha": args.bsp_sha,
            "source_tree": args.bsp_source_tree,
            "component_tree": args.bsp_component_tree,
            "version": args.bsp_version,
            "linked": bsp_linked,
            "relationship": bsp_relationship,
        },
        "baud": int(args.baud),
        "fqbn": args.fqbn if args.mode == "arduino" else None,
        "flash_settings": settings,
        "flash_args": flash_args_metadata,
        "files": flash_files,
        "debug_files": extra,
        "portable_flash_command": command,
    }
    if args.mode == "arduino":
        manifest["build_inputs"] = build_inputs
        manifest["build_identity"] = build_identity
    if args.mode == "esp-idf":
        manifest["original_flash_args"] = original
        manifest["merged_image"] = merged_meta
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checks = [
        (path, digest(path))
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{value}  {path.relative_to(output).as_posix()}\n"
            for path, value in checks
        ),
        encoding="utf-8",
    )
    if args.mode == "arduino":
        reject_private_public_text(output)
    if args.zip_output:
        create_deterministic_zip(output, args.zip_output.resolve())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("esp-idf", "arduino"))
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--product-label", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--variant-id", required=True)
    parser.add_argument("--resolution", required=True)
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--framework-version", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--bsp-sha")
    parser.add_argument("--bsp-source-tree", "--bsp-tree", dest="bsp_source_tree")
    parser.add_argument(
        "--bsp-component-tree", "--bsp-content-hash", dest="bsp_component_tree"
    )
    parser.add_argument("--bsp-version")
    parser.add_argument("--zip-output", type=Path)
    parser.add_argument("--profile-id", required=True, choices=sorted(PROFILES))
    parser.add_argument(
        "--artifact-kind", choices=("ci-example", "maintained-firmware"), default="ci-example"
    )
    parser.add_argument("--sdkconfig")
    parser.add_argument("--build-options")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--baud", default="921600")
    parser.add_argument("--scope", default="first-party example")
    parser.add_argument("--fqbn")
    parser.add_argument("--sketch")
    args = parser.parse_args()
    try:
        args.git_sha = validate_full_sha(args.git_sha, "product git SHA")
        bsp_values = (args.bsp_sha, args.bsp_source_tree, args.bsp_component_tree, args.bsp_version)
        if any(bsp_values) and not all(bsp_values):
            raise PackageError(
                "BSP source SHA, source tree, component tree, and version must be provided together"
            )
        if args.bsp_sha:
            args.bsp_sha = validate_full_sha(args.bsp_sha, "BSP git SHA")
            args.bsp_source_tree = validate_full_sha(args.bsp_source_tree, "BSP source tree")
            args.bsp_component_tree = validate_full_sha(
                args.bsp_component_tree, "BSP component tree"
            )
            args.bsp_version = validate_bsp_version(args.bsp_version)
        if args.target != "esp32p4":
            raise PackageError("only esp32p4 packages are permitted")
        safe_relative(args.project)
        if args.sketch:
            safe_relative(args.sketch)
        if args.mode == "arduino" and (
            args.profile_id != "rev3_x"
            or not args.fqbn
            or not args.sketch
            or not args.build_options
            or not args.source_root
            or not args.bsp_sha
            or not args.bsp_source_tree
            or not args.bsp_component_tree
            or not args.bsp_version
        ):
            raise PackageError(
                "Arduino artifacts require rev3_x ChipVariant=postv3 FQBN, sketch, source root, build options, and BSP reference pins"
            )
        if args.mode == "esp-idf" and not args.sdkconfig:
            raise PackageError("ESP-IDF artifacts require generated sdkconfig")
        if not args.baud.isdigit() or int(args.baud) <= 0:
            raise PackageError("baud must be a positive integer")
        package(args)
        return 0
    except (PackageError, OSError) as exc:
        print(f"artifact packaging failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
