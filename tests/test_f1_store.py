"""F1-T02 document store tests — ported from navigator-f1-core."""

from __future__ import annotations

from pathlib import Path

import pytest

from shaka_server.f1.core import ValidationError
from shaka_server.f1.store import DocumentStore, ImportInput


@pytest.fixture
def temp_store(tmp_path: Path) -> tuple[DocumentStore, Path]:
    data = tmp_path / "data"
    invoice = tmp_path / "invoice.txt"
    invoice.write_text("Faktura 9631 impeller x2", encoding="utf-8")
    return DocumentStore(data), invoice


class TestF1T02DocumentStore:
    def test_imports_with_sha256_mime_storage_ref(self, temp_store: tuple[DocumentStore, Path]) -> None:
        store, file_path = temp_store
        result = store.import_source(
            ImportInput(
                file_path=str(file_path),
                source_id="SRC-FAKTURA-9631",
                title="Faktura 9631",
                source_type="invoice",
                issuer="yard",
            )
        )
        assert result.imported is True
        assert len(result.source.content_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.source.content_hash)
        assert result.source.mime_type == "text/plain"
        assert result.source.storage_ref.startswith("blob://")

    def test_idempotent_reimport(self, temp_store: tuple[DocumentStore, Path]) -> None:
        store, file_path = temp_store
        first = store.import_source(
            ImportInput(
                file_path=str(file_path),
                source_id="SRC-1",
                title="t",
                source_type="invoice",
            )
        )
        second = store.import_source(
            ImportInput(
                file_path=str(file_path),
                source_id="SRC-1",
                title="t",
                source_type="invoice",
            )
        )
        assert first.reason == "created"
        assert second.reason == "idempotent_hit"
        assert second.source.content_hash == first.source.content_hash

    def test_fail_closed_on_missing_file(self, temp_store: tuple[DocumentStore, Path]) -> None:
        store, _ = temp_store
        with pytest.raises(ValidationError):
            store.import_source(
                ImportInput(
                    file_path="/no/such/file",
                    source_id="X",
                    title="t",
                    source_type="invoice",
                )
            )
