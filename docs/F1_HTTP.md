# F1 HTTP — Canonical Read Core routes

Read-only FastAPI surface so Navigator / KAI can call F1 through Shaka Server without bypassing the application boundary. Uses the frozen AC snapshot and deterministic Answer Composer. **No LLM. No DB / Foundation Drive writes.**

## Routes

| Method | Path | Body / query | Response |
|--------|------|--------------|----------|
| `POST` | `/api/v1/f1/answer` | `{ "query": "..." }` | Structured Answer JSON |
| `GET` | `/api/v1/f1/assets` | optional `?side=BB\|SB\|…` | `{ "assets": [ … ] }` |
| `GET` | `/api/v1/f1/assets/{asset_id}` | — | Asset JSON, or `404` |

Error shape matches the rest of Shaka Server: `{"error":{"code","message"}}`.

## Answer fields

`conclusion`, `basis`, `uncertainty_conflict`, `sources`, `epistemic_status`, `policy_results`, plus `query`, `selected_ids`, `snapshot_id`, `rejected`, `audit` when present.

Policy Guard remains fail-closed: invoice ≠ install; BB/SB never silently merge; conflicts surface.

## Module

- Router: `src/shaka_server/f1/http.py` (included from `create_app`)
- Reuses: `answer_query`, `list_assets`, `get_asset`
- Tests: `tests/test_f1_http.py`

## Example curls

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/f1/answer \
  -H 'Content-Type: application/json' \
  -d '{"query":"Hvornår blev impellerne sidst skiftet?"}'

curl -sS 'http://127.0.0.1:8000/api/v1/f1/assets?side=BB'

curl -sS http://127.0.0.1:8000/api/v1/f1/assets/AI-D4-BB-ENGINE
```
