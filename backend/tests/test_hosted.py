"""Hosted authorization, queue redelivery, and persistence boundaries."""

import asyncio
import hashlib
import time
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.api import routes_cloud_upload as uploads
from backend.api import state
from backend.api.errors import ApiError
from backend.api.hosted_jobs import HostedJobs
from backend.config import settings
from backend.models.schemas import VideoInfo
from backend.storage import cloud
from backend.worker import _process


@pytest.fixture
def intent(monkeypatch):
    monkeypatch.setattr(settings, "hosted", True)
    proof = uploads.UploadProof(
        analysis_id="abc123abc123", token="x" * 40,
        pathname="uploads/abc123abc123/clip.mp4",
    )
    record = {
        "token_hash": hashlib.sha256(proof.token.encode()).hexdigest(),
        "object_key": proof.pathname, "filename": "clip.mp4", "size_bytes": 123,
        "expires_at": time.time() + 3600,
    }
    database = Mock()
    database.get_intent.return_value = record
    monkeypatch.setattr(uploads, "cloud_database", lambda _: database)
    return proof, record, database


def test_upload_tokens_are_scoped_to_a_single_object(intent):
    proof, _, _ = intent
    tampered = proof.model_copy(update={"pathname": "uploads/another-video.mp4"})
    with pytest.raises(ApiError) as error:
        uploads._intent(tampered)
    assert error.value.status_code == 403


def test_wrong_upload_token_is_rejected(intent):
    proof, _, _ = intent
    with pytest.raises(ApiError) as error:
        uploads._intent(proof.model_copy(update={"token": "y" * 40}))
    assert error.value.status_code == 403


def test_expired_tokens_cannot_mint_blob_upload_tokens(intent):
    proof, record, _ = intent
    record["expires_at"] = time.time() - 1
    with pytest.raises(ApiError) as error:
        asyncio.run(uploads.authorize(proof))
    assert error.value.status_code == 403


def test_completion_can_acknowledge_a_running_job_without_waiting_for_worker_lock(intent):
    proof, _, database = intent
    database.get.return_value = {"status": "processing"}
    response = asyncio.run(uploads.complete(proof))
    assert response.analysis_id == proof.analysis_id
    database.job_lock.assert_not_called()


def test_upload_size_is_verified_from_blob_before_enqueue(intent, monkeypatch):
    from vercel.blob import sync as blob

    proof, _, database = intent
    database.get.return_value = None
    database.job_lock = unlocked
    monkeypatch.setattr(blob, "head_blob", lambda _: SimpleNamespace(size=124))
    jobs = Mock()
    monkeypatch.setattr(uploads, "jobs", jobs)
    with pytest.raises(ApiError) as error:
        asyncio.run(uploads.complete(proof))
    assert error.value.status_code == 400
    jobs.submit.assert_not_called()
    database.create.assert_not_called()


@contextmanager
def unlocked(_analysis_id):
    yield True


def test_publish_failure_does_not_acknowledge_upload_and_can_be_retried(intent, monkeypatch):
    from vercel.blob import sync as blob

    proof, _, database = intent
    database.get.return_value = None
    database.job_lock = unlocked
    monkeypatch.setattr(blob, "head_blob", lambda _: SimpleNamespace(size=123, url="private-url"))
    jobs = Mock()
    jobs.submit.side_effect = RuntimeError("Queue unavailable")
    monkeypatch.setattr(uploads, "jobs", jobs)
    with pytest.raises(RuntimeError, match="Queue unavailable"):
        asyncio.run(uploads.complete(proof))
    assert database.update.call_args.kwargs["stage"] == "dispatch_failed"
    # Failed dispatch does not fill queue capacity, and the same proof can retry.
    database.get.return_value = {"status": "error", "stage": "dispatch_failed"}
    jobs.submit.side_effect = None
    assert asyncio.run(uploads.complete(proof)).analysis_id == proof.analysis_id
    assert jobs.submit.call_count == 2


def test_hosted_api_start_does_not_fail_another_instances_jobs(monkeypatch):
    monkeypatch.setattr(settings, "hosted", True)
    database = Mock()
    monkeypatch.setattr(state, "database", database)
    assert state.reconcile_orphans() == 0
    database.update.assert_not_called()


def test_completed_queue_delivery_does_not_repeat_processing(monkeypatch):
    database = Mock()
    database.job_lock = unlocked
    database.get.return_value = {"status": "complete"}
    monkeypatch.setattr(cloud, "cloud_database", lambda _: database)
    download = Mock()
    monkeypatch.setattr(cloud, "download", download)
    _process("abc123abc123", 1)
    download.assert_not_called()


def test_worker_transient_failures_retry_and_final_attempt_records_error(monkeypatch):
    database = Mock()
    database.job_lock = unlocked
    database.get.return_value = {"status": "queued", "filename": "clip.mp4", "upload_path": "key"}
    monkeypatch.setattr(cloud, "cloud_database", lambda _: database)
    monkeypatch.setattr(cloud, "download", Mock(side_effect=OSError("Storage unavailable")))
    with pytest.raises(OSError, match="Storage unavailable"):
        _process("abc123abc123", 1)
    database.update.assert_not_called()
    _process("abc123abc123", 3)
    assert database.update.call_args.kwargs["status"] == "error"


def test_failed_blob_deletion_keeps_reference_for_retry(monkeypatch):
    from vercel.blob import sync as blob

    database = Mock()
    database.object_versions.return_value = [{"url": "private-url", "size_bytes": 123}]
    monkeypatch.setattr(cloud, "cloud_database", lambda _: database)
    monkeypatch.setattr(blob, "delete_blob", Mock(side_effect=OSError("Storage unavailable")))
    with pytest.raises(OSError):
        cloud.remove(settings, "processed/abc/result.json.gz")
    database.delete_version.assert_not_called()
    database.delete_object.assert_not_called()


def test_new_api_instance_reads_job_progress_from_database():
    video = VideoInfo(
        filename="clip.mp4", duration=10, fps=10, width=100, height=100,
        size_bytes=123, processed_fps=10, frame_count=100,
    )
    database = Mock()
    database.get.return_value = {
        "status": "processing", "stage": "detecting", "progress": 0.5,
        "video": video.model_dump(), "error": None, "hint": None,
        "created_at": time.time(), "updated_at": time.time(),
    }
    job = HostedJobs(database, settings).get("abc123abc123")
    assert job.status == "processing"
    assert job.progress == 0.5
    assert next(stage for stage in job.stages if stage.key == "detecting").status == "active"
