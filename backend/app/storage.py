"""Artifact storage. Files on disk (a Docker volume), metadata in the DB.

shortcut: local filesystem only; swap in MinIO/S3 + signed URLs in Phase 6 (evidence collector).
"""
import hashlib
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Artifact


def root() -> Path:
    return Path(settings.artifact_dir).resolve()


def save(db: Session, data: bytes, *, project_id, artifact_type: str, mime: str, ext: str,
         scan_run_id=None, test_execution_id=None) -> Artifact:
    art_id = uuid.uuid4()
    key = f"{project_id}/{art_id}.{ext}"
    path = root() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    art = Artifact(id=art_id, project_id=project_id, scan_run_id=scan_run_id, test_execution_id=test_execution_id,
                   artifact_type=artifact_type, storage_key=key, mime_type=mime, size_bytes=len(data),
                   checksum=hashlib.sha256(data).hexdigest())
    db.add(art)
    db.flush()
    return art


def path_for(art: Artifact) -> Path:
    p = (root() / art.storage_key).resolve()
    if root() not in p.parents:  # defence against a tampered storage_key
        raise ValueError("artifact path escapes storage root")
    return p
