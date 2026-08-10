from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "package_build_artifact.py"
SHA = "a" * 40


class ArtifactPackagingTests(unittest.TestCase):
    def run_package(self, mode: str, build: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), mode, "--build-dir", str(build), "--output-dir", str(output), "--product-label", "ESP32-P4-WIFI6-Touch-LCD-XC", "--variant", "3.4C", "--variant-id", "3_4c", "--resolution", "800x800", "--configuration", "default", "--framework-version", "v6.0.2", "--target", "esp32p4", "--project", "examples/test", "--git-sha", SHA, "--fqbn", "esp32:esp32:esp32p4", "--sketch", "test"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    @staticmethod
    def touch(build: Path, name: str, content: bytes = b"fixture") -> None:
        path = build / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def test_esp_idf_manifest_hashes_and_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            build, output = Path(temporary) / "build", Path(temporary) / "out"
            build.mkdir(); self.touch(build, "bootloader/bootloader.bin"); self.touch(build, "partition_table/partition-table.bin"); self.touch(build, "demo.bin"); self.touch(build, "demo.elf"); self.touch(build, "demo.map"); self.touch(build, "sdkconfig")
            (build / "flasher_args.json").write_text(json.dumps({"flash_files": {"0x1000": "bootloader/bootloader.bin", "0x8000": "partition_table/partition-table.bin", "0x10000": "demo.bin"}, "flash_settings": {"flash_mode": "qio", "flash_freq": "80m", "flash_size": "32MB"}}), encoding="utf-8")
            result = self.run_package("esp-idf", build, output)
            self.assertEqual(0, result.returncode, result.stderr)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("ci-example", manifest["artifact_kind"]); self.assertEqual("esp-idf", manifest["source_type"]); self.assertEqual("3_4c", manifest["product_variant_id"]); self.assertEqual(3, len(manifest["files"])); self.assertIn("--flash_mode qio", manifest["portable_flash_command"])
            self.assertTrue((output / "flash.sh").is_file()); self.assertTrue((output / "flash.bat").is_file())
            self.assertEqual(json.dumps(json.loads((build / "flasher_args.json").read_text(encoding="utf-8")), sort_keys=True, separators=(",", ":")) + "\n", (output / "flasher_args.json").read_text(encoding="utf-8"))
            sums = (output / "SHA256SUMS").read_text(encoding="utf-8")
            self.assertIn("manifest.json", sums); self.assertIn("bin/demo.bin", sums)
            self.assertEqual(hashlib.sha256((output / "bin" / "demo.bin").read_bytes()).hexdigest(), next(item["sha256"] for item in manifest["files"] if item["path"] == "bin/demo.bin"))

    def test_arduino_flash_args_and_merged_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            build, output = Path(temporary) / "build", Path(temporary) / "out"
            build.mkdir(); self.touch(build, "boot_app0.bin"); self.touch(build, "test.ino.bootloader.bin"); self.touch(build, "test.ino.partitions.bin"); self.touch(build, "test.ino.bin"); self.touch(build, "test.ino.merged.bin"); self.touch(build, "test.ino.elf")
            (build / "flash_args").write_text("--flash-mode qio --flash-freq 80m --flash-size 16MB\n0x1000 test.ino.bootloader.bin 0x8000 test.ino.partitions.bin 0xe000 boot_app0.bin 0x10000 test.ino.bin\n", encoding="utf-8")
            result = self.run_package("arduino", build, output)
            self.assertEqual(0, result.returncode, result.stderr)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("ci-example", manifest["artifact_kind"]); self.assertEqual("arduino", manifest["source_type"]); self.assertEqual("esp32:esp32:esp32p4", manifest["fqbn"]); self.assertEqual("bin/test.ino.merged.bin", manifest["merged_image"]["path"]); self.assertEqual([0x1000, 0x8000, 0xe000, 0x10000], [item["offset"] for item in manifest["files"]])
            self.assertEqual("--flash-mode qio --flash-freq 80m --flash-size 16MB 0x1000 test.ino.bootloader.bin 0x8000 test.ino.partitions.bin 0xe000 boot_app0.bin 0x10000 test.ino.bin\n", (output / "flash_args").read_text(encoding="utf-8"))
            self.assertIn("--flash-mode qio --flash-freq 80m --flash-size 16MB", manifest["portable_flash_command"])

    def test_arduino_full_write_flash_command_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            build, output = Path(temporary) / "build", Path(temporary) / "out"
            build.mkdir(); self.touch(build, "app.bin")
            (build / "flash_args").write_text("esptool.py --chip esp32p4 write-flash --flash-mode qio --flash-freq 80m --flash-size 16MB 0x10000 app.bin", encoding="utf-8")
            result = self.run_package("arduino", build, output)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("--flash-mode qio --flash-freq 80m --flash-size 16MB 0x10000 app.bin\n", (output / "flash_args").read_text(encoding="utf-8"))

    def test_missing_traversal_bad_and_duplicate_inputs_fail(self) -> None:
        cases = [
            ("esp-idf", {"flash_files": {"0x1000": "missing.bin"}}, None, "missing"),
            ("esp-idf", {"flash_files": {"bad": "demo.bin"}}, {"demo.bin": b"x"}, "invalid flash offset"),
            ("esp-idf", {"flash_files": {"0x1000": "../escape.bin"}}, None, "unsafe generated"),
            ("esp-idf", {"flash_files": {"0x1000": "/escape.bin"}}, None, "unsafe generated"),
            ("esp-idf", {"flash_files": {"0x1000": "C:\\\\escape.bin"}}, None, "unsafe generated"),
            ("esp-idf", {"flash_files": {"0x1000": "\\\\server\\\\share\\\\escape.bin"}}, None, "unsafe generated"),
            ("arduino", None, {"flash_args": b"write_flash 0x1000 one.bin 0x1000 two.bin", "one.bin": b"x", "two.bin": b"x"}, "duplicate"),
        ]
        for mode, data, files, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                build, output = Path(temporary) / "build", Path(temporary) / "out"; build.mkdir()
                if data is not None: (build / "flasher_args.json").write_text(json.dumps(data), encoding="utf-8")
                for name, content in (files or {}).items(): self.touch(build, name, content)
                result = self.run_package(mode, build, output)
                self.assertEqual(2, result.returncode); self.assertIn(expected, result.stderr)

    def test_symlink_escape_and_ambiguous_merged_images_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); build, output, outside = root / "build", root / "out", root / "outside.bin"
            build.mkdir(); outside.write_bytes(b"outside")
            try:
                os.symlink(outside, build / "escape.bin")
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            (build / "flasher_args.json").write_text(json.dumps({"flash_files": {"0x1000": "escape.bin"}}), encoding="utf-8")
            result = self.run_package("esp-idf", build, output)
            self.assertEqual(2, result.returncode); self.assertIn("unsafe generated", result.stderr)
        with tempfile.TemporaryDirectory() as temporary:
            build, output = Path(temporary) / "build", Path(temporary) / "out"
            build.mkdir(); self.touch(build, "app.bin"); self.touch(build, "one.merged.bin"); self.touch(build, "two.merged.bin")
            (build / "flash_args").write_text("0x10000 app.bin", encoding="utf-8")
            result = self.run_package("arduino", build, output)
            self.assertEqual(2, result.returncode); self.assertIn("ambiguous merged", result.stderr)


if __name__ == "__main__":
    unittest.main()
