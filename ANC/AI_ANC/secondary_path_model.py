from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


@dataclass
class SecondaryPathDataset(Dataset):
    """
    Sliding-window dataset built from repeated excitation-response recordings.

    Each item is a tuple (excitation_window, response_window) aligned such that
    the response reflects the loudspeaker->mic secondary path.
    """

    excitation: torch.Tensor  # shape: (num_samples,)
    response: torch.Tensor  # shape: (num_samples,)
    window_length: int
    stride: int = 1

    def __post_init__(self) -> None:
        if self.excitation.shape != self.response.shape:
            raise ValueError("Excitation and response must share shape.")
        if self.window_length <= 0:
            raise ValueError("Window length must be positive.")
        if self.stride <= 0:
            raise ValueError("Stride must be positive.")
        total = self.excitation.shape[0]
        self._starts = torch.arange(0, total - self.window_length + 1, self.stride)

    def __len__(self) -> int:
        return int(self._starts.numel())

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        start = int(self._starts[idx])
        end = start + self.window_length
        exc = self.excitation[start:end].unsqueeze(0)  # (1, L)
        rsp = self.response[start:end].unsqueeze(0)
        return exc, rsp


class SecondaryPathModel(nn.Module):
    """
    Lightweight 1D CNN that approximates the secondary path impulse response.
    """

    def __init__(self, window_length: int, hidden_channels: int = 16) -> None:
        super().__init__()
        if window_length <= 0:
            raise ValueError("window_length must be positive.")
        self.window_length = int(window_length)
        self.network = nn.Sequential(
            nn.Conv1d(1, hidden_channels, kernel_size=5, padding=2),
            nn.ELU(),
            nn.Conv1d(hidden_channels, hidden_channels, kernel_size=5, padding=2),
            nn.ELU(),
            nn.Conv1d(hidden_channels, 1, kernel_size=5, padding=2),
        )

    def forward(self, excitation_window: torch.Tensor) -> torch.Tensor:
        """
        Compute the predicted response for a batch of excitation windows.

        Args:
            excitation_window: Tensor shaped (batch, 1, L) or (batch, L).
        Returns:
            Predicted response tensor matching the input shape.
        """
        if excitation_window.dim() == 2:
            excitation_window = excitation_window.unsqueeze(1)
        return self.network(excitation_window)

    def fit(
        self,
        dataset: SecondaryPathDataset,
        *,
        epochs: int = 20,
        batch_size: int = 64,
        lr: float = 1e-3,
        device: str | torch.device | None = None,
    ) -> Iterable[float]:
        """
        Train the model using mean squared error; yields epoch losses.
        """
        if device is None:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        device = torch.device(device)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=False)
        opt = torch.optim.Adam(self.parameters(), lr=lr)
        loss_fn = nn.MSELoss()
        self.to(device)
        for _ in range(epochs):
            running = 0.0
            count = 0
            self.train()
            for exc, rsp in loader:
                exc = exc.to(device)
                rsp = rsp.to(device)
                pred = self.forward(exc)
                loss = loss_fn(pred, rsp)
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.parameters(), max_norm=2.0)
                opt.step()
                running += float(loss.item()) * exc.size(0)
                count += exc.size(0)
            yield running / max(count, 1)

    @torch.no_grad()
    def impulse_response(self, taps: int | None = None) -> np.ndarray:
        """
        Estimate FIR taps by exciting the model with a unit impulse.
        """
        taps = self.window_length if taps is None else int(taps)
        impulse = torch.zeros((1, 1, taps), device=self.network[0].weight.device)
        impulse[..., 0] = 1.0
        response = self.forward(impulse).squeeze().cpu().numpy()
        return response

    @torch.no_grad()
    def filter(self, signal: np.ndarray) -> np.ndarray:
        """
        Filter an arbitrary 1D numpy signal with the learned model.
        """
        tensor = torch.from_numpy(signal.astype(np.float32)).unsqueeze(0).unsqueeze(0)
        output = self.forward(tensor.to(self.network[0].weight.device))
        return output.squeeze().cpu().numpy()
