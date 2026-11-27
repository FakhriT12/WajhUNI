# Learning Log

## Part A: Pytest Auth Test Suite & Isolation

The auth tests use the shared fixtures from `conftest.py` as the boundary between test state and developer services:

- `client` sends async requests through the FastAPI app configured for tests.
- `engine` provides the test database for preparing and checking rows. Direct database setup and assertions use this engine rather than the development `wajhuni` database.
- `redis_test` is the test Redis connection used by the app for refresh-token state; refresh tests inspect it rather than touching Redis DB 0.
- `seeded_university` supplies the test university and its allowed `tbs.u-tunis.tn` email domain, so registrations and users have a known, test-owned university context.

Each test follows Arrange, Act, Assert (AAA): Arrange creates the unique user, token, or request data it needs; Act calls the route; Assert checks its status, response fields, or persisted state. Unique email addresses and fixture-owned database/Redis state keep tests from relying on data created by another test.

When verification state is needed, seed a pending user and the hash of a known verification token directly through `engine`, then assert the resulting database state. This is less brittle than scraping `stdout`: log wording, formatting, and whether development logging is enabled are incidental, while the database record and endpoint response are the actual contract under test.
