"""
Shared helpers for ANC scripts in ``Basic_ANC``.

These utilities centralise common tasks such as loading the secondary-path
estimate, constructing the FxLMS controller, and streaming the reference
signal through PyAudio. The goal is to keep the runnable entrypoints small
and focused on orchestration rather than boilerplate.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Type

import numpy as np
import sounddevice as sd  # type: ignore

from .fxlms_controller import DEFAULT_BLOCK_SIZE, FxLMSANC, read_mono_wav


def load_secondary_path(path: Path) -> np.ndarray:
    """Load a saved secondary-path impulse response."""
    if not path.exists():
        raise FileNotFoundError(f"Secondary path file not found: {path}")
    taps = np.load(path)
    if taps.ndim != 1:
        raise ValueError("Secondary path taps must be a 1-D array")
    return taps.astype(np.float32)


def create_controller(
    reference_path: Optional[Path],
    *,
    secondary_path_file: Optional[Path] = None,
    control_device: Optional[int] = None,
    record_device: Optional[int] = None,
    reference_device: Optional[int] = None,
    reference_input_device: Optional[int] = None,
    error_input_channel: int = 0,
    reference_input_channel: Optional[int] = None,
    control_output_gain: float = 1.0,
    require_reference: bool = True,
    control_output_channel: int = 0,
    reference_output_channel: int = 0,
    split_reference_channels: bool = False,
    play_reference: bool = False,
    step_size: float = 5e-4,
    block_size: Optional[int] = None,
    filter_length: Optional[int] = None,
    sample_rate: Optional[int] = None,
    manual_gain_mode: bool = False,
    manual_gain: float = 0.0,
    leakage: float = 1e-4,
    reference_lowpass_hz: Optional[float] = None,
    controller_cls: Type[FxLMSANC] = FxLMSANC,
) -> FxLMSANC:
    """
    Construct an ``FxLMSANC`` instance with shared configuration defaults.
    """
    init_kwargs = {
        "control_device_index": control_device,
        "record_device_index": record_device,
        "reference_device_index": reference_device,
        "split_reference_channels": split_reference_channels,
        "play_reference": play_reference,
        "step_size": step_size,
        "error_channel_index": error_input_channel,
        "control_output_gain": control_output_gain,
        "require_reference": require_reference,
        "control_output_channel": control_output_channel,
        "reference_output_channel": reference_output_channel,
        "manual_gain_mode": manual_gain_mode,
        "manual_gain": manual_gain,
        "leakage": leakage,
    }
    if reference_path is not None:
        init_kwargs["reference_path"] = str(reference_path)
    if reference_input_device is not None:
        init_kwargs["reference_input_device_index"] = reference_input_device
    if reference_input_channel is not None:
        init_kwargs["reference_channel_index"] = reference_input_channel
    if secondary_path_file is not None:
        init_kwargs["secondary_path"] = load_secondary_path(secondary_path_file)
    if block_size is not None:
        init_kwargs["block_size"] = block_size
    if filter_length is not None:
        init_kwargs["filter_length"] = filter_length
    if sample_rate is not None:
        init_kwargs["sample_rate"] = sample_rate
    if reference_lowpass_hz is not None:
        init_kwargs["reference_lowpass_hz"] = reference_lowpass_hz

    return controller_cls(**init_kwargs)


def play_reference(
    reference_path: Path,
    *,
    control_device: Optional[int],
    reference_device: Optional[int],
    output_channel: int = 0,
    split_reference_channels: bool,
    block_size: Optional[int],
    duration: Optional[float],
    loop: bool,
) -> None:
    """
    Stream the reference signal to the specified output(s).
    """
    signal, sample_rate = read_mono_wav(str(reference_path))
    block_len = block_size if block_size is not None else DEFAULT_BLOCK_SIZE

    ctrl_channels = 2 if split_reference_channels else max(1, output_channel + 1)
    control_stream = sd.OutputStream(
        samplerate=sample_rate,
        blocksize=block_len,
        dtype="float32",
        device=control_device,
        channels=ctrl_channels,
    )
    control_stream.start()
    reference_stream = None
    ref_channels = None
    if reference_device is not None:
        ref_channels = max(1, output_channel + 1)
        reference_stream = sd.OutputStream(
            samplerate=sample_rate,
            blocksize=block_len,
            dtype="float32",
            device=reference_device,
            channels=ref_channels,
        )
        reference_stream.start()

    index = 0
    start_time = time.time()
    try:
        while True:
            if duration is not None and (time.time() - start_time) >= duration:
                break

            block = signal[index : index + block_len]
            if len(block) == 0:
                if loop:
                    index = 0
                    continue
                break

            if len(block) < block_len:
                block = np.pad(block, (0, block_len - len(block))).astype(np.float32)
            else:
                block = np.array(block, dtype=np.float32, copy=False)

            if split_reference_channels:
                stereo = np.zeros((block_len, 2), dtype=np.float32)
                stereo[:, 0] = block
                control_stream.write(stereo)
            else:
                ctrl_buf = np.zeros((block_len, ctrl_channels), dtype=np.float32)
                ctrl_buf[:, output_channel] = block
                control_stream.write(ctrl_buf)

            if reference_stream is not None:
                ref_buf = np.zeros((block_len, ref_channels), dtype=np.float32)
                ref_buf[:, output_channel] = block
                reference_stream.write(ref_buf)

            index += block_len
            if index >= len(signal):
                if loop:
                    index = 0
                else:
                    break
    finally:
        control_stream.stop()
        control_stream.close()
        if reference_stream:
            reference_stream.stop()
            reference_stream.close()
