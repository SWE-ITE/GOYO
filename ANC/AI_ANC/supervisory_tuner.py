from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class SupervisoryTuner:
    """
    Contextual bandit that proposes controller presets based on logged features.
    """

    alpha: float = 1.0
    feature_dim: int = 6
    actions: Tuple[str, ...] = ("aggressive", "balanced", "conservative")

    def __post_init__(self) -> None:
        self.A: Dict[str, np.ndarray] = {a: np.eye(self.feature_dim) for a in self.actions}
        self.b: Dict[str, np.ndarray] = {a: np.zeros((self.feature_dim, 1)) for a in self.actions}

    def recommend(self, features: np.ndarray) -> str:
        """
        Compute LinUCB upper confidence for each action and return the best.
        """
        x = features.reshape(-1, 1)
        best_action = self.actions[0]
        best_value = -np.inf
        for action in self.actions:
            A = self.A[action]
            b = self.b[action]
            A_inv = np.linalg.inv(A)
            theta = A_inv @ b
            mean = float(theta.T @ x)
            confidence = self.alpha * float(np.sqrt(x.T @ A_inv @ x))
            value = mean + confidence
            if value > best_value:
                best_value = value
                best_action = action
        return best_action

    def update(self, features: np.ndarray, action: str, reward: float) -> None:
        if action not in self.actions:
            raise ValueError(f"Unknown action {action}")
        x = features.reshape(-1, 1)
        self.A[action] += x @ x.T
        self.b[action] += reward * x

    def presets(self) -> Dict[str, Dict[str, float]]:
        """
        Return controller preset suggestions keyed by policy label.
        """
        return {
            "aggressive": {"mu": 5e-2, "leakage": 1e-3, "nonlinear_lr": 5e-4},
            "balanced": {"mu": 1e-2, "leakage": 5e-4, "nonlinear_lr": 1e-4},
            "conservative": {"mu": 5e-3, "leakage": 1e-4, "nonlinear_lr": 5e-5},
        }
