from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "audit_markdown.py"
SPEC = importlib.util.spec_from_file_location("audit_markdown", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


class MarkdownAuditTests(unittest.TestCase):
    def test_name_status_parser_keeps_rename_and_deleted_paths(self) -> None:
        paths = audit.parse_name_status_z(
            "R100\0docs/old.md\0docs/new.md\0D\0docs/deleted.md\0"
        )
        self.assertEqual(
            ["docs/deleted.md", "docs/new.md", "docs/old.md"],
            paths,
        )

    def test_bilingual_companion_names(self) -> None:
        self.assertEqual("docs/CI_ZH.md", audit.expected_companion("docs/CI.md"))
        self.assertEqual("docs/CI.md", audit.expected_companion("docs/CI_ZH.md"))

    def test_public_text_hygiene_detects_local_paths_ports_and_tokens(self) -> None:
        findings = audit.check_public_text(
            "README.md",
            "C:\\Users\\name COM36 ghp_12345678901234567890",
        )
        self.assertEqual(
            {"LOCAL_ABSOLUTE_PATH", "ACTUAL_SERIAL_PORT", "CREDENTIAL_OR_TOKEN"},
            {finding.code for finding in findings},
        )

    def test_local_link_check_distinguishes_present_and_missing_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs").mkdir()
            (root / "docs" / "present.md").write_text("ok", encoding="utf-8")
            findings = audit.check_links(
                root,
                "README.md",
                "[present](docs/present.md) [missing](docs/missing.md)",
            )
        self.assertEqual(["RELATIVE_LINK_MISSING"], [finding.code for finding in findings])

    def test_docs_only_scope_rejects_source_files(self) -> None:
        config = audit.load_config(None)
        findings = audit.docs_only_findings(
            ROOT,
            ["docs/CI.md", "examples/esp-idf/02_HelloWorld/main/main.c"],
            config,
        )
        self.assertEqual(["DOCS_ONLY_SCOPE"], [finding.code for finding in findings])

    def test_deleting_one_language_page_reports_orphaned_companion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "GUIDE_ZH.md").write_text("[English](GUIDE.md)", encoding="utf-8")
            findings = audit.deleted_pair_findings(
                root,
                ["GUIDE.md"],
                audit.load_config(None),
            )
        self.assertEqual(
            ["BILINGUAL_PAIR_ORPHANED"],
            [finding.code for finding in findings],
        )


if __name__ == "__main__":
    unittest.main()
