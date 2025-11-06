from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import torch
from torch import nn


class _DynamicsModel(nn.Module):
    def __init__(self, order: int) -> None:
        super().__init__()
        self.F = nn.Parameter(torch.eye(order))
        self.H = nn.Parameter(torch.eye(order))
        self.log_q = nn.Parameter(torch.zeros(order))
        self.log_r = nn.Parameter(torch.zeros(order))

    @property
    def Q(self) -> torch.Tensor:
        return torch.diag(torch.exp(self.log_q))

    @property
    def R(self) -> torch.Tensor:
        return torch.diag(torch.exp(self.log_r))


@dataclass
class LearnedKalmanFilter:
    """
    Kalman filter whose linear dynamics parameters are learned from data.
    """

    state_dim: int
    device: torch.device | str = torch.device("cpu")

    def __post_init__(self) -> None:
        if self.state_dim <= 0:
            raise ValueError("state_dim must be positive.")
        self.device = torch.device(self.device)
        self.model = _DynamicsModel(self.state_dim).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3)
        self._x = torch.zeros(self.state_dim, 1, device=self.device)
        self._P = torch.eye(self.state_dim, device=self.device)

    @torch.no_grad()
    def reset(self, mean: np.ndarray | None = None, cov: np.ndarray | None = None) -> None:
        if mean is not None:
            self._x = torch.from_numpy(mean.astype(np.float32)).reshape(-1, 1).to(self.device)
        else:
            self._x.zero_()
        if cov is not None:
            self._P = torch.from_numpy(cov.astype(np.float32)).to(self.device)
        else:
            self._P = torch.eye(self.state_dim, device=self.device)

    def update_parameters(self, observations: torch.Tensor, controls: torch.Tensor, *, iters: int = 100) -> float:
        """
        Fit the dynamics matrices using a simple prediction loss.
        """
        obs = observations.to(self.device)
        ctrl = controls.to(self.device)
        loss_fn = nn.MSELoss()
        running = 0.0
        for _ in range(iters):
            self.optimizer.zero_grad()
            x = obs[:-1].unsqueeze(-1)
            x_next = obs[1:].unsqueeze(-1)
            pred = self.model.H @ (self.model.F @ x + ctrl[:-1].unsqueeze(-1))
            loss = loss_fn(pred, x_next)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=5.0)
            self.optimizer.step()
            running = float(loss.item())
        return running

    @torch.no_grad()
    def step(self, control: np.ndarray, measurement: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run one Kalman predict-update.
        """
        u = torch.from_numpy(control.astype(np.float32)).reshape(-1, 1).to(self.device)
        z = torch.from_numpy(measurement.astype(np.float32)).reshape(-1, 1).to(self.device)

        F = self.model.F
        H = self.model.H
        Q = self.model.Q
        R = self.model.R

        x_pred = F @ self._x + u
        P_pred = F @ self._P @ F.T + Q
        S = H @ P_pred @ H.T + R
        K = torch.linalg.solve(S, (H @ P_pred).T).T
        residual = z - H @ x_pred
        self._x = x_pred + K @ residual
        I = torch.eye(self.state_dim, device=self.device)
        self._P = (I - K @ H) @ P_pred

        return self._x.squeeze(-1).cpu().numpy(), residual.squeeze(-1).cpu().numpy()

    @property
    def mean(self) -> np.ndarray:
        return self._x.squeeze(-1).cpu().numpy()

    @property
    def covariance(self) -> np.ndarray:
        return self._P.cpu().numpy()
