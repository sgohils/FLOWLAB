"""``/api/health`` speaks to the browser; ``/api/ready`` speaks to Docker.

``/api/health`` answers 200 even when the weights never loaded, which is right
for the UI - the degraded banner has to be able to read *why* - and wrong for a
container healthcheck, which called a backend with no working detector healthy
and let ``condition: service_healthy`` start the dev server against it.  The two
questions are therefore two endpoints, and the compose healthcheck now asks the
one it means.

The second half is about the loop: ``detector.load()`` is a multi-second torch
import plus weight read, and the UI calls ``/api/health`` on every Home mount.
Run inline in an ``async def`` it stops the whole server answering for its
duration.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from backend.main import app
from backend.vision.detector import DetectorError, detector

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _broken_model(monkeypatch) -> None:
    def refuse() -> None:
        raise DetectorError("Model 'yolo11n.pt' could not be loaded.")

    monkeypatch.setattr(detector, "load", refuse)
    monkeypatch.setattr(detector, "_loaded", False)


def _working_model(monkeypatch) -> None:
    monkeypatch.setattr(detector, "load", lambda: None)
    monkeypatch.setattr(detector, "_loaded", True)


# ------------------------------------------------------- liveness vs readiness


def test_health_stays_200_for_a_backend_that_cannot_detect(client, monkeypatch):
    """The browser contract: the banner must be able to read the reason."""
    _broken_model(monkeypatch)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["model_loaded"] is False
    assert "yolo11n.pt" in body["message"]


def test_ready_is_503_for_that_same_backend(client, monkeypatch):
    """The orchestration contract: unusable is not healthy, and it says why."""
    _broken_model(monkeypatch)
    response = client.get("/api/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["model_loaded"] is False
    assert body["status"] == "degraded"
    assert body["message"]


def test_ready_is_200_once_the_model_is_loaded(client, monkeypatch):
    _working_model(monkeypatch)
    for path in ("/api/health", "/api/ready"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.json()["model_loaded"] is True, path


def test_the_two_endpoints_never_disagree(client, monkeypatch):
    for state in (_broken_model, _working_model):
        state(monkeypatch)
        health = client.get("/api/health")
        ready = client.get("/api/ready")
        assert health.json() == ready.json()
        assert health.status_code == 200
        assert ready.status_code == (200 if health.json()["model_loaded"] else 503)


# ------------------------------------------------------------- the event loop


def test_loading_the_model_does_not_block_the_event_loop(monkeypatch):
    """Two concurrent health checks must overlap, and neither may run on the loop."""
    load_threads: list[int] = []

    def slow_load() -> None:
        load_threads.append(threading.get_ident())
        time.sleep(0.25)

    monkeypatch.setattr(detector, "load", slow_load)
    monkeypatch.setattr(detector, "_loaded", True)

    async def scenario() -> tuple[float, list[int]]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api") as http:
            started = time.perf_counter()
            responses = await asyncio.gather(
                http.get("/api/health"), http.get("/api/health")
            )
            return time.perf_counter() - started, [r.status_code for r in responses]

    elapsed, statuses = asyncio.run(scenario())

    assert statuses == [200, 200]
    assert threading.get_ident() not in load_threads, (
        "detector.load() ran on the event loop, so every other request waited for it"
    )
    # Serialised, this is 2 x 0.25s.  The margin is deliberately generous: the
    # thread pool has to be woken up as well.
    assert elapsed < 0.45, f"two concurrent /api/health calls took {elapsed:.2f}s"


# ------------------------------------------------------------ what ships with it


def test_the_container_healthcheck_probes_readiness_not_liveness():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    probe = " ".join(compose["services"]["backend"]["healthcheck"]["test"])
    assert "/api/ready" in probe
    assert "/api/health" not in probe
    # A failing probe has to exit non-zero, which urlopen does by raising on 503.
    assert "urlopen" in probe
    start_period = compose["services"]["backend"]["healthcheck"]["start_period"]
    assert start_period.endswith("s") and int(start_period[:-1]) >= 30


def test_the_dockerfile_healthcheck_agrees_with_compose():
    """`docker run` must reach the same verdict as `docker compose up`.

    The Dockerfile HEALTHCHECK used to probe /api/health, which answers 200
    whether or not the detector loaded, so a container whose 6 MB weight
    download failed reported healthy - while the compose healthcheck, and the
    `--profile dev` server gated on it, said otherwise.  The two are now the
    same probe with the same timings; this test is what keeps them that way.
    """
    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    # The instruction is continued with a backslash, so the probe URL is on the
    # line after the HEALTHCHECK keywords.
    instruction = " ".join(
        line.rstrip().removesuffix("\\").strip()
        for line in dockerfile.splitlines()
        if line.startswith("HEALTHCHECK") or line.strip().startswith("CMD")
    )
    assert "/api/ready" in instruction
    assert "/api/health" not in instruction, (
        "a liveness probe makes an unloaded detector look healthy; /api/health "
        "stays 200 for the browser banner, which is why the container probes "
        "/api/ready instead"
    )
    assert "urlopen" in dockerfile, "the probe has to exit non-zero on 503"

    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    compose_health = compose["services"]["backend"]["healthcheck"]
    # A cold start imports torch and downloads the checkpoint, so the start
    # period has to cover it in both places.
    assert "--start-period=120s" in instruction
    assert compose_health["start_period"] == "120s"
    assert f"--interval={compose_health['interval']}" in instruction
    assert f"--timeout={compose_health['timeout']}" in instruction
