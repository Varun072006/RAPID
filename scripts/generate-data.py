#!/usr/bin/env python3
"""Generate 100K synthetic payment scenarios."""

from packages.ml.simulation.scenario_generator import ScenarioGenerator

if __name__ == "__main__":
    gen = ScenarioGenerator(seed=42, n_scenarios=100_000)
    gen.save("packages/ml/simulation")
    print("[OK] Scenarios generated.")
