"""The licensed real-video example works before hosted storage is configured."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api import routes_analysis, state
from backend.config import settings
from backend.main import app


@pytest.fixture
def real_demo_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "hosted", True)
    guards: list[Mock] = []

    def forbidden(name: str) -> Mock:
        guard = Mock(name=name, side_effect=AssertionError(f"Unexpected external access: {name}"))
        guards.append(guard)
        return guard

    database = Mock()
    for method in ("get", "create", "update", "delete", "list_recent"):
        setattr(database, method, forbidden(f"database.{method}"))
    jobs = Mock(get=forbidden("jobs.get"))
    monkeypatch.setattr(state, "database", database)
    monkeypatch.setattr(routes_analysis, "database", database)
    monkeypatch.setattr(state, "jobs", jobs)
    monkeypatch.setattr(routes_analysis, "jobs", jobs)
    monkeypatch.setattr(state, "read_result", forbidden("state.read_result"))
    monkeypatch.setattr(routes_analysis, "read_result", forbidden("routes.read_result"))
    monkeypatch.setattr(routes_analysis, "source_file", forbidden("source_file"))
    monkeypatch.setattr(routes_analysis, "annotated_file", forbidden("annotated_file"))
    monkeypatch.setattr(routes_analysis, "save_analysis", forbidden("save_analysis"))
    monkeypatch.setattr(routes_analysis, "delete_files", forbidden("delete_files"))
    with TestClient(app) as client:
        yield client
    for guard in guards:
        guard.assert_not_called()


def test_bundled_real_analysis_contains_credited_video_measurements():
    analysis = state.real_demo_analysis()
    assert analysis is not None, "Generate and commit backend/demo/real_analysis.json"
    assert analysis.analysis_id == state.REAL_DEMO_ID == "real-demo"
    assert analysis.source == "video"
    assert analysis.video.duration == pytest.approx(25.0)
    assert analysis.video.frame_count == 750
    assert analysis.summary.vehicles_tracked > 0
    assert analysis.trajectories
    assert all(track.points for track in analysis.trajectories)
    assert any(point.bbox for track in analysis.trajectories for point in track.points)
    assert analysis.arrivals, "The real example needs observed arrivals for scenario exploration"
    assert analysis.sample is not None
    assert analysis.sample.author == "Kjetil_r"
    assert "public domain" in analysis.sample.license.lower()
    assert analysis.sample.source_url == (
        "https://commons.wikimedia.org/wiki/File:E18-Lysaker_(02).ogv"
    )
    assert analysis.sample.license_url
    assert analysis.sample.processing_notes
    assert any("stabili" in note.lower() for note in analysis.sample.processing_notes)
    assert analysis.sample.video_url == "/demos/traffic-source.mp4"
    assert analysis.sample.annotated_video_url == "/demos/traffic-annotated.mp4"


def test_real_result_preserves_video_provenance_and_honors_point_limit(real_demo_client):
    response = real_demo_client.get("/api/analyses/real-demo/result?trajectory_points=10")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "video"
    assert body["sample"]["author"] == "Kjetil_r"
    assert body["summary"]["vehicles_tracked"] > 0
    assert body["trajectories"]
    assert all(len(track["points"]) <= 10 for track in body["trajectories"])


def test_real_status_is_complete_without_a_job_or_database_row(real_demo_client):
    response = real_demo_client.get("/api/analyses/real-demo/status")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["analysis_id"] == "real-demo"
    assert body["status"] == "complete"
    assert body["progress"] == 1.0
    assert body["video"]["duration"] == pytest.approx(25.0)


def test_real_replay_contains_tracked_vehicles_without_blob_access(real_demo_client):
    response = real_demo_client.get("/api/analyses/real-demo/timeline")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["duration"] == pytest.approx(25.0)
    assert body["vehicles"]
    assert all(vehicle["segments"] for vehicle in body["vehicles"])


@pytest.mark.parametrize("name", [
    "summary.json", "vehicles.csv", "queue.csv", "events.csv", "measurements",
])
def test_real_exports_need_no_hosted_storage(real_demo_client, name):
    response = real_demo_client.get(f"/api/analyses/real-demo/export/{name}")
    assert response.status_code == 200, response.text
    assert response.content
    if name != "measurements":
        assert "attachment" in response.headers["content-disposition"]
    if name == "summary.json":
        body = response.json()
        assert body["manifest"]["source"] == "video"
        assert body["analysis"]["sample"]["author"] == "Kjetil_r"


def test_real_example_runs_scenarios_from_observed_arrivals(real_demo_client):
    response = real_demo_client.post(
        "/api/analyses/real-demo/simulate", json={"scenario": {}}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["analysis_id"] == "real-demo"
    assert body["simulated"]["observation_seconds"] > 0
    assert body["baseline"] == body["simulated"]
    assert body["disclaimer"]


def test_real_example_offers_scenario_presets(real_demo_client):
    response = real_demo_client.get("/api/analyses/real-demo/simulation/presets")
    assert response.status_code == 200, response.text
    assert response.json()


def test_real_regions_cannot_be_saved_or_remeasured(real_demo_client):
    analysis = state.real_demo_analysis()
    assert analysis is not None
    response = real_demo_client.put(
        "/api/analyses/real-demo/regions",
        json={"regions": analysis.regions.model_dump(mode="json")},
    )
    assert response.status_code == 400, response.text
    assert "read-only" in response.json()["message"]


def test_real_example_cannot_be_deleted(real_demo_client):
    response = real_demo_client.delete("/api/analyses/real-demo")
    assert response.status_code == 400, response.text
    assert "cannot be deleted" in response.json()["message"]


@pytest.mark.parametrize("kind,location", [
    ("source", "/demos/traffic-source.mp4"),
    ("annotated", "/demos/traffic-annotated.mp4"),
])
def test_real_media_redirects_to_public_bundled_assets(real_demo_client, kind, location):
    response = real_demo_client.get(
        f"/api/analyses/real-demo/video/{kind}", follow_redirects=False
    )
    assert response.status_code == 307, response.text
    assert response.headers["location"] == location
