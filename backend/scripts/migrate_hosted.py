"""Apply the hosted schema and optionally copy completed local analyses."""

import argparse
from dataclasses import replace
from pathlib import Path

from ..config import settings
from ..storage import Database, annotated_path, result_path
from ..storage.cloud import key_for, publish
from ..storage.postgres import PostgresDatabase


def import_local(data_dir: Path, target: PostgresDatabase) -> int:
    data_dir = data_dir.resolve()
    local_path = data_dir / "flowlab.db"
    if not local_path.is_file():
        raise ValueError(f"No local database found at {local_path}")
    local = Database(local_path)
    cloud_settings = replace(
        settings, hosted=True, data_dir=data_dir, upload_dir=data_dir / "uploads",
        processed_dir=data_dir / "processed",
    )
    records = local.list_recent(limit=1_000_000)
    if any(item["status"] in {"queued", "processing"} for item in records):
        raise ValueError("Finish or cancel local jobs before importing analyses.")
    imported = 0
    for record in records:
        analysis_id = record["analysis_id"]
        if analysis_id == "demo" or target.get(analysis_id):
            continue
        paths = [
            annotated_path(cloud_settings, analysis_id), result_path(cloud_settings, analysis_id),
        ]
        source = Path(record["upload_path"]) if record.get("upload_path") else None
        if source:
            source = source.resolve()
            if not source.is_relative_to(data_dir):
                raise ValueError(f"Source video for {analysis_id} is outside the data directory.")
            paths.append(source)
        for path in paths:
            if path.is_file():
                publish(cloud_settings, path)
        target.create(
            analysis_id, source=record["source"], filename=record["filename"],
            upload_path=key_for(cloud_settings, source) if source else None,
        )
        target.update(analysis_id, **{
            name: record[name] for name in (
                "status", "stage", "progress", "created_at", "video", "summary", "error", "hint"
            )
        })
        imported += 1
    return imported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-local", type=Path, metavar="DATA_DIR")
    args = parser.parse_args()
    database = PostgresDatabase(settings.database_url)
    database.migrate()
    print("Hosted PostgreSQL schema is ready.")
    if args.import_local:
        print(f"Imported {import_local(args.import_local, database)} local analyses.")
