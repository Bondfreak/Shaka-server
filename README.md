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
uvicorn shaka_server.app:app --host 127.0.0.1 --port 8000 --reload
```

Repository tests use a fake Core and do not require database access.

CORS allowlist is `SHAKA_UI_ORIGINS` (comma-separated; no `*`). Defaults cover local Atlas ports and `https://bondfreak.github.io` (GitHub Pages for Bondfreak/atlas-ipad). See [docs/S4_RUNTIME.md](docs/S4_RUNTIME.md).

### S4 F1 runtime smoke

```bash
python scripts/smoke_f1_runtime.py              # TestClient, ac-fixture-v1
# with uvicorn running:
python scripts/smoke_f1_runtime.py --mode http --base-url http://127.0.0.1:8000
# or: make smoke-f1 / make smoke-f1-http
```

## F1 schema / store / policy / retrieval / assets (T01–T05)

`shaka_server.f1` ports Navigator F1 core types, a content-addressed document store, Policy Guard v0, deterministic Search/Retrieval + read-only Answer Composer, and Shaka Asset Instance bootstrap (BB/SB).

- Package: `src/shaka_server/f1/` (`core`, `store`, `policy`, `snapshot`, `retrieval`, `composer`, `assets`)
- Docs: [docs/F1_T01_T03.md](docs/F1_T01_T03.md), [docs/F1_T04.md](docs/F1_T04.md), [docs/F1_T05.md](docs/F1_T05.md), [docs/F1_HTTP.md](docs/F1_HTTP.md), [docs/F1_KAI_TOOL.md](docs/F1_KAI_TOOL.md), [docs/GATE_C_PREVIEW_MANIFEST.md](docs/GATE_C_PREVIEW_MANIFEST.md) (owner preview freeze — not Gate C PASS), [docs/S4_RUNTIME.md](docs/S4_RUNTIME.md) (local uvicorn / CORS / smoke)
- Tests: `tests/test_f1_*.py`
- API: `answer_query(query, snapshot=...)` → structured Answer; `bootstrap_shaka_assets()` / `get_asset` / `list_assets`

Invariants: KO ≠ Asset; Source ≠ Evidence; never invent serials; BB/SB never merge; policy downgrades rather than silent prefer. Fixture serials BB `2004030432` / SB `2004030433` only. Impeller side stays unknown (CF-002). Frozen AC snapshot covers AC-01…06 (no LLM).

### F1 HTTP (read-only)

Bounded routes included from `create_app` via `shaka_server.f1.http`:

- `POST /api/v1/f1/answer` — `{ "query": "..." }` → structured Answer (frozen snapshot, no LLM)
- `GET /api/v1/f1/assets` — optional `?side=`
- `GET /api/v1/f1/assets/{asset_id}` — `404` if missing

See [docs/F1_HTTP.md](docs/F1_HTTP.md).

### F1 KAI tool (read-only)

KAI may call `f1_answer_query` (`query`: non-empty string) as a **Server-controlled** tool only. It wraps the same deterministic `answer_query` path as `POST /api/v1/f1/answer` — no Core DB, no writes, fail-closed. See [docs/F1_KAI_TOOL.md](docs/F1_KAI_TOOL.md).

