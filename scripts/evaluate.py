#!/usr/bin/env python3
"""Run full evaluation — baselines + RAPID + distribution shift."""
import json
import pickle
from pathlib import Path

from packages.ml.evaluation.evaluator import HeldOutEvaluator
from packages.ml.simulation.scenario_generator import ScenarioGenerator

if __name__ == "__main__":
    print("Loading test data...")
    test_df = ScenarioGenerator.load("test")
    shift_df = ScenarioGenerator.load("distribution_shift")

    model_path = Path("packages/ml/models/recovery_models.pkl")
    model_bundle = None
    if model_path.exists():
        with open(model_path, "rb") as f:
            model_bundle = pickle.load(f)
    else:
        print("⚠  No trained models found. Run: make train")

    print("\n=== Held-out Evaluation ===")
    evaluator = HeldOutEvaluator(test_df)
    report = evaluator.generate_report(model_bundle)
    print(json.dumps(report, indent=2))

    print("\n=== Distribution Shift Evaluation ===")
    shift_evaluator = HeldOutEvaluator(shift_df)
    shift_report = shift_evaluator.generate_report(model_bundle)
    print(json.dumps(shift_report, indent=2))

    output = {"test": report, "distribution_shift": shift_report}
    output_path = Path("packages/ml/evaluation/report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[OK] Report saved -> {output_path}")
