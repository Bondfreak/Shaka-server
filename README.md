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
