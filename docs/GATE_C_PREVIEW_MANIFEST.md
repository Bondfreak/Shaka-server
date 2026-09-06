# Gate C preview freeze — owner baseline

Frozen baseline for **owner preview** of F1 Canonical Read Core (Answer Composer + HTTP + KAI tool) on the AC fixture pack.

**This is not Gate C PASS.** It freezes a reproducible SHA and fixture identity so an owner can review behaviour before a formal Gate C decision.

## Freeze identity

| Field | Value |
|-------|-------|
| Git SHA | `c678f6a4b35863e22efe3760fb070e81579f5e48` |
| Branch tip (at freeze) | `main` @ `c678f6a` (Merge PR #18 — F1 KAI tool) |
| `snapshot_id` | `ac-fixture-v1` |
| `response_version` | `f1-t04-v1` |
| Composer model label | `deterministic-f1-t04` |

Built from in-repo fixture snapshot (`shaka_server.f1.snapshot.build_ac_fixture_snapshot`). **No LLM. No Core DB. No Foundation Drive writes.**

## Surfaces in scope

### HTTP (read-only)

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/v1/f1/answer` | `{ "query": "..." }` → structured Answer (`snapshot_id`, `response_version` via audit) |
| `GET` | `/api/v1/f1/assets` | optional `?side=` |
| `GET` | `/api/v1/f1/assets/{asset_id}` | `404` if missing |

See [F1_HTTP.md](F1_HTTP.md).

### KAI tool (Server-controlled)

| Tool | Arguments | Behaviour |
|------|-----------|-----------|
| `f1_answer_query` | `query` (non-empty string) | Same deterministic `answer_query` path as `POST /api/v1/f1/answer` |

See [F1_KAI_TOOL.md](F1_KAI_TOOL.md).

## Acceptance / conflict coverage

### In scope (preview)

| ID | Discipline (summary) |
|----|----------------------|
| **AC-01** | Impeller event date / source; invoice ≠ install / action ≠ lasting outcome |
| **AC-02** | Quantity ×2 does not conclude both BB/SB sides |
| **AC-03** | PCU cleaned — not replaced without evidence |
| **AC-04** | Lasting result unknown after test run |
| **AC-05** | Oily PCU = possible cause only (hypothesis ≠ root cause) |
| **AC-06** | Bounded absence for unknown P/N; no topic switch |
| **CF-001** | D4 vs D6 conflicted labour wording on Faktura 9631 must surface |
| **CF-002** | Impeller side stays unknown (invoice ×2 ≠ BB/SB install split) |
| **CF-003** | BB PCU serial / asset context remains unknown where undocumented |

Fixture serials when present: BB `2004030432` / SB `2004030433` only. Never invent serials.

### Out of scope (this freeze)

- Formal **Gate C PASS** / Gate C decision record
- LLM-backed or non-deterministic answering
- Core DB reads/writes; Foundation Drive mutation
- Live / non-fixture snapshots (anything other than `ac-fixture-v1`)
- AC cases beyond **AC-01…06** (e.g. broader Navigator AC catalog as PASS criteria)
- Write paths, admin APIs, or Core-bypass tool use outside Server-controlled `f1_answer_query`
- Changing Policy Guard semantics or inventing missing evidence

## Reproduce

```bash
git checkout c678f6a4b35863e22efe3760fb070e81579f5e48
python -m pip install -e '.[test]'
pytest -q
```

Expected: all tests green (F1 composer / HTTP / KAI covered under `tests/test_f1_*.py`).

Answer via HTTP (server listening on `:8000`):

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/f1/answer \
  -H 'Content-Type: application/json' \
  -d '{"query":"Hvornår blev impellerne sidst skiftet?"}'
```

Confirm response / audit carry `snapshot_id: ac-fixture-v1` and `response_version: f1-t04-v1` (or equivalent audit fields).

## Drive twin

A **Drive twin** of this preview freeze also exists under Foundation Experiments manifests (owner / lab tracking). This repo file is the Shaka Server canonical pointer for the same SHA + fixture identity.

## Related docs

- [F1_T04.md](F1_T04.md) — composer + AC fixture
- [F1_HTTP.md](F1_HTTP.md) — HTTP routes
- [F1_KAI_TOOL.md](F1_KAI_TOOL.md) — `f1_answer_query`
- [F1_T05.md](F1_T05.md) — asset bootstrap (CF-002 / CF-003 context)
