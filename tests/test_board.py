"""Upload wrapper tests use a fake Arduino CLI and never access hardware."""

from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import board


class BoardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="board tests ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.firmware = self.root / "firmware/.pio/build/uno_r4_wifi/firmware.bin"
        self.firmware.parent.mkdir(parents=True)
        self.firmware.write_bytes(b"test binary; not executable firmware")

    def test_upload_uses_existing_binary_and_explicit_board(self) -> None:
        self.assertEqual(board.command("upload", self.root, "uno_r4_wifi", "/dev/cu.target"),
                         ["upload", "--fqbn", "arduino:renesas_uno:unor4wifi", "--port",
                          "/dev/cu.target", "--input-file", str(self.firmware)])

    def test_ports_and_monitor_do_not_require_build(self) -> None:
        self.firmware.unlink()
        self.assertEqual(board.command("ports", self.root, "uno_r4_wifi", ""), ["board", "list"])
        self.assertEqual(board.command("monitor", self.root, "uno_r4_wifi", "COM4"),
                         ["monitor", "--port", "COM4", "--config", "baudrate=115200"])

    def test_missing_and_blank_ports_are_rejected(self) -> None:
        for action in ("upload", "monitor"):
            for port in ("", "  "):
                with self.subTest(action=action, port=port), self.assertRaisesRegex(ValueError, "PORT is required"):
                    board.command(action, self.root, "uno_r4_wifi", port)

    def test_missing_empty_and_directory_artifacts_are_rejected(self) -> None:
        self.firmware.unlink()
        for state in ("missing", "empty", "directory"):
            if state == "empty":
                self.firmware.touch()
            elif state == "directory":
                self.firmware.unlink()
                self.firmware.mkdir()
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, "make firmware"):
                board.command("upload", self.root, "uno_r4_wifi", "COM4")

    def test_unsupported_board_is_rejected(self) -> None:
        for action in ("ports", "upload", "monitor"):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, "Only BOARD"):
                board.command(action, self.root, "esp32", "COM4")

    def test_missing_tool_explains_installation_without_launching(self) -> None:
        output = io.StringIO()
        with patch.dict(os.environ, {"BOARD": "uno_r4_wifi"}), patch.object(board.shutil, "which", return_value=None), \
                patch.object(board.subprocess, "run") as run, redirect_stderr(output):
            self.assertEqual(board.main(["ports"]), 2)
        run.assert_not_called()
        self.assertIn("Install it on the host", output.getvalue())

    def test_invalid_upload_does_not_launch_tool(self) -> None:
        with patch.dict(os.environ, {"BOARD": "uno_r4_wifi", "PORT": ""}), \
                patch.object(board.subprocess, "run") as run, redirect_stderr(io.StringIO()):
            self.assertEqual(board.main(["upload"]), 2)
        run.assert_not_called()

    def test_launch_error_and_interrupt_are_reported(self) -> None:
        for error, expected in ((OSError("cannot execute"), 2), (KeyboardInterrupt(), 130)):
            with self.subTest(error=type(error).__name__), patch.dict(os.environ, {"BOARD": "uno_r4_wifi"}), \
                    patch.object(board.shutil, "which", return_value="fake-cli"), \
                    patch.object(board.subprocess, "run", side_effect=error), redirect_stderr(io.StringIO()):
                self.assertEqual(board.main(["ports"]), expected)

    def test_child_exit_status_is_preserved(self) -> None:
        for status, expected in ((0, 0), (7, 7), (-15, 143)):
            with self.subTest(status=status), patch.dict(os.environ, {"BOARD": "uno_r4_wifi"}), \
                    patch.object(board.shutil, "which", return_value="fake-cli"), \
                    patch.object(board.subprocess, "run", return_value=subprocess.CompletedProcess([], status)), \
                    redirect_stderr(io.StringIO()):
                self.assertEqual(board.main(["ports"]), expected)


class MakeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="make upload tests ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copy(board.ROOT / "Makefile", self.root)
        (self.root / "scripts").mkdir()
        shutil.copy(board.ROOT / "scripts/board.py", self.root / "scripts/board.py")
        (self.root / ".venv/bin").mkdir(parents=True)
        (self.root / ".venv/bin/python").symlink_to(sys.executable)
        self.firmware = self.root / "firmware/.pio/build/uno_r4_wifi/firmware.bin"
        self.firmware.parent.mkdir(parents=True)
        self.firmware.write_bytes(b"fixture")
        self.record = self.root / "calls.json"
        fake = self.root / "fake.py"
        fake.write_text("import json, os, pathlib, sys\n"
                        "pathlib.Path(os.environ['CALL_RECORD']).write_text(json.dumps(sys.argv[1:]))\n"
                        "print('fake CLI progress', file=sys.stderr)\n"
                        "sys.exit(int(os.environ.get('CLI_EXIT', '0')))\n")
        self.cli = self.root / "arduino cli"
        self.cli.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(fake))} \"$@\"\n")
        self.cli.chmod(0o755)
        self.environment = os.environ.copy()
        for name in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES"):
            self.environment.pop(name, None)
        self.environment.update(ARDUINO_CLI=str(self.cli), CALL_RECORD=str(self.record))

    def make(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(["make", *arguments, "DOCKER=must-not-run", "BOARD=uno_r4_wifi"],
                              cwd=self.root, env=self.environment, capture_output=True, text=True, timeout=10)

    def test_upload_handles_spaces_and_shell_characters_as_literal_arguments(self) -> None:
        # A mistaken shell interpolation would create this marker file.
        port = "/dev/cu.fake; touch INJECTED; #"
        result = self.make("upload", f"PORT={port}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.record.read_text()),
                         ["upload", "--fqbn", "arduino:renesas_uno:unor4wifi", "--port", port,
                          "--input-file", str(self.firmware.resolve())])
        self.assertFalse((self.root / "INJECTED").exists())
        self.assertIn("fake CLI progress", result.stderr)
        self.assertEqual(self.firmware.read_bytes(), b"fixture")

    def test_ports_and_monitor_make_targets(self) -> None:
        for target, port, expected in (("ports", "", ["board", "list"]),
                                       ("monitor", "COM7", ["monitor", "--port", "COM7", "--config", "baudrate=115200"])):
            with self.subTest(target=target):
                result = self.make(target, f"PORT={port}")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(self.record.read_text()), expected)

    def test_missing_port_fails_before_upload(self) -> None:
        result = self.make("upload", "PORT=")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PORT is required", result.stderr)
        self.assertFalse(self.record.exists())

    def test_make_reports_upload_failure_without_retry(self) -> None:
        self.environment["CLI_EXIT"] = "7"
        result = self.make("upload", "PORT=COM7")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed (exit 7)", result.stderr)


if __name__ == "__main__":
    unittest.main()
