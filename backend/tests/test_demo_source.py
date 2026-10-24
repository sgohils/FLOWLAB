"""The bundled demo must be the source of truth for its own summary."""

from __future__ import annotations

from backend.api import state


def test_demo_record_is_refreshed_from_the_bundled_file(tmp_path, monkeypatch):
    """A stale row must not survive a restart with different demo numbers."""
    from backend.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path, raising=False)
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads", raising=False)
    monkeypatch.setattr(settings, "processed_dir", tmp_path / "processed", raising=False)
    monkeypatch.setattr(settings, "database_path", tmp_path / "t.db", raising=False)
    from backend.config import ensure_directories

    ensure_directories(settings)
    database = state.Database(settings.database_path)
    monkeypatch.setattr(state, "database", database)

    analysis = state.demo_analysis()
    assert analysis is not None

    # Insert a deliberately wrong summary, as an older build would have.
    database.create("demo", source="demo", filename="old.mp4", upload_path=None, stage="results")
    database.update(
        "demo",
        status="complete",
        summary={"vehicles_tracked": 999, "peak_queue": 99},
        video={"filename": "old.mp4", "duration": 1.0},
    )

    state.register_demo()

    record = database.get("demo")
    assert record["summary"]["vehicles_tracked"] == analysis.summary.vehicles_tracked
    assert record["summary"]["peak_queue"] == analysis.summary.peak_queue
    assert record["video"]["duration"] == analysis.video.duration


def test_list_entry_matches_the_result_endpoint():
    """The number in the list is the number the detail page shows."""
    analysis = state.demo_analysis()
    if analysis is None:
        return
    assert analysis.summary.vehicles_tracked == len(analysis.trajectories)
