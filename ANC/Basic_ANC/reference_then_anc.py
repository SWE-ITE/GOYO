"""
Play the reference noise alone for a short preview, then switch to ANC.

Configuration below is hard-coded; adjust to match your setup and run:
    python -m ANC.reference_then_anc
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .session_utils import create_controller, play_reference

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REFERENCE_PATH = "src/sine_200Hz.wav"
SECONDARY_PATH = Path(__file__).resolve().parent / "secondary_path.npy"

CONTROL_DEVICE = 3
RECORD_DEVICE = 1
REFERENCE_DEVICE: Optional[int] = None

SPLIT_REFERENCE_CHANNELS = True  # Left = reference, right = anti-noise
STEP_SIZE = 1e-4
BLOCK_SIZE: Optional[int] = None
FILTER_LENGTH: Optional[int] = None

REFERENCE_PREVIEW_SECONDS = 3.0
ANC_DURATION: Optional[float] = None  # None = run until Ctrl+C after preview
# ---------------------------------------------------------------------------


def play_reference_preview() -> None:
    play_reference(
        reference_path=REFERENCE_PATH,
        control_device=CONTROL_DEVICE,
        reference_device=REFERENCE_DEVICE,
        split_reference_channels=SPLIT_REFERENCE_CHANNELS,
        block_size=BLOCK_SIZE,
        duration=REFERENCE_PREVIEW_SECONDS,
        loop=True,
    )


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
        controller.run(loop_reference=ANC_DURATION is None, max_duration=ANC_DURATION, metrics_callback=log_metrics)
    except KeyboardInterrupt:
        logging.info("ANC stopped by user.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Playing reference preview for %.1f seconds.", REFERENCE_PREVIEW_SECONDS)
    play_reference_preview()
    logging.info("Preview finished. Switching to ANC...")
    run_anc()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
