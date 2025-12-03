"""
Full-auto zero-crossing ANC (Optimized Logging Version).
Moves RMS calculation inside Numba to prevent GIL contention and audio dropouts.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd  # type: ignore
from numba import njit

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ANC.basic_ANC.fxlms_controller import read_mono_wav
from ANC.enhanced_ANC import config as cfg
from ANC.enhanced_ANC import io_utils

ANC_ROOT = cfg.ANC_ROOT
REFERENCE_PATH = cfg.REFERENCE_PATH
SECONDARY_PATH = cfg.SECONDARY_PATH

# Sample/data setup
try:
    REFERENCE_SIGNAL, REFERENCE_SAMPLE_RATE = read_mono_wav(str(REFERENCE_PATH))
    REFERENCE_SIGNAL = REFERENCE_SIGNAL.astype(np.float32)
    REFERENCE_SAMPLE_RATE = int(REFERENCE_SAMPLE_RATE)
except Exception:
    REFERENCE_SIGNAL = np.zeros(2048, dtype=np.float32)
    REFERENCE_SAMPLE_RATE = 48_000

# Shared configuration aliases
CONTROL_DEVICE = cfg.CONTROL_DEVICE
RECORD_DEVICE = cfg.RECORD_DEVICE
REFERENCE_DEVICE = cfg.REFERENCE_DEVICE
ERROR_INPUT_CHANNEL = cfg.ERROR_INPUT_CHANNEL
REFERENCE_INPUT_CHANNEL = cfg.REFERENCE_INPUT_CHANNEL
CONTROL_OUTPUT_CHANNEL = cfg.CONTROL_OUTPUT_CHANNEL
REFERENCE_OUTPUT_CHANNEL = cfg.REFERENCE_OUTPUT_CHANNEL
BLOCK_SIZE = cfg.BLOCK_SIZE
STEP_SIZE = cfg.STEP_SIZE
LEAKAGE = cfg.LEAKAGE
PLAY_REFERENCE = cfg.PLAY_REFERENCE
PREROLL_SECONDS = cfg.PREROLL_SECONDS
LOOP_REFERENCE = cfg.LOOP_REFERENCE
BASELINE_MEASURE_SECONDS = cfg.BASELINE_MEASURE_SECONDS
WEIGHT_UPDATE_SIGN = cfg.WEIGHT_UPDATE_SIGN
FREEZE_ADAPTATION = cfg.FREEZE_ADAPTATION
FREEZE_RELATIVE_DROP = cfg.FREEZE_RELATIVE_DROP
FREEZE_MIN_SECONDS = cfg.FREEZE_MIN_SECONDS
FREEZE_BASELINE_MIN_ERR = cfg.FREEZE_BASELINE_MIN_ERR
MEASUREMENT_DURATION = cfg.MEASUREMENT_DURATION
EXCITATION_LEVEL = cfg.EXCITATION_LEVEL
MEASUREMENT_FIR_LENGTH = cfg.MEASUREMENT_FIR_LENGTH
MEASUREMENT_SAMPLE_RATE = cfg.MEASUREMENT_SAMPLE_RATE
MEASUREMENT_REPEATS = cfg.MEASUREMENT_REPEATS


def _require_non_negative(value: int, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative (got {value}).")


@njit(cache=True, fastmath=True)
def _smart_anc_process(
    ref_block: np.ndarray,
    err_block: np.ndarray,
    out_block: np.ndarray,
    state: np.ndarray,  # [prev, phase, samples, freq, wa, wb, ref_rms, err_rms, out_rms]
    sample_rate: float,
    step_size: float,
    leakage: float,
) -> None:
    # Load state
    prev_ref = state[0]
    phase = state[1]
    samples_since = state[2]
    freq_hz = state[3]
    wa = state[4]
    wb = state[5]
    
    alpha = 0.1
    n = len(ref_block)
    
    # RMS Accumulators
    sum_ref_sq = 0.0
    sum_err_sq = 0.0
    sum_out_sq = 0.0

    for i in range(n):
        ref_sample = ref_block[i]
        err_sample = err_block[i]
        
        # Accumulate RMS stats (Cost-free inside loop)
        sum_ref_sq += ref_sample * ref_sample
        sum_err_sq += err_sample * err_sample

        # --- Zero Crossing Logic ---
        crossing = False
        if ref_sample >= 0.0 and prev_ref < 0.0:
            crossing = True
        elif ref_sample < 0.0 and prev_ref >= 0.0:
            crossing = True

        if crossing and samples_since > 1:
            half_period = float(samples_since)
            freq_est = sample_rate / (2.0 * half_period)
            if 50.0 < freq_est < 1000.0:
                freq_hz = (1.0 - alpha) * freq_hz + alpha * freq_est
            samples_since = 0

        omega = 2.0 * math.pi * freq_hz / sample_rate

        # --- Synthesis & LMS ---
        ref_sin = math.sin(phase)
        ref_cos = math.cos(phase)

        anti_noise = wa * ref_sin + wb * ref_cos

        wa += WEIGHT_UPDATE_SIGN * step_size * err_sample * ref_sin
        wb += WEIGHT_UPDATE_SIGN * step_size * err_sample * ref_cos

        wa *= (1.0 - leakage)
        wb *= (1.0 - leakage)

        # Clip output
        if anti_noise > 1.0:
            anti_noise = 1.0
        elif anti_noise < -1.0:
            anti_noise = -1.0
        out_block[i] = anti_noise
        
        sum_out_sq += anti_noise * anti_noise

        phase += omega
        if phase > 2.0 * math.pi:
            phase -= 2.0 * math.pi

        prev_ref = ref_sample
        samples_since += 1

    # Save state
    state[0] = prev_ref
    state[1] = phase
    state[2] = samples_since
    state[3] = freq_hz
    state[4] = wa
    state[5] = wb
    
    # Store calculated RMS in state (Slots 6, 7, 8)
    # Main thread just reads these, avoiding computation overhead.
    state[6] = math.sqrt(sum_ref_sq / n)
    state[7] = math.sqrt(sum_err_sq / n)
    state[8] = math.sqrt(sum_out_sq / n)


def start_reference_playback() -> Tuple[Optional[threading.Thread], Optional[threading.Event]]:
    if not PLAY_REFERENCE:
        return None, None
    return io_utils.start_reference_playback(
        signal=REFERENCE_SIGNAL,
        sample_rate=REFERENCE_SAMPLE_RATE,
        block_size=BLOCK_SIZE,
        device_index=REFERENCE_DEVICE,
        output_channel=REFERENCE_OUTPUT_CHANNEL,
        loop=LOOP_REFERENCE,
    )


def run_auto_anc(log_enabled: bool) -> None:
    _require_non_negative(ERROR_INPUT_CHANNEL, "ERROR_INPUT_CHANNEL")
    _require_non_negative(REFERENCE_INPUT_CHANNEL, "REFERENCE_INPUT_CHANNEL")
    _require_non_negative(CONTROL_OUTPUT_CHANNEL, "CONTROL_OUTPUT_CHANNEL")

    # Increased state size to 9 to hold RMS values
    # [0-5]: Logic vars, [6]: Ref RMS, [7]: Err RMS, [8]: Out RMS
    state = np.zeros(9, dtype=np.float64)
    state[3] = 200.0  # Initial freq
    state[2] = 100.0  # Initial samples_since
    
    ref_buf = np.zeros(BLOCK_SIZE, dtype=np.float32)
    err_buf = np.zeros(BLOCK_SIZE, dtype=np.float32)
    out_buf = np.zeros(BLOCK_SIZE, dtype=np.float32)

    baseline_duration = max(0.0, BASELINE_MEASURE_SECONDS)
    baseline_active = baseline_duration > 0.0
    adaptation_active = not baseline_active
    baseline_sum = 0.0
    baseline_count = 0
    baseline_err: Optional[float] = None
    best_err = float("inf")
    freeze_announced = False
    input_channels = max(ERROR_INPUT_CHANNEL, REFERENCE_INPUT_CHANNEL) + 1
    output_channels = max(1, CONTROL_OUTPUT_CHANNEL + 1)
    record_detail = f"error={ERROR_INPUT_CHANNEL}, reference={REFERENCE_INPUT_CHANNEL}"
    io_utils.ensure_available_channels(
        device_index=RECORD_DEVICE,
        direction="input",
        required_channels=input_channels,
        label="Record device",
        detail=record_detail,
    )
    control_detail = f"control output index={CONTROL_OUTPUT_CHANNEL}"
    io_utils.ensure_available_channels(
        device_index=CONTROL_DEVICE,
        direction="output",
        required_channels=output_channels,
        label="Control device",
        detail=control_detail,
    )
    status_flag: Optional[sd.CallbackFlags] = None

    def audio_callback(indata, outdata, frames, time_info, status):  # type: ignore[override]
        nonlocal status_flag
        if status and status_flag is None:
            status_flag = status
        if frames != BLOCK_SIZE:
            outdata.fill(0.0)
            return
            
        # Copy to pre-allocated buffers (Safe)
        ref_buf[:] = indata[:, REFERENCE_INPUT_CHANNEL]
        err_buf[:] = indata[:, ERROR_INPUT_CHANNEL]
        
        # Run Numba (includes RMS calc)
        step_size = STEP_SIZE if adaptation_active else 0.0
        leakage = LEAKAGE if adaptation_active else 0.0
        _smart_anc_process(
            ref_buf,
            err_buf,
            out_buf,
            state,
            float(REFERENCE_SAMPLE_RATE),
            step_size,
            leakage,
        )
        outdata.fill(0.0)
        outdata[:, CONTROL_OUTPUT_CHANNEL] = out_buf

    stream = sd.Stream(
        samplerate=REFERENCE_SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        dtype="float32",
        channels=(input_channels, output_channels),
        device=(RECORD_DEVICE, CONTROL_DEVICE),
        callback=audio_callback,
    )

    logging.info("Auto zero-cross ANC started.")
    if baseline_active:
        logging.info(
            "Capturing baseline noise for %.2f s before enabling ANC.",
            baseline_duration,
        )
    last_log = time.time()
    baseline_start = last_log
    anc_enabled_at: Optional[float] = None if baseline_active else baseline_start

    with stream:
        while True:
            time.sleep(0.05)
            now = time.time()
            err_rms = float(state[7])

            if baseline_active:
                baseline_sum += err_rms
                baseline_count += 1
                if (now - baseline_start) >= baseline_duration:
                    measured = baseline_sum / max(1, baseline_count)
                    baseline_err = max(measured, FREEZE_BASELINE_MIN_ERR)
                    baseline_active = False
                    adaptation_active = True
                    best_err = baseline_err
                    anc_enabled_at = now
                    logging.info(
                        "Baseline captured over %.2f s (err_rms=%.6f). Enabling ANC.",
                        baseline_duration,
                        baseline_err,
                    )
            else:
                if baseline_err is None and err_rms > FREEZE_BASELINE_MIN_ERR:
                    baseline_err = err_rms
                    best_err = err_rms
                if err_rms > FREEZE_BASELINE_MIN_ERR and err_rms < best_err:
                    best_err = err_rms

            if (
                FREEZE_ADAPTATION
                and adaptation_active
                and not baseline_active
                and baseline_err is not None
                and anc_enabled_at is not None
                and (now - anc_enabled_at) >= FREEZE_MIN_SECONDS
                and best_err < float("inf")
            ):
                improvement = (baseline_err - best_err) / baseline_err
                if improvement >= FREEZE_RELATIVE_DROP:
                    adaptation_active = False
                    freeze_announced = True
                    logging.info(
                        "Freezing adaptation after %.2f s: err_rms improved from %.6f to %.6f (%.1f%% drop).",
                        now - anc_enabled_at,
                        baseline_err,
                        best_err,
                        improvement * 100.0,
                    )

            if log_enabled and (now - last_log) >= 0.5:
                freq = state[3]
                amp = math.sqrt(state[4] ** 2 + state[5] ** 2)
                ref_rms = state[6]
                ctrl_rms = state[8]
                status = ""
                if baseline_active:
                    status = " [baseline]"
                elif freeze_announced and not adaptation_active:
                    status = " [frozen]"
                logging.info(
                    "freq=%.1f Hz amp=%.4f | ref=%.6f err=%.6f out=%.6f%s",
                    freq,
                    amp,
                    ref_rms,
                    err_rms,
                    ctrl_rms,
                    status,
                )
                last_log = now


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full-auto zero-crossing ANC runner or secondary-path measurement tool.",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("anc", "measure"),
        default="anc",
        help="Select 'anc' (default) to run cancellation or 'measure' to capture the secondary path.",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Enable periodic RMS logging while running ANC.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.mode == "measure":
        io_utils.measure_secondary_path()
        return 0

    playback_thread, playback_stop = start_reference_playback()
    if PREROLL_SECONDS > 0:
        time.sleep(PREROLL_SECONDS)

    try:
        run_auto_anc(log_enabled=args.log)
    except KeyboardInterrupt:
        logging.info("ANC stopped by user.")
    finally:
        if playback_stop:
            playback_stop.set()
        if playback_thread:
            playback_thread.join(timeout=1.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
