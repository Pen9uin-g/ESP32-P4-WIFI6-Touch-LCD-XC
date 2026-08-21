from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SCRIPT = ROOT / ".github" / "scripts" / "package_build_artifact.py"
VALIDATOR_SCRIPT = ROOT / ".github" / "scripts" / "validate_flash_artifact.py"
BSP_SHA = "bfeb6e6d5737178cdde78b630c8118074da0a657"
BSP_SOURCE_TREE = "7c12c7115599b4bb84072ad9ea68cc8c3e81b9c6"
BSP_COMPONENT_TREE = "eff6286f5bb97145fb43a33102b9dafdfa5f5c0b"
BSP_VERSION = "3.0.1"
FQBN = (
    "esp32:esp32:esp32p4:ChipVariant=postv3,PSRAM=enabled,FlashSize=32M,"
    "FlashMode=qio,FlashFreq=80,PartitionScheme=app13M_data7M_32MB,"
    "USBMode=hwcdc,CDCOnBoot=cdc,UploadMode=default,UploadSpeed=921600"
)
LEGACY_FQBN = FQBN.replace("ChipVariant=postv3", "ChipVariant=prev3")
PACKAGE_MODULE_SPEC = importlib.util.spec_from_file_location(
    "package_build_artifact", PACKAGE_SCRIPT
)
if PACKAGE_MODULE_SPEC is None or PACKAGE_MODULE_SPEC.loader is None:
    raise RuntimeError("unable to load package artifact module")
PACKAGE_MODULE = importlib.util.module_from_spec(PACKAGE_MODULE_SPEC)
PACKAGE_MODULE_SPEC.loader.exec_module(PACKAGE_MODULE)


