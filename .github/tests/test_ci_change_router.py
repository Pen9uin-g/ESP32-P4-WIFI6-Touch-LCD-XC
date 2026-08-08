from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "ci_change_router.py"
SPEC = importlib.util.spec_from_file_location("ci_change_router", SCRIPT)
assert SPEC and SPEC.loader
router = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = router
SPEC.loader.exec_module(router)


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.previous_cwd = Path.cwd()
        os.chdir(ROOT)
        cls.idf = set(router.list_idf_projects())
        cls.arduino = set(router.list_arduino_sketches())

    @classmethod
    def tearDownClass(cls) -> None:
        os.chdir(cls.previous_cwd)

    def test_inventory_and_complete_matrix_sizes(self) -> None:
        self.assertEqual(12, len(self.idf))
        self.assertEqual(5, len(self.arduino))
        self.assertEqual(26, len(router.idf_matrix(sorted(self.idf))["include"]))
        self.assertEqual(10, len(router.arduino_matrix(sorted(self.arduino))["include"]))

    def test_usb_vendor_only_matrix_is_explicit(self) -> None:
        entries = router.idf_matrix([router.USB_PROJECT])["include"]
        self.assertEqual(4, len(entries))
        vendor = [entry for entry in entries if entry["configuration"] == "vendor-only"]
        self.assertEqual(2, len(vendor))
        self.assertTrue(all("sdkconfig.ci.vendor-only" in entry["command"] for entry in vendor))

    def test_parse_name_status_preserves_both_rename_sides(self) -> None:
        changes = router.parse_name_status_z(
            "R100\0examples/esp-idf/01_HowToCreateProject/old.c\0docs/new.md\0"
            "D\0examples/arduino/examples/HelloWorld/HelloWorld.ino\0"
        )
        self.assertEqual("R100", changes[0].status)
        self.assertEqual(2, len(changes[0].paths))
        self.assertEqual("D", changes[1].status)

    def test_inventory_names_reject_shell_metacharacters(self) -> None:
        with self.assertRaises(router.RoutingError):
            router.validate_inventory({"examples/esp-idf/bad'name"}, "project")

    def test_documentation_only_selects_no_product_builds(self) -> None:
        route = router.route_changes(
            [router.Change("M", ("README.md",)), router.Change("M", ("docs/CI.md",))],
            self.idf,
            self.arduino,
        )
        self.assertTrue(route["docs_only"])
        self.assertEqual([], route["idf_projects"])
        self.assertEqual([], route["arduino_sketches"])

    def test_direct_source_changes_select_only_affected_items(self) -> None:
        project = "examples/esp-idf/02_HelloWorld"
        sketch = "examples/arduino/examples/HelloWorld"
        route = router.route_changes(
            [
                router.Change("M", (project + "/main/main.c",)),
                router.Change("M", (sketch + "/HelloWorld.ino",)),
            ],
            self.idf,
            self.arduino,
        )
        self.assertEqual([project], route["idf_projects"])
        self.assertEqual([sketch], route["arduino_sketches"])

    def test_shared_arduino_library_selects_every_sketch(self) -> None:
        route = router.route_changes(
            [router.Change("M", ("examples/arduino/libraries/displays/gt911.cpp",))],
            self.idf,
            self.arduino,
        )
        self.assertEqual(sorted(self.arduino), route["arduino_sketches"])
        self.assertEqual([], route["idf_projects"])

    def test_rename_and_deletion_route_using_old_paths(self) -> None:
        project = "examples/esp-idf/03_i2c_tools"
        route = router.route_changes(
            [router.Change("R100", (project + "/main/i2c.c", "docs/i2c.md"))],
            self.idf,
            self.arduino,
        )
        self.assertEqual([project], route["idf_projects"])
        self.assertFalse(route["docs_only"])

        deleted = router.route_changes(
            [router.Change("D", (project + "/main/i2c.c",))],
            self.idf,
            self.arduino,
        )
        self.assertEqual([project], deleted["idf_projects"])

    def test_firmware_is_visible_but_outside_example_matrices(self) -> None:
        route = router.route_changes(
            [
                router.Change("M", ("firmware/brookesia/main/app_main.cpp",)),
                router.Change("A", ("firmware/brookesia/release/factory.bin",)),
            ],
            self.idf,
            self.arduino,
        )
        self.assertEqual([], route["idf_projects"])
        self.assertEqual([], route["arduino_sketches"])
        self.assertEqual(2, len(route["firmware_paths"]))
        self.assertEqual(["firmware/brookesia/release/factory.bin"], route["release_paths"])

    def test_unknown_path_is_conservative_and_reported(self) -> None:
        route = router.route_changes(
            [router.Change("A", ("new_product/source.c",))],
            self.idf,
            self.arduino,
        )
        self.assertEqual(sorted(self.idf), route["idf_projects"])
        self.assertEqual(sorted(self.arduino), route["arduino_sketches"])
        self.assertEqual(["new_product/source.c"], route["unknown_paths"])

    def run_cli(self, changed_text: str, *extra: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            changed = temp / "changed.txt"
            output = temp / "github-output.txt"
            changed.write_text(changed_text, encoding="utf-8")
            env = os.environ.copy()
            env["GITHUB_OUTPUT"] = str(output)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--changed-files-from",
                    str(changed),
                    *extra,
                ],
                cwd=ROOT,
                env=env,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            result.github_output = output.read_text(encoding="utf-8") if output.exists() else ""
            return result

    def test_cli_writes_exact_github_outputs(self) -> None:
        result = self.run_cli("M\tREADME.md\n")
        self.assertEqual(0, result.returncode, result.stderr)
        outputs = dict(
            line.split("=", 1) for line in result.github_output.splitlines() if line
        )
        self.assertEqual("false", outputs["has_idf"])
        self.assertEqual("false", outputs["has_arduino"])
        self.assertEqual("true", outputs["docs_only"])
        self.assertEqual({"include": []}, json.loads(outputs["idf_matrix"]))
        self.assertEqual({"include": []}, json.loads(outputs["arduino_matrix"]))

    def test_cli_empty_diff_is_an_operational_failure(self) -> None:
        result = self.run_cli("")
        self.assertEqual(2, result.returncode)
        self.assertIn("refusing a silent no-build result", result.stderr)
        self.assertEqual("", result.github_output)

    def test_cli_strict_unknown_fails_after_conservative_route(self) -> None:
        result = self.run_cli("A\tnew_product/source.c\n", "--strict-unknown")
        self.assertEqual(3, result.returncode)
        self.assertIn("Unclassified paths", result.stderr)


if __name__ == "__main__":
    unittest.main()
