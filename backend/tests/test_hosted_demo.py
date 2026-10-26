"""A fresh hosted deployment can use the demo before cloud storage is connected."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api import routes_analysis, state
from backend.config import settings
from backend.main import app
from backend.storage.postgres import PostgresDatabase


@pytest.fixture
def hosted_client(monkeypatch):
    monkeypatch.setattr(settings, "hosted", True)
    unavailable = Mock(side_effect=AssertionError("Demo must not access external storage"))
    database = Mock()
    database.get = unavailable
    database.create = unavailable
    database.update = unavailable
    monkeypatch.setattr(state, "database", database)
    monkeypatch.setattr(routes_analysis, "database", database)
    monkeypatch.setattr(routes_analysis, "jobs", Mock(get=unavailable))
    monkeypatch.setattr(state, "read_result", unavailable)
    monkeypatch.setattr(routes_analysis, "read_result", unavailable)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("path", [
    "/api/demo", "/api/analyses/demo/result", "/api/analyses/demo/status",
    "/api/analyses/demo/timeline", "/api/analyses/demo/simulation/presets",
    "/api/analyses/demo/export/summary.json", "/api/analyses/demo/export/vehicles.csv",
    "/api/analyses/demo/export/queue.csv", "/api/analyses/demo/export/events.csv",
    "/api/analyses/demo/export/measurements",
])
def test_hosted_demo_endpoints_need_no_database_or_blob(hosted_client, path):
    response = hosted_client.get(path)
    assert response.status_code == 200, response.text


def test_hosted_demo_runs_a_real_simulation(hosted_client):
    response = hosted_client.post("/api/analyses/demo/simulate", json={"scenario": {}})
    assert response.status_code == 200, response.text
    assert response.json()["analysis_id"] == "demo"
    assert response.json()["simulated"]["observation_seconds"] > 0


@pytest.mark.parametrize("kind", ["annotated", "source"])
def test_demo_video_reports_absence_without_cloud_lookup(hosted_client, kind):
    assert hosted_client.get(f"/api/analyses/demo/video/{kind}").status_code == 404


def test_hosted_probe_does_not_load_detection_model(hosted_client, monkeypatch):
    from backend.vision.detector import detector

    load = Mock(side_effect=AssertionError("Detection belongs to the worker"))
    monkeypatch.setattr(detector, "load", load)
    for path in ("/api/health", "/api/ready"):
        response = hosted_client.get(path)
        assert response.status_code == 200
        assert response.json()["processing_mode"] == "queue"
    load.assert_not_called()


def test_missing_database_returns_actionable_503_without_breaking_demo(hosted_client, monkeypatch):
    monkeypatch.setattr(routes_analysis, "database", PostgresDatabase(""))
    response = hosted_client.get("/api/analyses")
    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["hint"]
    assert "demo still works" in response.json()["hint"]
    assert hosted_client.get("/api/demo").status_code == 200


def test_hosted_list_includes_bundled_demo_without_creating_a_row(hosted_client, monkeypatch):
    database = Mock()
    database.list_recent.return_value = []
    monkeypatch.setattr(routes_analysis, "database", database)
    response = hosted_client.get("/api/analyses")
    assert response.status_code == 200
    assert {item["analysis_id"] for item in response.json()} == {"demo", "real-demo"}
    assert all(item["read_only"] for item in response.json())
    database.create.assert_not_called()


def test_unconfigured_upload_is_explained_before_sending_video_bytes(hosted_client, monkeypatch):
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    response = hosted_client.get("/api/uploads/config")
    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["hint"]
    assert "BLOB_READ_WRITE_TOKEN" in response.json()["hint"]