class ArtifactPackagingTests(unittest.TestCase):
    def test_fqbn_parser_supports_explicit_legacy_profile(self) -> None:
        self.assertEqual(
            "prev3",
            PACKAGE_MODULE.parse_fqbn_selections(LEGACY_FQBN, "rev1_3")["ChipVariant"],
        )
        self.assertEqual(
            "postv3",
            PACKAGE_MODULE.parse_fqbn_selections(FQBN, "rev3_x")["ChipVariant"],
        )
        with self.assertRaises(PACKAGE_MODULE.PackageError):
            PACKAGE_MODULE.parse_fqbn_selections(LEGACY_FQBN, "rev3_x")

    def test_custom_build_property_screen_defines_accept_assignment_form(self) -> None:
        self.assertEqual(
            ["CURRENT_SCREEN=SCREEN_3INCH_4_DSI"],
            PACKAGE_MODULE.parse_custom_property_screen_defines(
                "compiler.cpp.extra_flags=-DCURRENT_SCREEN=SCREEN_3INCH_4_DSI"
            ),
        )
        self.assertEqual(
            ["CURRENT_SCREEN=SCREEN_4INCH_DSI"],
            PACKAGE_MODULE.parse_custom_property_screen_defines(
                "compiler.cpp.extra_flags=-DCURRENT_SCREEN=SCREEN_4INCH_DSI"
            ),
        )

    def test_custom_build_property_screen_defines_preserve_invalid_and_conflicting_inputs(self) -> None:
        self.assertEqual(
            [],
            PACKAGE_MODULE.parse_custom_property_screen_defines(
                "compiler.cpp.extra_flags=-DCURRENT_SCREEN=SCREEN_3INCH_4_DSI;bad"
            ),
        )
        self.assertEqual(
            [
                "CURRENT_SCREEN=SCREEN_3INCH_4_DSI",
                "CURRENT_SCREEN=SCREEN_4INCH_DSI",
            ],
            PACKAGE_MODULE.parse_custom_property_screen_defines(
                "compiler.cpp.extra_flags=-DCURRENT_SCREEN=SCREEN_3INCH_4_DSI "
                "-DCURRENT_SCREEN=SCREEN_4INCH_DSI"
            ),
        )

    @classmethod
    def create_source_repository(cls, root: Path, marker: str) -> str:
        for project, sketch in (("examples/test", "test"), ("examples/other", "other")):
            source = root / project / f"{sketch}.ino"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                f"void setup() {{}}\nvoid loop() {{}} // {marker}-{sketch}\n",
                encoding="utf-8",
            )
        script_directory = root / ".github" / "scripts"
        script_directory.mkdir(parents=True)
        shutil.copy2(PACKAGE_SCRIPT, script_directory / PACKAGE_SCRIPT.name)
        shutil.copy2(VALIDATOR_SCRIPT, script_directory / VALIDATOR_SCRIPT.name)
        subprocess.run(
            ["git", "init", "-q", str(root)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["git", "-C", str(root), "add", "."],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        commit_environment = os.environ.copy()
        commit_environment.update(
            {
                "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
                "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
            }
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Artifact Test",
                "-c",
                "user.email=artifact-test@example.invalid",
                "commit",
                "-q",
                "-m",
                "fixture",
            ],
            check=True,
            env=commit_environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout.strip()

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_temporary = tempfile.TemporaryDirectory()
        temporary_root = Path(cls.source_temporary.name)
        cls.source_root = temporary_root / "source-a"
        cls.source_root_b = temporary_root / "source-b"
        cls.product_sha = cls.create_source_repository(cls.source_root, "repo-a")
        cls.product_sha_b = cls.create_source_repository(cls.source_root_b, "repo-b")
        cls.package_script = cls.source_root / ".github/scripts/package_build_artifact.py"
        cls.validator_script = cls.source_root / ".github/scripts/validate_flash_artifact.py"
        cls.package_script_b = (
            cls.source_root_b / ".github/scripts/package_build_artifact.py"
        )
        cls.validator_script_b = (
            cls.source_root_b / ".github/scripts/validate_flash_artifact.py"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.source_temporary.cleanup()

    @staticmethod
    def touch(build: Path, name: str, content: bytes = b"fixture") -> None:
        path = build / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    @staticmethod
    def write_sums(output: Path) -> None:
        records = []
        for path in sorted(item for item in output.rglob("*") if item.is_file()):
            if path.name == "SHA256SUMS":
                continue
            value = hashlib.sha256(path.read_bytes()).hexdigest()
            records.append(f"{value}  {path.relative_to(output).as_posix()}\n")
        (output / "SHA256SUMS").write_text("".join(records), encoding="utf-8")

    @staticmethod
    def write_manifest(output: Path, manifest: dict[str, object]) -> None:
        (output / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        ArtifactPackagingTests.write_sums(output)

    @staticmethod
    def rewrite_zip(
        source: Path,
        destination: Path,
        replacements: dict[str, bytes | None],
    ) -> None:
        with zipfile.ZipFile(source) as archive:
            payloads = {
                info.filename: archive.read(info)
                for info in archive.infolist()
                if not info.is_dir()
            }
            modes = {
                info.filename: info.external_attr
                for info in archive.infolist()
                if not info.is_dir()
            }
        for relative, payload in replacements.items():
            if relative not in payloads:
                raise AssertionError(f"fixture ZIP is missing {relative}")
            if payload is None:
                payloads.pop(relative)
            else:
                payloads[relative] = payload
        payloads["SHA256SUMS"] = "".join(
            f"{hashlib.sha256(payload).hexdigest()}  {relative}\n"
            for relative, payload in sorted(payloads.items())
            if relative != "SHA256SUMS"
        ).encode("utf-8")
        with zipfile.ZipFile(
            destination,
            "x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative, payload in sorted(payloads.items()):
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = modes.get(relative, (stat.S_IFREG | 0o644) << 16)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, payload)

    def run_package(
        self,
        mode: str,
        build: Path,
        output: Path,
        *,
        zip_output: Path | None = None,
        artifact_kind: str = "ci-example",
        profile_id: str = "rev3_x",
        sdkconfig_extra: str = "",
        fqbn: str = FQBN,
        build_fqbn: str | None = None,
        framework_version: str | None = None,
        project: str = "examples/test",
        sketch: str = "test",
        metadata_project: str | None = None,
        metadata_sketch: str | None = None,
        compile_fqbn: str | None = None,
        compile_usb_mode: str = "1",
        compile_cdc_on_boot: str = "1",
        compile_source_project: str | None = None,
        custom_build_properties: str | None = None,
        source_root: Path | None = None,
        product_sha: str | None = None,
        package_script: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        selected_source_root = source_root or self.source_root
        selected_product_sha = product_sha or self.product_sha
        sdkconfig = build / "sdkconfig"
        profile = (
            "CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y\n"
            "CONFIG_ESP32P4_REV_MIN_100=y\n"
            "# CONFIG_ESP32P4_REV_MIN_300 is not set\n"
            "# CONFIG_ESP32P4_REV_MIN_301 is not set\n"
            if profile_id == "rev1_3"
            else "# CONFIG_ESP32P4_SELECTS_REV_LESS_V3 is not set\n"
            "# CONFIG_ESP32P4_REV_MIN_100 is not set\n"
            "CONFIG_ESP32P4_REV_MIN_300=y\n"
            "# CONFIG_ESP32P4_REV_MIN_301 is not set\n"
        )
        sdkconfig.write_text(
            'CONFIG_IDF_TARGET="esp32p4"\n'
            "CONFIG_ESPTOOLPY_FLASHSIZE_32MB=y\n"
            'CONFIG_ESPTOOLPY_FLASHSIZE="32MB"\n'
            + profile
            + sdkconfig_extra,
            encoding="utf-8",
        )
        options = build / "build.options.json"
        generated_project = metadata_project or project
        generated_sketch = metadata_sketch or sketch
        options.write_text(
            json.dumps(
                {
                    "fqbn": build_fqbn if build_fqbn is not None else fqbn,
                    "hardwareFolders": "/opt/arduino/packages/esp32/hardware/esp32/3.3.11",
                    "customBuildProperties": custom_build_properties or (
                        "compiler.cpp.extra_flags=-I/home/ubuntu/private "
                        "-I/tmp/tool-cache -DCURRENT_SCREEN=SCREEN_3INCH_4_DSI"
                    ),
                    "sketchLocation": str(selected_source_root / generated_project),
                    "otherLibrariesFolders": "\\\\server\\share\\libraries",
                }
            ),
            encoding="utf-8",
        )
        if mode == "arduino":
            generated_root = build / "sketch"
            generated_root.mkdir(parents=True, exist_ok=True)
            translation_unit = generated_root / f"{generated_sketch}.ino.cpp"
            object_file = generated_root / f"{generated_sketch}.ino.cpp.o"
            translation_unit.write_bytes(
                f'#include "{generated_sketch}.ino"\n'.encode("utf-8")
            )
            object_file.write_bytes(b"OBJECT\x00" + generated_sketch.encode("utf-8"))
            (build / "compile_commands.json").write_text(
                json.dumps(
                    [
                        {
                            "directory": str(selected_source_root),
                            "file": str(translation_unit),
                            "arguments": [
                                "g++",
                                "-DCURRENT_SCREEN=SCREEN_3INCH_4_DSI",
                                f'-DARDUINO_FQBN="{compile_fqbn or fqbn}"',
                                f"-DARDUINO_USB_MODE={compile_usb_mode}",
                                f"-DARDUINO_USB_CDC_ON_BOOT={compile_cdc_on_boot}",
                                f"-I{selected_source_root / (compile_source_project or generated_project)}",
                                "-o",
                                str(object_file),
                                str(translation_unit),
                            ],
                        }
                    ]
                ),
                encoding="utf-8",
            )
        version = framework_version or ("3.3.11" if mode == "arduino" else "v6.0.2")
        command = [
            sys.executable,
            str(package_script or self.package_script),
            mode,
            "--build-dir",
            str(build),
            "--output-dir",
            str(output),
            "--product-label",
            "ESP32-P4-WIFI6-Touch-LCD-XC",
            "--variant",
            "3.4C",
            "--variant-id",
            "3_4c",
            "--resolution",
            "800x800",
            "--configuration",
            "default",
            "--framework-version",
            version,
            "--target",
            "esp32p4",
            "--project",
            project,
            "--git-sha",
            selected_product_sha,
            "--profile-id",
            profile_id,
            "--artifact-kind",
            artifact_kind,
            "--sdkconfig",
            str(sdkconfig),
            "--build-options",
            str(options),
        ]
        if zip_output:
            command.extend(("--zip-output", str(zip_output)))
        if mode == "arduino":
            command.extend(
                (
                    "--fqbn",
                    fqbn,
                    "--sketch",
                    sketch,
                    "--source-root",
                    str(selected_source_root),
                    "--bsp-sha",
                    BSP_SHA,
                    "--bsp-source-tree",
                    BSP_SOURCE_TREE,
                    "--bsp-component-tree",
                    BSP_COMPONENT_TREE,
                    "--bsp-version",
                    BSP_VERSION,
                )
            )
        return subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def run_validator(
        self,
        artifact: Path,
        build: Path,
        *,
        equivalent: Path | None = None,
        source_root: Path | None = None,
        product_sha: str | None = None,
        validator_script: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(validator_script or self.validator_script),
            str(artifact),
            "--target",
            "esp32p4",
            "--product-sha",
            product_sha or self.product_sha,
            "--fqbn",
            FQBN,
            "--framework-version",
            "3.3.11",
            "--bsp-sha",
            BSP_SHA,
            "--bsp-source-tree",
            BSP_SOURCE_TREE,
            "--bsp-component-tree",
            BSP_COMPONENT_TREE,
            "--bsp-version",
            BSP_VERSION,
            "--bsp-linked",
            "false",
            "--build-dir",
            str(build),
            "--build-options",
            str(build / "build.options.json"),
            "--source-root",
            str(source_root or self.source_root),
        ]
        if equivalent:
            command.extend(("--equivalent-directory", str(equivalent)))
        return subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def make_arduino_build(
        self,
        build: Path,
        *,
        pairs: list[tuple[int, str, bytes]] | None = None,
        merged_size: int = 0,
    ) -> list[tuple[int, str, bytes]]:
        selected = pairs or [
            (0x2000, "test.ino.bootloader.bin", b"bootloader" * 32),
            (0x8000, "test.ino.partitions.bin", b"partition" * 64),
            (0xE000, "boot_app0.bin", b"boot-app" * 128),
            (0x10000, "test.ino.bin", b"app-/tmp-is-binary-and-allowed" * 256),
        ]
        build.mkdir(parents=True)
        for _, name, payload in selected:
            self.touch(build, name, payload)
        arguments = " ".join(f"0x{address:x} {name}" for address, name, _ in selected)
        (build / "flash_args").write_text(
            f"--flash-mode dio --flash-freq 80m --flash-size 32MB {arguments}\n",
            encoding="utf-8",
        )
        self.touch(build, "test.ino.elf", b"ELF\x00/home/ubuntu/private\x00/tmp/cache")
        self.touch(build, "test.ino.map", b"/home/ubuntu/private /tmp/tool-cache C:\\Users\\builder")
        if merged_size:
            with (build / "test.ino.merged.bin").open("wb") as stream:
                stream.truncate(merged_size)
        return selected

    def make_valid_arduino_artifact(
        self, root: Path, *, app_suffix: bytes = b""
    ) -> tuple[Path, Path, Path]:
        build, output, archive = root / "build", root / "out", root / "artifact.zip"
        pairs = [
            (0x2000, "test.ino.bootloader.bin", b"boot"),
            (0x8000, "test.ino.partitions.bin", b"part"),
            (0xE000, "boot_app0.bin", b"boot-app"),
            (0x10000, "test.ino.bin", b"application" + app_suffix),
        ]
        self.make_arduino_build(build, pairs=pairs, merged_size=16 * 1024 * 1024)
        result = self.run_package("arduino", build, output, zip_output=archive)
        self.assertEqual(0, result.returncode, result.stderr)
        return build, output, archive

    def test_esp_idf_packaging_remains_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            build, output = Path(temporary) / "build", Path(temporary) / "out"
            build.mkdir()
            self.touch(build, "bootloader/bootloader.bin")
            self.touch(build, "partition_table/partition-table.bin")
            self.touch(build, "demo.bin")
            self.touch(build, "demo.elf")
            self.touch(build, "demo.map")
            (build / "flasher_args.json").write_text(
                json.dumps(
                    {
                        "flash_files": {
                            "0x1000": "bootloader/bootloader.bin",
                            "0x8000": "partition_table/partition-table.bin",
                            "0x10000": "demo.bin",
                        },
                        "flash_settings": {
                            "flash_mode": "qio",
                            "flash_freq": "80m",
                            "flash_size": "32MB",
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_package("esp-idf", build, output)
            self.assertEqual(0, result.returncode, result.stderr)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(3, manifest["schema"])
            self.assertEqual("rev3_x", manifest["profile_id"])
            self.assertEqual(self.product_sha, manifest["product_git_sha"])
            self.assertEqual(3, manifest["segment_count"])
            self.assertEqual(sum(item["size"] for item in manifest["files"]), manifest["segmented_payload_total"])
            self.assertIn("--flash_mode qio", manifest["portable_flash_command"])
            self.assertIn("original_flash_args", manifest)
            self.assertIn("merged_image", manifest)

    def test_real_core_four_segment_artifact_excludes_merged_and_private_debug(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build, output, archive = self.make_valid_arduino_artifact(root)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            expected_offsets = [0x2000, 0x8000, 0xE000, 0x10000]
            self.assertEqual(expected_offsets, [item["offset"] for item in manifest["files"]])
            self.assertEqual(4, manifest["segment_count"])
            self.assertEqual(sum(item["size"] for item in manifest["files"]), manifest["total_segment_bytes"])
            self.assertEqual(manifest["total_segment_bytes"], manifest["segmented_payload_total"])
            self.assertLess(manifest["segmented_payload_total"], 16 * 1024 * 1024)
            self.assertEqual([], manifest["debug_files"])
            self.assertNotIn("merged_image", manifest)
            self.assertNotIn("original_flash_args", manifest)
            self.assertEqual(False, manifest["bsp_linked"])
            self.assertEqual("reference-only", manifest["bsp_relationship"])
            self.assertEqual(
                {
                    "source_sha": BSP_SHA,
                    "source_tree": BSP_SOURCE_TREE,
                    "component_tree": BSP_COMPONENT_TREE,
                    "version": BSP_VERSION,
                    "linked": False,
                    "relationship": "reference-only",
                },
                manifest["bsp"],
            )
            for segment in manifest["files"]:
                self.assertEqual("esp32p4", segment["target"])
                self.assertEqual(FQBN, segment["fqbn"])
                self.assertEqual(self.product_sha, segment["product_git_sha"])
                self.assertEqual(BSP_SHA, segment["bsp_git_sha"])
                self.assertEqual(BSP_SOURCE_TREE, segment["bsp_source_tree"])
                self.assertEqual(BSP_COMPONENT_TREE, segment["bsp_component_tree"])
                self.assertEqual(BSP_VERSION, segment["bsp_version"])
                self.assertIs(False, segment["bsp_linked"])
            self.assertEqual("build.options.json", manifest["build_inputs"]["build_options"]["basename"])
            self.assertEqual("flash_args", manifest["build_inputs"]["flash_args"]["basename"])
            self.assertEqual(
                "compile_commands.json",
                manifest["build_inputs"]["compile_commands"]["basename"],
            )
            self.assertEqual(self.product_sha, manifest["build_identity"]["product_git_sha"])
            self.assertEqual("examples/test", manifest["build_identity"]["project"])
            self.assertEqual("test", manifest["build_identity"]["sketch"])
            self.assertEqual(FQBN, manifest["build_identity"]["fqbn"])
            self.assertEqual(
                "CURRENT_SCREEN=SCREEN_3INCH_4_DSI",
                manifest["build_identity"]["screen_define"],
            )
            self.assertEqual(
                "examples/test/test.ino",
                manifest["build_identity"]["primary_source"]["path"],
            )
            self.assertEqual(
                "test.ino.cpp",
                manifest["build_identity"]["translation_unit"]["basename"],
            )
            self.assertEqual(
                "test.ino.cpp.o", manifest["build_identity"]["object"]["basename"]
            )
            self.assertEqual(
                {
                    "source_basename": "test.ino.bin",
                    "path": "bin/test.ino.bin",
                    "offset": 0x10000,
                    "size": len(b"application"),
                    "sha256": hashlib.sha256(b"application").hexdigest(),
                },
                manifest["build_identity"]["application"],
            )
            self.assertTrue((build / "test.ino.merged.bin").is_file())
            self.assertEqual(16 * 1024 * 1024, (build / "test.ino.merged.bin").stat().st_size)
            output_names = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
            self.assertFalse(any("merged" in name.lower() for name in output_names))
            self.assertFalse(any(name.endswith((".elf", ".map", "sdkconfig", "build.options.json")) for name in output_names))
            public_text = b"\n".join(
                path.read_bytes() for path in output.rglob("*") if path.is_file() and path.suffix != ".bin"
            )
            for private_value in (b"/home/ubuntu", b"/tmp/", b"C:\\", b"\\\\server", b"tool-cache"):
                self.assertNotIn(private_value, public_text)
            with zipfile.ZipFile(archive) as packaged:
                names = packaged.namelist()
                self.assertEqual(sorted(names), names)
                self.assertEqual(output_names, set(names))
                self.assertFalse(any("merged" in name.lower() for name in names))
                self.assertFalse(any(info.file_size >= 16 * 1024 * 1024 for info in packaged.infolist()))
                self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in packaged.infolist()))
            directory_result = self.run_validator(output, build)
            self.assertEqual(0, directory_result.returncode, directory_result.stderr)
            zip_result = self.run_validator(archive, build, equivalent=output)
            self.assertEqual(0, zip_result.returncode, zip_result.stderr)

    def test_zip_is_byte_reproducible_for_identical_build_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / "build"
            self.make_arduino_build(build)
            archives: list[Path] = []
            for name in ("one", "two"):
                output = root / name
                archive = root / f"{name}.zip"
                result = self.run_package(
                    "arduino", build, output, zip_output=archive
                )
                self.assertEqual(0, result.returncode, result.stderr)
                archives.append(archive)
            self.assertEqual(archives[0].read_bytes(), archives[1].read_bytes())

    def test_build_metadata_rejects_swapped_build_and_spoofed_cli_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_a, output_a, archive_a = self.make_valid_arduino_artifact(root / "a")
            build_b, output_b = root / "b" / "build", root / "b" / "out"
            self.make_arduino_build(
                build_b,
                pairs=[
                    (0x2000, "other.ino.bootloader.bin", b"boot-b"),
                    (0x8000, "other.ino.partitions.bin", b"part-b"),
                    (0xE000, "boot_app0.bin", b"boot-app-b"),
                    (0x10000, "other.ino.bin", b"application-b"),
                ],
            )
            package_b = self.run_package(
                "arduino",
                build_b,
                output_b,
                project="examples/other",
                sketch="other",
            )
            self.assertEqual(0, package_b.returncode, package_b.stderr)
            swapped = self.run_validator(archive_a, build_b)
            self.assertEqual(2, swapped.returncode)
            self.assertIn("external", swapped.stderr)

            spoof_cases = (
                {
                    "label": "sketch",
                    "project": "examples/test",
                    "sketch": "other",
                    "metadata_project": "examples/test",
                    "metadata_sketch": "test",
                },
                {
                    "label": "project",
                    "project": "examples/other",
                    "sketch": "test",
                    "metadata_project": "examples/test",
                    "metadata_sketch": "test",
                },
            )
            for case in spoof_cases:
                with self.subTest(label=case["label"]):
                    spoof_output = root / f"spoof-{case['label']}"
                    result = self.run_package(
                        "arduino",
                        build_a,
                        spoof_output,
                        project=case["project"],
                        sketch=case["sketch"],
                        metadata_project=case["metadata_project"],
                        metadata_sketch=case["metadata_sketch"],
                    )
                    self.assertEqual(2, result.returncode)
                    self.assertTrue(
                        "sketchLocation" in result.stderr
                        or "project/sketch identity" in result.stderr,
                        result.stderr,
                    )

    def test_trusted_script_root_rejects_cross_repository_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_b, output_b, archive_b = (
                root / "build-b",
                root / "out-b",
                root / "artifact-b.zip",
            )
            self.make_arduino_build(build_b)

            package_b = self.run_package(
                "arduino",
                build_b,
                output_b,
                zip_output=archive_b,
                source_root=self.source_root_b,
                product_sha=self.product_sha_b,
                package_script=self.package_script_b,
            )
            self.assertEqual(0, package_b.returncode, package_b.stderr)
            validate_b = self.run_validator(
                archive_b,
                build_b,
                equivalent=output_b,
                source_root=self.source_root_b,
                product_sha=self.product_sha_b,
                validator_script=self.validator_script_b,
            )
            self.assertEqual(0, validate_b.returncode, validate_b.stderr)

            validate_b_with_a = self.run_validator(
                archive_b,
                build_b,
                source_root=self.source_root_b,
                product_sha=self.product_sha_b,
                validator_script=self.validator_script,
            )
            self.assertEqual(2, validate_b_with_a.returncode)
            self.assertIn("trusted repository root", validate_b_with_a.stderr)

            package_b_with_a = self.run_package(
                "arduino",
                build_b,
                root / "out-b-with-a",
                source_root=self.source_root_b,
                product_sha=self.product_sha_b,
                package_script=self.package_script,
            )
            self.assertEqual(2, package_b_with_a.returncode)
            self.assertIn("trusted repository root", package_b_with_a.stderr)

    def test_compile_identity_rejects_wrong_fqbn_and_usb_definitions(self) -> None:
        cases = (
            {
                "label": "fqbn",
                "compile_fqbn": FQBN.replace("USBMode=hwcdc", "USBMode=default"),
            },
            {"label": "usb_mode", "compile_usb_mode": "0"},
            {"label": "cdc_on_boot", "compile_cdc_on_boot": "0"},
            {"label": "source_include", "compile_source_project": "examples/other"},
        )
        for case in cases:
            with self.subTest(label=case["label"]), tempfile.TemporaryDirectory() as temporary:
                build, output = Path(temporary) / "build", Path(temporary) / "out"
                self.make_arduino_build(build)
                compile_overrides = {
                    key: value for key, value in case.items() if key != "label"
                }
                result = self.run_package(
                    "arduino", build, output, **compile_overrides
                )
                self.assertEqual(2, result.returncode)
                expected = (
                    "compile source identity"
                    if case["label"] == "source_include"
                    else "compile FQBN/USB identity"
                )
                self.assertIn(expected, result.stderr)

    def test_package_build_options_accepts_assignment_and_rejects_invalid_or_conflicting_screen_defines(self) -> None:
        cases = (
            {
                "label": "assignment",
                "properties": "compiler.cpp.extra_flags=-DCURRENT_SCREEN=SCREEN_3INCH_4_DSI",
                "returncode": 0,
            },
            {
                "label": "invalid",
                "properties": "compiler.cpp.extra_flags=-DCURRENT_SCREEN=SCREEN_3INCH_4_DSI;bad",
                "returncode": 2,
            },
            {
                "label": "conflicting",
                "properties": (
                    "compiler.cpp.extra_flags=-DCURRENT_SCREEN=SCREEN_3INCH_4_DSI "
                    "-DCURRENT_SCREEN=SCREEN_4INCH_DSI"
                ),
                "returncode": 2,
            },
        )
        for case in cases:
            with self.subTest(label=case["label"]), tempfile.TemporaryDirectory() as temporary:
                build, output = Path(temporary) / "build", Path(temporary) / "out"
                self.make_arduino_build(build)
                result = self.run_package(
                    "arduino",
                    build,
                    output,
                    custom_build_properties=case["properties"],
                )
                self.assertEqual(case["returncode"], result.returncode, result.stderr)
                if case["returncode"]:
                    self.assertIn("build options screen identity", result.stderr)

    def test_validator_rejects_manifest_project_and_sketch_spoofing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build, output, archive = self.make_valid_arduino_artifact(root)

            manifest_path = output / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["sketch"] = "other"
            self.write_manifest(output, manifest)
            directory_result = self.run_validator(output, build)
            self.assertEqual(2, directory_result.returncode)
            self.assertTrue(
                "sketchLocation" in directory_result.stderr
                or "project/sketch identity" in directory_result.stderr,
                directory_result.stderr,
            )

            with zipfile.ZipFile(archive) as packaged:
                zip_manifest = json.loads(packaged.read("manifest.json"))
            zip_manifest["project"] = "examples/other"
            spoofed_zip = root / "project-spoof.zip"
            self.rewrite_zip(
                archive,
                spoofed_zip,
                {
                    "manifest.json": (
                        json.dumps(zip_manifest, indent=2, sort_keys=True) + "\n"
                    ).encode("utf-8")
                },
            )
            zip_result = self.run_validator(spoofed_zip, build)
            self.assertEqual(2, zip_result.returncode)
            self.assertIn("sketchLocation", zip_result.stderr)

    def test_zip_validator_rejects_ten_flash_helper_tamper_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build, _, archive = self.make_valid_arduino_artifact(root)
            with zipfile.ZipFile(archive) as packaged:
                originals = {
                    helper: packaged.read(helper)
                    for helper in ("flash.sh", "flash.bat")
                }
            mutations = (
                ("member_deleted", None, None),
                (
                    "segment_deleted",
                    b" 0xe000 bin/boot_app0.bin",
                    b"",
                ),
                (
                    "offset_changed",
                    b"0xe000 bin/boot_app0.bin",
                    b"0xf000 bin/boot_app0.bin",
                ),
                (
                    "filename_changed",
                    b"bin/boot_app0.bin",
                    b"bin/substitute.bin",
                ),
                ("flash_option_changed", b"--flash-mode dio", b"--flash-mode qio"),
            )
            for helper, original in originals.items():
                for label, old, new in mutations:
                    with self.subTest(helper=helper, mutation=label):
                        if old is None:
                            replacement = None
                        else:
                            self.assertEqual(1, original.count(old))
                            replacement = original.replace(old, new, 1)
                            self.assertNotEqual(original, replacement)
                        attacked = root / f"{helper.replace('.', '-')}-{label}.zip"
                        self.rewrite_zip(archive, attacked, {helper: replacement})
                        result = self.run_validator(attacked, build)
                        self.assertEqual(2, result.returncode, result.stdout)
                        self.assertIn(
                            f"{helper} does not match the segmented flash plan",
                            result.stderr,
                        )

    def test_offset_zero_bootloader_is_valid_without_optional_boot_app0(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build, output = root / "build", root / "out"
            pairs = [
                (0, "test.ino.bootloader.bin", b"boot"),
                (0x9000, "test.ino.partitions.bin", b"part"),
                (0x23000, "test.ino.bin", b"app"),
            ]
            self.make_arduino_build(build, pairs=pairs)
            result = self.run_package("arduino", build, output)
            self.assertEqual(0, result.returncode, result.stderr)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([0, 0x9000, 0x23000], [item["offset"] for item in manifest["files"]])
            self.assertFalse(any(item["path"].endswith("boot_app0.bin") for item in manifest["files"]))
            validation = self.run_validator(output, build)
            self.assertEqual(0, validation.returncode, validation.stderr)

    def test_full_write_flash_command_with_nonzero_app_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            build, output = Path(temporary) / "build", Path(temporary) / "out"
            build.mkdir()
            self.touch(build, "test.ino.bin")
            (build / "flash_args").write_text(
                "esptool.py --chip esp32p4 write-flash --flash-mode dio --flash-freq 80m "
                "--flash-size 32MB 0x10000 test.ino.bin",
                encoding="utf-8",
            )
            result = self.run_package("arduino", build, output)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn(
                "0x10000 test.ino.bin",
                (output / "flash_args").read_text(encoding="utf-8"),
            )

    def test_single_offset_zero_and_merged_or_whole_plans_fail(self) -> None:
        cases = [
            ("0x0 app.bin", {"app.bin": b"app"}, "single whole-flash"),
            ("0x0 merged.bin", {"merged.bin": b"merged"}, "merged or whole-flash"),
            ("0x0 test.ino.merged.bin", {"test.ino.merged.bin": b"merged"}, "merged or whole-flash"),
            ("0x0 whole-flash.bin", {"whole-flash.bin": b"whole"}, "merged or whole-flash"),
            ("0x10000 test.ino.merged.bin", {"test.ino.merged.bin": b"merged"}, "merged or whole-flash"),
        ]
        for plan, files, expected in cases:
            with self.subTest(plan=plan), tempfile.TemporaryDirectory() as temporary:
                build, output = Path(temporary) / "build", Path(temporary) / "out"
                build.mkdir()
                for name, payload in files.items():
                    self.touch(build, name, payload)
                (build / "flash_args").write_text(
                    f"--flash-mode dio --flash-freq 80m --flash-size 32MB {plan}",
                    encoding="utf-8",
                )
                result = self.run_package("arduino", build, output)
                self.assertEqual(2, result.returncode)
                self.assertIn(expected, result.stderr)

    def test_invalid_paths_duplicates_overlap_bounds_and_missing_files_fail(self) -> None:
        cases = [
            ("0x1000 missing.bin", {}, "missing"),
            ("bad app.bin", {"app.bin": b"x"}, "invalid flash offset"),
            ("0x1000 ../escape.bin", {}, "unsafe generated"),
            ("0x1000 C:\\escape.bin", {}, "unsafe generated"),
            ("0x1000 one.bin 0x1000 two.bin", {"one.bin": b"x", "two.bin": b"x"}, "duplicate"),
            ("0x1000 Same.bin 0x2000 same.bin", {"Same.bin": b"x", "same.bin": b"x"}, "duplicate"),
            ("0x1000 one.bin 0x1100 two.bin", {"one.bin": b"x" * 0x200, "two.bin": b"x"}, "overlap"),
            ("0x1ffffff app.bin", {"app.bin": b"xx"}, "exceeds 32 MiB"),
            ("0x1000 empty.bin", {"empty.bin": b""}, "empty"),
        ]
        for plan, files, expected in cases:
            with self.subTest(plan=plan), tempfile.TemporaryDirectory() as temporary:
                build, output = Path(temporary) / "build", Path(temporary) / "out"
                build.mkdir()
                for name, payload in files.items():
                    self.touch(build, name, payload)
                (build / "flash_args").write_text(
                    f"--flash-mode dio --flash-freq 80m --flash-size 32MB {plan}",
                    encoding="utf-8",
                )
                result = self.run_package("arduino", build, output)
                self.assertEqual(2, result.returncode)
                self.assertIn(expected, result.stderr)

    def test_symlink_source_wrong_core_and_wrong_immutable_fqbn_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build, output, outside = root / "build", root / "out", root / "outside.bin"
            build.mkdir()
            outside.write_bytes(b"outside")
            try:
                os.symlink(outside, build / "app.bin")
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            (build / "flash_args").write_text(
                "--flash-mode dio --flash-freq 80m --flash-size 32MB 0x10000 app.bin",
                encoding="utf-8",
            )
            result = self.run_package("arduino", build, output)
            self.assertEqual(2, result.returncode)
            self.assertIn("unsafe generated", result.stderr)
        wrong_fqbn = FQBN.replace("USBMode=hwcdc", "USBMode=default")
        with tempfile.TemporaryDirectory() as temporary:
            build, output = Path(temporary) / "build", Path(temporary) / "out"
            self.make_arduino_build(build)
            result = self.run_package("arduino", build, output, fqbn=wrong_fqbn)
            self.assertEqual(2, result.returncode)
            self.assertIn("USBMode=hwcdc", result.stderr)
        with tempfile.TemporaryDirectory() as temporary:
            build, output = Path(temporary) / "build", Path(temporary) / "out"
            self.make_arduino_build(build)
            result = self.run_package("arduino", build, output, fqbn=FQBN + ",DebugLevel=debug")
            self.assertEqual(2, result.returncode)
            self.assertIn("unsupported extra selections", result.stderr)
        with tempfile.TemporaryDirectory() as temporary:
            build, output = Path(temporary) / "build", Path(temporary) / "out"
            self.make_arduino_build(build)
            result = self.run_package("arduino", build, output, framework_version="3.3.10")
            self.assertEqual(2, result.returncode)
            self.assertIn("3.3.11", result.stderr)

    def test_validator_rejects_tampered_segment_hash_size_and_flash_args(self) -> None:
        mutations = ("size", "hash", "payload", "flash_args")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                build, output, _ = self.make_valid_arduino_artifact(Path(temporary))
                manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
                if mutation == "size":
                    manifest["files"][0]["size"] += 1
                elif mutation == "hash":
                    manifest["files"][0]["sha256"] = "0" * 64
                elif mutation == "payload":
                    published = output / manifest["files"][-1]["path"]
                    published.write_bytes(b"attacker-replaced-payload")
                    manifest["files"][-1]["size"] = published.stat().st_size
                    manifest["files"][-1]["sha256"] = hashlib.sha256(published.read_bytes()).hexdigest()
                    total = sum(item["size"] for item in manifest["files"])
                    manifest["total_segment_bytes"] = total
                    manifest["segmented_payload_total"] = total
                else:
                    flash_args = output / "flash_args"
                    flash_args.write_text(
                        flash_args.read_text(encoding="utf-8").replace("0x2000", "0x3000"),
                        encoding="utf-8",
                    )
                    manifest["flash_args"]["size"] = flash_args.stat().st_size
                    manifest["flash_args"]["sha256"] = hashlib.sha256(flash_args.read_bytes()).hexdigest()
                self.write_manifest(output, manifest)
                result = self.run_validator(output, build)
                self.assertEqual(2, result.returncode)
                self.assertTrue(
                    any(
                        word in result.stderr
                        for word in (
                            "size",
                            "hash",
                            "segments",
                            "plan",
                            "external",
                            "identity",
                        )
                    ),
                    result.stderr,
                )

    def test_validator_rejects_zip_traversal_duplicate_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build, _, archive = self.make_valid_arduino_artifact(root)
            attacks: list[tuple[str, zipfile.ZipInfo, bytes]] = []
            traversal = zipfile.ZipInfo("../escape.txt")
            attacks.append(("traversal", traversal, b"escape"))
            duplicate = zipfile.ZipInfo("manifest.json")
            attacks.append(("duplicate", duplicate, b"{}"))
            symlink = zipfile.ZipInfo("link")
            symlink.create_system = 3
            symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
            attacks.append(("symlink", symlink, b"manifest.json"))
            collision = zipfile.ZipInfo("bin")
            attacks.append(("collision", collision, b"file-prefix-collision"))
            for label, malicious_info, payload in attacks:
                with self.subTest(label=label):
                    attacked = root / f"{label}.zip"
                    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(attacked, "w") as target:
                        for info in source.infolist():
                            target.writestr(info, source.read(info))
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", UserWarning)
                            target.writestr(malicious_info, payload)
                    result = self.run_validator(attacked, build)
                    self.assertEqual(2, result.returncode)
                    self.assertIn(label if label != "traversal" else "unsafe", result.stderr.lower())

    def test_validator_rejects_private_or_merged_public_text_everywhere(self) -> None:
        mutations = {
            "index": ("index.json", b'{"path":"/home/ubuntu/private/merged.bin"}\n'),
            "command": ("flash.sh", b"\necho /tmp/workdir/test.ino.merged.bin\n"),
            "manifest": ("manifest.json", None),
            "windows": ("index.json", b'{"path":"C:\\\\Users\\\\builder\\\\cache"}\n'),
            "unc": ("index.json", b'{"path":"\\\\\\\\server\\\\share\\\\workdir"}\n'),
        }
        for label, (relative, payload) in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                build, output, _ = self.make_valid_arduino_artifact(Path(temporary))
                target = output / relative
                if label == "manifest":
                    manifest = json.loads(target.read_text(encoding="utf-8"))
                    manifest["merged_image"] = {"path": "bin/test.ino.merged.bin"}
                    target.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
                elif label == "command":
                    target.write_bytes(target.read_bytes() + payload)
                else:
                    target.write_bytes(payload or b"")
                self.write_sums(output)
                result = self.run_validator(output, build)
                self.assertEqual(2, result.returncode)
                self.assertTrue(
                    "private build path" in result.stderr or "merged or whole-flash" in result.stderr,
                    result.stderr,
                )

    def test_validator_checks_zip_equivalence_to_validated_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_one, output_one, archive_one = self.make_valid_arduino_artifact(
                root / "one", app_suffix=b"same"
            )
            output_two = root / "two"
            shutil.copytree(output_one, output_two)
            second_manifest = json.loads((output_two / "manifest.json").read_text(encoding="utf-8"))
            second_manifest["product_label"] = "equivalence-negative-fixture"
            self.write_manifest(output_two, second_manifest)
            result = self.run_validator(archive_one, build_one, equivalent=output_two)
            self.assertEqual(2, result.returncode)
            self.assertIn("equivalent", result.stderr)


if __name__ == "__main__":
    unittest.main()
