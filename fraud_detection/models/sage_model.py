"""
GraphSAGE model for binary node classification (Fraud / Benign).

Architecture
------------
Two stacked SAGEConv layers with BatchNorm, ELU activation, and dropout.
SAGEConv uses *mean* aggregation by default — ideal for inductive learning
on dynamically growing fraud graphs where unseen nodes appear at inference.

Why SAGEConv over GCN?
  GCN requires the full graph Laplacian at train time, making it
  *transductive*.  SAGEConv samples and aggregates neighbor features,
  so a node added at inference inherits signal from its neighborhood
  without retraining — critical for real-time scam detection.
"""

from __future__ import annotations

import logging

import torch
import torch.nn.functional as F
from torch import Tensor
from torch_geometric.nn import SAGEConv, BatchNorm

logger = logging.getLogger(__name__)


class FraudSAGE(torch.nn.Module):
    """Inductive GraphSAGE classifier.

    Parameters
    ----------
    in_channels : int
        Dimensionality of input node features.
    hidden_channels : int
        Width of each hidden SAGEConv layer.
    out_channels : int
        Number of output classes (default 2: fraud / benign).
    num_layers : int
        Depth of the message-passing stack (default 2).
    dropout : float
        Dropout probability applied after each hidden layer.
    """

    def __init__(
        self,
        in_channels: int = 16,
        hidden_channels: int = 64,
        out_channels: int = 2,
        num_layers: int = 2,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()
        self.dropout = dropout

        self.convs = torch.nn.ModuleList()
        self.norms = torch.nn.ModuleList()

        self.convs.append(SAGEConv(in_channels, hidden_channels))
        self.norms.append(BatchNorm(hidden_channels))

        for _ in range(num_layers - 2):
            self.convs.append(SAGEConv(hidden_channels, hidden_channels))
            self.norms.append(BatchNorm(hidden_channels))

        self.convs.append(SAGEConv(hidden_channels, out_channels))

        self._reset_parameters()

    def _reset_parameters(self) -> None:
        for conv in self.convs:
            conv.reset_parameters()
        for norm in self.norms:
            norm.reset_parameters()

    def forward(self, x: Tensor, edge_index: Tensor) -> Tensor:
        """Run forward pass and return log-softmax logits."""
        for i, conv in enumerate(self.convs[:-1]):
            x = conv(x, edge_index)
            x = self.norms[i](x)
            x = F.elu(x, inplace=True)
            x = F.dropout(x, p=self.dropout, training=self.training)

        x = self.convs[-1](x, edge_index)
        return F.log_softmax(x, dim=-1)

    def predict_proba(self, x: Tensor, edge_index: Tensor) -> Tensor:
        """Return class probabilities (no gradient tracking)."""
        self.eval()
        with torch.no_grad():
            logits = self.forward(x, edge_index)
        return logits.exp()  # log_softmax → softmax


def train_one_epoch(
    model: FraudSAGE,
    optimizer: torch.optim.Optimizer,
    x: Tensor,
    edge_index: Tensor,
    labels: Tensor,
    train_mask: Tensor,
) -> float:
    """Standard supervised training step.  Returns loss value."""
    model.train()
    optimizer.zero_grad()
    out = model(x, edge_index)
    loss = F.nll_loss(out[train_mask], labels[train_mask])
    loss.backward()
    optimizer.step()
    return loss.item()


@torch.no_grad()
def evaluate(
    model: FraudSAGE,
    x: Tensor,
    edge_index: Tensor,
    labels: Tensor,
    mask: Tensor,
) -> dict[str, float]:
    """Return accuracy and loss on the given mask split."""
    model.eval()
    out = model(x, edge_index)
    loss = F.nll_loss(out[mask], labels[mask]).item()
    preds = out[mask].argmax(dim=-1)
    correct = (preds == labels[mask]).sum().item()
    total = mask.sum().item()
    return {"loss": loss, "accuracy": correct / total if total else 0.0}
