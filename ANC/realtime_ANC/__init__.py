"""
Real-time ANC orchestration helpers.

This subpackage intentionally reuses the FxLMS components that live in
``ANC.Basic_ANC`` so that we can compose higher-level workflows (reference
preview, secondary-path calibration, adaptive control) without duplicating DSP
logic.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
