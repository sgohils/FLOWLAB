"""Simulation endpoints: run a scenario against a stored analysis."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..models.schemas import Scenario, SimulationResult
from ..simulation.simulator import run_scenario
from .state import DEMO_ID, load_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["simulation"])


class ScenarioRequest(BaseModel):
    scenario: Scenario = Scenario()


@router.post("/analyses/{analysis_id}/simulate", response_model=SimulationResult)
async def simulate(analysis_id: str, payload: ScenarioRequest) -> SimulationResult:
    """Run one scenario.  The model is deterministic, so results repeat exactly."""
    analysis = load_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No analysis with id '{analysis_id}'.")
    if not analysis.arrivals:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This analysis has no vehicle arrivals, so there is nothing to simulate. "
            "Define an entry line, or upload a clip that contains moving vehicles.",
        )
    if analysis.analysis_id != DEMO_ID and analysis.summary.vehicles_tracked == 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No vehicles were tracked in this analysis, so no arrival pattern could be "
            "measured. Try different footage.",
        )
    try:
        return await asyncio.to_thread(run_scenario, analysis, payload.scenario)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/analyses/{analysis_id}/simulation/presets", response_model=list[Scenario])
async def presets(analysis_id: str) -> list[Scenario]:
    """Starting points offered by the UI sliders."""
    analysis = load_analysis(analysis_id)
    baseline = Scenario()
    if analysis is None:
        return [baseline]
    from ..simulation.scenarios import presets as build_presets

    return list(build_presets(baseline).values())
