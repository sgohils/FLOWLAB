"""Developer check: how closely does the baseline simulation reproduce the
observed behaviour of the demo dataset, and do the scenario controls move the
metrics in the expected direction?

    python -m backend.scripts.check_calibration
"""

from __future__ import annotations

import json

from ..models.schemas import Analysis, Scenario
from ..simulation.simulator import run_scenario

DEMO_FILE = "backend/demo/sample_analysis.json"


def main() -> None:
    with open(DEMO_FILE, encoding="utf-8") as handle:
        analysis = Analysis.model_validate(json.load(handle))
    summary = analysis.summary
    print("observed : peak", summary.peak_queue, "avgq", summary.average_queue,
          "avgwait", summary.average_wait_seconds, "maxwait", summary.max_wait_seconds,
          "thr", summary.throughput_per_minute)
    scenarios = [
        ("baseline", Scenario()),
        ("volume -25%", Scenario(volume=0.75)),
        ("exit x1.5", Scenario(service_multiplier=1.5)),
        ("second lane", Scenario(channels=2)),
        ("spread +120s", Scenario(spread_seconds=120.0)),
        ("volume +25% + exit", Scenario(volume=1.25, service_multiplier=1.25, channels=2)),
    ]
    for label, scenario in scenarios:
        result = run_scenario(analysis, scenario)
        metrics = result.simulated
        print(
            f"{label:<20} peak={metrics.peak_queue:>3} avgq={metrics.average_queue:>5} "
            f"avgwait={metrics.average_wait_seconds:>6} maxwait={metrics.max_wait_seconds:>6} "
            f"thr={metrics.throughput_per_minute:>6} veh={metrics.vehicles}"
        )


if __name__ == "__main__":
    main()
