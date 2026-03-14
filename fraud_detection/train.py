"""
Standalone training script for the GraphSAGE fraud classifier.

Usage
-----
    python -m fraud_detection.train                # defaults
    python -m fraud_detection.train --epochs 500   # more training
"""

from __future__ import annotations

import argparse
import logging
import time

import torch

from fraud_detection.config import AppConfig
from fraud_detection.data.synthetic import generate_fraud_ring_dataset
from fraud_detection.models.sage_model import FraudSAGE, train_one_epoch, evaluate

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train GraphSAGE fraud classifier")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--lr", type=float, default=0.005)
    parser.add_argument("--hidden", type=int, default=64)
    parser.add_argument("--layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--save", type=str, default="fraud_sage.pt")
    args = parser.parse_args()

    logging.basicConfig(level="INFO", format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    logger.info("Generating synthetic dataset (seed=%d)…", args.seed)
    dataset = generate_fraud_ring_dataset(
        n_benign_phones=400,
        n_fraud_rings=10,
        ring_size=5,
        calls_per_benign=4,
        calls_per_fraud=8,
        seed=args.seed
    )
    pyg = dataset["pyg_data"]
    stats = dataset["stats"]
    logger.info("Dataset stats: %s", stats)

    model = FraudSAGE(
        in_channels=pyg.x.size(1),
        hidden_channels=args.hidden,
        out_channels=2,
        num_layers=args.layers,
        dropout=args.dropout,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    logger.info("Training for %d epochs…", args.epochs)
    t0 = time.perf_counter()

    best_val_acc = 0.0
    for epoch in range(1, args.epochs + 1):
        loss = train_one_epoch(model, optimizer, pyg.x, pyg.edge_index, pyg.y, pyg.train_mask)
        if epoch % 20 == 0 or epoch == 1:
            val = evaluate(model, pyg.x, pyg.edge_index, pyg.y, pyg.val_mask)
            marker = ""
            if val["accuracy"] > best_val_acc:
                best_val_acc = val["accuracy"]
                torch.save(model.state_dict(), args.save)
                marker = " *saved*"
            logger.info(
                "Epoch %3d  loss=%.4f  val_acc=%.3f  val_loss=%.4f%s",
                epoch, loss, val["accuracy"], val["loss"], marker,
            )

    elapsed = time.perf_counter() - t0
    test = evaluate(model, pyg.x, pyg.edge_index, pyg.y, pyg.test_mask)
    logger.info("Training complete in %.1fs", elapsed)
    logger.info("Test accuracy: %.3f  Test loss: %.4f", test["accuracy"], test["loss"])
    logger.info("Best model saved to %s", args.save)

    # Quick class distribution
    fraud_count = (pyg.y == 1).sum().item()
    benign_count = (pyg.y == 0).sum().item()
    logger.info("Label distribution: fraud=%d  benign=%d  ratio=%.2f%%",
                fraud_count, benign_count, 100 * fraud_count / (fraud_count + benign_count))


if __name__ == "__main__":
    main()
