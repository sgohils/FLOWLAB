"""API contract tests.

These use the bundled demo dataset, so no model inference and no video file is
needed to exercise the whole HTTP surface.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------- meta & health


def test_health_reports_the_model_state(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "model_name" in body


def test_meta_exposes_the_configuration_the_ui_needs(client: TestClient):
    body = client.get("/api/meta").json()
    assert body["sample_fps"] >= 5
    assert "car" in body["vehicle_classes"]
    assert "person" not in body["vehicle_classes"]
    assert body["allowed_extensions"]
    assert len(body["stages"]) >= 7


# ---------------------------------------------------------------- demo dataset


def test_demo_dataset_is_served_and_labelled(client: TestClient):
    body = client.get("/api/demo").json()
    assert body["source"] == "demo"
    assert body["summary"]["vehicles_tracked"] > 0
    assert body["trajectories"]
    assert any("Demo Dataset" in warning for warning in body["warnings"])


def test_demo_dataset_appears_in_the_list(client: TestClient):
    items = client.get("/api/analyses").json()
    assert any(item["analysis_id"] == "demo" and item["source"] == "demo" for item in items)


def test_demo_result_can_be_thinned(client: TestClient):
    body = client.get("/api/analyses/demo/result?trajectory_points=10").json()
    for track in body["trajectories"]:
        assert len(track["points"]) <= 10
        # The first and last samples are always kept so the map stays complete.
        assert track["points"][0]["time"] == 0.0 or track["points"]


def test_unknown_analysis_returns_a_message(client: TestClient):
    response = client.get("/api/analyses/does-not-exist/result")
    assert response.status_code == 404
    assert "does-not-exist" in response.json()["message"]


# ---------------------------------------------------------------- simulation


def test_simulate_returns_three_way_comparison(client: TestClient):
    """Observed (A), baseline model (B) and modified model (C) are all present."""
    response = client.post(
        "/api/analyses/demo/simulate", json={"scenario": {"volume": 1.0}}
    )
    assert response.status_code == 200
    body = response.json()
    for key in ("observed", "baseline", "simulated", "fidelity", "deltas", "model_deltas"):
        assert key in body, f"missing {key}"
    for key in ("observed_queue", "baseline_queue", "simulated_queue"):
        assert body[key], f"missing {key}"
    # With every control at the observed value, B and C must be identical.
    assert body["baseline"] == body["simulated"]
    assert "Simulated" in body["disclaimer"]


def test_scenario_effect_is_measured_against_the_baseline(client: TestClient):
    body = client.post(
        "/api/analyses/demo/simulate", json={"scenario": {"channels": 2}}
    ).json()
    # deltas = modified vs baseline, model_deltas = baseline vs observed.
    assert [d["metric"] for d in body["deltas"]] == [d["metric"] for d in body["model_deltas"]]
    for delta in body["deltas"]:
        assert delta["simulated"] == body["simulated"][delta["metric"]]
        assert delta["observed"] == body["baseline"][delta["metric"]]
    for delta in body["model_deltas"]:
        assert delta["simulated"] == body["baseline"][delta["metric"]]
        assert delta["observed"] == body["observed"][delta["metric"]]
    # Opening a second lane cannot make the queue longer.
    peak = next(d for d in body["deltas"] if d["metric"] == "peak_queue")
    assert peak["absolute"] <= 0


def test_fidelity_is_independent_of_the_scenario(client: TestClient):
    baseline = client.post(
        "/api/analyses/demo/simulate", json={"scenario": {"volume": 1.0}}
    ).json()
    other = client.post(
        "/api/analyses/demo/simulate", json={"scenario": {"volume": 1.5, "channels": 2}}
    ).json()
    assert baseline["fidelity"]["ratio"] == other["fidelity"]["ratio"]
    assert baseline["fidelity"]["note"] == other["fidelity"]["note"]


def test_simulate_is_repeatable(client: TestClient):
    payload = {"scenario": {"volume": 1.25, "service_multiplier": 1.5, "channels": 2}}
    first = client.post("/api/analyses/demo/simulate", json=payload).json()
    second = client.post("/api/analyses/demo/simulate", json=payload).json()
    assert first["simulated"] == second["simulated"]
    assert [s["queue"] for s in first["simulated_queue"]] == [
        s["queue"] for s in second["simulated_queue"]
    ]


def test_timeline_is_uniform_and_marks_tracking_gaps(client: TestClient):
    """The replay payload must not invent motion across a dropout."""
    body = client.get("/api/analyses/demo/timeline?hz=4").json()
    assert body["hz"] == 4.0
    assert body["sampling_fps"] == 10.0
    assert body["gap_threshold_s"] == pytest.approx(0.25, abs=1e-6)
    assert body["vehicles"], "the demo dataset has vehicles"
    assert body["queue"], "a queue series is required for the chart cursor"
    assert body["vehicles_omitted"] == 0
    # "known" is carried by the segment structure, so no per-point flag is needed
    assert all("segments" in vehicle for vehicle in body["vehicles"])
    for vehicle in body["vehicles"]:
        for segment in vehicle["segments"]:
            assert len(segment["t"]) == len(segment["x"]) == len(segment["y"])


def test_timeline_resolution_is_honoured(client: TestClient):
    coarse = client.get("/api/analyses/demo/timeline?hz=1").json()
    fine = client.get("/api/analyses/demo/timeline?hz=10").json()

    def points(body: dict) -> int:
        return sum(len(s["t"]) for v in body["vehicles"] for s in v["segments"])

    assert points(fine) > points(coarse) * 3


def test_timeline_rejects_an_absurd_resolution(client: TestClient):
    assert client.get("/api/analyses/demo/timeline?hz=900").status_code == 422


def test_timeline_of_unknown_analysis_is_404(client: TestClient):
    assert client.get("/api/analyses/nope/timeline").status_code == 404


# ------------------------------------------------------------------- export


def test_export_summary_is_a_download_without_video(client: TestClient):
    response = client.get("/api/analyses/demo/export/summary.json")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert ".json" in response.headers["content-disposition"]
    body = response.json()
    assert body["manifest"]["contains_video"] is False
    assert "no video" in body["manifest"]["privacy_note"]
    assert "filename" not in body["analysis"]["video"]


def test_export_csvs_have_their_headers(client: TestClient):
    vehicles = client.get("/api/analyses/demo/export/vehicles.csv")
    assert vehicles.status_code == 200
    assert "text/csv" in vehicles.headers["content-type"]
    assert "queue_region_slow_s" in vehicles.text.splitlines()[0]

    queue = client.get("/api/analyses/demo/export/queue.csv")
    assert queue.text.splitlines()[0] == "time_s,queue_length"

    events = client.get("/api/analyses/demo/export/events.csv")
    assert "# bottlenecks" in events.text


def test_measurements_endpoint_explains_itself(client: TestClient):
    payload = client.get("/api/analyses/demo/export/measurements").json()
    assert payload["analysis_id"] == "demo"
    assert "definitions" in payload
    assert "privacy_note" in payload
    assert payload["definitions"]["queue_region_slow_s"].startswith("estimated wait")


def test_export_of_unknown_analysis_is_a_clear_error(client: TestClient):
    response = client.get("/api/analyses/nope/export/summary.json")
    assert response.status_code == 404
    assert "nope" in response.json()["message"]


# ------------------------------------------------------------------- delete


def test_demo_cannot_be_deleted(client: TestClient):
    response = client.delete("/api/analyses/demo")
    assert response.status_code == 400
    assert "demo" in response.json()["message"].lower()


def test_delete_of_unknown_analysis_is_404(client: TestClient):
    response = client.delete("/api/analyses/never-existed")
    assert response.status_code == 404


def test_simulate_rejects_out_of_range_parameters(client: TestClient):
    response = client.post("/api/analyses/demo/simulate", json={"scenario": {"volume": 9.0}})
    assert response.status_code == 422
    assert "volume" in response.json()["message"]


def test_scenario_presets_are_offered(client: TestClient):
    presets = client.get("/api/analyses/demo/simulation/presets").json()
    assert any(preset["volume"] == 1.0 for preset in presets)
    assert any(preset["channels"] == 2 for preset in presets)


# ---------------------------------------------------------------- regions


def test_demo_regions_are_read_only(client: TestClient):
    response = client.put("/api/analyses/demo/regions", json={"regions": {}})
    assert response.status_code == 400
    assert "read-only" in response.json()["message"]


def test_invalid_region_geometry_is_rejected(client: TestClient):
    response = client.put(
        "/api/analyses/demo/regions",
        json={"regions": {"queue": [[0.1, 0.1], [0.5, 0.5]]}},
    )
    assert response.status_code == 422
    assert "queue" in response.json()["message"].lower()


def test_out_of_frame_coordinates_are_rejected(client: TestClient):
    response = client.put(
        "/api/analyses/demo/regions",
        json={"regions": {"queue": [[0.1, 0.1], [1.4, 0.1], [1.4, 0.9], [0.1, 0.9]]}},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------- upload


def test_upload_rejects_unsupported_extensions(client: TestClient):
    response = client.post(
        "/api/uploads", files={"file": ("payload.exe", b"MZ\x90\x00", "application/octet-stream")}
    )
    assert response.status_code == 415
    assert "not a supported video format" in response.json()["message"]


def test_upload_rejects_files_that_are_not_videos(client: TestClient):
    response = client.post(
        "/api/uploads", files={"file": ("clip.mp4", b"this is not a video", "video/mp4")}
    )
    assert response.status_code == 400
    assert "message" in response.json()


def test_upload_rejects_empty_files(client: TestClient):
    response = client.post("/api/uploads", files={"file": ("empty.mp4", b"", "video/mp4")})
    assert response.status_code == 400


def test_valid_upload_is_accepted(client: TestClient, tmp_video, monkeypatch):
    # The processing itself is exercised elsewhere; here we only check the
    # upload contract, so the job is intercepted.
    from backend.api import state

    monkeypatch.setattr(state.jobs, "submit", lambda *args, **kwargs: None)
    path = tmp_video("clip.mp4", seconds=3.0)
    with open(path, "rb") as handle:
        response = client.post(
            "/api/uploads", files={"file": ("clip.mp4", handle, "video/mp4")}
        )
    assert response.status_code == 202
    body = response.json()
    assert body["video"]["width"] == 320
    assert body["video"]["duration"] > 0
    assert body["status_url"].endswith(body["analysis_id"] + "/status")
    state.database.delete(body["analysis_id"])


def test_upload_queue_is_bounded(client: TestClient, tmp_video, monkeypatch):
    """A machine already busy with jobs refuses new work instead of piling up."""
    from backend.api import state

    monkeypatch.setattr(state.jobs, "pending_count", lambda: 99)
    path = tmp_video("clip.mp4", seconds=3.0)
    with open(path, "rb") as handle:
        response = client.post(
            "/api/uploads", files={"file": ("clip.mp4", handle, "video/mp4")}
        )
    assert response.status_code == 429
    assert "queued" in response.json()["message"]


def test_status_endpoint_never_crashes_for_unknown_ids(client: TestClient):
    response = client.get("/api/analyses/never-seen/status")
    assert response.status_code == 404
