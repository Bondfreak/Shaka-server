"""Public answer_query API used by tests and callers."""

from __future__ import annotations

from shaka_server.f1.composer.answer import Answer
from shaka_server.f1.composer.compose import compose_answer
from shaka_server.f1.retrieval.index import SnapshotIndex
from shaka_server.f1.snapshot.pack import FixtureSnapshot, default_snapshot


def answer_query(query: str, snapshot: FixtureSnapshot | None = None) -> Answer:
    """Search the frozen snapshot and compose a Policy-Guard-checked Answer.

    Deterministic, read-only, no LLM. Fail-closed / downgrade via Policy Guard.
    """
    snap = snapshot if snapshot is not None else default_snapshot()
    index = SnapshotIndex(snap)
    return compose_answer(query, index, snap)
