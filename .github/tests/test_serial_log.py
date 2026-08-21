from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERIAL_LOG = ROOT / "examples" / "arduino" / "libraries" / "displays" / "serial_log.h"
SKETCH_ROOT = ROOT / "examples" / "arduino" / "examples"
LIBRARY_ROOT = ROOT / "examples" / "arduino" / "libraries"
DISPLAY_SUPPORT_ROOT = LIBRARY_ROOT / "displays"
SERIAL_OBJECT = r"(?:Serial(?:[0-2])?|USBSerial|HWCDCSerial)"
SERIAL_WAIT = re.compile(
    rf"\b(?:while|for)\s*\([^)]*\b{SERIAL_OBJECT}\b[^)]*\)",
    re.MULTILINE,
)
COMMENTED_READINESS_WAIT = re.compile(
    rf"while\s*\(\s*!\s*{SERIAL_OBJECT}\s*\)"
)
SERIAL_REFERENCE = re.compile(rf"\b{SERIAL_OBJECT}\b")
DIRECT_LOG = re.compile(
    rf"\b{SERIAL_OBJECT}\s*\.\s*(?:begin|print|println|printf|write|availableForWrite|setTxTimeoutMs)\s*\("
)


def without_comments(content: str) -> str:
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    return re.sub(r"//.*", "", content)


