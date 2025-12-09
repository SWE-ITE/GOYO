"""
Shared helper utilities for enhanced ANC entrypoints.

This module centralises common tasks such as validating device/channel
counts, handling baseline capture and freeze logic, streaming reference
audio, and measuring the secondary path.
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

# Add parent directory to path to locate Basic_ANC
sys.path.append(str(Path(__file__).resolve().parent.parent))

from Basic_ANC.session_utils import create_controller
from . import config as cfg


def resolve_device_index(device_index: Optional[int], direction: str) -> int:
    """Return an explicit device index, falling back to sounddevice defaults."""
    if device_index is not None:
        return device_index
    defaults = getattr(sd.default, "device", None)
    if not isinstance(defaults, (tuple, list)) or len(defaults) != 2:
        raise ValueError(f"No default {direction} device configured; set {direction.upper()}_DEVICE.")
    idx = defaults[0 if direction == "input" else 1]
    if idx is None or idx < 0:
        raise ValueError(f"No default {direction} device configured; set {direction.upper()}_DEVICE.")
    return int(idx)


def ensure_available_channels(
    *,
    device_index: Optional[int],
    direction: str,
    required_channels: int,
    label: str,
    detail: Optional[str] = None,
) -> None:
    """Validate that a device exposes at least the desired number of channels."""
    if required_channels <= 0:
        raise ValueError(f"{label} requires at least one {direction} channel.")
    resolved_index = resolve_device_index(device_index, direction)
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


def start_reference_playback(
    *,
    signal: np.ndarray,
    sample_rate: int,
    block_size: int,
    device_index: Optional[int],
    output_channel: Optional[int],
    loop: bool,
) -> Tuple[Optional[threading.Thread], Optional[threading.Event]]:
    """Start a background thread that continuously plays the reference signal."""
    if device_index is None:
        return None, None

    stop_event = threading.Event()
    ref_channel = 0 if output_channel is None else output_channel
    channels = max(1, ref_channel + 1)
    ensure_available_channels(
        device_index=device_index,
        direction="output",
        required_channels=channels,
        label="Reference playback device",
    )

    def _worker() -> None:
        try:
            with sd.OutputStream(
                samplerate=sample_rate,
                blocksize=block_size,
                dtype="float32",
                channels=channels,
                device=device_index,
            ) as stream:
                idx = 0
                length = len(signal)
                while not stop_event.is_set():
                    block = signal[idx : idx + block_size]
                    if len(block) < block_size:
                        if not loop:
                            block = np.pad(block, (0, block_size - len(block)))
                            stop_event.set()
                        else:
                            rem = block_size - len(block)
                            block = np.concatenate([block, signal[:rem]])
                        idx = 0
                    else:
                        idx += block_size
                        if idx >= length and loop:
                            idx = 0
                    buf = np.zeros((block_size, channels), dtype=np.float32)
                    buf[:, ref_channel] = block.astype(np.float32)
                    stream.write(buf)
        except Exception as exc:
            logging.warning("Reference playback stopped: %s", exc)

    thread = threading.Thread(target=_worker, daemon=True, name="ReferencePlayback")
    thread.start()
    return thread, stop_event


def measure_secondary_path() -> None:
    """Excite the secondary path using shared configuration and save the taps."""
    controller = create_controller(
        reference_path=None,
        control_device=cfg.CONTROL_DEVICE,
        record_device=cfg.RECORD_DEVICE,
        error_input_channel=cfg.ERROR_INPUT_CHANNEL,
        sample_rate=cfg.MEASUREMENT_SAMPLE_RATE,
        require_reference=False,
        play_reference=False,
        block_size=cfg.BLOCK_SIZE,
        filter_length=cfg.MEASUREMENT_FIR_LENGTH,
    )
    try:
        logging.info(
            "Measuring secondary path: duration=%.2fs level=%.3f taps=%d repeats=%d",
            cfg.MEASUREMENT_DURATION,
            cfg.EXCITATION_LEVEL,
            cfg.MEASUREMENT_FIR_LENGTH,
            cfg.MEASUREMENT_REPEATS,
        )
        tap_sets: list[np.ndarray] = []
        for run in range(cfg.MEASUREMENT_REPEATS):
            logging.info("Measurement run %d/%d", run + 1, cfg.MEASUREMENT_REPEATS)
            taps = controller.measure_secondary_path(
                duration=cfg.MEASUREMENT_DURATION,
                excitation_level=cfg.EXCITATION_LEVEL,
                fir_length=cfg.MEASUREMENT_FIR_LENGTH,
            )
            tap_sets.append(taps.astype(np.float32))
        averaged = (
            tap_sets[0]
            if len(tap_sets) == 1
            else np.mean(np.stack(tap_sets, axis=0), axis=0).astype(np.float32)
        )
        cfg.SECONDARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.save(cfg.SECONDARY_PATH, averaged)
        logging.info("Saved secondary path to %s", cfg.SECONDARY_PATH)
    finally:
        controller.stop()


def log_baseline_and_freeze_status(
    *,
    state: np.ndarray,
    baseline_active: bool,
    frozen: bool,
    last_log: float,
    log_interval: float,
) -> float:
    """Periodic log helper shared between runners."""
    if (time.time() - last_log) < log_interval:
        return last_log
    freq = state[3]
    amp = math.sqrt(state[4] ** 2 + state[5] ** 2)
    ref_rms = state[6]
    err_rms = state[7]
    ctrl_rms = state[8]
    status = " [baseline]" if baseline_active else " [frozen]" if frozen else ""
    logging.info(
        "freq=%.1f Hz amp=%.4f | ref=%.6f err=%.6f out=%.6f%s",
        freq,
        amp,
        ref_rms,
        err_rms,
        ctrl_rms,
        status,
    )
    return time.time()
