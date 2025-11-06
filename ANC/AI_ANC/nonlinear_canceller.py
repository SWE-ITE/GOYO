from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch
from torch import nn


class PolynomialFeatures(nn.Module):
    """
    Simple fixed feature map with odd-order polynomial terms.
    """

    def __init__(self, order: int = 3) -> None:
        super().__init__()
        if order < 1:
            raise ValueError("order must be >= 1")
        self.order = int(order)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feats = [x]
        for k in range(2, self.order + 1):
            feats.append(torch.pow(x, k))
        return torch.cat(feats, dim=-1)


class NonlinearBlock(nn.Module):
    def __init__(self, order: int = 3, hidden: int = 32) -> None:
        super().__init__()
        self.features = PolynomialFeatures(order=order)
        input_dim = order
        self.mlp = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.Tanh(),
            nn.Linear(hidden, hidden),
            nn.Tanh(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feats = self.features(x.unsqueeze(-1))
        return self.mlp(feats).squeeze(-1)


@dataclass
class NonlinearCanceller:
    """
    Shallow nonlinear ANC block trained online with gradient descent.
    """

    order: int = 3
    hidden: int = 32
    lr: float = 1e-4
    device: torch.device | str = torch.device("cpu")

    def __post_init__(self) -> None:
        self.device = torch.device(self.device)
        self.net = NonlinearBlock(order=self.order, hidden=self.hidden).to(self.device)
        self.optimizer = torch.optim.Adam(self.net.parameters(), lr=self.lr)

    def forward(self, reference: np.ndarray) -> np.ndarray:
        tensor = torch.from_numpy(reference.astype(np.float32)).to(self.device)
        with torch.no_grad():
            out = self.net(tensor)
        return out.cpu().numpy()

    def update(
        self,
        reference: np.ndarray,
        residual_error: np.ndarray,
        *,
        weight: Optional[float] = None,
    ) -> float:
        """
        Online training step using instantaneous residual error as target.
        """
        ref = torch.from_numpy(reference.astype(np.float32)).to(self.device)
        target = torch.from_numpy(residual_error.astype(np.float32)).to(self.device)
        prediction = self.net(ref)
        loss = torch.mean((prediction - target) ** 2 if weight is None else weight * (prediction - target) ** 2)
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.net.parameters(), max_norm=10.0)
        self.optimizer.step()
        return float(loss.item())
