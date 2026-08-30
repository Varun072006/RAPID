#!/usr/bin/env python3
"""Train failure classifier and recovery models."""
from packages.ml.training.train_failure import train as train_failure
from packages.ml.training.train_recovery import train as train_recovery

if __name__ == "__main__":
    print("Training failure classifier...")
    train_failure()
    print("\nTraining recovery models...")
    train_recovery()
    print("\n[OK] All models trained and saved.")
