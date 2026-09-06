"""Content-addressed document store with fail-closed import semantics."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from shaka_server.f1.core.types import Source
from shaka_server.f1.core.validators import ValidationError, validate_source


@dataclass(kw_only=True)
class ImportInput:
    file_path: str
    source_id: str
    title: str
    source_type: str
    issuer: str | None = None
    revision: str | None = None
    authority_class: str | None = None
    mime_type: str | None = None


@dataclass
class ImportResult:
    source: Source
    imported: bool
    reason: Literal["created", "idempotent_hit", "hash_collision"]


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _guess_mime(file_path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    lower = file_path.name.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".txt") or lower.endswith(".md"):
        return "text/plain"
    if lower.endswith(".json"):
        return "application/json"
    return "application/octet-stream"


def _source_to_wire(source: Source) -> dict[str, Any]:
    """Serialize Source using camelCase wire keys (F1 schema)."""
    payload: dict[str, Any] = {
        "id": source.id,
        "kind": source.kind,
        "sourceType": source.source_type,
        "title": source.title,
        "contentHash": source.content_hash,
        "mimeType": source.mime_type,
        "storageRef": source.storage_ref,
    }
    if source.issuer is not None:
        payload["issuer"] = source.issuer
    if source.revision is not None:
        payload["revision"] = source.revision
    if source.authority_class is not None:
        payload["authorityClass"] = source.authority_class
    if source.created_at is not None:
        payload["createdAt"] = source.created_at
    if source.updated_at is not None:
        payload["updatedAt"] = source.updated_at
    return payload


class DocumentStore:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.blobs_dir = self.root_dir / "blobs"
        self.meta_dir = self.root_dir / "meta"
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    def _meta_path(self, source_id: str) -> Path:
        return self.meta_dir / f"{quote(source_id, safe='')}.json"

    def _blob_path(self, content_hash: str) -> Path:
        return self.blobs_dir / content_hash

    def get_source(self, source_id: str) -> Source | None:
        path = self._meta_path(source_id)
        if not path.exists():
            return None
        return validate_source(json.loads(path.read_text(encoding="utf-8")))

    def list_sources(self) -> list[Source]:
        results: list[Source] = []
        for path in sorted(self.meta_dir.glob("*.json")):
            results.append(validate_source(json.loads(path.read_text(encoding="utf-8"))))
        return results

    def import_source(self, input_data: ImportInput | dict[str, Any]) -> ImportResult:
        if isinstance(input_data, dict):
            if not input_data:
                raise ValidationError("import input required", "FAIL_CLOSED")
            try:
                input_data = ImportInput(
                    file_path=str(input_data.get("filePath") or input_data.get("file_path") or ""),
                    source_id=str(input_data.get("sourceId") or input_data.get("source_id") or ""),
                    title=str(input_data.get("title") or ""),
                    source_type=str(input_data.get("sourceType") or input_data.get("source_type") or ""),
                    issuer=input_data.get("issuer"),
                    revision=input_data.get("revision"),
                    authority_class=input_data.get("authorityClass") or input_data.get("authority_class"),
                    mime_type=input_data.get("mimeType") or input_data.get("mime_type"),
                )
            except (TypeError, ValueError) as exc:
                raise ValidationError("import input required", "FAIL_CLOSED") from exc

        if not input_data.file_path or not input_data.source_id or not input_data.title or not input_data.source_type:
            raise ValidationError("filePath, sourceId, title, sourceType required", "FAIL_CLOSED")

        abs_path = Path(input_data.file_path).resolve()
        if not abs_path.exists():
            raise ValidationError(f"File not found: {abs_path}", "FAIL_CLOSED")

        content_hash = _sha256_file(abs_path)
        mime = _guess_mime(abs_path, input_data.mime_type)
        storage_ref = f"blob://{content_hash}"
        candidate = validate_source(
            {
                "id": input_data.source_id,
                "kind": "Source",
                "sourceType": input_data.source_type,
                "issuer": input_data.issuer,
                "title": input_data.title,
                "revision": input_data.revision,
                "contentHash": content_hash,
                "mimeType": mime,
                "storageRef": storage_ref,
                "authorityClass": input_data.authority_class,
            }
        )

        existing = self.get_source(input_data.source_id)
        if existing is not None:
            if existing.content_hash == content_hash:
                return ImportResult(source=existing, imported=False, reason="idempotent_hit")
            raise ValidationError(
                f"Source id {input_data.source_id} already exists with different hash",
                "FAIL_CLOSED",
            )

        dest = self._blob_path(content_hash)
        if not dest.exists():
            shutil.copyfile(abs_path, dest)
        elif _sha256_file(dest) != content_hash:
            raise ValidationError("Blob path hash collision", "FAIL_CLOSED")

        meta_path = self._meta_path(input_data.source_id)
        meta_path.write_text(json.dumps(_source_to_wire(candidate), indent=2) + "\n", encoding="utf-8")
        return ImportResult(source=candidate, imported=True, reason="created")