class SerialLogTests(unittest.TestCase):
    def compile_and_run(self, arduino_header: str, harness: str) -> None:
        compiler = shutil.which("g++")
        self.assertIsNotNone(compiler, "g++ is required for the serial-log host regression test")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Arduino.h").write_text(textwrap.dedent(arduino_header), encoding="utf-8")
            source = root / "serial_log_test.cpp"
            source.write_text(textwrap.dedent(harness), encoding="utf-8")
            binary = root / "serial_log_test"

            compile_result = subprocess.run(
                [
                    compiler,
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(root),
                    "-I",
                    str(SERIAL_LOG.parent),
                    str(source),
                    "-o",
                    str(binary),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, compile_result.returncode, compile_result.stderr)

            run_result = subprocess.run(
                [str(binary)],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            self.assertEqual(0, run_result.returncode, run_result.stderr)

    def test_hwcdc_drops_disconnected_or_capacity_limited_logs(self) -> None:
        self.compile_and_run(
            r"""
            #pragma once
            #include <cstddef>
            #include <cstdint>
            #include <string>

            #define ARDUINO_USB_MODE 1
            #define ARDUINO_USB_CDC_ON_BOOT 1

            class FakeSerial {
             public:
              bool connected = false;
              int writable = 0;
              int sequence = 0;
              int begin_sequence = 0;
              int timeout_sequence = 0;
              int begin_calls = 0;
              int timeout_calls = 0;
              int available_calls = 0;
              int println_calls = 0;
              unsigned long baud = 0;
              uint32_t timeout = 99;
              std::string last_message;

              void begin(unsigned long value) {
                begin_calls++;
                baud = value;
                begin_sequence = ++sequence;
              }
              void setTxTimeoutMs(uint32_t value) {
                timeout_calls++;
                timeout = value;
                timeout_sequence = ++sequence;
              }
              explicit operator bool() const { return connected; }
              int availableForWrite() {
                available_calls++;
                return writable;
              }
              size_t println(const char *message) {
                println_calls++;
                last_message = message;
                return last_message.size() + 2;
              }
            };

            extern FakeSerial HWCDCSerial;
            #define Serial HWCDCSerial
            """,
            r"""
            #include <cassert>
            #include <cstring>
            #include "serial_log.h"

            FakeSerial HWCDCSerial;

            int main() {
              serial_log::begin(115200);
              assert(HWCDCSerial.begin_calls == 1);
              assert(HWCDCSerial.baud == 115200);
              assert(HWCDCSerial.timeout_calls == 1);
              assert(HWCDCSerial.timeout == 0);
              assert(HWCDCSerial.begin_sequence < HWCDCSerial.timeout_sequence);

              HWCDCSerial.connected = false;
              HWCDCSerial.writable = 4096;
              serial_log::println("disconnected");
              assert(HWCDCSerial.println_calls == 0);
              assert(HWCDCSerial.available_calls == 0);

              const char *message = "connected";
              HWCDCSerial.connected = true;
              HWCDCSerial.writable = static_cast<int>(std::strlen(message) + 2);
              serial_log::println(message);
              assert(HWCDCSerial.println_calls == 1);
              assert(HWCDCSerial.last_message == message);

              HWCDCSerial.writable = static_cast<int>(std::strlen(message) + 1);
              serial_log::println(message);
              assert(HWCDCSerial.println_calls == 1);

              HWCDCSerial.writable = -1;
              serial_log::println(message);
              assert(HWCDCSerial.println_calls == 1);
              return 0;
            }
            """,
        )

    def test_non_usb_serial_keeps_ordinary_begin_and_println(self) -> None:
        self.compile_and_run(
            r"""
            #pragma once
            #include <cstddef>
            #include <string>

            #define ARDUINO_USB_MODE 0
            #define ARDUINO_USB_CDC_ON_BOOT 0

            class FakeSerial {
             public:
              int begin_calls = 0;
              int println_calls = 0;
              unsigned long baud = 0;
              std::string last_message;

              void begin(unsigned long value) {
                begin_calls++;
                baud = value;
              }
              size_t println(const char *message) {
                println_calls++;
                last_message = message;
                return last_message.size() + 2;
              }
            };

            extern FakeSerial Serial;
            """,
            r"""
            #include <cassert>
            #include "serial_log.h"

            FakeSerial Serial;

            int main() {
              serial_log::begin(115200);
              serial_log::println("ordinary serial");
              assert(Serial.begin_calls == 1);
              assert(Serial.baud == 115200);
              assert(Serial.println_calls == 1);
              assert(Serial.last_message == "ordinary serial");
              return 0;
            }
            """,
        )

    def test_first_party_sketches_use_helper_without_serial_waits(self) -> None:
        sketches = sorted(SKETCH_ROOT.rglob("*.ino"))
        self.assertEqual(10, len(sketches))

        for sketch in sketches:
            with self.subTest(sketch=sketch.relative_to(ROOT).as_posix()):
                content = sketch.read_text(encoding="utf-8")
                code = without_comments(content)

                self.assertIn('#include "serial_log.h"', content)
                self.assertIn("serial_log::begin(115200);", code)
                self.assertIn("serial_log::println(", code)
                self.assertIsNone(SERIAL_WAIT.search(code))
                self.assertIsNone(SERIAL_WAIT.search(content))
                self.assertIsNone(COMMENTED_READINESS_WAIT.search(content))
                self.assertIsNone(DIRECT_LOG.search(code))
                self.assertIsNone(SERIAL_REFERENCE.search(code))

        lvgl = (SKETCH_ROOT / "04_LVGLV9_Arduino" / "04_LVGLV9_Arduino.ino").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            lvgl,
            r"serial_log::println\(message\);\s*while\s*\(true\)",
        )

    def test_first_party_shared_support_has_no_serial_wait_or_direct_log_bypass(self) -> None:
        display_sources = {
            path
            for path in DISPLAY_SUPPORT_ROOT.rglob("*")
            if path.is_file()
            and path != SERIAL_LOG
            and path.suffix in {".c", ".cc", ".cpp", ".h", ".hpp", ".ino"}
        }
        root_sources = {
            path
            for path in LIBRARY_ROOT.iterdir()
            if path.is_file()
            and path.suffix in {".c", ".cc", ".cpp", ".h", ".hpp", ".ino"}
        }
        sources = sorted(display_sources | root_sources)
        self.assertTrue(sources)
        self.assertIn(LIBRARY_ROOT / "lv_conf.h", sources)
        self.assertIsNotNone(
            COMMENTED_READINESS_WAIT.search("// while(!Serial);"),
            "the raw-source guard must catch misleading commented readiness waits",
        )

        for source in sources:
            with self.subTest(source=source.relative_to(ROOT).as_posix()):
                content = source.read_text(encoding="utf-8")
                code = without_comments(content)
                self.assertIsNone(SERIAL_WAIT.search(code))
                self.assertIsNone(SERIAL_WAIT.search(content))
                self.assertIsNone(COMMENTED_READINESS_WAIT.search(content))
                self.assertIsNone(DIRECT_LOG.search(code))
                self.assertIsNone(SERIAL_REFERENCE.search(code))

    def test_wait_guard_detects_common_active_and_commented_forms(self) -> None:
        active_waits = (
            "while (!Serial) {}",
            "for (; !USBSerial; ) {}",
            "do {} while (HWCDCSerial.availableForWrite() == 0);",
        )
        for source in active_waits:
            with self.subTest(source=source):
                self.assertIsNotNone(SERIAL_WAIT.search(without_comments(source)))

        commented_waits = (
            "// while (!Serial) {}",
            "/* for (; !USBSerial; ) {} */",
        )
        for source in commented_waits:
            with self.subTest(source=source):
                self.assertIsNotNone(SERIAL_WAIT.search(source))
                self.assertIsNone(SERIAL_WAIT.search(without_comments(source)))


if __name__ == "__main__":
    unittest.main()
