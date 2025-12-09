"""
Simple harness to compare raw reference playback and FxLMS ANC with a saved secondary path.

Run as a module from the parent directory:
    python -m Basic_ANC.ANC_test [options]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Allow running as a script from the directory itself
if __package__ is None and str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

try:
    from .session_utils import create_controller, play_reference
except ImportError:
    from session_utils import create_controller, play_reference

# Default Paths
CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_REF_PATH = CURRENT_DIR.parent / "src" / "sine_200Hz.wav"
DEFAULT_SEC_PATH = CURRENT_DIR.parent / "enhanced_ANC" / "secondary_path.npy"

def parse_args():
    parser = argparse.ArgumentParser(description="Run FxLMS ANC test session.")
    parser.add_argument("--mode", choices=["anc", "reference"], default="reference", help="Operation mode.")
    parser.add_argument("--ref-file", type=Path, default=DEFAULT_REF_PATH, help="Path to reference audio.")
    parser.add_argument("--sec-path", type=Path, default=DEFAULT_SEC_PATH, help="Path to secondary path npy file.")
    parser.add_argument("--control-device", type=int, default=3, help="Output device index.")
    parser.add_argument("--record-device", type=int, default=1, help="Input device index (ANC mode).")
    parser.add_argument("--ref-device", type=int, default=None, help="Separate reference speaker device.")
    parser.add_argument("--split-channels", action="store_true", default=True, help="Split reference (L) and anti-noise (R).")
    parser.add_argument("--no-split", action="store_false", dest="split_channels", help="Disable channel splitting.")
    parser.add_argument("--step-size", type=float, default=1e-4, help="LMS step size.")
    parser.add_argument("--duration", type=float, default=None, help="Duration in seconds (default: infinite).")
    parser.add_argument("--block-size", type=int, default=None, help="Block size.")
    parser.add_argument("--filter-length", type=int, default=None, help="Filter length.")
    return parser.parse_args()

def run_anc(args) -> None:
    if not args.sec_path.exists():
        logging.error(f"Secondary path file not found at {args.sec_path}")
        sys.exit(1)

    controller = create_controller(
        reference_path=args.ref_file,
        secondary_path_file=args.sec_path,
        control_device=args.control_device,
        record_device=args.record_device,
        reference_device=args.ref_device,
        split_reference_channels=args.split_channels,
        play_reference=True,
        step_size=args.step_size,
        block_size=args.block_size,
        filter_length=args.filter_length,
    )

    def log_metrics(metrics) -> None:
        logging.info("frame=%05d error_rms=%.6f", metrics.frame_index, metrics.error_rms)

    logging.info("Starting ANC session (Ctrl+C to stop).")
    try:
        controller.run(loop_reference=args.duration is None, max_duration=args.duration, metrics_callback=log_metrics)
    except KeyboardInterrupt:
        logging.info("ANC stopped by user.")


def play_reference_only(args) -> None:
    play_reference(
        reference_path=args.ref_file,
        control_device=args.control_device,
        reference_device=args.ref_device,
        split_reference_channels=args.split_channels,
        block_size=args.block_size,
        duration=args.duration,
        loop=args.duration is None,
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    if not args.ref_file.exists():
        logging.error(f"Reference file not found at {args.ref_file}")
        return 1

    if args.mode == "anc":
        run_anc(args)
    else:
        play_reference_only(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
