"""Central configuration for the fraud detection engine."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GraphConfig:
    """Knobs for the knowledge graph and risk scorer."""
    max_hop: int = 2
    fraud_neighbor_weight: float = 0.6
    shared_account_weight: float = 0.25
    persona_similarity_weight: float = 0.15
    risk_threshold: float = 0.65


@dataclass(frozen=True)
class GNNConfig:
    """Hyper-parameters for the GraphSAGE model."""
    input_dim: int = 16
    hidden_dim: int = 64
    output_dim: int = 2          # Fraud / Benign
    num_layers: int = 2
    dropout: float = 0.3
    learning_rate: float = 0.005
    epochs: int = 200
    aggregator: str = "mean"     # SAGEConv default


@dataclass(frozen=True)
class LLMConfig:
    """Settings for the LLM entity extractor."""
    model_name: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    temperature: float = 0.0
    max_tokens: int = 512
    timeout_seconds: float = 5.0


@dataclass(frozen=True)
class AppConfig:
    graph: GraphConfig = field(default_factory=GraphConfig)
    gnn: GNNConfig = field(default_factory=GNNConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
