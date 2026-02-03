"""
Federated learning module for distributed model training.
"""

from agent.federated.federated_learning import (
    FederatedLearningCoordinator,
    ClientLocalTrainer,
    GradientCompressor,
    DifferentialPrivacyManager,
    FederatedAveraging,
    ModelUpdate,
    DifferentialPrivacyConfig,
    AggregationType,
)

__all__ = [
    "FederatedLearningCoordinator",
    "ClientLocalTrainer",
    "GradientCompressor",
    "DifferentialPrivacyManager",
    "FederatedAveraging",
    "ModelUpdate",
    "DifferentialPrivacyConfig",
    "AggregationType",
]
