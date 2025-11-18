"""
Measure and save the secondary-path impulse response (speaker -> error mic).

Edit the constants below to match your setup, then run:
    python -m ANC.2ndPath_test
"""

from __future__ import annotations

import logging
from pathlib import Path
import numpy as np

from .session_utils import create_controller

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REFERENCE_PATH = "src/sine_200Hz.wav"
OUTPUT_PATH = Path(__file__).resolve().parent / "secondary_path.npy"

CONTROL_DEVICE = 3          # Output device index for the control/anti-noise speaker
RECORD_DEVICE = 1           # Input device index for the error microphone

SPLIT_REFERENCE_CHANNELS = True  # Match ANC_test.py (excitation on right channel)
DURATION = 3.0                 # Seconds of white-noise excitation per measurement
EXCITATION_LEVEL = 0.12        # Amplitude of the injected white noise
FIR_LENGTH = 256               # Number of taps to solve for
AVERAGE_COUNT = 5              # Number of repeated measurements to average

# ---------------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    controller = create_controller(
        reference_path=REFERENCE_PATH,
        control_device=CONTROL_DEVICE,
        record_device=RECORD_DEVICE,
        split_reference_channels=SPLIT_REFERENCE_CHANNELS,
        play_reference=False,
    )

    try:
        logging.info(
            "Measuring secondary path: duration=%.2f s level=%.3f taps=%d averages=%d",
            DURATION,
            EXCITATION_LEVEL,
            FIR_LENGTH,
            AVERAGE_COUNT,
        )
        tap_runs = []
        for run_idx in range(AVERAGE_COUNT):
            logging.info("Measurement %d/%d", run_idx + 1, AVERAGE_COUNT)
            taps = controller.measure_secondary_path(
                duration=DURATION,
                excitation_level=EXCITATION_LEVEL,
                fir_length=FIR_LENGTH,
            )
            tap_runs.append(taps)
        averaged_taps = np.mean(np.stack(tap_runs, axis=0), axis=0).astype(np.float32)
        np.save(OUTPUT_PATH, averaged_taps)
        logging.info("Saved secondary path to %s", OUTPUT_PATH)
    finally:
        controller.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
