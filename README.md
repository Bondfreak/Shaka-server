# Shaka Server

Shaka Server is Navigator's application-server component. In the accepted runtime architecture, Navigator UI contains Atlas (visual application/UX) and KAI (AI/agent layer), while Shaka Server provides the bounded application boundary toward Shaka Core.

The service remains intentionally bounded: normal domain reads flow through Shaka Server to Shaka Core, and KAI may use only explicitly exposed Server-controlled tools. Shaka Core remains authoritative for domain facts; Shaka Server does not access Shaka DB directly.

## Current boundaries

- no direct Shaka DB / Neon access
- no generic proxying or arbitrary Core paths
- bounded KAI integration only through explicit Server routes/tools
- no database writes
- fail closed on malformed or unexpected Core behavior
- explicit, bounded browser CORS policy

Historical SIP-M05/M06/M08 activity records remain the authoritative evidence for how these capabilities were introduced and accepted; their historical terminology and identifiers are not rewritten here.

## Local development

```bash
python -m pip install -e '.[test]'
export SHAKA_CORE_BASE_URL=http://127.0.0.1:8001
uvicorn shaka_server.app:app --reload
```

Repository tests use a fake Core and do not require database access.

## F1 schema / store / policy / retrieval (T01–T04)

`shaka_server.f1` ports Navigator F1 core types, a content-addressed document store, Policy Guard v0, and deterministic Search/Retrieval + read-only Answer Composer.

- Package: `src/shaka_server/f1/` (`core`, `store`, `policy`, `snapshot`, `retrieval`, `composer`)
- Docs: [docs/F1_T01_T03.md](docs/F1_T01_T03.md), [docs/F1_T04.md](docs/F1_T04.md)
- Tests: `tests/test_f1_*.py`
- API: `answer_query(query, snapshot=...)` → structured Answer (Conclusion / Basis / Uncertainty / Sources) with Policy Guard

Invariants: KO ≠ Asset; Source ≠ Evidence; never invent serials; BB/SB never merge; policy downgrades rather than silent prefer. Fixture serials BB `2004030432` / SB `2004030433` only. Frozen AC snapshot covers AC-01…06 (no LLM).

