"""
Numba-accelerated FxLMS controller.

This module subclasses the base ``FxLMSANC`` implementation and replaces the
two hottest loops (block synthesis and LMS weight update) with ``numba`` JIT
versions. The public API mirrors ``FxLMSANC`` so entrypoints can drop in the
Numba variant without touching orchestration code, while still benefiting from
the low-latency optimizations.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Tuple

import numpy as np
from numba import njit

# Add parent directory to path to locate Basic_ANC
sys.path.append(str(Path(__file__).resolve().parent.parent))

from Basic_ANC.fxlms_controller import (
    EPSILON,
    MAX_NORM,
    MIN_REFERENCE_POWER,
    FxLMSANC,
)


@njit(cache=True)
def _synthesize_block_numba(
    anti_noise: np.ndarray,
    fx_vectors: np.ndarray,
    ref_block: np.ndarray,
    weights: np.ndarray,
    ref_history: np.ndarray,
    sec_history: np.ndarray,
    secondary_path: np.ndarray,
    fx_history: np.ndarray,
) -> None:
    block_size = ref_block.shape[0]
    filter_length = weights.shape[0]
    sec_length = secondary_path.shape[0]

    for i in range(block_size):
        x_n = ref_block[i]

        for j in range(filter_length - 1, 0, -1):
            ref_history[j] = ref_history[j - 1]
        ref_history[0] = x_n

        acc = 0.0
        for j in range(filter_length):
            acc += weights[j] * ref_history[j]
        anti_noise[i] = acc

        for j in range(sec_length - 1, 0, -1):
            sec_history[j] = sec_history[j - 1]
        sec_history[0] = x_n

        filtered = 0.0
        for j in range(sec_length):
            filtered += secondary_path[j] * sec_history[j]

        for j in range(filter_length - 1, 0, -1):
            fx_history[j] = fx_history[j - 1]
        fx_history[0] = filtered

        for j in range(filter_length):
            fx_vectors[i, j] = fx_history[j]


@njit(cache=True)
def _update_weights_numba(
    weights: np.ndarray,
    error_block: np.ndarray,
    fx_vectors: np.ndarray,
    base_step_size: float,
    leakage: float,
    min_reference_power: float,
    epsilon: float,
    max_norm: float,
) -> None:
    n_frames = error_block.shape[0]
    filter_length = weights.shape[0]

    for i in range(n_frames):
        err = error_block[i]
        fx_vec = fx_vectors[i]
        power = 0.0
        for j in range(filter_length):
            val = fx_vec[j]
            power += val * val

        if power < min_reference_power:
            continue

        mu_eff = base_step_size / (power + epsilon)

        if leakage > 0.0:
            leak_scale = 1.0 - leakage
            for j in range(filter_length):
                weights[j] *= leak_scale

        for j in range(filter_length):
            weights[j] -= mu_eff * err * fx_vec[j]

    norm_sq = 0.0
    for j in range(filter_length):
        norm_sq += weights[j] * weights[j]
    norm = math.sqrt(norm_sq)
    if norm > max_norm:
        scale = max_norm / max(norm, epsilon)
        for j in range(filter_length):
            weights[j] *= scale


class NumbaFxLMSANC(FxLMSANC):
    """FxLMSANC variant that offloads the DSP-heavy loops to Numba."""

    def _synthesize_block(self, ref_block: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        anti_noise = np.zeros(self.block_size, dtype=np.float32)
        fx_vectors = np.zeros((self.block_size, self.filter_length), dtype=np.float32)
        ref_block32 = ref_block.astype(np.float32, copy=False)
        _synthesize_block_numba(
            anti_noise,
            fx_vectors,
            ref_block32,
            self.weights,
            self.ref_history,
            self.sec_history,
            self.secondary_path,
            self.fx_history,
        )
        return anti_noise, fx_vectors

    def _update_weights(self, error_block: np.ndarray, fx_vectors: np.ndarray) -> None:
        error_block32 = error_block.astype(np.float32, copy=False)
        _update_weights_numba(
            self.weights,
            error_block32,
            fx_vectors.astype(np.float32, copy=False),
            self.base_step_size,
            self.leakage,
            MIN_REFERENCE_POWER,
            EPSILON,
            MAX_NORM,
        )
