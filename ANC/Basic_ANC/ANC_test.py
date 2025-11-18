"""
Simple harness to compare raw reference playback and FxLMS ANC with a saved secondary path.

Edit the configuration constants below, then run from the repo root:
    python -m ANC.ANC_test
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from basic_ANC.session_utils import create_controller, play_reference

# ---------------------------------------------------------------------------
# Configuration (adjust for your setup)
# ---------------------------------------------------------------------------
REFERENCE_PATH = Path(__file__).resolve().parent / "src/sine_200Hz.wav"
SECONDARY_PATH = Path(__file__).resolve().parent / "secondary_path.npy"

CONTROL_DEVICE = 3          # Output device index for the stereo speaker
RECORD_DEVICE = 1           # Input device index for the error microphone
REFERENCE_DEVICE: Optional[int] = None  # Separate speaker when not splitting channels

SPLIT_REFERENCE_CHANNELS = True  # Left = reference, right = anti-noise
STEP_SIZE = 1e-4
BLOCK_SIZE: Optional[int] = None  # None uses controller default
FILTER_LENGTH: Optional[int] = None  # None uses controller default
DURATION: Optional[float] = None  # Seconds; None runs until Ctrl+C

# Choose between "anc" for adaptive cancellation or "reference" for raw playback.
MODE = "reference"  # "anc" or "reference"

# ---------------------------------------------------------------------------


def validate_config() -> None:
    if MODE not in {"anc", "reference"}:
        raise ValueError(f"Unsupported MODE '{MODE}'. Use 'anc' or 'reference'.")
    if CONTROL_DEVICE is None:
        raise ValueError("CONTROL_DEVICE must be set.")
    if MODE == "anc" and RECORD_DEVICE is None:
        raise ValueError("RECORD_DEVICE must be set when MODE == 'anc'.")
    if SPLIT_REFERENCE_CHANNELS and REFERENCE_DEVICE is not None:
        raise ValueError("REFERENCE_DEVICE must be None when SPLIT_REFERENCE_CHANNELS is True.")
    if BLOCK_SIZE is not None and BLOCK_SIZE <= 0:
        raise ValueError("BLOCK_SIZE must be positive.")
    if FILTER_LENGTH is not None and FILTER_LENGTH <= 0:
        raise ValueError("FILTER_LENGTH must be positive.")


def run_anc() -> None:
    controller = create_controller(
        reference_path=REFERENCE_PATH,
        secondary_path_file=SECONDARY_PATH,
        control_device=CONTROL_DEVICE,
        record_device=RECORD_DEVICE,
        reference_device=REFERENCE_DEVICE,
        split_reference_channels=SPLIT_REFERENCE_CHANNELS,
        play_reference=True,
        step_size=STEP_SIZE,
        block_size=BLOCK_SIZE,
        filter_length=FILTER_LENGTH,
    )

    def log_metrics(metrics) -> None:
        logging.info("frame=%05d error_rms=%.6f", metrics.frame_index, metrics.error_rms)

    logging.info("Starting ANC session (Ctrl+C to stop).")
    try:
        controller.run(loop_reference=DURATION is None, max_duration=DURATION, metrics_callback=log_metrics)
    except KeyboardInterrupt:
        logging.info("ANC stopped by user.")


def play_reference_only() -> None:
    play_reference(
        reference_path=REFERENCE_PATH,
        control_device=CONTROL_DEVICE,
        reference_device=REFERENCE_DEVICE,
        split_reference_channels=SPLIT_REFERENCE_CHANNELS,
        block_size=BLOCK_SIZE,
        duration=DURATION,
        loop=DURATION is None,
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    validate_config()

    if MODE == "anc":
        run_anc()
    else:
        play_reference_only()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
