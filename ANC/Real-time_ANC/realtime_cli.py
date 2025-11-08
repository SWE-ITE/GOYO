"""
Minimal real-time FxLMS runner that uses a dedicated reference microphone for
the filtered-x LMS loop.

Edit the configuration constants below to match your device indices (reference
mic, error mic, control speaker) and secondary-path measurements. Then launch
one of the modes with:

    python -m ANC.Real-time_ANC.realtime_cli [anc|preview|measure]

If no mode is provided, ``anc`` is used by default.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import sys

# Make sure the repository root is importable when executing directly.
REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ANC.Basic_ANC.fxlms_controller import AncMetrics
from ANC.Basic_ANC.session_utils import create_controller, play_reference

ANC_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REFERENCE_PATH = ANC_ROOT / "src" / "sine_200Hz.wav"
SECONDARY_PATH = ANC_ROOT / "Basic_ANC" / "secondary_path.npy"

CONTROL_DEVICE: Optional[int] = None # Anti-noise playback device
RECORD_DEVICE: Optional[int] = None # Error microphone
REFERENCE_DEVICE: Optional[int] = None # Reference playback device
REFERENCE_INPUT_DEVICE: Optional[int] = None  # Reference noise microphone

SPLIT_REFERENCE_CHANNELS = False  # Set True if REFERENCE_PATH has stereo channels (left=control, right=reference mic)
STEP_SIZE = 1e-4
BLOCK_SIZE: Optional[int] = None
FILTER_LENGTH: Optional[int] = None
PLAY_REFERENCE = False  # Play reference signal to the control speaker(Will play with my Phone)
LOOP_REFERENCE = True
RUN_DURATION: Optional[float] = None
METRICS_EVERY = 10  # Frames
REFERENCE_SAMPLE_RATE: Optional[int] = 16_000

AUTO_PREVIEW = True
PREVIEW_DURATION = 3.0  # Seconds for the optional preview
PREVIEW_LOOP = False

AUTO_MEASURE_ON_START = False  # Set True to (re)measure before running ANC
MEASUREMENT_DURATION = 3.0
EXCITATION_LEVEL = 0.12
MEASUREMENT_FIR_LENGTH = 256
MEASUREMENT_AVERAGES = 5

MODE_CHOICES = ("anc", "preview", "measure")
DEFAULT_MODE = "anc"
# ---------------------------------------------------------------------------


def validate_common_paths(mode: str) -> None:
    if not REFERENCE_PATH.exists():
        raise FileNotFoundError(f"Reference file not found: {REFERENCE_PATH}")
    if mode in {"anc", "measure"} and RECORD_DEVICE is None:
        raise ValueError("RECORD_DEVICE must be set for ANC or measurement modes.")
    if mode in {"anc", "measure"} and CONTROL_DEVICE is None:
        raise ValueError("CONTROL_DEVICE must be set for ANC or measurement modes.")
    if mode == "anc" and REFERENCE_INPUT_DEVICE is None:
        raise ValueError("REFERENCE_INPUT_DEVICE must be set for ANC mode (reference mic).")
    if mode == "anc" and REFERENCE_INPUT_DEVICE is not None and REFERENCE_SAMPLE_RATE is None:
        raise ValueError("REFERENCE_SAMPLE_RATE must be set when using the reference mic.")
    if SPLIT_REFERENCE_CHANNELS and REFERENCE_DEVICE is not None:
        raise ValueError("REFERENCE_DEVICE must be None when splitting reference channels.")


def ensure_secondary_path(mode: str) -> None:
    if SECONDARY_PATH.exists():
        return
    if not AUTO_MEASURE_ON_START and mode != "measure":
        raise FileNotFoundError(
            f"Secondary path missing: {SECONDARY_PATH}. "
            "Enable AUTO_MEASURE_ON_START or run with MODE='measure'."
        )
    measure_secondary_path()


def preview_reference() -> None:
    logging.info("Playing reference preview for %.1f seconds.", PREVIEW_DURATION)
    play_reference(
        reference_path=REFERENCE_PATH,
        control_device=CONTROL_DEVICE,
        reference_device=REFERENCE_DEVICE,
        split_reference_channels=SPLIT_REFERENCE_CHANNELS,
        block_size=BLOCK_SIZE,
        duration=None if PREVIEW_LOOP else PREVIEW_DURATION,
        loop=PREVIEW_LOOP,
    )


def run_anc() -> None:
    ensure_secondary_path("anc")
    controller = create_controller(
        reference_path=None if REFERENCE_INPUT_DEVICE is not None else REFERENCE_PATH,
        secondary_path_file=SECONDARY_PATH,
        control_device=CONTROL_DEVICE,
        record_device=RECORD_DEVICE,
        reference_device=REFERENCE_DEVICE,
        reference_input_device=REFERENCE_INPUT_DEVICE,
        split_reference_channels=SPLIT_REFERENCE_CHANNELS,
        play_reference=PLAY_REFERENCE,
        step_size=STEP_SIZE,
        block_size=BLOCK_SIZE,
        filter_length=FILTER_LENGTH,
        sample_rate=REFERENCE_SAMPLE_RATE if REFERENCE_INPUT_DEVICE is not None else None,
    )

    def log_metrics(metrics: AncMetrics) -> None:
        if METRICS_EVERY <= 0:
            return
        if metrics.frame_index % METRICS_EVERY == 0:
            logging.info("frame=%05d error_rms=%.6f", metrics.frame_index, metrics.error_rms)

    logging.info("Starting ANC session (Ctrl+C to stop).")
    try:
        controller.run(
            loop_reference=LOOP_REFERENCE,
            max_duration=RUN_DURATION,
            metrics_callback=log_metrics if METRICS_EVERY > 0 else None,
        )
    except KeyboardInterrupt:
        logging.info("ANC stopped by user.")


def measure_secondary_path() -> None:
    controller = create_controller(
        reference_path=REFERENCE_PATH,
        control_device=CONTROL_DEVICE,
        record_device=RECORD_DEVICE,
        split_reference_channels=SPLIT_REFERENCE_CHANNELS,
        play_reference=False,
        block_size=BLOCK_SIZE,
        filter_length=FILTER_LENGTH,
    )

    tap_runs = []
    try:
        logging.info(
            "Measuring secondary path: duration=%.2fs level=%.3f taps=%d averages=%d",
            MEASUREMENT_DURATION,
            EXCITATION_LEVEL,
            MEASUREMENT_FIR_LENGTH,
            MEASUREMENT_AVERAGES,
        )
        for idx in range(MEASUREMENT_AVERAGES):
            logging.info("Measurement %d/%d", idx + 1, MEASUREMENT_AVERAGES)
            taps = controller.measure_secondary_path(
                duration=MEASUREMENT_DURATION,
                excitation_level=EXCITATION_LEVEL,
                fir_length=MEASUREMENT_FIR_LENGTH,
            )
            tap_runs.append(taps)
        averaged = (
            tap_runs[0]
            if len(tap_runs) == 1
            else np.mean(np.stack(tap_runs, axis=0), axis=0)
        ).astype(np.float32)
        SECONDARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.save(SECONDARY_PATH, averaged)
        logging.info("Saved secondary path to %s", SECONDARY_PATH)
    finally:
        controller.stop()


def parse_args(argv: Optional[list[str]] = None) -> str:
    parser = argparse.ArgumentParser(
        description="Run real-time ANC workflows (anc, preview, measure).",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=MODE_CHOICES,
        default=DEFAULT_MODE,
        help="Mode to execute (default: anc).",
    )
    args = parser.parse_args(argv)
    return args.mode


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    mode = parse_args(argv)
    validate_common_paths(mode)

    if mode == "preview":
        preview_reference()
    elif mode == "measure":
        measure_secondary_path()
    elif mode == "anc":
        if AUTO_PREVIEW and PREVIEW_DURATION > 0.0:
            preview_reference()
        run_anc()
    else:
        raise ValueError(f"Unsupported MODE '{mode}'. Use 'anc', 'preview', or 'measure'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
