from __future__ import annotations

import argparse
import logging
import math
import os
import sys
import time
import wave
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

import numpy as np
import pyaudio  # type: ignore


DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_FILTER_LENGTH = 128
DEFAULT_BLOCK_SIZE = 128
EPSILON = 1e-9  # Small constant to avoid divide-by-zero


@dataclass
class AncMetrics:
    """Lightweight container for streaming diagnostics."""

    frame_index: int
    error_rms: float
    step_size: float
    reference_rms: float
    output_rms: float


def read_mono_wav(path: str) -> Tuple[np.ndarray, int]:
    """Load a WAV file as a float32 mono array in the range [-1, 1]."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Reference audio not found: {path}")

    with wave.open(path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        n_frames = wav_file.getnframes()
        raw = wav_file.readframes(n_frames)

    if sample_width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width * 8} bits")

    if channels > 1:
        data = data.reshape(-1, channels)[:, 0]

    return data, sample_rate


class FxLMSANC:
    """Adaptive ANC controller using the Filtered-x LMS algorithm."""

    def __init__(
        self,
        reference_path: Optional[str] = None,
        sample_rate: Optional[int] = None,
        filter_length: int = DEFAULT_FILTER_LENGTH,
        step_size: float = 5e-4,
        block_size: int = DEFAULT_BLOCK_SIZE,
        secondary_path: Optional[np.ndarray] = None,
        control_device_index: Optional[int] = None,
        record_device_index: Optional[int] = None,
        reference_device_index: Optional[int] = None,
        reference_input_device_index: Optional[int] = None,
        error_channel_index: int = 0,
        reference_channel_index: Optional[int] = None,
        split_reference_channels: bool = False,
        play_reference: bool = False,
        control_output_gain: float = 1.0,
        control_output_channel: int = 0,
        reference_output_channel: int = 0,
        normalize_step: bool = True,
        require_reference: bool = True,
        leakage: float = 1e-4,
        manual_gain_mode: bool = False,
        manual_gain: float = 0.0,
        reference_lowpass_hz: Optional[float] = None,
    ):
        if (
            reference_path is None
            and reference_input_device_index is None
            and reference_channel_index is None
            and require_reference
        ):
            raise ValueError(
                "Provide reference_path or a live reference source (reference_input_device_index or reference_channel_index)."
            )

        if (
            reference_input_device_index is not None
            and reference_channel_index is not None
        ):
            raise ValueError(
                "Specify either reference_input_device_index or reference_channel_index, not both."
            )

        self.block_size = block_size
        self.filter_length = filter_length
        self.base_step_size = step_size
        self.normalize_step = normalize_step
        self.play_reference = play_reference
        self.split_reference_channels = split_reference_channels
        self.control_output_gain = control_output_gain
        self.control_output_channel = control_output_channel
        self.reference_output_channel = reference_output_channel
        self.leakage = leakage
        self.manual_gain_mode = manual_gain_mode
        self.manual_gain = manual_gain
        self.reference_lowpass_hz = (
            reference_lowpass_hz if reference_lowpass_hz and reference_lowpass_hz > 0.0 else None
        )
        self._reference_lowpass_alpha: Optional[float] = None
        self._reference_lowpass_state = 0.0

        self.reference_input_device_index = reference_input_device_index
        self.reference_channel_index = reference_channel_index
        self.error_channel_index = error_channel_index
        self._reference_from_record_stream = reference_channel_index is not None
        self._live_reference = (
            self.reference_input_device_index is not None or self._reference_from_record_stream
        )

        if reference_path is not None:
            self.reference_signal, ref_rate = read_mono_wav(reference_path)
            self.sample_rate = sample_rate or ref_rate
            if self.sample_rate != ref_rate:
                raise ValueError(
                    f"Reference sample rate ({ref_rate} Hz) does not match "
                    f"requested {self.sample_rate} Hz. Resample the file before use."
                )
        else:
            if sample_rate is None:
                raise ValueError(
                    "sample_rate must be provided when using a live reference microphone."
                )
            self.sample_rate = sample_rate
            self.reference_signal = np.zeros(self.block_size, dtype=np.float32)
        self._configure_reference_lowpass()

        if secondary_path is None:
            # Use a single-sample delta if no model is provided.
            self.secondary_path = np.zeros(8, dtype=np.float32)
            self.secondary_path[0] = 1.0
        else:
            self.secondary_path = np.array(secondary_path, dtype=np.float32)

        if self.secondary_path.ndim != 1:
            raise ValueError("secondary_path must be a 1-D array")

        if self._reference_from_record_stream and record_device_index is None:
            raise ValueError(
                "record_device_index is required when reference_channel_index is provided."
            )

        self.control_device_index = control_device_index
        self.record_device_index = record_device_index
        self.reference_device_index = reference_device_index
        record_channel_count = max(
            self.error_channel_index,
            self.reference_channel_index if self.reference_channel_index is not None else -1,
        )
        self.record_channels = record_channel_count + 1

        if self.split_reference_channels and self.reference_device_index is not None:
            raise ValueError(
                "Cannot set reference_device_index when split_reference_channels is True."
            )

        self._audio = pyaudio.PyAudio()
        self._control_stream = None
        self._reference_stream = None
        self._input_stream = None
        self._reference_input_stream = None
        self._stop_requested = False
        self._pending_reference_block: Optional[np.ndarray] = None
        self._control_channels = 1
        self._reference_channels = 1

        self._reset_state()

    def _reset_state(self) -> None:
        """Initialise adaptive filter state."""
        self.weights = np.zeros(self.filter_length, dtype=np.float32)
        self.ref_history = np.zeros(self.filter_length, dtype=np.float32)
        self.sec_history = np.zeros(len(self.secondary_path), dtype=np.float32)
        self.fx_history = np.zeros(self.filter_length, dtype=np.float32)
        self.reference_index = 0
        self.frame_index = 0
        self._reference_lowpass_state = 0.0

    def _configure_reference_lowpass(self) -> None:
        """Initialise low-pass filter coefficient/state if requested."""
        self._reference_lowpass_state = 0.0
        if self.reference_lowpass_hz is None:
            self._reference_lowpass_alpha = None
            return
        cutoff = min(self.reference_lowpass_hz, self.sample_rate / 2)
        if cutoff <= 0:
            self._reference_lowpass_alpha = None
            return
        self._reference_lowpass_alpha = 1.0 - math.exp(
            -2.0 * math.pi * cutoff / float(self.sample_rate)
        )

    def _apply_reference_lowpass(self, block: np.ndarray) -> np.ndarray:
        """Run the optional one-pole low-pass on the reference block."""
        if self._reference_lowpass_alpha is None:
            return block
        filtered = np.empty_like(block)
        state = self._reference_lowpass_state
        alpha = self._reference_lowpass_alpha
        for idx, sample in enumerate(block):
            state += alpha * (sample - state)
            filtered[idx] = state
        self._reference_lowpass_state = state
        return filtered

    def stop(self) -> None:
        """Request the processing loop to halt after the current block."""
        self._stop_requested = True

    def _open_streams(self) -> None:
        """Open PyAudio output and input streams."""
        if self._control_stream is None:
            channels = 2 if self.split_reference_channels else max(1, self.control_output_channel + 1)
            self._control_channels = channels
            self._control_stream = self._audio.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.block_size,
                output_device_index=self.control_device_index,
            )

        if (
            self.play_reference
            and self.reference_device_index is not None
            and not self.split_reference_channels
            and self._reference_stream is None
        ):
            ref_channels = max(1, self.reference_output_channel + 1)
            self._reference_channels = ref_channels
            self._reference_stream = self._audio.open(
                format=pyaudio.paFloat32,
                channels=ref_channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.block_size,
                output_device_index=self.reference_device_index,
            )

        if self._input_stream is None:
            self._input_stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=self.record_channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.block_size,
                input_device_index=self.record_device_index,
            )

        if (
            self.reference_input_device_index is not None
            and self._reference_input_stream is None
        ):
            self._reference_input_stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.block_size,
                input_device_index=self.reference_input_device_index,
            )

    def _close_streams(self) -> None:
        """Close streams and terminate PyAudio."""
        if self._control_stream:
            self._control_stream.stop_stream()
            self._control_stream.close()
            self._control_stream = None
        if self._reference_stream:
            self._reference_stream.stop_stream()
            self._reference_stream.close()
            self._reference_stream = None
        if self._input_stream:
            self._input_stream.stop_stream()
            self._input_stream.close()
            self._input_stream = None
        if self._reference_input_stream:
            self._reference_input_stream.stop_stream()
            self._reference_input_stream.close()
            self._reference_input_stream = None
        if self._audio:
            self._audio.terminate()

    def _read_input_frames(self) -> np.ndarray:
        """Read and reshape a block of samples from the configured input device."""
        if self._input_stream is None:
            raise RuntimeError("Input stream is not open.")
        raw = self._input_stream.read(self.block_size, exception_on_overflow=False)
        frames = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        frames /= 32768.0
        frames = frames.reshape(-1, self.record_channels)
        return frames

    def _read_error_block(self) -> np.ndarray:
        """Extract the configured error channel from the latest input block."""
        frames = self._read_input_frames()
        return frames[:, self.error_channel_index]

    def _read_shared_reference_error_block(self) -> Tuple[np.ndarray, np.ndarray]:
        """Read reference and error blocks from a shared multi-channel device."""
        if self.reference_channel_index is None:
            raise RuntimeError("reference_channel_index is not configured.")
        frames = self._read_input_frames()
        reference = frames[:, self.reference_channel_index]
        error = frames[:, self.error_channel_index]
        return reference, error

    def _prime_shared_reference_block(self) -> None:
        """Preload the first reference block when sharing the recording device."""
        reference, _ = self._read_shared_reference_error_block()
        self._pending_reference_block = reference

    def _next_reference_block(self, loop: bool) -> np.ndarray:
        """Fetch the next reference block, padding or looping as required."""
        if self.reference_input_device_index is not None:
            if self._reference_input_stream is None:
                raise RuntimeError("Reference input stream is not open.")
            raw = self._reference_input_stream.read(
                self.block_size, exception_on_overflow=False
            )
            block = (
                np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            )
            return block
        if self._reference_from_record_stream:
            if self._pending_reference_block is None:
                raise RuntimeError("Shared reference block not primed.")
            block = self._pending_reference_block
            self._pending_reference_block = None
            return block

        start = self.reference_index
        end = start + self.block_size
        if start >= len(self.reference_signal):
            if loop:
                self.reference_index = 0
                return self._next_reference_block(loop=False)
            return np.zeros(self.block_size, dtype=np.float32)

        block = self.reference_signal[start:end]
        if len(block) < self.block_size:
            if loop:
                remaining = self.block_size - len(block)
                self.reference_index = 0
                block = np.concatenate(
                    [block, self._next_reference_block(loop=False)[:remaining]]
                )
                self.reference_index = remaining
            else:
                block = np.pad(block, (0, self.block_size - len(block)))
                self.reference_index = len(self.reference_signal)
                return block.astype(np.float32)
        else:
            self.reference_index = end
        return block.astype(np.float32)

    def run(
        self,
        loop_reference: bool = False,
        max_duration: Optional[float] = None,
        metrics_callback: Optional[Callable[[AncMetrics], None]] = None,
    ) -> None:
        """
        Execute the adaptive control loop.
        """
        self._open_streams()
        self._reset_state()
        self._stop_requested = False

        if self._reference_from_record_stream:
            self._prime_shared_reference_block()

        start_time = time.time()

        try:
            while not self._stop_requested:
                if max_duration and (time.time() - start_time) >= max_duration:
                    break

                ref_block = self._next_reference_block(loop_reference)
                adapt_block = self._apply_reference_lowpass(ref_block)
                if (
                    not self._live_reference
                    and not loop_reference
                    and self.reference_index >= len(self.reference_signal)
                ):
                    # We are at the final padded block and will exit next iteration.
                    self._stop_requested = True

                if self.manual_gain_mode:
                    anti_noise_block = self.manual_gain * adapt_block
                    fx_vectors = None
                else:
                    anti_noise_block, fx_vectors = self._synthesize_block(adapt_block)
                scaled_anti_noise = anti_noise_block * self.control_output_gain

                if self.split_reference_channels:
                    left = ref_block if self.play_reference else np.zeros_like(ref_block)
                    right = scaled_anti_noise
                    stereo = np.empty(self.block_size * 2, dtype=np.float32)
                    stereo[0::2] = np.clip(left, -1.0, 1.0)
                    stereo[1::2] = np.clip(right, -1.0, 1.0)
                    self._control_stream.write(stereo.tobytes())
                    output_block = right  # for metrics
                elif self.play_reference and self.reference_device_index is not None and self._reference_stream:
                    reference_out = np.clip(ref_block, -1.0, 1.0).astype(np.float32)
                    if self._reference_channels > 1:
                        ref_stereo = np.zeros((self.block_size, self._reference_channels), dtype=np.float32)
                        ref_stereo[:, self.reference_output_channel] = reference_out
                        self._reference_stream.write(ref_stereo.astype(np.float32).tobytes())
                    else:
                        self._reference_stream.write(reference_out.tobytes())
                    output_block = np.clip(scaled_anti_noise, -1.0, 1.0)
                elif self.play_reference:
                    output_block = np.clip(ref_block + scaled_anti_noise, -1.0, 1.0)
                else:
                    output_block = np.clip(scaled_anti_noise, -1.0, 1.0)

                if not self.split_reference_channels:
                    control_out = output_block.astype(np.float32)
                    if self._control_channels > 1:
                        ctrl = np.zeros((self.block_size, self._control_channels), dtype=np.float32)
                        ctrl[:, self.control_output_channel] = control_out
                        self._control_stream.write(ctrl.astype(np.float32).tobytes())
                    else:
                        self._control_stream.write(control_out.tobytes())

                if self._reference_from_record_stream:
                    next_ref, error_block = self._read_shared_reference_error_block()
                    self._pending_reference_block = next_ref
                else:
                    error_block = self._read_error_block()

                if not self.manual_gain_mode:
                    self._update_weights(error_block, fx_vectors)

                if metrics_callback:
                    error_rms = float(np.sqrt(np.mean(error_block**2)))
                    ref_rms = float(np.sqrt(np.mean(ref_block**2)))
                    out_rms = float(np.sqrt(np.mean(output_block**2)))
                    metrics = AncMetrics(
                        frame_index=self.frame_index,
                        error_rms=error_rms,
                        step_size=self.base_step_size,
                        reference_rms=ref_rms,
                        output_rms=out_rms,
                    )
                    metrics_callback(metrics)

                self.frame_index += 1

        except KeyboardInterrupt:
            logging.info("ANC loop interrupted by user.")
        finally:
            self._close_streams()

    def _synthesize_block(
        self, ref_block: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute the anti-noise block and capture filtered-x vectors.

        Returns
        -------
        anti_noise_block:
            Array of length block_size containing the control signal.
        fx_vectors:
            Matrix with shape (block_size, filter_length) containing the
            filtered reference vectors per sample for LMS updates.
        """
        anti_noise = np.zeros(self.block_size, dtype=np.float32)
        fx_vectors = np.zeros((self.block_size, self.filter_length), dtype=np.float32)

        for i in range(self.block_size):
            x_n = ref_block[i]

            # Update reference history
            self.ref_history[1:] = self.ref_history[:-1]
            self.ref_history[0] = x_n

            # Control output y[n] = w^T * x
            anti_noise[i] = float(np.dot(self.weights, self.ref_history))

            # Filtered-x: pass the reference through secondary path estimate
            self.sec_history[1:] = self.sec_history[:-1]
            self.sec_history[0] = x_n
            filtered_sample = float(np.dot(self.secondary_path, self.sec_history))

            self.fx_history[1:] = self.fx_history[:-1]
            self.fx_history[0] = filtered_sample

            fx_vectors[i] = self.fx_history

        return anti_noise, fx_vectors

    def _update_weights(self, error_block: np.ndarray, fx_vectors: np.ndarray) -> None:
        """LMS weight adaptation for the current block."""
        for e, fx in zip(error_block, fx_vectors):
            power = float(np.dot(fx, fx)) + EPSILON
            mu_eff = self.base_step_size / power

            if self.leakage > 0.0:
                self.weights *= (1.0 - self.leakage)

            self.weights += mu_eff * e * fx


    def measure_secondary_path(
        self,
        duration: float = 2.0,
        excitation_level: float = 0.2,
        fir_length: int = 64,
    ) -> np.ndarray:
        """
        Excite the secondary path (speaker→mic) and estimate an FIR model.
        """
        self._open_streams()

        n_samples = int(duration * self.sample_rate)
        excitation = np.random.uniform(-1.0, 1.0, size=n_samples).astype(np.float32)
        excitation *= excitation_level

        recorded = np.zeros(n_samples, dtype=np.float32)
        ptr = 0

        logging.info("Measuring secondary path for %.2f s", duration)

        while ptr < n_samples:
            block = excitation[ptr : ptr + self.block_size]
            if len(block) < self.block_size:
                block = np.pad(block, (0, self.block_size - len(block)))

            if self.split_reference_channels:
                stereo_block = np.zeros(self.block_size * 2, dtype=np.float32)
                stereo_block[1::2] = block.astype(np.float32)
                self._control_stream.write(stereo_block.tobytes())
            else:
                self._control_stream.write(block.astype(np.float32).tobytes())
            error_block = self._read_error_block()
            slice_len = min(self.block_size, n_samples - ptr)
            recorded[ptr : ptr + slice_len] = error_block[:slice_len]
            ptr += self.block_size

        excitation_rms = float(np.sqrt(np.mean(excitation**2)))
        recorded_rms = float(np.sqrt(np.mean(recorded**2)))
        self._last_measure_excitation_rms = excitation_rms
        self._last_measure_recorded_rms = recorded_rms

        # Build Toeplitz matrix for least squares: y = Xh
        X = np.zeros((n_samples - fir_length, fir_length), dtype=np.float32)
        for i in range(fir_length):
            X[:, i] = excitation[i : i + n_samples - fir_length]
        y = recorded[fir_length:]

        h, *_ = np.linalg.lstsq(X, y, rcond=None)

        # Normalize secondary path energy to 1.0
        energy = float(np.sqrt(np.sum(h**2) + 1e-12))
        if energy > 0.0:
            h = h / energy

        self.secondary_path = h.astype(np.float32)
        logging.info(
            "Secondary path updated (length %d, norm=%.3e)", fir_length, energy
        )
        return self.secondary_path.copy()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run FxLMS ANC session.")
    parser.add_argument("reference_path", help="Path to reference noise WAV file")
    parser.add_argument(
        "--filter-length",
        type=int,
        default=DEFAULT_FILTER_LENGTH,
        help="Number of taps in the adaptive filter",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=DEFAULT_BLOCK_SIZE,
        help="Processing block size in samples",
    )
    parser.add_argument(
        "--step-size",
        type=float,
        default=5e-4,
        help="Base LMS step size",
    )
    parser.add_argument(
        "--play-reference",
        action="store_true",
        help="Audibly play the reference noise (requires --reference-device for separate speaker)",
    )
    parser.add_argument(
        "--control-device",
        type=int,
        default=None,
        help="Output device index for anti-noise speaker",
    )
    parser.add_argument(
        "--reference-device",
        type=int,
        default=None,
        help="Output device index for reference noise speaker",
    )
    parser.add_argument(
        "--record-device",
        type=int,
        default=None,
        help="Input device index for error microphone",
    )
    parser.add_argument(
        "--split-reference-channels",
        action="store_true",
        help="Send reference (left) and anti-noise (right) over the control output stereo pair",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional maximum runtime in seconds",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    controller = FxLMSANC(
        reference_path=args.reference_path,
        filter_length=args.filter_length,
        block_size=args.block_size,
        step_size=args.step_size,
        play_reference=args.play_reference,
        control_device_index=args.control_device,
        record_device_index=args.record_device,
        reference_device_index=args.reference_device,
        split_reference_channels=args.split_reference_channels,
    )

    def log_metrics(metrics: AncMetrics) -> None:
        logging.info(
            "frame=%05d error_rms=%.6f",
            metrics.frame_index,
            metrics.error_rms,
        )

    controller.run(
        loop_reference=True if args.duration else False,
        max_duration=args.duration,
        metrics_callback=log_metrics,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
