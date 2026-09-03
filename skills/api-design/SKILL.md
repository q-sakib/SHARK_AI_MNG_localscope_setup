# API Design Skill


REST is the default.

## REST checklist
- resource-oriented URLs
- correct HTTP semantics
- explicit request/response DTOs
- validation
- pagination
- filtering/sorting rules
- consistent errors
- authentication/authorization
- idempotency where needed
- rate limiting where needed
- versioning strategy
- observability
- OpenAPI when appropriate

## Alternative protocols
Use GraphQL, WebSocket, gRPC, events, or queues only when requirements justify them.

Always explain protocol tradeoffs before introducing one.
