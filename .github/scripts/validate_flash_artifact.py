#!/usr/bin/env python3
"""Fail-closed validation for packaged flash-artifact directories and ZIP files."""
from __future__ import annotations

import argparse
import json
import re
import stat
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True
import package_build_artifact as package_lib


class ValidationError(RuntimeError):
    pass


SUM_RE = re.compile(r"([0-9a-f]{64})  (.+)")
ZIP_UNCOMPRESSED_LIMIT = 128 * 1024 * 1024


@dataclass(frozen=True)
class ArtifactContents:
    label: str
    files: dict[str, bytes]
    modes: dict[str, int]


def safe_artifact_path(value: str) -> PurePosixPath:
    try:
        return package_lib.safe_relative(value)
    except package_lib.PackageError as exc:
        raise ValidationError(str(exc)) from exc


def add_unique_path(seen: set[str], value: str) -> str:
    path = safe_artifact_path(value)
    key = package_lib.path_key(path)
    if key in seen:
        raise ValidationError(f"duplicate or case-colliding artifact path: {value!r}")
    seen.add(key)
    return path.as_posix()


def read_directory(root: Path) -> ArtifactContents:
    if root.is_symlink() or not root.is_dir():
        raise ValidationError(f"artifact directory is missing or unsafe: {root}")
    files: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    seen: set[str] = set()
    for item in sorted(root.rglob("*")):
        if item.is_symlink():
            raise ValidationError(f"artifact directory contains a symlink: {item}")
        item_mode = item.lstat().st_mode
        if stat.S_ISDIR(item_mode):
            continue
        if not stat.S_ISREG(item_mode):
            raise ValidationError(f"artifact directory contains a special file: {item}")
        relative = add_unique_path(seen, item.relative_to(root).as_posix())
        files[relative] = item.read_bytes()
        modes[relative] = stat.S_IMODE(item_mode)
    return ArtifactContents(str(root), files, modes)


def read_zip(path: Path) -> ArtifactContents:
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"artifact ZIP is missing or unsafe: {path}")
    files: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    seen: set[str] = set()
    total_size = 0
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.flag_bits & 0x1:
                    raise ValidationError(f"encrypted ZIP member is forbidden: {info.filename!r}")
                if "\\" in info.filename:
                    raise ValidationError(f"ZIP member must use POSIX separators: {info.filename!r}")
                raw_name = info.filename[:-1] if info.is_dir() else info.filename
                relative = add_unique_path(seen, raw_name)
                relative_key = relative.casefold()
                if any(
                    existing.startswith(relative_key + "/")
                    or relative_key.startswith(existing + "/")
                    for existing in seen
                    if existing != relative_key
                ):
                    raise ValidationError(
                        f"ZIP contains a file/directory path collision: {info.filename!r}"
                    )
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                file_type = stat.S_IFMT(unix_mode)
                if file_type == stat.S_IFLNK:
                    raise ValidationError(f"ZIP symlink is forbidden: {info.filename!r}")
                if info.is_dir():
                    raise ValidationError(
                        f"ZIP directory entries are forbidden: {info.filename!r}"
                    )
                if file_type not in {0, stat.S_IFREG}:
                    raise ValidationError(f"ZIP member is not a regular file: {info.filename!r}")
                total_size += info.file_size
                if info.file_size > package_lib.FLASH_CAPACITY or total_size > ZIP_UNCOMPRESSED_LIMIT:
                    raise ValidationError("ZIP uncompressed payload exceeds the validation limit")
                files[relative] = archive.read(info)
                modes[relative] = stat.S_IMODE(unix_mode) if unix_mode else 0o644
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f"invalid artifact ZIP: {exc}") from exc
    return ArtifactContents(str(path), files, modes)


def read_artifact(path: Path) -> ArtifactContents:
    if path.is_dir():
        return read_directory(path)
    return read_zip(path)


