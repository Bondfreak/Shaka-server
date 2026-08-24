# P16 EVC topology proxy

This change adds a bounded read-only Server proxy for the Core endpoint:

`GET /api/v1/cog/topologies/{system_id}`

The Server validates the topology contract before returning it to Navigator:

- status is `canonical_partial` or `canonical_complete`
- verified edges must remain `verified`
- deferred relations must remain explicit `candidate` entries
- all edge endpoints must exist in the returned node set
- `physicalCableRoutingVerified` must be `false` for the current P16 EVC projection

No EVC candidate relation is promoted by Server. The endpoint is transport + contract validation only.
