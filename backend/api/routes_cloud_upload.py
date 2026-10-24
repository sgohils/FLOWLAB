"""Authorize direct private Blob uploads, then durably enqueue processing."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings
from ..models.schemas import VideoInfo
from ..storage import extension_allowed, new_id, safe_filename
from ..storage.cloud import cloud_database
from .errors import api_error
from .routes_upload import UploadResponse
from .state import jobs

router = APIRouter(prefix="/api/uploads", tags=["upload"])


class IntentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)


class UploadProof(BaseModel):
    analysis_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    token: str = Field(min_length=32, max_length=100)
    pathname: str


def _require_hosted() -> None:
    if not settings.hosted:
        raise api_error(404, "Direct Blob uploads are available only in hosted mode.")


def _intent(proof: UploadProof, *, allow_expired: bool = False) -> dict:
    _require_hosted()
    record = cloud_database(settings).get_intent(proof.analysis_id)
    digest = hashlib.sha256(proof.token.encode()).hexdigest()
    if not record or not hmac.compare_digest(digest, record["token_hash"]):
        raise api_error(403, "The upload authorization is invalid.")
    if proof.pathname != record["object_key"]:
        raise api_error(403, "The upload pathname does not match its authorization.")
    if not allow_expired and record["expires_at"] < time.time():
        raise api_error(403, "The upload authorization has expired. Start the upload again.")
    return record


@router.get("/config")
async def upload_config() -> dict:
    return {"mode": "blob" if settings.hosted else "local"}


@router.post("/intent")
async def create_intent(payload: IntentRequest) -> dict:
    _require_hosted()
    filename = safe_filename(payload.filename)
    if not extension_allowed(filename, settings):
        raise api_error(415, "This video format is not supported.")
    if payload.size > settings.max_upload_bytes:
        raise api_error(413, "The file exceeds the configured upload limit.")
    if jobs.pending_count() >= settings.max_queued_jobs:
        raise api_error(429, "The processing queue is full. Try again later.")
    analysis_id, token = new_id(), secrets.token_urlsafe(32)
    pathname = f"uploads/{analysis_id}/{filename}"
    cloud_database(settings).create_intent((
        analysis_id, hashlib.sha256(token.encode()).hexdigest(), filename,
        pathname, payload.size, time.time() + 3600,
    ))
    return {"analysis_id": analysis_id, "token": token, "pathname": pathname}


@router.post("/authorize")
async def authorize(proof: UploadProof) -> dict:
    intent = _intent(proof)
    return {
        "maximumSizeInBytes": intent["size_bytes"],
        "allowedContentTypes": [
            "video/mp4", "video/quicktime", "video/x-msvideo", "video/webm",
            "video/x-matroska", "video/x-m4v", "application/octet-stream",
        ],
        "validUntil": int(intent["expires_at"] * 1000),
    }


@router.post("/complete", response_model=UploadResponse, status_code=202)
async def complete(proof: UploadProof) -> UploadResponse:
    from vercel.blob import sync as blob

    intent = _intent(proof, allow_expired=True)
    database = cloud_database(settings)
    existing = database.get(proof.analysis_id)
    # A worker can hold the job lock for the full processing time. A browser
    # retry must still be able to acknowledge an already accepted upload.
    if (
        existing and existing["status"] in {"processing", "complete", "error"}
        and existing.get("stage") != "dispatch_failed"
    ):
        return _response(proof, intent)
    with database.job_lock(proof.analysis_id) as acquired:
        if not acquired:
            raise api_error(409, "This upload is being finalized. Try again shortly.")
        record = database.get(proof.analysis_id)
        if record is None:
            if intent["expires_at"] + 3600 < time.time():
                raise api_error(403, "The upload completion window has expired.")
            metadata = blob.head_blob(intent["object_key"])
            if metadata.size != intent["size_bytes"]:
                raise api_error(400, "The uploaded video size does not match its authorization.")
            database.put_object(intent["object_key"], metadata.url, metadata.size)
            database.create(
                proof.analysis_id, source="video", filename=intent["filename"],
                upload_path=intent["object_key"],
            )
        # The worker probes the real video; no video bytes traverse this request.
        if (
            record is None or record["status"] == "queued"
            or record.get("stage") == "dispatch_failed"
        ):
            database.update(proof.analysis_id, status="queued", stage="queued", error=None)
            try:
                jobs.submit(proof.analysis_id, Path(intent["object_key"]))
            except Exception:
                database.update(
                    proof.analysis_id, status="error", stage="dispatch_failed",
                    error="The processing queue is unavailable. Retry the upload completion.",
                )
                raise
        return _response(proof, intent)


def _response(proof: UploadProof, intent: dict) -> UploadResponse:
    video = VideoInfo(
        filename=intent["filename"], size_bytes=intent["size_bytes"],
        width=0, height=0, fps=0.0, duration=0.0, frame_count=0, processed_fps=0.0,
    )
    return UploadResponse(
        analysis_id=proof.analysis_id, video=video,
        status_url=f"/api/analyses/{proof.analysis_id}/status",
        result_url=f"/api/analyses/{proof.analysis_id}/result",
        message="Upload accepted. Processing is queued.",
    )
