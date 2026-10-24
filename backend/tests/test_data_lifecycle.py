"""Local data lifecycle: delete removes files, exports contain no footage.

These are the promises the privacy panel makes to the user, so they are tested
against a real temporary data directory rather than mocked.
"""

from __future__ import annotations

import gzip
import json

import pytest

from backend.analytics.metrics import build_analysis, serialise_analysis
from backend.api import state as api_state
from backend.api.exports import (
    PRIVACY_NOTE,
    build_events_csv,
    build_queue_csv,
    build_summary_json,
    build_trajectories_csv,
    measurements_payload,
)
from backend.config import ensure_directories, settings
from backend.models.schemas import VideoInfo
from backend.storage import Database, annotated_path, upload_path, write_result
from backend.tests.conftest import make_regions, make_track


@pytest.fixture()
def stored_analysis(tmp_path, monkeypatch):
    """A stored analysis with a real upload file and a real result payload."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "data_dir", data_dir, raising=False)
    monkeypatch.setattr(settings, "upload_dir", data_dir / "uploads", raising=False)
    monkeypatch.setattr(settings, "processed_dir", data_dir / "processed", raising=False)
    monkeypatch.setattr(settings, "database_path", data_dir / "test.db", raising=False)
    ensure_directories(settings)
    database = Database(settings.database_path)
    monkeypatch.setattr(api_state, "database", database)

    video = VideoInfo(
        filename="clip.mp4",
        duration=20.0,
        fps=10.0,
        width=640,
        height=360,
        size_bytes=1234,
        processed_fps=10.0,
        frame_count=200,
    )
    tracks = [
        make_track(index, [(0.2, 0.6)] + [(0.5, 0.6)] * 4 + [(0.7, 0.6), (0.9, 0.6)])
        for index in range(1, 4)
    ]
    analysis = build_analysis("deleteme", video, tracks, make_regions(), min_track_points=3)

    upload = upload_path(settings, "deleteme", "clip.mp4")
    upload.write_bytes(b"fake video bytes" * 100)
    annotated = annotated_path(settings, "deleteme")
    annotated.parent.mkdir(parents=True, exist_ok=True)
    annotated.write_bytes(b"fake annotated video" * 100)
    write_result(settings, "deleteme", serialise_analysis(analysis, raw_tracks=tracks))
    database.create("deleteme", source="video", filename="clip.mp4", upload_path=str(upload))
    database.update("deleteme", status="complete", progress=1.0)
    return analysis, database


# ------------------------------------------------------------------- delete


def test_delete_removes_upload_annotated_video_and_result(stored_analysis):
    _analysis, database = stored_analysis
    assert upload_path(settings, "deleteme", "clip.mp4").exists()
    assert annotated_path(settings, "deleteme").exists()

    files, freed = api_state.delete_analysis("deleteme")

    assert files == 3, "upload + annotated video + result payload"
    assert freed > 0
    assert not upload_path(settings, "deleteme", "clip.mp4").exists()
    assert not annotated_path(settings, "deleteme").exists()
    assert not (settings.processed_dir / "deleteme").exists()
    assert database.get("deleteme") is None


def test_delete_is_idempotent(stored_analysis):
    _analysis, _database = stored_analysis
    api_state.delete_analysis("deleteme")
    files, freed = api_state.delete_analysis("deleteme")
    assert files == 0
    assert freed == 0


def test_delete_reports_nothing_left_behind(stored_analysis):
    _analysis, _database = stored_analysis
    api_state.delete_analysis("deleteme")
    leftovers = [
        path
        for path in settings.data_dir.rglob("*")
        if path.is_file() and not path.name.startswith("test.db")
    ]
    assert leftovers == [], f"files survived the delete: {leftovers}"


# ------------------------------------------------------------------- export


def test_summary_export_contains_no_points_by_default(stored_analysis):
    analysis, _ = stored_analysis
    bundle = build_summary_json(analysis)
    body = json.loads(bundle.content)
    assert body["manifest"]["contains_video"] is False
    assert body["manifest"]["contains_trajectory_samples"] is False
    assert all(track["points"] == [] for track in body["analysis"]["trajectories"])
    assert PRIVACY_NOTE in body["manifest"]["privacy_note"]
    assert "queue_length" in body["manifest"]["definitions"]


def test_summary_export_can_include_points(stored_analysis):
    analysis, _ = stored_analysis
    body = json.loads(build_summary_json(analysis, include_points=True).content)
    assert body["manifest"]["contains_trajectory_samples"] is True
    assert any(track["points"] for track in body["analysis"]["trajectories"])


def test_no_export_mentions_video_content(stored_analysis):
    """The export must not contain a video path, a filename or a frame reference."""
    analysis, _ = stored_analysis
    for bundle in (
        build_summary_json(analysis, include_points=True),
        build_trajectories_csv(analysis),
        build_queue_csv(analysis),
        build_events_csv(analysis),
    ):
        text = bundle.content.decode("utf-8").lower()
        assert ".mp4" not in text
        assert "annotated_path" not in text
        assert "clip.mp4" not in text
        assert "data/uploads" not in text
        assert "data/processed" not in text


def test_export_keeps_useful_video_facts_without_the_filename(stored_analysis):
    analysis, _ = stored_analysis
    body = json.loads(build_summary_json(analysis).content)
    video = body["analysis"]["video"]
    assert video["duration"] == 20.0
    assert video["width"] == 640
    assert "filename" not in video
    assert "filename omitted" in video["source"]


def test_vehicle_csv_reports_censoring_and_units(stored_analysis):
    analysis, _ = stored_analysis
    text = build_trajectories_csv(analysis).content.decode("utf-8")
    header = text.splitlines()[0]
    for column in (
        "traversal_s",
        "slow_time_s",
        "queue_region_slow_s",
        "queue_region_total_s",
        "complete_visits",
        "censored_visits",
    ):
        assert column in header
    assert "# units:" in text.splitlines()[1]


def test_queue_csv_matches_the_series(stored_analysis):
    analysis, _ = stored_analysis
    rows = build_queue_csv(analysis).content.decode("utf-8").strip().splitlines()
    assert rows[0] == "time_s,queue_length"
    assert len(rows) - 1 == len(analysis.queue_timeseries)


def test_events_csv_contains_evidence_tables(stored_analysis):
    analysis, _ = stored_analysis
    text = build_events_csv(analysis).content.decode("utf-8")
    assert "# bottlenecks" in text
    assert "distinct_vehicles" in text
    assert "# stopped intervals" in text


def test_measurements_payload_defines_every_number(stored_analysis):
    analysis, _ = stored_analysis
    payload = measurements_payload(analysis)
    assert payload["observation_window_s"] == 20.0
    assert payload["privacy_note"] == PRIVACY_NOTE
    for key in ("peak_queue_vehicles", "average_wait_s", "throughput_veh_per_min"):
        assert key in payload
        assert key.rsplit("_", 1)[0] in payload["definitions"] or key in payload["definitions"]


# -------------------------------------------------------- orphan reconciliation


def test_interrupted_jobs_are_marked_failed_on_startup(stored_analysis):
    _analysis, database = stored_analysis
    database.update("deleteme", status="processing", stage="detecting", progress=0.4)
    assert database.get("deleteme")["status"] == "processing"

    repaired = api_state.reconcile_orphans()

    record = database.get("deleteme")
    assert repaired == 1
    assert record["status"] == "error"
    assert "interrupted" in record["error"].lower()
    assert record["hint"]


def test_reconcile_leaves_completed_analyses_alone(stored_analysis):
    _analysis, database = stored_analysis
    assert api_state.reconcile_orphans() == 0
    assert database.get("deleteme")["status"] == "complete"


def test_result_file_is_gzipped_json_on_disk(stored_analysis):
    """Storage format check: a stray result file must not break a re-measure."""
    from backend.storage import read_result

    payload = read_result(settings, "deleteme")
    assert payload is not None
    assert "analysis_id" in payload or "raw_tracks" in payload
    raw = (settings.processed_dir / "deleteme" / "result.json.gz").read_bytes()
    assert raw[:2] == b"\x1f\x8b", "result payload should be gzip compressed"
    json.loads(gzip.decompress(raw).decode("utf-8"))
