from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Tuple

import torch
from torch import nn


def _to_tensor(x: Sequence[float] | torch.Tensor) -> torch.Tensor:
    if isinstance(x, torch.Tensor):
        return x.float()
    return torch.tensor(x, dtype=torch.float32)


class _PolicyNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(4, 32),
            nn.LayerNorm(32),
            nn.ReLU(),
            nn.Linear(32, 32),
            nn.ReLU(),
            nn.Linear(32, 2),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.layers(features)


@dataclass
class SchedulerExperience:
    features: torch.Tensor
    reward: float


@dataclass
class AdaptiveStepScheduler:
    """
    Lightweight policy network that adjusts LMS step and leakage parameters.
    """

    step_bounds: Tuple[float, float] = (1e-6, 5e-2)
    leakage_bounds: Tuple[float, float] = (0.0, 5e-3)
    gamma: float = 0.98
    device: torch.device | str = field(
        default_factory=lambda: torch.device("cuda" if torch.cuda.is_available() else "cpu")
    )

    def __post_init__(self) -> None:
        self.device = torch.device(self.device)
        self.policy = _PolicyNet().to(self.device)
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=1e-3)
        self._buffer: List[SchedulerExperience] = []

    @torch.no_grad()
    def select(self, error_energy: float, weight_norm: float, gradient_norm: float, snr: float) -> Tuple[float, float]:
        """
        Map recent controller statistics to (step_size, leakage).
        """
        features = torch.tensor(
            [error_energy, weight_norm, gradient_norm, snr],
            dtype=torch.float32,
            device=self.device,
        )
        logits = self.policy(features.unsqueeze(0)).squeeze(0)
        step = torch.sigmoid(logits[0])
        leakage = torch.sigmoid(logits[1])
        step_value = float(self.step_bounds[0] + step * (self.step_bounds[1] - self.step_bounds[0]))
        leakage_value = float(
            self.leakage_bounds[0] + leakage * (self.leakage_bounds[1] - self.leakage_bounds[0])
        )
        return step_value, leakage_value

    def store(self, features: Sequence[float], reward: float) -> None:
        feat_tensor = _to_tensor(features).to(self.device)
        self._buffer.append(SchedulerExperience(feat_tensor, reward))

    def update(self) -> Iterable[float]:
        """
        One policy-gradient step over the stored experience.
        """
        if not self._buffer:
            return []
        losses: List[float] = []
        returns: List[float] = []
        g = 0.0
        for exp in reversed(self._buffer):
            g = exp.reward + self.gamma * g
            returns.insert(0, g)
        returns_tensor = torch.tensor(returns, dtype=torch.float32, device=self.device)
        returns_tensor = (returns_tensor - returns_tensor.mean()) / (returns_tensor.std() + 1e-6)
        for exp, ret in zip(self._buffer, returns_tensor, strict=True):
            logits = self.policy(exp.features.unsqueeze(0))
            probs = torch.sigmoid(logits)
            # Encourage higher reward for the selected parameterization.
            log_prob = probs.log().sum()
            loss = -(log_prob * ret)
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.policy.parameters(), max_norm=5.0)
            self.optimizer.step()
            losses.append(float(loss.item()))
        self._buffer.clear()
        return losses
