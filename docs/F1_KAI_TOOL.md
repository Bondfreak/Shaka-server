# F1 KAI tool — `f1_answer_query`

Bounded, Server-controlled KAI tool that wraps the same logic as `POST /api/v1/f1/answer`.

## Tool

| Name | Arguments | Behavior |
|------|-----------|----------|
| `f1_answer_query` | `query` (required non-empty string) | Calls `shaka_server.f1.composer.api.answer_query` and returns the structured Answer as a JSON-serializable dict (same shape as the HTTP route). |

- Deterministic frozen-snapshot composer
- **No LLM**, **no Core DB**, **no writes**
- Fail-closed via Policy Guard (same as HTTP)
- Empty / missing `query` → `KaiToolError` (`invalid_request`, HTTP 400)

KAI may use this tool **only** through the Server dispatcher / provider allowlist — not as a free-form Core bypass.

## Wiring

- `SUPPORTED_TOOLS` + `KaiToolDispatcher.execute` in `src/shaka_server/kai.py`
- Advertised to the OpenAI provider in `src/shaka_server/openai_provider.py` (`TOOLS`)
- Tests: `tests/test_f1_kai_tool.py` (dispatcher only; no LLM)

## Related

- HTTP surface: [F1_HTTP.md](F1_HTTP.md)
- Composer / AC: [F1_T04.md](F1_T04.md)
