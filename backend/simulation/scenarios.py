"""Scenario definitions and the exact transformations they apply.

A scenario only ever changes four things relative to the observed baseline:

``volume``            how many vehicles arrive (observed count * volume)
``service_multiplier`` how fast the exit processes a vehicle
                      (service_time = observed / service_multiplier)
``spread_seconds``    how much longer the arrival burst is stretched over
``channels``          how many parallel exit processing lanes exist

Nothing else is invented: the corridor, the free-flow speed and the stopping
behaviour always come from the calibration of the observed footage.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.schemas import Scenario


@dataclass(frozen=True, slots=True)
class ScenarioPlan:
    """Concrete numbers handed to the simulator."""

    label: str
    volume: float
    service_time: float
    window_seconds: float
    arrival_times: list[float]
    channels: int
    seed: int
    notes: list[str]

    @property
    def vehicle_count(self) -> int:
        return len(self.arrival_times)


#: Deterministic spacing added when new vehicles are injected by a volume
#: increase, in seconds.  Fixed (not random) so a scenario always repeats.
_EXTRA_SPACING = 0.35


def build_arrivals(
    observed: list[float],
    volume: float,
    spread_seconds: float,
    span: float,
    seed: int,
) -> list[float]:
    """Transform the observed arrival sequence into a scenario arrival sequence.

    * ``volume < 1``  -> drop vehicles at evenly spaced indices, so the
      remaining vehicles keep their real order and spacing.
    * ``volume > 1``  -> keep every observed vehicle and insert extra ones at a
      fixed spacing around the same window.
    * ``spread``      -> linearly stretch the whole sequence so it occupies
      ``span + spread`` seconds instead of ``span``.

    The result is fully deterministic: the same inputs always give the same
    arrivals, which is what makes the comparison reproducible.
    """
    base = sorted(observed) or [0.0]
    if span <= 0:
        span = max(base[-1], 1.0)

    count = max(1, int(round(len(base) * volume)))
    arrivals: list[float] = []
    if count <= len(base):
        # Even decimation: keeps the first vehicle and the temporal spread.
        step = len(base) / count
        for index in range(count):
            arrivals.append(base[min(len(base) - 1, int(index * step))])
    else:
        extra = count - len(base)
        window = max(base[-1] - base[0], 1e-6)
        for index in range(extra):
            offset = (index + 1) * _EXTRA_SPACING * seed_factor(seed)
            position = base[0] + (window * (index + 1)) / (extra + 1)
            arrivals.append(position + offset)
        arrivals.extend(base)

    arrivals.sort()
    first, last = arrivals[0], arrivals[-1]
    target_span = max(span + spread_seconds, 0.5)
    current_span = last - first
    if current_span > 1e-6:
        scale = target_span / current_span
    else:
        scale = 1.0
    return [round(first + (t - first) * scale, 3) for t in arrivals]


def seed_factor(seed: int) -> float:
    """A stable 0.5-1.5 multiplier derived from the seed (keeps runs repeatable)."""
    return 0.5 + ((seed % 1000) / 1000.0)


def plan_scenario(scenario: Scenario, calibration, observed_arrivals: list[float]) -> ScenarioPlan:
    """Translate a :class:`Scenario` into concrete simulator inputs.

    Time window rule: with no spreading, the scenario runs over **exactly** the
    observation window of the clip, so observed and simulated throughput cover the
    same duration.  Spreading arrivals is the only control that lengthens it, and
    the result says so in its notes.
    """
    notes: list[str] = []
    observation = max(calibration.observation_seconds, 1.0)
    window = observation + max(0.0, scenario.spread_seconds)
    arrivals = build_arrivals(
        observed_arrivals,
        scenario.volume,
        scenario.spread_seconds,
        observation,
        scenario.seed,
    )
    # The arrival series is rescaled onto the window above; anchoring it at zero
    # keeps the simulated timeline and the clip timeline aligned.
    if arrivals and arrivals[0] > 0:
        offset = arrivals[0]
        arrivals = [round(max(0.0, moment - offset), 3) for moment in arrivals]
    service_time = max(
        0.5, round(calibration.service_time_seconds / scenario.service_multiplier, 3)
    )

    if abs(scenario.volume - 1.0) > 1e-9:
        notes.append(
            f"Traffic volume {scenario.volume:+.0%}: {len(arrivals)} vehicles instead of "
            f"{len(observed_arrivals)}."
        )
    if scenario.spread_seconds > 0:
        notes.append(
            f"Arrivals spread over {observation + scenario.spread_seconds:.0f}s instead of {observation:.0f}s."
        )
    if abs(scenario.service_multiplier - 1.0) > 1e-9:
        notes.append(
            f"Exit service time {service_time:.2f}s per vehicle "
            f"({scenario.service_multiplier:.2f}x observed)."
        )
    if scenario.channels > 1:
        notes.append(f"A second exit processing channel is open ({scenario.channels} lanes).")
    if not notes:
        notes.append("Baseline scenario: identical to the observed conditions.")
    return ScenarioPlan(
        label=describe(scenario),
        volume=scenario.volume,
        service_time=service_time,
        window_seconds=round(window, 2),
        arrival_times=arrivals,
        channels=scenario.channels,
        seed=scenario.seed,
        notes=notes,
    )


def describe(scenario: Scenario) -> str:
    """Short human label for the scenario, used in the UI header."""
    if abs(scenario.volume - 1.0) < 1e-9 and abs(scenario.service_multiplier - 1.0) < 1e-9:
        base = "Observed"
    else:
        parts = []
        if abs(scenario.volume - 1.0) > 1e-9:
            parts.append(f"volume {scenario.volume:+.0%}")
        if abs(scenario.service_multiplier - 1.0) > 1e-9:
            parts.append(
                "faster exit" if scenario.service_multiplier > 1 else "slower exit"
            )
        if scenario.spread_seconds > 0:
            parts.append(f"spread +{scenario.spread_seconds:.0f}s")
        if scenario.channels > 1:
            parts.append("second exit lane")
        base = ", ".join(parts)
    return base or "Observed"


def presets(observed: Scenario) -> dict[str, Scenario]:
    """Named starting points for the sliders in the simulation panel."""
    return {
        "observed": observed,
        "lower_volume": observed.model_copy(update={"volume": 0.75}),
        "faster_exit": observed.model_copy(update={"service_multiplier": 1.5}),
        "spread_arrivals": observed.model_copy(update={"spread_seconds": 120.0}),
        "second_channel": observed.model_copy(update={"channels": 2}),
    }
