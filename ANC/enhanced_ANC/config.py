"""
Shared configuration values for enhanced ANC entrypoints.

Keeping these constants in one module ensures that tools such as the
zero-crossing and low-frequency runners operate with identical hardware,
channel, and adaptation parameters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

ANC_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_PATH = ANC_ROOT / "src" / "sine_200Hz.wav"
SECONDARY_PATH = ANC_ROOT / "enhanced_ANC" / "secondary_path.npy"

# Hardware configuration
CONTROL_DEVICE: Optional[int] = 9
RECORD_DEVICE: Optional[int] = 9
REFERENCE_DEVICE: Optional[int] = 9
REFERENCE_INPUT_DEVICE: Optional[int] = None

# Channel mapping
ERROR_INPUT_CHANNEL = 0
REFERENCE_INPUT_CHANNEL = 1
CONTROL_OUTPUT_CHANNEL = 0
REFERENCE_OUTPUT_CHANNEL = None

# Algorithm configuration
BLOCK_SIZE = 64
STEP_SIZE = 5e-3
LEAKAGE = 1e-6
PLAY_REFERENCE = False
PREROLL_SECONDS = False
LOOP_REFERENCE = True
BASELINE_MEASURE_SECONDS = 1.0

# Weight update behaviour (+ => add, - => subtract)
WEIGHT_UPDATE_SIGN = -1.0  # Set to +1.0 to flip LMS direction.
if WEIGHT_UPDATE_SIGN not in (-1.0, 1.0):
    raise ValueError("WEIGHT_UPDATE_SIGN must be either +1.0 or -1.0.")

# Adaptation freeze configuration
FREEZE_ADAPTATION = True
FREEZE_RELATIVE_DROP = 0.15
FREEZE_MIN_SECONDS = 2.0
FREEZE_BASELINE_MIN_ERR = 1e-6

# Secondary path measurement configuration
MEASUREMENT_DURATION = 3.0
EXCITATION_LEVEL = 0.1
MEASUREMENT_FIR_LENGTH = 256
MEASUREMENT_SAMPLE_RATE = 48_000
MEASUREMENT_REPEATS = 4

# Low-frequency controller specifics
REFERENCE_LOWPASS_HZ: Optional[float] = 210.0
CONTROL_OUTPUT_GAIN: float = 2.0
REFERENCE_SAMPLE_RATE: Optional[int] = 48_000
MANUAL_GAIN_MODE = False
MANUAL_K = -0.4
RUN_DURATION: Optional[float] = None
METRICS_EVERY = 200
REF_MIN = 0.05
SKIP_INITIAL_FRAMES = 40
