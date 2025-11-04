"""
Measure and save the secondary-path impulse response (speaker -> error mic).

Edit the constants below to match your setup, then run:
    python -m ANC.2ndPath_test
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from fxlms_controller import FxLMSANC

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REFERENCE_PATH = Path(__file__).resolve().parent / "src/sine_200Hz.wav"
OUTPUT_PATH = Path(__file__).resolve().parent / "secondary_path.npy"

CONTROL_DEVICE = 3          # Output device index for the control/anti-noise speaker
RECORD_DEVICE = 1           # Input device index for the error microphone

SPLIT_REFERENCE_CHANNELS = True  # Match ANC_test.py (excitation on right channel)
DURATION = 3.0                 # Seconds of white-noise excitation
EXCITATION_LEVEL = 0.12        # Amplitude of the injected white noise
FIR_LENGTH = 64                # Number of taps to solve for

# ---------------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    controller = FxLMSANC(
        reference_path=str(REFERENCE_PATH),
        control_device_index=CONTROL_DEVICE,
        record_device_index=RECORD_DEVICE,
        play_reference=False,
        split_reference_channels=SPLIT_REFERENCE_CHANNELS,
    )

    try:
        logging.info(
            "Measuring secondary path: duration=%.2f s level=%.3f taps=%d",
            DURATION,
            EXCITATION_LEVEL,
            FIR_LENGTH,
        )
        taps = controller.measure_secondary_path(
            duration=DURATION,
            excitation_level=EXCITATION_LEVEL,
            fir_length=FIR_LENGTH,
        )
        np.save(OUTPUT_PATH, taps)
        logging.info("Saved secondary path to %s", OUTPUT_PATH)
    finally:
        controller.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
