# Testing Standards

## Coverage
- Test coverage MUST be >= 90% on all files in `/services/`. Enforced by CI — not self-assessed.
- New code MUST NOT reduce overall coverage below this threshold.

## Naming
- All test functions MUST follow: `test_<what>_when_<condition>_then_<expected>`

## Test Focus
- Tests MUST assert behavior and observable outcomes — not implementation details.
- Fragile implementation-coupled tests are PROHIBITED.

## Model and Persistence Tests
For any new persistent model, MUST cover:
- Creation and basic lifecycle.
- All uniqueness and integrity constraints.
- Cascade and relationship behavior.
- Failure paths and validation errors.

## Integration Tests
- Integration tests MUST exercise real persistence and boundary layers (DB, queues) where feasible.
- Over-mocking the data layer in integration tests is PROHIBITED.

## Task File TDD Standard (Rule 20)
Every task file MUST specify — not checkbox criteria:
- Exact test function names.
- Test file paths.
- Mock setup requirements.
- Arrange-act-assert structure for each test.
