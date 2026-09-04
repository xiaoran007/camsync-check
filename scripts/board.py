"""Host-side UNO R4 upload and serial commands; compilation stays in Docker."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FQBN = "arduino:renesas_uno:unor4wifi"


def command(action: str, root: Path, board: str, port: str) -> list[str]:
    if board != "uno_r4_wifi":
        raise ValueError("Only BOARD=uno_r4_wifi is supported by the host uploader")
    if action == "ports":
        return ["board", "list"]
    if not port.strip():
        raise ValueError(f"PORT is required. Run 'make ports', then 'make {action} PORT=...'")
    if action == "monitor":
        return ["monitor", "--port", port, "--config", "baudrate=115200"]
    if action != "upload":
        raise ValueError(f"Unknown board action: {action}")
    firmware = root / "firmware" / ".pio" / "build" / board / "firmware.bin"
    if not firmware.is_file() or firmware.stat().st_size == 0:
        raise ValueError(f"Firmware is missing or empty: {firmware}. Run 'make firmware' first")
    return ["upload", "--fqbn", FQBN, "--port", port, "--input-file", str(firmware)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("ports", "upload", "monitor"))
    args = parser.parse_args(argv)
    try:
        arguments = command(args.action, ROOT, os.environ.get("BOARD", "uno_r4_wifi"),
                            os.environ.get("PORT", ""))
        executable = shutil.which(os.environ.get("ARDUINO_CLI", "arduino-cli"))
        if executable is None:
            raise ValueError("Arduino CLI was not found. Install it on the host as described in "
                             "README.md, or set ARDUINO_CLI to its executable path")
        if args.action == "upload":
            print(f"Uploading existing RA4M1 firmware: {arguments[-1]} -> {os.environ['PORT']}",
                  file=sys.stderr, flush=True)
        # Inherit terminal streams so upload progress and the interactive monitor remain visible.
        result = subprocess.run([executable, *arguments], check=False)
        if result.returncode:
            print(f"Arduino CLI {args.action} failed (exit {result.returncode})", file=sys.stderr)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode
    except (OSError, ValueError) as error:
        print(f"board: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
