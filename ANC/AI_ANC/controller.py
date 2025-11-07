from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Iterable, Optional

import numpy as np
import torch

from .adaptive_scheduler import AdaptiveStepScheduler
from .nonlinear_canceller import NonlinearCanceller
from .predictive_reference import ReferencePredictor
from .secondary_path_model import SecondaryPathDataset, SecondaryPathModel
from .state_estimator import LearnedKalmanFilter
from .supervisory_tuner import SupervisoryTuner


@dataclass
class AIANCController:
    """
    Composite controller that layers AI components on top of an FxLMS core.
    """

    filter_length: int = 128
    scheduler: AdaptiveStepScheduler = field(default_factory=AdaptiveStepScheduler)
    nonlinear: NonlinearCanceller = field(default_factory=NonlinearCanceller)
    predictor: ReferencePredictor = field(default_factory=ReferencePredictor)
    tuner: SupervisoryTuner = field(default_factory=SupervisoryTuner)
    device: torch.device | str = torch.device("cpu")

    def __post_init__(self) -> None:
        self.device = torch.device(self.device)
        self.secondary_model = SecondaryPathModel(window_length=self.filter_length).to(self.device)
        self.secondary_taps = np.zeros(self.filter_length, dtype=np.float32)
        self.secondary_taps[0] = 1.0
        self.weights = np.zeros(self.filter_length, dtype=np.float32)
        self._ref_buffer: Deque[float] = deque([0.0] * self.filter_length, maxlen=self.filter_length)
        self._filtered_buffer: Deque[float] = deque([0.0] * self.filter_length, maxlen=self.filter_length)
        self.state_estimator = LearnedKalmanFilter(state_dim=self.filter_length, device=self.device)
        self.reference_history = deque(
            [0.0] * self.predictor.lookback,
            maxlen=self.predictor.lookback,
        )

    def train_secondary_path(
        self,
        excitation: np.ndarray,
        response: np.ndarray,
        *,
        epochs: int = 20,
        batch_size: int = 64,
        stride: int = 1,
    ) -> Iterable[float]:
        """
        Fit the learned secondary path model by supervised training.
        """
        excitation = torch.from_numpy(excitation.astype(np.float32))
        response = torch.from_numpy(response.astype(np.float32))
        dataset = SecondaryPathDataset(excitation, response, window_length=self.filter_length, stride=stride)
        history = list(
            self.secondary_model.fit(
                dataset,
                epochs=epochs,
                batch_size=batch_size,
                device=self.device,
            )
        )
        self.secondary_taps = self.secondary_model.impulse_response(self.filter_length).astype(np.float32)
        return history

    def fit_reference_predictor(
        self,
        reference_signal: np.ndarray,
        *,
        epochs: int = 10,
        batch_size: int = 32,
    ) -> Optional[float]:
        """
        Train the predictive reference model.
        """
        return self.predictor.fit(
            reference_signal,
            epochs=epochs,
            batch_size=batch_size,
            stride=max(1, self.predictor.horizon // 2),
        )

    def kalman_warmup(
        self,
        observations: torch.Tensor,
        controls: torch.Tensor,
        *,
        iters: int = 100,
    ) -> float:
        """
        Fit the Kalman dynamics on historical data before going online.
        """
        return self.state_estimator.update_parameters(observations, controls, iters=iters)

    def _filtered_ref_vector(self) -> np.ndarray:
        return np.fromiter(self._filtered_buffer, dtype=np.float32, count=self.filter_length)

    def _ref_vector(self) -> np.ndarray:
        return np.fromiter(self._ref_buffer, dtype=np.float32, count=self.filter_length)

    def process_block(
        self,
        reference_block: np.ndarray,
        error_block: np.ndarray,
        *,
        prediction_lead: int = 4,
        scheduler_reward_scale: float = 1.0,
        tuner_context: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """
        Run the composite controller over a block of samples.
        """
        if reference_block.shape != error_block.shape:
            raise ValueError("reference_block and error_block shapes must match.")
        block_size = reference_block.shape[0]
        if block_size == 0:
            return {}

        reference_copy = reference_block.astype(np.float32).copy()
        history_vector = np.array(self.reference_history, dtype=np.float32)
        if np.any(history_vector) and self.predictor.lookback == history_vector.shape[0]:
            predicted_future = self.predictor.predict(history_vector)
            lead = min(prediction_lead, block_size, predicted_future.shape[0])
            if lead > 0:
                reference_copy[-lead:] = predicted_future[:lead]

        error_energy = float(np.mean(error_block.astype(np.float32) ** 2))
        weight_norm = float(np.linalg.norm(self.weights) + 1e-9)
        filtered_vec = self._filtered_ref_vector()
        gradient_norm = float(np.linalg.norm(filtered_vec) + 1e-9)
        ref_power = float(np.mean(reference_block.astype(np.float32) ** 2) + 1e-9)
        snr = 10.0 * np.log10(ref_power / (error_energy + 1e-9))

        step_size, leakage = self.scheduler.select(
            error_energy=error_energy,
            weight_norm=weight_norm,
            gradient_norm=gradient_norm,
            snr=snr,
        )

        nonlinear_losses = []
        outputs = []
        for i in range(block_size):
            sample_ref = float(reference_copy[i])
            sample_err = float(error_block[i])

            self._ref_buffer.appendleft(sample_ref)

            ref_vec = self._ref_vector()
            filtered_sample = float(np.dot(self.secondary_taps, ref_vec))
            self._filtered_buffer.appendleft(filtered_sample)
            filtered_vec = self._filtered_ref_vector()

            control_linear = float(np.dot(self.weights, ref_vec))
            nonlinear_adjust = float(self.nonlinear.forward(np.array([control_linear], dtype=np.float32))[0])
            control_signal = control_linear + nonlinear_adjust
            outputs.append(control_signal)

            self.weights = (1.0 - leakage) * self.weights + 2.0 * step_size * sample_err * filtered_vec

            nonlin_loss = self.nonlinear.update(
                np.array([control_linear], dtype=np.float32),
                np.array([sample_err], dtype=np.float32),
            )
            nonlinear_losses.append(nonlin_loss)

            kalman_control = filtered_vec
            kalman_measurement = self.weights
            self.state_estimator.step(kalman_control, kalman_measurement)

            self.reference_history.append(sample_ref)

        reward = -error_energy * scheduler_reward_scale
        self.scheduler.store(
            [error_energy, weight_norm, gradient_norm, snr],
            reward,
        )
        self.scheduler.update()

        if tuner_context is None:
            tuner_context = np.array(
                [
                    error_energy,
                    weight_norm,
                    step_size,
                    leakage,
                    float(np.mean(outputs) if outputs else 0.0),
                    snr,
                ],
                dtype=np.float32,
            )
        preset_label = self.tuner.recommend(tuner_context)
        self.tuner.update(tuner_context, preset_label, reward)

        return {
            "error_energy": error_energy,
            "step_size": step_size,
            "leakage": leakage,
            "nonlinear_loss": float(np.mean(nonlinear_losses)) if nonlinear_losses else 0.0,
            "snr": snr,
            "preset": {"label": preset_label, **self.tuner.presets()[preset_label]},
        }
