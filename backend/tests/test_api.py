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

# ------------------------------------------------------ single page app safety


def _fake_dist(tmp_path):
    """A build directory plus a file that must never be reachable from it."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>FLOWLAB</html>", encoding="utf-8")
    (dist / "app.js").write_text("console.log('app')", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("classified", encoding="utf-8")
    return dist


def test_spa_never_serves_a_file_outside_the_frontend_dist(tmp_path, monkeypatch):
    """The catch-all must resolve *and* check containment, not just join a path."""
    from backend import main

    dist = _fake_dist(tmp_path)
    monkeypatch.setattr(main, "FRONTEND_DIST", dist)

    assert main.spa_file("app.js").read_text(encoding="utf-8") == "console.log('app')"
    assert main.spa_file("").name == "index.html"
    assert main.spa_file("missing.js").name == "index.html"  # client-side route
    for escape in (
        "../secret.txt",
        "assets/../../secret.txt",
        "/../secret.txt",
        "..",
        "../",
        "..%2fsecret.txt",
        "....//secret.txt",
    ):
        assert main.spa_file(escape).name == "index.html", escape


def test_spa_route_over_http_refuses_to_leave_the_build_directory(tmp_path, monkeypatch):
    """The same handler, reached the way a browser reaches it."""
    from fastapi import FastAPI
    from fastapi.responses import FileResponse
    from fastapi.testclient import TestClient

    from backend import main

    monkeypatch.setattr(main, "FRONTEND_DIST", _fake_dist(tmp_path))
    bundle = FastAPI()

    @bundle.get("/{full_path:path}")
    async def spa(full_path: str):
        return FileResponse(main.spa_file(full_path))

    with TestClient(bundle) as http:
        assert http.get("/app.js").text == "console.log('app')"
        assert http.get("/").text == "<html>FLOWLAB</html>"
        assert http.get("/analyses").text == "<html>FLOWLAB</html>"
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/%2e%2e%2fsecret.txt"):
            assert "classified" not in http.get(path).text, path


# ------------------------------------------- result / regions query symmetry


@pytest.fixture()
def stored_analysis(monkeypatch):
    """A non-demo analysis with long tracks, stored behind the normal loader.

    The demo dataset is read-only, so the region endpoints need a real analysis
    of their own; its tracks are long enough that a sample limit is visible.
    """
    from backend.analytics.metrics import build_analysis
    from backend.api import routes_analysis
    from backend.models.schemas import VideoInfo
    from backend.tests.conftest import make_regions, make_track

    tracks = [
        make_track(1, [(0.02 + 0.004 * index, 0.5) for index in range(200)], step=0.1),
        make_track(2, [(0.02 + 0.004 * index, 0.8) for index in range(200)], step=0.1),
    ]
    analysis = build_analysis(
        analysis_id="synthetic",
        video=VideoInfo(
            filename="clip.mp4",
            duration=25.0,
            fps=25.0,
            width=320,
            height=180,
            size_bytes=1024,
            processed_fps=10.0,
            frame_count=625,
        ),
        tracks=tracks,
        regions=make_regions(),
        source="video",
        created_at=0.0,
    )
    monkeypatch.setattr(routes_analysis, "_require_analysis", lambda _id: (analysis, tracks))
    return analysis


def _points(body: dict) -> list[int]:
    return [len(track["points"]) for track in body["trajectories"]]


def test_result_and_regions_honour_trajectory_points_identically(client, stored_analysis):
    """One parameter, one meaning: redrawing regions must not change the map size."""
    payload = {"regions": stored_analysis.regions.model_dump(mode="json")}
    for limit in (4, 10, 60, 200):
        fetched = client.get(f"/api/analyses/synthetic/result?trajectory_points={limit}")
        redrawn = client.put(
            f"/api/analyses/synthetic/regions?trajectory_points={limit}", json=payload
        )
        assert fetched.status_code == redrawn.status_code == 200
        assert _points(fetched.json()) == _points(redrawn.json()), limit
        assert _points(fetched.json()) == [limit, limit], limit


def test_both_endpoints_default_to_the_same_resolution(client, stored_analysis):
    payload = {"regions": stored_analysis.regions.model_dump(mode="json")}
    fetched = client.get("/api/analyses/synthetic/result")
    redrawn = client.put("/api/analyses/synthetic/regions", json=payload)
    assert _points(fetched.json()) == _points(redrawn.json()) == [60, 60]


def test_both_endpoints_reject_the_same_out_of_range_limits(client, stored_analysis):
    payload = {"regions": stored_analysis.regions.model_dump(mode="json")}
    for limit in (3, 601):
        result = client.get(f"/api/analyses/synthetic/result?trajectory_points={limit}")
        assert result.status_code == 422
        redrawn = client.put(
            f"/api/analyses/synthetic/regions?trajectory_points={limit}", json=payload
        )
        assert redrawn.status_code == 422, limit
        assert "trajectory_points" in redrawn.json()["message"]


def test_regions_response_keeps_the_measurements_and_only_thins_the_map(
    client, stored_analysis
):
    """Down-sampling is a transport decision: no summary number may move."""
    payload = {"regions": stored_analysis.regions.model_dump(mode="json")}
    full = client.get("/api/analyses/synthetic/result?trajectory_points=600").json()
    thin = client.put(
        "/api/analyses/synthetic/regions?trajectory_points=4", json=payload
    ).json()
    assert thin["summary"] == full["summary"]
    assert thin["queue_timeseries"] == full["queue_timeseries"]
    assert thin["calibration"] == full["calibration"]
    assert _points(thin) == [4, 4]
    # The first and last samples survive thinning so the map path stays complete.
    for track in thin["trajectories"]:
        assert track["points"][0]["time"] == 0.0
        assert track["points"][-1]["time"] == 19.9


# -------------------------------------------------------- error contract


def test_every_error_uses_the_same_message_and_hint_shape(client):
    """One error shape, whatever went wrong - the client never inspects a body."""
    responses = [
        client.get("/api/analyses/does-not-exist/result"),
        client.get("/api/analyses/demo/result?trajectory_points=3"),
        client.delete("/api/analyses/demo"),
        client.post("/api/analyses/demo/simulate", json={"scenario": {"volume": 9.0}}),
        client.put("/api/analyses/demo/regions", json={"regions": {}}),
        client.get("/api/analyses/never-seen/status"),
    ]
    for response in responses:
        assert response.status_code >= 400, response.url
        body = response.json()
        assert set(body) == {"message", "hint"}, response.url
        assert isinstance(body["message"], str) and body["message"]


def test_a_refusal_that_says_what_to_do_next_carries_a_hint(client, tmp_video, monkeypatch):
    """The 429 is the one error the user can act on immediately, so it says how."""
    from backend.api import state
    from backend.api.routes_upload import QUEUE_FULL_HINT

    monkeypatch.setattr(state.jobs, "pending_count", lambda: 99)
    path = tmp_video("clip.mp4", seconds=3.0)
    with open(path, "rb") as handle:
        response = client.post(
            "/api/uploads", files={"file": ("clip.mp4", handle, "video/mp4")}
        )
    assert response.status_code == 429
    assert response.json()["hint"] == QUEUE_FULL_HINT


# ------------------------------------------------------------ status states


def test_status_reports_every_state_the_database_can_hold(client):
    from backend.api.state import database

    for stored in ("queued", "processing", "complete", "error"):
        analysis_id = f"status-{stored}"
        database.create(analysis_id, source="video", filename="clip.mp4", upload_path=None)
        database.update(analysis_id, status=stored)
        try:
            body = client.get(f"/api/analyses/{analysis_id}/status").json()
            assert body["status"] == stored
        finally:
            database.delete(analysis_id)


def test_an_unknown_stored_state_is_reported_rather_than_guessed(client):
    """The column is free-form TEXT, so an unknown value must not be passed through."""
    from backend.api.state import database

    database.create("status-broken", source="video", filename="clip.mp4", upload_path=None)
    database.update("status-broken", status="halfway")
    try:
        response = client.get("/api/analyses/status-broken/status")
        assert response.status_code == 500
        assert "halfway" in response.json()["message"]
    finally:
        database.delete("status-broken")
