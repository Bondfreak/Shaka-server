# P17 EVC diagnostic proxy

Read-only Server proxy for Core diagnostic scenario `EVC-BB-NO-WAKE`.

Endpoint: `GET /api/v1/cog/diagnostics/{scenario_id}`.

Fail-closed guarantees:
- `rootCauseDetermined` must remain `false`;
- verified anchors must remain `verified`;
- deferred investigation relations must remain `candidate`;
- `candidateRelationsPromoted` must remain `false`;
- physical cable routing must remain unverified;
- diagnostic payload remains a scenario template, not a root-cause determination.
