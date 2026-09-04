"""Command-line orchestration for offline optical synchronization checks."""

import argparse
from pathlib import Path
import sys

from . import __version__


def main() -> int:
    parser = argparse.ArgumentParser(description="Check saved camera images against an UNO R4 LED target.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", required=True, type=Path, help="Run configuration JSON")
    args = parser.parse_args()
    # Delay scientific-library imports until an actual task is requested.
    import cv2
    from .analysis import analyze
    from .config import load_config
    from .report import write_report
    try:
        run = load_config(args.config)
        pairs, summary = analyze(run)
        write_report(run, pairs, summary)
        print(run.output / "report.html")
        print(f"Representative pairs: {summary['representative_pair']['valid_pairs']} valid / "
              f"{summary['representative_pair']['total_pairs']} supplied", file=sys.stderr)
    except (OSError, ValueError, TypeError, cv2.error) as error:
        print(f"camsync-check: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("camsync-check: interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
