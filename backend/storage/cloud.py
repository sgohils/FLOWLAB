"""Private Blob objects; PostgreSQL points to immutable versions.

Only scratch copies live in the local filesystem. Fresh immutable URLs avoid
serving stale cached result payloads after a region edit or worker retry.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from ..config import Settings
from .postgres import PostgresDatabase


def cloud_database(settings: Settings) -> PostgresDatabase:
    return PostgresDatabase(settings.database_url)


def key_for(settings: Settings, path: Path) -> str:
    return path.relative_to(settings.data_dir).as_posix()


def publish(settings: Settings, path: Path) -> None:
    from vercel.blob import sync as blob

    key = key_for(settings, path)
    database = cloud_database(settings)
    size = path.stat().st_size
    with path.open("rb") as source:
        uploaded = blob.put_blob(
            f"objects/{uuid.uuid4().hex}/{path.name}", source,
            access="private", content_length=size,
        )
    database.put_object(key, uploaded.url, size)


def download(settings: Settings, key: str, destination: Path) -> bool:
    from vercel.blob import sync as blob

    record = cloud_database(settings).get_object(key)
    if not record:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with (
            blob.stream_blob(record["url"], access="private") as source,
            destination.open("wb") as output,
        ):
            for chunk in source:
                output.write(chunk)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return True


def publish_bytes(settings: Settings, key: str, payload: bytes) -> None:
    from vercel.blob import sync as blob

    uploaded = blob.put_blob(
        f"objects/{uuid.uuid4().hex}/{Path(key).name}", payload, access="private",
    )
    cloud_database(settings).put_object(key, uploaded.url, len(payload))


def remove(settings: Settings, key: str) -> tuple[int, int]:
    from vercel.blob import sync as blob

    database = cloud_database(settings)
    versions = database.object_versions(key)
    # Keep the reference when deletion fails, so retrying deletion can finish.
    for record in versions:
        blob.delete_blob(record["url"])
        database.delete_version(key, record["url"])
    database.delete_object(key)
    return len(versions), sum(record["size_bytes"] for record in versions)
