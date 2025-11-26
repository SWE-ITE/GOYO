"""
Full-auto zero-crossing ANC (Optimized Logging Version).
Moves RMS calculation inside Numba to prevent GIL contention and audio dropouts.
"""

from __future__ import annotations

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

ANC_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_PATH = ANC_ROOT / "src" / "sine_200Hz.wav"

# Sample/data setup
try:
    REFERENCE_SIGNAL, REFERENCE_SAMPLE_RATE = read_mono_wav(str(REFERENCE_PATH))
    REFERENCE_SIGNAL = REFERENCE_SIGNAL.astype(np.float32)
    REFERENCE_SAMPLE_RATE = int(REFERENCE_SAMPLE_RATE)
except Exception:
    REFERENCE_SIGNAL = np.zeros(2048, dtype=np.float32)
    REFERENCE_SAMPLE_RATE = 48_000

# Hardware configuration
CONTROL_DEVICE: Optional[int] = 9
RECORD_DEVICE: Optional[int] = 9
REFERENCE_DEVICE: Optional[int] = 9

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


def _require_non_negative(value: int, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative (got {value}).")


def _resolve_device_index(device_index: Optional[int], direction: str) -> int:
    if device_index is not None:
        return device_index
    defaults = getattr(sd.default, "device", None)
    if not isinstance(defaults, (tuple, list)) or len(defaults) != 2:
        raise ValueError(f"No default {direction} device configured; set {direction.upper()}_DEVICE.")
    idx = defaults[0 if direction == "input" else 1]
    if idx is None or idx < 0:
        raise ValueError(f"No default {direction} device configured; set {direction.upper()}_DEVICE.")
    return int(idx)


def _ensure_available_channels(
    *,
    device_index: Optional[int],
    direction: str,
    required_channels: int,
    label: str,
    detail: Optional[str] = None,
) -> None:
    if required_channels <= 0:
        raise ValueError(f"{label} requires at least one {direction} channel.")
    resolved_index = _resolve_device_index(device_index, direction)
    info = sd.query_devices(resolved_index)
    capacity_key = "max_input_channels" if direction == "input" else "max_output_channels"
    available = int(info.get(capacity_key, 0))
    if available < required_channels:
        extra = f" ({detail})" if detail else ""
        raise ValueError(
            f"{label} '{info['name']}' provides {available} {direction} channel(s), "
            f"but {required_channels} are required{extra}. "
            "Adjust the channel constants or select a compatible audio device."
        )


def _reference_output_channel_index() -> int:
    return 0 if REFERENCE_OUTPUT_CHANNEL is None else REFERENCE_OUTPUT_CHANNEL


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

        wa -= step_size * err_sample * ref_sin
        wb -= step_size * err_sample * ref_cos

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
    if not PLAY_REFERENCE or REFERENCE_DEVICE is None:
        return None, None

    stop_event = threading.Event()
    signal = REFERENCE_SIGNAL
    block_len = BLOCK_SIZE
    ref_out_channel = _reference_output_channel_index()
    channels = max(1, ref_out_channel + 1)
    _ensure_available_channels(
        device_index=REFERENCE_DEVICE,
        direction="output",
        required_channels=channels,
        label="Reference playback device",
    )

    def _worker() -> None:
        try:
            with sd.OutputStream(
                samplerate=REFERENCE_SAMPLE_RATE,
                blocksize=block_len,
                dtype="float32",
                channels=channels,
                device=REFERENCE_DEVICE,
            ) as stream:
                idx = 0
                length = len(signal)
                while not stop_event.is_set():
                    block = signal[idx : idx + block_len]
                    if len(block) < block_len:
                        if not LOOP_REFERENCE:
                            block = np.pad(block, (0, block_len - len(block)))
                            stop_event.set()
                        else:
                            rem = block_len - len(block)
                            block = np.concatenate([block, signal[:rem]])
                        idx = 0
                    else:
                        idx += block_len
                        if idx >= length and LOOP_REFERENCE:
                            idx = 0
                    buf = np.zeros((block_len, channels), dtype=np.float32)
                    buf[:, ref_out_channel] = block.astype(np.float32)
                    stream.write(buf)
        except Exception as exc:
            logging.warning("Reference playback stopped: %s", exc)

    thread = threading.Thread(target=_worker, daemon=True, name="ReferencePlayback")
    thread.start()
    return thread, stop_event


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

    input_channels = max(ERROR_INPUT_CHANNEL, REFERENCE_INPUT_CHANNEL) + 1
    output_channels = max(1, CONTROL_OUTPUT_CHANNEL + 1)
    record_detail = f"error={ERROR_INPUT_CHANNEL}, reference={REFERENCE_INPUT_CHANNEL}"
    _ensure_available_channels(
        device_index=RECORD_DEVICE,
        direction="input",
        required_channels=input_channels,
        label="Record device",
        detail=record_detail,
    )
    control_detail = f"control output index={CONTROL_OUTPUT_CHANNEL}"
    _ensure_available_channels(
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
        _smart_anc_process(
            ref_buf,
            err_buf,
            out_buf,
            state,
            float(REFERENCE_SAMPLE_RATE),
            STEP_SIZE,
            LEAKAGE,
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
    last_log = time.time()

    with stream:
        while True:
            time.sleep(0.05)
            if log_enabled and (time.time() - last_log) >= 0.5:
                # Just Read from State Array (No heavy computation here!)
                freq = state[3]
                amp = math.sqrt(state[4] ** 2 + state[5] ** 2)
                ref_rms = state[6]
                err_rms = state[7]
                ctrl_rms = state[8]
                
                logging.info(
                    "freq=%.1f Hz amp=%.4f | ref=%.3f err=%.3f out=%.3f",
                    freq,
                    amp,
                    ref_rms,
                    err_rms,
                    ctrl_rms,
                )
                last_log = time.time()


def main(argv: Optional[list[str]] = None) -> int:
    log_enabled = False
    if argv is None:
        argv = sys.argv[1:]
    if "--log" in argv:
        log_enabled = True
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    playback_thread, playback_stop = start_reference_playback()
    if PREROLL_SECONDS > 0:
        time.sleep(PREROLL_SECONDS)

    try:
        run_auto_anc(log_enabled=log_enabled)
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
