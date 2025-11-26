"""
Low-frequency-focused ANC runner.

This entrypoint reuses the existing FxLMS controller but applies a 1-pole
low-pass to the reference so adaptation concentrates on low-frequency
content (where most steady-state disturbances live). Use "anc" to run the
loop or "measure" to generate a secondary-path estimate saved beside this
module.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

# Ensure repository root is importable when executed directly.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ANC.basic_ANC.fxlms_controller import AncMetrics
from ANC.basic_ANC.session_utils import create_controller, play_reference
from ANC.enhanced_ANC import config as cfg
from ANC.enhanced_ANC import io_utils
from ANC.enhanced_ANC.fxlms_controller_numba import NumbaFxLMSANC

REFERENCE_PATH = cfg.REFERENCE_PATH
SECONDARY_PATH = cfg.SECONDARY_PATH
CONTROL_DEVICE = cfg.CONTROL_DEVICE
RECORD_DEVICE = cfg.RECORD_DEVICE
REFERENCE_DEVICE = cfg.REFERENCE_DEVICE
REFERENCE_INPUT_DEVICE = cfg.REFERENCE_INPUT_DEVICE
ERROR_INPUT_CHANNEL = cfg.ERROR_INPUT_CHANNEL
REFERENCE_INPUT_CHANNEL = cfg.REFERENCE_INPUT_CHANNEL
CONTROL_OUTPUT_CHANNEL = cfg.CONTROL_OUTPUT_CHANNEL
REFERENCE_OUTPUT_CHANNEL = cfg.REFERENCE_OUTPUT_CHANNEL
REFERENCE_SAMPLE_RATE = cfg.REFERENCE_SAMPLE_RATE
REFERENCE_LOWPASS_HZ = cfg.REFERENCE_LOWPASS_HZ
FILTER_LENGTH: Optional[int] = 256
BLOCK_SIZE = cfg.BLOCK_SIZE
STEP_SIZE = cfg.STEP_SIZE
LEAKAGE = cfg.LEAKAGE
CONTROL_OUTPUT_GAIN = cfg.CONTROL_OUTPUT_GAIN
MANUAL_GAIN_MODE = cfg.MANUAL_GAIN_MODE
MANUAL_K = cfg.MANUAL_K
LOOP_REFERENCE = cfg.LOOP_REFERENCE
RUN_DURATION = cfg.RUN_DURATION
PLAY_REFERENCE = cfg.PLAY_REFERENCE
PREROLL_SECONDS = cfg.PREROLL_SECONDS
METRICS_EVERY = cfg.METRICS_EVERY
REF_MIN = cfg.REF_MIN
SKIP_INITIAL_FRAMES = cfg.SKIP_INITIAL_FRAMES
MEASUREMENT_DURATION = cfg.MEASUREMENT_DURATION
EXCITATION_LEVEL = cfg.EXCITATION_LEVEL
MEASUREMENT_FIR_LENGTH = cfg.MEASUREMENT_FIR_LENGTH
MEASUREMENT_SAMPLE_RATE = cfg.MEASUREMENT_SAMPLE_RATE
MEASUREMENT_REPEATS = cfg.MEASUREMENT_REPEATS


def live_reference_enabled() -> bool:
    return REFERENCE_INPUT_DEVICE is not None or REFERENCE_INPUT_CHANNEL is not None


def validate_configuration(mode: str) -> None:
    if CONTROL_DEVICE is None or RECORD_DEVICE is None:
        raise ValueError("Set CONTROL_DEVICE and RECORD_DEVICE before running ANC.")
    if mode == "anc" and PLAY_REFERENCE and REFERENCE_DEVICE is None and not live_reference_enabled():
        raise ValueError("Set REFERENCE_DEVICE when PLAY_REFERENCE is True and not using a live reference mic.")
    if REFERENCE_INPUT_DEVICE is not None and REFERENCE_INPUT_CHANNEL is not None:
        raise ValueError("Set only one of REFERENCE_INPUT_DEVICE or REFERENCE_INPUT_CHANNEL.")
    if mode == "anc" and PLAY_REFERENCE and not REFERENCE_PATH.exists():
        raise FileNotFoundError(f"Reference file not found: {REFERENCE_PATH}")
    if live_reference_enabled() and REFERENCE_SAMPLE_RATE is None:
        raise ValueError("REFERENCE_SAMPLE_RATE must be set when using a live reference mic.")


def ensure_secondary_path() -> None:
    if SECONDARY_PATH.exists():
        return
    logging.info("Secondary path missing; measuring now to %s", SECONDARY_PATH)
    io_utils.measure_secondary_path()


def run_lowfreq_anc(log_metrics: bool = False) -> None:
    ensure_secondary_path()
    use_live_reference = live_reference_enabled()
    playback_thread: Optional[threading.Thread] = None
    metrics_log: list[AncMetrics] = []
    err_sum = 0.0
    err_count = 0
    controller_play_reference = PLAY_REFERENCE and not use_live_reference
    preroll_used = False

    if PLAY_REFERENCE and REFERENCE_DEVICE is not None and use_live_reference:
        def _play_ref() -> None:
            play_reference(
                reference_path=REFERENCE_PATH,
                control_device=REFERENCE_DEVICE,
                reference_device=None,
                output_channel=REFERENCE_OUTPUT_CHANNEL,
                split_reference_channels=False,
                block_size=BLOCK_SIZE,
                duration=RUN_DURATION,
                loop=LOOP_REFERENCE,
            )

        playback_thread = threading.Thread(target=_play_ref, daemon=True)
        playback_thread.start()
        if PREROLL_SECONDS and PREROLL_SECONDS > 0:
            preroll_used = True
            logging.info("Prerolling reference for %.1f s before ANC starts.", PREROLL_SECONDS)
            time.sleep(PREROLL_SECONDS)

    controller = create_controller(
        reference_path=None if use_live_reference else REFERENCE_PATH,
        secondary_path_file=SECONDARY_PATH,
        control_device=CONTROL_DEVICE,
        record_device=RECORD_DEVICE,
        reference_device=None if use_live_reference else REFERENCE_DEVICE,
        reference_input_device=REFERENCE_INPUT_DEVICE,
        error_input_channel=ERROR_INPUT_CHANNEL,
        reference_input_channel=REFERENCE_INPUT_CHANNEL,
        step_size=STEP_SIZE,
        block_size=BLOCK_SIZE,
        filter_length=FILTER_LENGTH,
        sample_rate=REFERENCE_SAMPLE_RATE if use_live_reference else None,
        control_output_gain=CONTROL_OUTPUT_GAIN,
        control_output_channel=CONTROL_OUTPUT_CHANNEL,
        reference_output_channel=REFERENCE_OUTPUT_CHANNEL,
        play_reference=controller_play_reference,
        manual_gain_mode=MANUAL_GAIN_MODE,
        manual_gain=MANUAL_K,
        leakage=LEAKAGE,
        reference_lowpass_hz=REFERENCE_LOWPASS_HZ,
        controller_cls=NumbaFxLMSANC,
    )

    def log_metrics_cb(metrics: AncMetrics) -> None:
        if not log_metrics or METRICS_EVERY <= 0:
            return
        metrics_log.append(metrics)
        if metrics.frame_index >= SKIP_INITIAL_FRAMES and metrics.reference_rms > REF_MIN:
            nonlocal err_sum, err_count
            err_sum += metrics.error_rms
            err_count += 1
        if metrics.frame_index % METRICS_EVERY == 0:
            logging.info(
                "frame=%05d err_rms=%.6f ref_rms=%.6f out_rms=%.6f",
                metrics.frame_index,
                metrics.error_rms,
                metrics.reference_rms,
                metrics.output_rms,
            )

    logging.info(
        "Starting low-frequency ANC (Ctrl+C to stop). LPF=%s Hz preroll=%s",
        f"{REFERENCE_LOWPASS_HZ:.1f}" if REFERENCE_LOWPASS_HZ else "off",
        f"{PREROLL_SECONDS}s" if preroll_used else "none",
    )
    try:
        controller.run(
            loop_reference=LOOP_REFERENCE,
            max_duration=RUN_DURATION,
            metrics_callback=log_metrics_cb if log_metrics and METRICS_EVERY > 0 else None,
        )
    except KeyboardInterrupt:
        logging.info("ANC stopped by user.")
    if playback_thread is not None:
        playback_thread.join(timeout=1.0)
    if log_metrics and metrics_log:
        mean_err = float(np.mean([m.error_rms for m in metrics_log]))
        logging.info("Session mean_err_rms=%.6f over %d frames", mean_err, len(metrics_log))


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run low-frequency-focused ANC (anc or measure).",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("anc", "measure"),
        default="anc",
        help="Mode to execute (default: anc).",
    )
    parser.add_argument(
        "--log-metrics",
        action="store_true",
        help="Periodically log RMS metrics instead of staying quiet.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    validate_configuration(args.mode)
    if args.mode == "measure":
        io_utils.measure_secondary_path()
    else:
        run_lowfreq_anc(log_metrics=args.log_metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
