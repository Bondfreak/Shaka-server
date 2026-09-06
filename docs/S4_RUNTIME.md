# S4 runtime — F1 local uvicorn, CORS, smoke (Mål A)

Navigator S4 Mål A: kør F1 Canonical Read Core lokalt mod fixture-freeze `ac-fixture-v1`, med CORS så Atlas (Bondfreak/atlas-ipad) kan kalde Server fra localhost og GitHub Pages.

**Ingen Foundation Drive-skrivning. Ingen live Foundation-import. Ingen LLM i F1 composer.**

Gate E freeze-baseline: SHA `b28f835` / snapshot `ac-fixture-v1` (efterfølgende commits på `main` skal stadig servere samme fixture-id).

## Local uvicorn (F1 uden live Core)

F1-ruterne (`/api/v1/f1/*`) bruger den indbyggede AC-fixture og behøver ikke et rigtigt Shaka Core. `create_app` kræver dog stadig en Core-base-URL ved modul-import / cold start — sæt en stub-URL:

```bash
python -m pip install -e '.[test]'
export SHAKA_CORE_BASE_URL=http://127.0.0.1:8001   # ikke kaldt af F1-ruterne
# valgfrit — defaults dækker allerede lokal Atlas + GH Pages:
# export SHAKA_UI_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,https://bondfreak.github.io
uvicorn shaka_server.app:app --host 127.0.0.1 --port 8000
```

Bemærk: Atlas' egen README foreslår `python3 -m http.server 8000`. Kør derfor Atlas på en anden port (fx `8080`) når Server lytter på `8000`, eller omvendt. CORS-defaults tillader begge.

### Proven paths (TestClient — samme som CI)

Uden live server:

```bash
pytest -q tests/test_f1_http.py tests/test_m06_cors.py tests/test_f1_kai_tool.py
python scripts/smoke_f1_runtime.py                 # --mode testclient (default)
```

Med kørende uvicorn:

```bash
python scripts/smoke_f1_runtime.py --mode http --base-url http://127.0.0.1:8000
# eller: make smoke-f1
```

Forventet: `snapshot_id=ac-fixture-v1`, BB-assets inkl. `AI-D4-BB-ENGINE`.

## CORS / `SHAKA_UI_ORIGINS`

Comma-separated allowlist. Wildcard `*` er fail-closed.

| Kilde | Default origins (uddrag) |
|-------|--------------------------|
| Lokal Atlas (`http.server` / Vite) | `http://localhost:8000`, `:8080`, `:5173`, `:3000` (+ `127.0.0.1`) |
| GitHub Pages (Bondfreak/atlas-ipad) | `https://bondfreak.github.io` (project pages origin) |

Override:

```bash
export SHAKA_UI_ORIGINS=http://localhost:8080,https://bondfreak.github.io
```

Methods: `GET`, `POST`. Headers: `Accept`, `Content-Type`. Credentials: off.

## KAI `explain` + `f1_answer_query`

`POST /api/v1/kai/explain` kan (via provider tool-loop) kalde Server-tool `f1_answer_query`, som wrapper samme deterministiske `answer_query` som `POST /api/v1/f1/answer`:

- fail-closed (tom query → 400 / `KaiToolError`)
- ingen LLM i F1 composer
- ingen Drive-/DB-skrivning

Se [F1_KAI_TOOL.md](F1_KAI_TOOL.md). KAI-provider kræver egen konfiguration; F1 HTTP/smoke kræver det ikke.

## Relateret

- [F1_HTTP.md](F1_HTTP.md) — ruter + curl
- [GATE_C_PREVIEW_MANIFEST.md](GATE_C_PREVIEW_MANIFEST.md) — fixture-freeze / AC-scope
- Tests: `tests/test_f1_http.py`, `tests/test_m06_cors.py`, `tests/test_f1_kai_tool.py`
