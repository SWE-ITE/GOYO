"""
Sweep manual gain K to find a value that reduces error RMS relative to a baseline
(ANC off). Uses the configuration from realtime_cli.py directly.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from ANC.basic_ANC.session_utils import create_controller, play_reference

CONTROL_DEVICE: Optional[int] = 10  # Anti-noise playback device
RECORD_DEVICE: Optional[int] = 10  # Aggregate device containing microphones
REFERENCE_DEVICE: Optional[int] = 10  # Dedicated reference playback device
REFERENCE_INPUT_DEVICE: Optional[int] = None  # Standalone reference microphone device index
ERROR_INPUT_CHANNEL: int = 0  # Channel on RECORD_DEVICE for the error mic
REFERENCE_INPUT_CHANNEL: Optional[int] = 1  # Channel on RECORD_DEVICE for the reference mic
CONTROL_OUTPUT_CHANNEL: int = 0  # Channel on CONTROL_DEVICE for anti-noise
REFERENCE_OUTPUT_CHANNEL: int = 2  # Channel on REFERENCE_DEVICE for reference playback

CONTROL_OUTPUT_GAIN: float = 0.5
STEP_SIZE = 1e-4
BLOCK_SIZE: Optional[int] = 64
FILTER_LENGTH: Optional[int] = 256
LOOP_REFERENCE = True
RUN_DURATION: Optional[float] = None
REFERENCE_SAMPLE_RATE: Optional[int] = 48_000
PLAY_REFERENCE = True

# Paths
from pathlib import Path  # noqa

ANC_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_PATH = ANC_ROOT / "src" / "sine_200Hz.wav"
SECONDARY_PATH = ANC_ROOT / "enhanced_ANC" / "secondary_path.npy"

# Experiment parameters (fixed here)
TRIAL_DURATION = 8.0  # seconds per trial
SKIP_INITIAL_FRAMES = 50  # ignore first N frames in averaging (settling)
SWEEP_KS = np.linspace(-1.0, 1.0, num=21, endpoint=True)  # inclusive sweep


@dataclass
class TrialResult:
    k: float
    mean_err_rms: float
    frames_used: int


def _start_reference_playback(duration: Optional[float]) -> Optional[threading.Thread]:
    use_live_reference = RECORD_DEVICE is not None and (
        REFERENCE_INPUT_DEVICE is not None or REFERENCE_INPUT_CHANNEL is not None
    )
    if not (PLAY_REFERENCE and REFERENCE_DEVICE is not None and use_live_reference):
        return None

    def _play() -> None:
        try:
            play_reference(
                reference_path=REFERENCE_PATH,
                control_device=REFERENCE_DEVICE,
                reference_device=None,
                output_channel=REFERENCE_OUTPUT_CHANNEL,
                split_reference_channels=False,
                block_size=BLOCK_SIZE,
                duration=duration,
                loop=LOOP_REFERENCE,
            )
        except OSError as exc:
            logging.warning("Reference playback failed (device %s): %s", REFERENCE_DEVICE, exc)

    t = threading.Thread(target=_play, daemon=True)
    t.start()
    return t


def _run_trial(k: float, duration: float) -> TrialResult:
    use_live_reference = REFERENCE_INPUT_DEVICE is not None or REFERENCE_INPUT_CHANNEL is not None

    metrics_err: list[float] = []  # collected after warmup

    controller = create_controller(
        reference_path=None if use_live_reference else REFERENCE_PATH,
        secondary_path_file=SECONDARY_PATH,
        control_device=CONTROL_DEVICE,
        record_device=RECORD_DEVICE,
        reference_device=None if use_live_reference else REFERENCE_DEVICE,
        reference_input_device=REFERENCE_INPUT_DEVICE,
        error_input_channel=ERROR_INPUT_CHANNEL,
        reference_input_channel=REFERENCE_INPUT_CHANNEL,
        step_size=0.0,  # no adaptation
        block_size=BLOCK_SIZE,
        filter_length=FILTER_LENGTH,
        sample_rate=REFERENCE_SAMPLE_RATE if use_live_reference else None,
        control_output_gain=CONTROL_OUTPUT_GAIN,
        control_output_channel=CONTROL_OUTPUT_CHANNEL,
        reference_output_channel=REFERENCE_OUTPUT_CHANNEL,
        play_reference=PLAY_REFERENCE and not use_live_reference,
        manual_gain_mode=True,
        manual_gain=float(k),
        leakage=0.0,
    )

    def cb(metrics) -> None:
        if metrics.frame_index >= SKIP_INITIAL_FRAMES:
            metrics_err.append(metrics.error_rms)

    try:
        controller.run(
            loop_reference=LOOP_REFERENCE,
            max_duration=duration,
            metrics_callback=cb,
        )
    except OSError as exc:
        logging.error(
            "Audio stream error (control_device=%s, record_device=%s): %s",
            CONTROL_DEVICE,
            RECORD_DEVICE,
            exc,
        )
        raise
    finally:
        pass

    if not metrics_err:
        raise RuntimeError(f"No metrics collected for K={k}; check device configuration.")

    mean_err = float(np.mean(metrics_err))
    return TrialResult(k=k, mean_err_rms=mean_err, frames_used=len(metrics_err))


def compute_baseline(duration: float) -> TrialResult:
    logging.info("Running baseline (ANC off, K=0, CONTROL_OUTPUT_GAIN=0 recommended).")
    return _run_trial(k=0.0, duration=duration)


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    total_trials = 1 + len([k for k in SWEEP_KS if abs(k) >= 1e-9])
    playback_duration = TRIAL_DURATION * total_trials if RUN_DURATION is None else RUN_DURATION
    playback_thread = _start_reference_playback(playback_duration)

    duration = TRIAL_DURATION

    baseline = compute_baseline(duration)
    logging.info("Baseline: K=%.3f mean_err_rms=%.6f (frames=%d)", baseline.k, baseline.mean_err_rms, baseline.frames_used)

    best = baseline
    for k in SWEEP_KS:
        if abs(k) < 1e-9:
            continue  # already measured baseline
        logging.info("Running trial K=%.3f", k)
        res = _run_trial(k, duration)
        logging.info("Result K=%.3f mean_err_rms=%.6f (frames=%d)", res.k, res.mean_err_rms, res.frames_used)
        if res.mean_err_rms < best.mean_err_rms:
            best = res

    logging.info(
        "Best K=%.3f mean_err_rms=%.6f (baseline=%.6f)",
        best.k,
        best.mean_err_rms,
        baseline.mean_err_rms,
    )

    if best.mean_err_rms >= baseline.mean_err_rms:
        logging.warning("No K improved on baseline. Check routing/geometry before using adaptive ANC.")

    if playback_thread is not None:
        playback_thread.join(timeout=1.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