def json_no_duplicates(raw: bytes, label: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationError(f"{label} has a duplicate JSON key: {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{label} is not valid UTF-8 JSON: {exc}") from exc


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def require_integer(value: object, label: str, *, positive: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or (positive and value <= 0):
        qualifier = "positive " if positive else ""
        raise ValidationError(f"{label} must be a {qualifier}integer")
    return value


def require_sha(value: object, label: str, length: int = 40) -> str:
    text = require_string(value, label)
    if not re.fullmatch(rf"[0-9a-f]{{{length}}}", text):
        raise ValidationError(f"{label} must be a lowercase {length}-hex digest")
    return text


def validate_sha256sums(contents: ArtifactContents) -> None:
    try:
        raw = contents.files["SHA256SUMS"].decode("utf-8")
    except KeyError as exc:
        raise ValidationError("artifact is missing SHA256SUMS") from exc
    except UnicodeDecodeError as exc:
        raise ValidationError("SHA256SUMS is not UTF-8") from exc
    declared: dict[str, str] = {}
    seen: set[str] = set()
    for line in raw.splitlines():
        match = SUM_RE.fullmatch(line)
        if not match:
            raise ValidationError(f"invalid SHA256SUMS line: {line!r}")
        relative = add_unique_path(seen, match.group(2))
        if relative == "SHA256SUMS":
            raise ValidationError("SHA256SUMS must not claim a self hash")
        declared[relative] = match.group(1)
    expected_paths = set(contents.files) - {"SHA256SUMS"}
    if set(declared) != expected_paths:
        raise ValidationError("SHA256SUMS file set does not exactly match the artifact")
    for relative, expected in declared.items():
        actual = package_lib.digest_bytes(contents.files[relative])
        if actual != expected:
            raise ValidationError(f"SHA256SUMS mismatch for {relative}")


def validate_public_text_privacy(contents: ArtifactContents) -> None:
    """Reject private build paths and whole-image references in public metadata."""
    for relative, payload in contents.files.items():
        if PurePosixPath(relative).suffix.casefold() == ".bin":
            continue
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError(f"public metadata is not UTF-8 text: {relative}") from exc
        if package_lib.contains_private_public_text(text):
            raise ValidationError(f"public metadata contains a private build path: {relative}")
        if package_lib.FORBIDDEN_PUBLIC_IMAGE_TEXT_RE.search(text):
            raise ValidationError(
                f"public metadata references a merged or whole-flash image: {relative}"
            )


def validate_file_metadata(
    contents: ArtifactContents,
    metadata: object,
    label: str,
    seen_paths: set[str],
) -> str:
    if not isinstance(metadata, dict):
        raise ValidationError(f"{label} metadata must be an object")
    relative = add_unique_path(seen_paths, require_string(metadata.get("path"), f"{label}.path"))
    if relative not in contents.files:
        raise ValidationError(f"{label} file is missing: {relative}")
    expected_size = require_integer(metadata.get("size"), f"{label}.size", positive=True)
    expected_hash = require_sha(metadata.get("sha256"), f"{label}.sha256", 64)
    payload = contents.files[relative]
    if len(payload) != expected_size:
        raise ValidationError(f"{label} size mismatch: {relative}")
    if package_lib.digest_bytes(payload) != expected_hash:
        raise ValidationError(f"{label} hash mismatch: {relative}")
    return relative


def source_path_from_published(value: str) -> str:
    path = safe_artifact_path(value)
    if len(path.parts) < 2 or path.parts[0] != "bin":
        raise ValidationError(f"published build file must be below bin/: {value!r}")
    return PurePosixPath(*path.parts[1:]).as_posix()


def validate_global_bindings(manifest: dict[str, Any], args: argparse.Namespace) -> str:
    if manifest.get("schema") != 3:
        raise ValidationError("manifest schema must be 3")
    source_type = manifest.get("source_type")
    if source_type not in {"arduino", "esp-idf"}:
        raise ValidationError("manifest source_type is invalid")
    target = require_string(manifest.get("target"), "manifest.target")
    if target != args.target:
        raise ValidationError("manifest target does not match the expected target")
    product_sha = require_sha(manifest.get("product_git_sha"), "manifest.product_git_sha")
    if product_sha != args.product_sha or manifest.get("git_sha") != product_sha:
        raise ValidationError("manifest product SHA binding is inconsistent")
    if manifest.get("flash_capacity_bytes") != package_lib.FLASH_CAPACITY:
        raise ValidationError("manifest flash_capacity_bytes is not 32 MiB")
    if manifest.get("flash_size_bytes") != package_lib.FLASH_CAPACITY or manifest.get("flash_size") != "32MiB":
        raise ValidationError("manifest flash_size binding is invalid")
    if source_type == "arduino":
        required_cli = {
            "fqbn": args.fqbn,
            "framework version": args.framework_version,
            "BSP source SHA": args.bsp_sha,
            "BSP source tree": args.bsp_source_tree,
            "BSP component tree": args.bsp_component_tree,
            "BSP version": args.bsp_version,
        }
        if any(not value for value in required_cli.values()):
            raise ValidationError("Arduino validation requires all expected FQBN/framework/BSP pins")
        try:
            package_lib.parse_fqbn_selections(args.fqbn)
        except package_lib.PackageError as exc:
            raise ValidationError(str(exc)) from exc
        if manifest.get("fqbn") != args.fqbn:
            raise ValidationError("manifest FQBN does not match the expected generated FQBN")
        framework = manifest.get("framework")
        if framework != {"name": "Arduino-ESP32", "version": args.framework_version}:
            raise ValidationError("manifest Arduino framework binding is invalid")
        if args.framework_version != package_lib.ARDUINO_CORE_VERSION:
            raise ValidationError("Arduino framework pin must be 3.3.11")
        if manifest.get("profile_id") != "rev1_3":
            raise ValidationError("Arduino artifact profile must be rev1_3")
        expected_bsp = {
            "source_sha": args.bsp_sha,
            "source_tree": args.bsp_source_tree,
            "component_tree": args.bsp_component_tree,
            "version": args.bsp_version,
            "linked": False,
            "relationship": "reference-only",
        }
        if manifest.get("bsp") != expected_bsp:
            raise ValidationError("manifest BSP provenance object is inconsistent")
        direct_bsp = {
            "bsp_git_sha": args.bsp_sha,
            "bsp_source_tree": args.bsp_source_tree,
            "bsp_component_tree": args.bsp_component_tree,
            "bsp_version": args.bsp_version,
            "bsp_linked": False,
            "bsp_relationship": "reference-only",
        }
        if any(manifest.get(key) != value for key, value in direct_bsp.items()):
            raise ValidationError("manifest direct BSP bindings are inconsistent")
        if args.bsp_linked not in {None, False}:
            raise ValidationError("Arduino BSP relationship must be expected as unlinked")
        if "merged_image" in manifest:
            raise ValidationError("Arduino manifest must not contain merged_image")
    return source_type


def validate_external_build_inputs(
    contents: ArtifactContents,
    manifest: dict[str, Any],
    args: argparse.Namespace,
    packaged_plan: list[tuple[int, PurePosixPath]],
) -> None:
    if not args.build_dir or not args.build_options or not args.source_root:
        raise ValidationError(
            "Arduino validation requires --build-dir, --build-options, and --source-root"
        )
    build = args.build_dir.resolve()
    build_options = args.build_options.resolve()
    expected_options = build / "build.options.json"
    if (
        args.build_dir.is_symlink()
        or args.build_options.is_symlink()
        or not build.is_dir()
        or build_options != expected_options
        or not build_options.is_file()
    ):
        raise ValidationError("external Arduino build options are not the exact build-path file")
    source_flash_args = build / "flash_args"
    if source_flash_args.is_symlink() or not source_flash_args.is_file():
        raise ValidationError("external Arduino flash_args is missing or unsafe")
    try:
        build_options_data = package_lib.parse_build_options(
            build_options, "rev1_3", args.fqbn, args.framework_version
        )
    except package_lib.PackageError as exc:
        raise ValidationError(str(exc)) from exc
    expected_inputs = {
        "build_options": package_lib.external_file_identity(build_options),
        "flash_args": package_lib.external_file_identity(source_flash_args),
    }
    try:
        raw_source_args = source_flash_args.read_text(encoding="utf-8")
        source_plan, source_settings, _ = package_lib.parse_arduino_flash_args(raw_source_args)
    except (OSError, UnicodeDecodeError, package_lib.PackageError) as exc:
        raise ValidationError(f"external Arduino flash_args is invalid: {exc}") from exc
    if source_plan != packaged_plan or source_settings != manifest.get("flash_settings"):
        raise ValidationError("external and packaged Arduino flash plans differ")
    try:
        expected_build_identity, compile_commands_identity = (
            package_lib.arduino_build_identity(
                build=build,
                source_root_path=args.source_root,
                build_options=build_options_data,
                product_sha=args.product_sha,
                project=require_string(manifest.get("project"), "manifest.project"),
                sketch=require_string(manifest.get("sketch"), "manifest.sketch"),
                fqbn=args.fqbn,
                variant_id=require_string(
                    manifest.get("product_variant_id"), "manifest.product_variant_id"
                ),
                plan=packaged_plan,
                flash_files=manifest["files"],
            )
        )
    except package_lib.PackageError as exc:
        raise ValidationError(str(exc)) from exc
    expected_inputs["compile_commands"] = compile_commands_identity
    if manifest.get("build_inputs") != expected_inputs:
        raise ValidationError("manifest external build-input identities are inconsistent")
    if manifest.get("build_identity") != expected_build_identity:
        raise ValidationError("manifest canonical Arduino build identity is inconsistent")
    for (_, source_path), segment in zip(packaged_plan, manifest["files"]):
        unresolved = build.joinpath(*source_path.parts)
        cursor = build
        for part in source_path.parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValidationError(f"external Arduino segment is a symlink: {source_path}")
        resolved = unresolved.resolve()
        try:
            resolved.relative_to(build)
        except ValueError as exc:
            raise ValidationError(f"external Arduino segment escapes the build path: {source_path}") from exc
        if not resolved.is_file():
            raise ValidationError(f"external Arduino segment is missing: {source_path}")
        published = require_string(segment.get("path"), "manifest segment path")
        if resolved.read_bytes() != contents.files[published]:
            raise ValidationError(f"published segment differs from the external build: {source_path}")


def validate_manifest(contents: ArtifactContents, args: argparse.Namespace) -> dict[str, Any]:
    try:
        raw_manifest = contents.files["manifest.json"]
    except KeyError as exc:
        raise ValidationError("artifact is missing manifest.json") from exc
    manifest = json_no_duplicates(raw_manifest, "manifest.json")
    if not isinstance(manifest, dict):
        raise ValidationError("manifest.json root must be an object")
    source_type = validate_global_bindings(manifest, args)
    if source_type == "arduino":
        for relative in contents.files:
            if package_lib.is_forbidden_published_image(relative):
                raise ValidationError(f"Arduino artifact publishes a merged or whole image: {relative}")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValidationError("manifest files must be a non-empty segment list")
    published_paths: set[str] = set()
    manifest_plan: list[tuple[int, str]] = []
    ranges: list[tuple[int, int, str]] = []
    binding_values = {
        "target": manifest.get("target"),
        "fqbn": manifest.get("fqbn"),
        "product_git_sha": manifest.get("product_git_sha"),
        "bsp_git_sha": manifest.get("bsp_git_sha"),
        "bsp_source_tree": manifest.get("bsp_source_tree"),
        "bsp_component_tree": manifest.get("bsp_component_tree"),
        "bsp_version": manifest.get("bsp_version"),
        "bsp_linked": manifest.get("bsp_linked"),
    }
    for index, segment in enumerate(files):
        label = f"manifest.files[{index}]"
        relative = validate_file_metadata(contents, segment, label, published_paths)
        if source_type == "arduino" and package_lib.is_forbidden_published_image(relative):
            raise ValidationError(f"Arduino segment is a merged or whole image: {relative}")
        if not isinstance(segment, dict):
            raise ValidationError(f"{label} must be an object")
        if any(segment.get(key) != value for key, value in binding_values.items()):
            raise ValidationError(f"{label} provenance binding is inconsistent")
        current_offset = require_integer(segment.get("offset"), f"{label}.offset")
        if current_offset < 0:
            raise ValidationError(f"{label}.offset must not be negative")
        current_size = require_integer(segment.get("size"), f"{label}.size", positive=True)
        manifest_plan.append((current_offset, source_path_from_published(relative)))
        ranges.append((current_offset, current_offset + current_size, relative))
    if ranges != sorted(ranges):
        raise ValidationError("manifest segments must be sorted by offset")
    if len({start for start, _, _ in ranges}) != len(ranges):
        raise ValidationError("manifest segments have duplicate offsets")
    for start, end, relative in ranges:
        if start >= package_lib.FLASH_CAPACITY or end > package_lib.FLASH_CAPACITY:
            raise ValidationError(f"segment exceeds 32 MiB flash capacity: {relative}")
    for previous, current in zip(ranges, ranges[1:]):
        if previous[1] > current[0]:
            raise ValidationError(f"flash segments overlap: {previous[2]} and {current[2]}")
    if len(ranges) == 1 and ranges[0][0] == 0:
        raise ValidationError("single-file whole-flash plan at offset 0x0 is forbidden")
    total = sum(end - start for start, end, _ in ranges)
    if manifest.get("segment_count") != len(ranges):
        raise ValidationError("manifest segment_count is inconsistent")
    for key in ("total_segment_bytes", "segmented_payload_total"):
        if manifest.get(key) != total:
            raise ValidationError(f"manifest {key} is inconsistent")
    if source_type == "arduino" and total >= package_lib.ARDUINO_SEGMENT_BYTES_LIMIT:
        raise ValidationError("Arduino segmented payload is not significantly below 32 MiB")
    debug_files = manifest.get("debug_files")
    if not isinstance(debug_files, list):
        raise ValidationError("manifest debug_files must be a list")
    if source_type == "arduino" and debug_files:
        raise ValidationError("Arduino artifacts must not publish debug files")
    for index, metadata in enumerate(debug_files):
        validate_file_metadata(contents, metadata, f"manifest.debug_files[{index}]", published_paths)
    args_name = "flash_args" if source_type == "arduino" else "flasher_args.json"
    flash_args_path = validate_file_metadata(
        contents, manifest.get("flash_args"), "manifest.flash_args", published_paths
    )
    if flash_args_path != args_name:
        raise ValidationError("manifest flash_args path is inconsistent with source_type")
    try:
        raw_args = contents.files[args_name].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{args_name} is not UTF-8") from exc
    if source_type == "arduino":
        try:
            parsed_plan, parsed_settings, normalized = package_lib.parse_arduino_flash_args(raw_args)
        except package_lib.PackageError as exc:
            raise ValidationError(str(exc)) from exc
        if raw_args != normalized + "\n":
            raise ValidationError("packaged flash_args is not canonical")
        if "original_flash_args" in manifest:
            raise ValidationError("Arduino manifest must not expose raw original_flash_args")
        try:
            derived_capacity = package_lib.arduino_flash_capacity(parsed_settings, manifest["fqbn"])
        except package_lib.PackageError as exc:
            raise ValidationError(str(exc)) from exc
        if derived_capacity != manifest.get("flash_size_bytes"):
            raise ValidationError("derived Arduino flash capacity does not match manifest")
        validate_external_build_inputs(contents, manifest, args, parsed_plan)
    else:
        try:
            parsed_plan, parsed_settings, canonical = package_lib.parse_idf_flasher_args(raw_args)
        except package_lib.PackageError as exc:
            raise ValidationError(str(exc)) from exc
        if raw_args != canonical + "\n":
            raise ValidationError("packaged flasher_args.json is not canonical")
        if manifest.get("original_flash_args") != [canonical]:
            raise ValidationError("manifest original_flash_args is inconsistent")
    parsed_pairs = [(entry_offset, entry_path.as_posix()) for entry_offset, entry_path in parsed_plan]
    if parsed_pairs != manifest_plan:
        raise ValidationError("manifest segments do not match framework flash_args")
    if manifest.get("flash_settings") != parsed_settings:
        raise ValidationError("manifest flash_settings does not match framework flash_args")
    baud = require_integer(manifest.get("baud"), "manifest.baud", positive=True)
    try:
        portable, shell, batch = package_lib.flash_helper_contents(
            manifest["target"], str(baud), files, parsed_settings
        )
    except package_lib.PackageError as exc:
        raise ValidationError(str(exc)) from exc
    if manifest.get("portable_flash_command") != portable:
        raise ValidationError("portable segmented flash command is inconsistent")
    if contents.files.get("flash.sh") != shell.encode("utf-8"):
        raise ValidationError("flash.sh does not match the segmented flash plan")
    if contents.files.get("flash.bat") != batch.encode("utf-8"):
        raise ValidationError("flash.bat does not match the segmented flash plan")
    if not contents.modes.get("flash.sh", 0) & 0o111:
        raise ValidationError("flash.sh is not executable")
    published_paths.update({"manifest.json", "sha256sums", "flash.sh", "flash.bat"})
    if {relative.casefold() for relative in contents.files} != published_paths:
        raise ValidationError("artifact contains files that are not declared by the manifest")
    return manifest


def validate(contents: ArtifactContents, args: argparse.Namespace) -> dict[str, Any]:
    validate_public_text_privacy(contents)
    validate_sha256sums(contents)
    return validate_manifest(contents, args)


def parse_expected_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value == "true"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--product-sha", required=True)
    parser.add_argument("--fqbn")
    parser.add_argument("--framework-version")
    parser.add_argument("--bsp-sha")
    parser.add_argument("--bsp-source-tree", "--bsp-tree", dest="bsp_source_tree")
    parser.add_argument(
        "--bsp-component-tree", "--bsp-content-hash", dest="bsp_component_tree"
    )
    parser.add_argument("--bsp-version")
    parser.add_argument("--bsp-linked", choices=("true", "false"))
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--build-options", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--equivalent-directory", type=Path)
    args = parser.parse_args()
    try:
        args.product_sha = package_lib.validate_full_sha(args.product_sha, "expected product SHA")
        for name in ("bsp_sha", "bsp_source_tree", "bsp_component_tree"):
            value = getattr(args, name)
            if value:
                setattr(args, name, package_lib.validate_full_sha(value, f"expected {name}"))
        if args.bsp_version:
            args.bsp_version = package_lib.validate_bsp_version(args.bsp_version)
        args.bsp_linked = parse_expected_bool(args.bsp_linked)
        contents = read_artifact(args.artifact)
        manifest = validate(contents, args)
        if args.equivalent_directory:
            directory = read_directory(args.equivalent_directory)
            validate(directory, args)
            if contents.files != directory.files:
                raise ValidationError("ZIP contents are not byte-for-byte equivalent to the directory")
        print(
            f"validated {contents.label}: {manifest['segment_count']} segments, "
            f"{manifest['segmented_payload_total']} payload bytes"
        )
        return 0
    except (ValidationError, package_lib.PackageError, OSError) as exc:
        print(f"artifact validation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
