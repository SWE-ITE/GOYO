"""
AI-augmented active noise control toolkit.

This package combines several learning-based enhancements for FxLMS-style
controllers, including a learned secondary path model, adaptive step size
policy, nonlinear cancellation block, learned state estimator, predictive
reference synthesis, and a supervisory tuner.
"""

from .controller import AIANCController
from .secondary_path_model import SecondaryPathModel, SecondaryPathDataset
from .adaptive_scheduler import AdaptiveStepScheduler
from .nonlinear_canceller import NonlinearCanceller
from .state_estimator import LearnedKalmanFilter
from .predictive_reference import ReferencePredictor
from .supervisory_tuner import SupervisoryTuner

__all__ = [
    "AIANCController",
    "SecondaryPathModel",
    "SecondaryPathDataset",
    "AdaptiveStepScheduler",
    "NonlinearCanceller",
    "LearnedKalmanFilter",
    "ReferencePredictor",
    "SupervisoryTuner",
]
