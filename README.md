# Shaka Server

Shaka Server is the application-server component in the Shakai architecture.

For SIP-M05 it is intentionally limited to a bounded, read-only HTTP gateway to already accepted Shaka Core contracts.

## M05 boundaries

- no direct Core DB / Neon access
- no generic proxying or arbitrary Core paths
- no GPT integration
- no Shaka UI migration
- no writes
- fail closed on malformed or unexpected Core behavior

## Local development

```bash
python -m pip install -e '.[test]'
export SHAKA_CORE_BASE_URL=http://127.0.0.1:8001
uvicorn shaka_server.app:app --reload
```

Repository tests use a fake Core and do not require database access.
