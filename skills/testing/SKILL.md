# Testing Skill


Test behavior, not implementation details.

Prefer a pyramid appropriate to the system:
- unit tests for deterministic business logic
- integration tests for boundaries
- contract/API tests
- end-to-end tests for critical user journeys
- performance/load tests for measurable scale requirements

Every bug fix should consider regression protection.
