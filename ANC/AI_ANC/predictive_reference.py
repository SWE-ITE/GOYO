from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


class _ReferenceDataset(Dataset):
    def __init__(self, signal: torch.Tensor, lookback: int, horizon: int, stride: int) -> None:
        super().__init__()
        if lookback <= 0 or horizon <= 0:
            raise ValueError("lookback and horizon must be positive.")
        self.signal = signal
        self.lookback = lookback
        self.horizon = horizon
        self.stride = stride
        limit = signal.shape[0] - lookback - horizon + 1
        self._starts = torch.arange(0, limit, stride)

    def __len__(self) -> int:
        return int(self._starts.numel())

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        start = int(self._starts[idx])
        end = start + self.lookback
        target_end = end + self.horizon
        context = self.signal[start:end]
        target = self.signal[end:target_end]
        return context, target


class _SequenceModel(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, num_layers: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
        )
        self.head = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor, horizon: int) -> torch.Tensor:
        outputs = []
        h, c = None, None
        out, (h, c) = self.lstm(x.unsqueeze(-1), (h, c) if h is not None else None)
        last = out[:, -1:, :]
        for _ in range(horizon):
            pred = self.head(last)
            outputs.append(pred)
            out, (h, c) = self.lstm(pred, (h, c))
            last = out
        return torch.cat(outputs, dim=1).squeeze(-1)


@dataclass
class ReferencePredictor:
    """
    Sequence model that forecasts the reference signal a few steps ahead.
    """

    lookback: int = 128
    horizon: int = 16
    hidden_dim: int = 64
    num_layers: int = 1
    device: torch.device | str = torch.device("cpu")

    def __post_init__(self) -> None:
        self.device = torch.device(self.device)
        self.model = _SequenceModel(1, self.hidden_dim, self.num_layers).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=5e-4)
        self.loss_fn = nn.MSELoss()

    def fit(
        self,
        signal: np.ndarray,
        *,
        epochs: int = 10,
        batch_size: int = 32,
        stride: int = 1,
    ) -> Optional[float]:
        tensor = torch.from_numpy(signal.astype(np.float32)).to(self.device)
        dataset = _ReferenceDataset(tensor, self.lookback, self.horizon, stride)
        if len(dataset) == 0:
            return None
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        for _ in range(epochs):
            losses = []
            for context, target in loader:
                context = context.to(self.device)
                target = target.to(self.device)
                pred = self.model(context, self.horizon)
                loss = self.loss_fn(pred, target)
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=5.0)
                self.optimizer.step()
                losses.append(float(loss.item()))
        return float(np.mean(losses)) if losses else None

    @torch.no_grad()
    def predict(self, context: np.ndarray) -> np.ndarray:
        tensor = torch.from_numpy(context.astype(np.float32)).unsqueeze(0).to(self.device)
        pred = self.model(tensor, self.horizon)
        return pred.squeeze(0).cpu().numpy()
