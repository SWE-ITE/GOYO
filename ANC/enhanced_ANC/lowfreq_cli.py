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

ANC_ROOT = Path(__file__).resolve().parent.parent

# Core configuration (adjust to match your hardware)
REFERENCE_PATH = ANC_ROOT / "src" / "sine_200Hz.wav"
SECONDARY_PATH = ANC_ROOT / "enhanced_ANC" / "secondary_path.npy"

CONTROL_DEVICE: Optional[int] = 10  # Anti-noise playback device
RECORD_DEVICE: Optional[int] = 10  # Aggregate device containing error+ref mics
REFERENCE_DEVICE: Optional[int] = 10  # Dedicated reference playback device
REFERENCE_INPUT_DEVICE: Optional[int] = None  # Standalone reference mic device index

ERROR_INPUT_CHANNEL: int = 0  # Channel on RECORD_DEVICE for the error mic
REFERENCE_INPUT_CHANNEL: Optional[int] = 1  # Channel on RECORD_DEVICE for the reference mic

CONTROL_OUTPUT_CHANNEL: int = 0  # Channel on CONTROL_DEVICE for anti-noise
REFERENCE_OUTPUT_CHANNEL: int = 2  # Channel on REFERENCE_DEVICE for reference playback
REFERENCE_SAMPLE_RATE: Optional[int] = 48_000  # Required when using a live reference mic

# Adaptation behaviour
REFERENCE_LOWPASS_HZ: Optional[float] = 400.0  # Low-pass cutoff to bias adaptation to LF
FILTER_LENGTH: Optional[int] = 512
BLOCK_SIZE: Optional[int] = 128
STEP_SIZE = 1e-5
LEAKAGE = 1e-6
CONTROL_OUTPUT_GAIN: float = 0.5

# Runtime options
MANUAL_GAIN_MODE = False
MANUAL_K = -0.5
LOOP_REFERENCE = True
RUN_DURATION: Optional[float] = None
PLAY_REFERENCE = True
PREROLL_SECONDS = 3.0  # For live-reference playback before ANC starts

# Metrics/logging
METRICS_EVERY = 200
REF_MIN = 0.05
SKIP_INITIAL_FRAMES = 40

# Measurement settings
MEASUREMENT_DURATION = 3.0
EXCITATION_LEVEL = 0.1
MEASUREMENT_FIR_LENGTH = 256
MEASUREMENT_SAMPLE_RATE = 48_000
MEASUREMENT_REPEATS = 5


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
    measure_secondary_path()


def run_lowfreq_anc(plot_error_live: bool = False) -> None:
    ensure_secondary_path()
    use_live_reference = live_reference_enabled()
    live_plotter = _create_live_plotter() if plot_error_live else None
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
    )

    def log_metrics(metrics: AncMetrics) -> None:
        if METRICS_EVERY <= 0:
            return
        metrics_log.append(metrics)
        if metrics.frame_index >= SKIP_INITIAL_FRAMES and metrics.reference_rms > REF_MIN:
            nonlocal err_sum, err_count
            err_sum += metrics.error_rms
            err_count += 1
        if live_plotter is not None:
            live_plotter.tick(metrics)
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
            metrics_callback=log_metrics if METRICS_EVERY > 0 else None,
        )
    except KeyboardInterrupt:
        logging.info("ANC stopped by user.")
    if live_plotter is not None:
        live_plotter.close()
    if playback_thread is not None:
        playback_thread.join(timeout=1.0)
    if metrics_log:
        mean_err = float(np.mean([m.error_rms for m in metrics_log]))
        logging.info("Session mean_err_rms=%.6f over %d frames", mean_err, len(metrics_log))


def measure_secondary_path() -> None:
    controller = create_controller(
        reference_path=None,
        control_device=CONTROL_DEVICE,
        record_device=RECORD_DEVICE,
        error_input_channel=ERROR_INPUT_CHANNEL,
        sample_rate=MEASUREMENT_SAMPLE_RATE,
        require_reference=False,
        play_reference=False,
        block_size=BLOCK_SIZE,
        filter_length=FILTER_LENGTH,
    )
    try:
        logging.info(
            "Measuring secondary path (%d runs): duration=%.2fs level=%.3f taps=%d",
            MEASUREMENT_REPEATS,
            MEASUREMENT_DURATION,
            EXCITATION_LEVEL,
            MEASUREMENT_FIR_LENGTH,
        )
        tap_sets = []
        for idx in range(MEASUREMENT_REPEATS):
            logging.info("Measurement run %d/%d", idx + 1, MEASUREMENT_REPEATS)
            taps = controller.measure_secondary_path(
                duration=MEASUREMENT_DURATION,
                excitation_level=EXCITATION_LEVEL,
                fir_length=MEASUREMENT_FIR_LENGTH,
            )
            tap_sets.append(taps)
        averaged_taps = np.mean(np.stack(tap_sets, axis=0), axis=0)
        SECONDARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.save(SECONDARY_PATH, averaged_taps)
        logging.info("Saved secondary path to %s", SECONDARY_PATH)
    finally:
        controller.stop()


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
        "--plot-error-live",
        action="store_true",
        help="Show a live-updating error RMS plot during ANC.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    validate_configuration(args.mode)
    if args.mode == "measure":
        measure_secondary_path()
    else:
        run_lowfreq_anc(plot_error_live=args.plot_error_live)
    return 0


class _LivePlotter:
    """Lightweight live plot for error RMS."""

    def __init__(self) -> None:
        import matplotlib.pyplot as plt

        plt.ion()
        self.plt = plt
        self.fig, self.ax = plt.subplots(num="Low-Frequency ANC Error RMS (live)")
        (self.line,) = self.ax.plot([], [], marker=".", linewidth=1)
        self.ax.set_xlabel("Frame")
        self.ax.set_ylabel("Error RMS")
        self.ax.grid(True, which="both", linestyle="--", alpha=0.5)
        self.fig.tight_layout()
        self.frames: list[int] = []
        self.errors: list[float] = []

    def tick(self, metrics: AncMetrics) -> None:
        self.frames.append(metrics.frame_index)
        self.errors.append(metrics.error_rms)
        self.line.set_data(self.frames, self.errors)
        if self.frames:
            self.ax.set_xlim(0, max(self.frames))
        if self.errors:
            self.ax.set_ylim(0, max(self.errors) * 1.1 if max(self.errors) > 0 else 1.0)
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        self.plt.pause(0.001)

    def close(self) -> None:
        self.plt.ioff()
        self.plt.show()


def _create_live_plotter() -> Optional["_LivePlotter"]:
    try:
        return _LivePlotter()
    except Exception as exc:  # pragma: no cover - UI helper
        logging.warning("Unable to start live plot (matplotlib unavailable): %s", exc)
        return None


if __name__ == "__main__":
    raise SystemExit(main())
