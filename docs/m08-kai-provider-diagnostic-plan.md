# M08 KAI provider diagnostic plan

Scope: expose internal provider failure reason without leaking secrets.

Rules:
- Keep external API response unchanged: kai_unavailable / HTTP 503.
- Never log API keys or secret values.
- Log only bounded diagnostic metadata.

Acceptance:
- CI green before PR review.
- No Core, DB, schema, or privilege changes.
