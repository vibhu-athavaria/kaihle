# Port Configuration Test Plan

## Overview

This document outlines comprehensive test coverage for the PostgreSQL port configuration change (from 5432 to 5433) implemented to avoid conflicts with local PostgreSQL installations.

### Configuration Context

| Environment | Host | Port | Use Case |
|-------------|------|------|----------|
| Docker Compose (Host) | localhost | 5433 | External connections from host machine |
| Docker Compose (Container) | postgres | 5432 | Internal Docker networking |
| CI/GitHub Actions | localhost | 5432 | Service containers use standard ports |
| Local Dev (No Docker) | localhost | 5432 | Direct local PostgreSQL connection |

### Files Affected

- [`docker-compose.yml`](../../docker-compose.yml:11) - Port mapping `5433:5432`
- [`backend/app/tests/integration/conftest.py`](../../backend/app/tests/integration/conftest.py:32) - `TEST_DATABASE_URL` with port 5433
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml:42) - CI service port 5432
- [`.env.example`](../../.env.example:2) - Documentation for local development

---

## 1. Backend Unit Tests

### 1.1 Configuration Parsing Tests

#### Test: Database URL Parsing with Different Ports
```python
def test_database_url_parsing_with_custom_port():
    """Verify Settings correctly parses DATABASE_URL with non-standard port."""
    # Test URL: postgresql+asyncpg://user:pass@localhost:5433/dbname
    # Assert: port is correctly extracted as 5433
```

**Edge Cases:**
- URL with explicit port 5433 (Docker host mode)
- URL with explicit port 5432 (standard/default)
- URL without explicit port (should default to 5432)
- URL with invalid port (e.g., 99999, abc)
- URL with port 0 (ephemeral port)

#### Test: Environment Variable Override
```python
def test_database_url_env_override():
    """Verify TEST_DATABASE_URL environment variable overrides default."""
```

**Edge Cases:**
- Empty string environment variable
- Malformed URL in environment variable
- URL with special characters in password
- URL with IPv6 address format
- URL with Unix socket path instead of TCP

### 1.2 Settings Validation Tests

#### Test: Invalid Port Configuration Detection
```python
def test_settings_rejects_invalid_port():
    """Verify Settings validation catches invalid port configurations."""
```

**Edge Cases:**
- Port number out of range (negative, > 65535)
- Non-numeric port values
- Reserved port numbers (< 1024 without permissions)

---

## 2. Backend Integration Tests

### 2.1 Database Connectivity Tests

#### Test: Async Engine Creation with Port 5433
```python
@pytest.mark.asyncio
async def test_async_engine_connects_to_port_5433():
    """Verify async engine successfully connects to PostgreSQL on port 5433."""
    # Located in: backend/app/tests/integration/conftest.py
    # Uses: TEST_DATABASE_URL with port 5433
```

**Edge Cases:**
- Connection refused (port 5433 not listening)
- Connection timeout (firewall blocking)
- Wrong port (trying 5432 when only 5433 is available)
- Connection pool exhaustion
- DNS resolution failure for 'localhost'

#### Test: Database Session Lifecycle
```python
@pytest.mark.asyncio
async def test_db_session_with_port_5433():
    """Verify full session lifecycle works with custom port configuration."""
```

**Edge Cases:**
- Session creation when database is temporarily unavailable
- Session rollback on error
- Session commit with network interruption
- Connection pool pre-ping with port 5433

### 2.2 Migration Tests

#### Test: Alembic Migration with Custom Port
```python
def test_alembic_upgrade_with_port_5433():
    """Verify migrations execute successfully against port 5433."""
```

**Edge Cases:**
- Migration when database is starting up (not ready)
- Migration with connection string missing port
- Concurrent migration attempts
- Migration rollback after partial failure

### 2.3 Connection Retry Logic Tests

#### Test: Connection Retry on Port Conflict
```python
@pytest.mark.asyncio
async def test_connection_retry_when_port_busy():
    """Verify retry logic when target port is temporarily unavailable."""
```

**Edge Cases:**
- Port 5432 in use by local PostgreSQL
- Port 5433 in use by another process
- Port becomes available after retry
- Max retries exceeded
- Exponential backoff behavior

### 2.4 Concurrent Connection Tests

#### Test: Multiple Test Sessions on Same Port
```python
@pytest.mark.asyncio
async def test_concurrent_sessions_port_5433():
    """Verify multiple concurrent sessions work on port 5433."""
```

**Edge Cases:**
- Max connections limit reached
- Connection pool overflow
- Transaction isolation across connections
- Deadlock scenarios

---

## 3. Docker/Infrastructure Tests

### 3.1 Docker Compose Port Mapping Tests

#### Test: Host-to-Container Port Mapping
```bash
# Test command
docker compose ps postgres
# Verify: 0.0.0.0:5433->5432/tcp
```

**Edge Cases:**
- Port 5433 already in use on host
- Port binding to specific interface only
- IPv6 binding issues
- Port mapping collision detection

#### Test: Container-to-Container Communication
```python
def test_backend_to_postgres_internal_port():
    """Verify backend container connects to postgres:5432 internally."""
    # From backend container, postgres resolves to container IP
    # Port is always 5432 inside Docker network
```

**Edge Cases:**
- Container DNS resolution failure
- Network isolation issues
- Container restart breaks connections
- Cross-container connection pool sharing

### 3.2 Container Health Check Tests

#### Test: PostgreSQL Health Check on Port 5432
```yaml
# docker-compose.yml healthcheck
test: ["CMD-SHELL", "pg_isready -U kaihle -d kaihle"]
```

**Edge Cases:**
- Health check before database is ready
- Health check during high load
- False positive health checks
- Health check timeout configuration

### 3.3 Service Dependency Tests

#### Test: Backend Waits for PostgreSQL
```python
def test_backend_startup_depends_on_postgres():
    """Verify backend fails gracefully if postgres port unavailable."""
```

**Edge Cases:**
- PostgreSQL starts but port not immediately listening
- PostgreSQL crashes after startup
- Backend starts before PostgreSQL (should retry)
- Race condition in service startup

### 3.4 Network Connectivity Tests

#### Test: Inter-Service Network Communication
```bash
# From backend container
docker compose exec backend nc -zv postgres 5432
```

**Edge Cases:**
- Network partition between services
- DNS resolution delays
- MTU size issues
- Firewall rules blocking internal ports

### 3.5 Volume and Persistence Tests

#### Test: Database Persistence Across Restarts
```bash
# Write data, restart container, verify data persists
docker compose restart postgres
```

**Edge Cases:**
- Port remains bound during restart
- Data corruption on unclean shutdown
- Volume mount permissions
- Init scripts execution on fresh volume

---

## 4. E2E Tests

### 4.1 Full Stack Connectivity Tests

#### Test: Frontend → Backend → Database Flow
```python
def test_end_to_end_request_flow():
    """Verify complete request flow through all layers."""
    # Frontend (localhost:3001) → Backend (localhost:8000) → PostgreSQL (postgres:5432)
```

**Edge Cases:**
- Database connection lost mid-request
- Backend restart during active session
- Request timeout due to slow queries
- Connection pool exhaustion under load

### 4.2 User Authentication Flow Tests

#### Test: Login Flow with Database on Port 5433
```python
def test_login_flow_with_custom_db_port():
    """Verify authentication works when database uses port 5433."""
```

**Edge Cases:**
- Token generation during database reconnect
- Session validation with stale connections
- Concurrent login attempts
- Password hashing during connection issues

### 4.3 Data Persistence Flow Tests

#### Test: CRUD Operations Through Full Stack
```python
def test_crud_operations_end_to_end():
    """Verify create, read, update, delete work through all layers."""
```

**Edge Cases:**
- Transaction rollback on frontend error
- Partial write with connection failure
- Read-after-write consistency
- Concurrent modification detection

### 4.4 Celery Task Integration Tests

#### Test: Celery Worker Database Access
```python
def test_celery_task_database_access():
    """Verify celery workers connect to correct database port."""
```

**Edge Cases:**
- Task execution during database restart
- Result backend connection issues
- Worker prefetch with failed connections
- Task retry with connection recovery

---

## 5. CI/CD Pipeline Tests

### 5.1 GitHub Actions Service Container Tests

#### Test: CI Service Container Port Availability
```yaml
# .github/workflows/ci.yml
services:
  postgres:
    ports:
      - 5432:5432  # CI uses standard port
```

**Edge Cases:**
- Service container startup delay
- Port conflict with runner services
- Health check timeout in CI
- Service cleanup between jobs

### 5.2 Migration Tests in CI

#### Test: Database Migration in CI Environment
```bash
# CI step
alembic upgrade head
```

**Edge Cases:**
- Migration fails due to connection string issues
- Concurrent migrations in parallel jobs
- Migration timeout in slow CI runners
- Rollback testing after failed migration

### 5.3 Test Execution in CI

#### Test: Pytest with CI Database URL
```yaml
# CI environment
DATABASE_URL: postgresql+asyncpg://kaihle:kaihle@localhost:5432/kaihle_test
```

**Edge Cases:**
- Database not ready when tests start
- Connection limit exceeded in CI
- Test isolation failures
- Coverage reporting with connection issues

### 5.4 Multi-Environment Configuration Tests

#### Test: Environment-Specific Port Handling
```python
def test_environment_specific_port_config():
    """Verify correct port is used based on environment."""
    # CI: port 5432
    # Local Docker: port 5433
    # Production: port from secrets
```

**Edge Cases:**
- Missing environment variable
- Wrong environment detection
- Fallback to incorrect default
- Environment variable injection issues

---

## Edge Case Reference Matrix

| Edge Case Category | Test Type | Priority | Implementation |
|-------------------|-----------|----------|----------------|
| Port conflicts | Unit, Integration | High | Mock port binding failures |
| Connection retries | Integration | High | Test exponential backoff |
| Environment variable handling | Unit, CI | High | Parameterized tests |
| Container startup order | Docker | Medium | Health check validation |
| Network partitioning | Docker, E2E | Medium | Network simulation |
| SSL/TLS configuration | Integration | Medium | SSL mode testing |
| Pool exhaustion | Integration | Medium | Load testing |
| DNS resolution | Docker | Low | Custom network testing |

---

## Test Execution Commands

### Local Development (Docker)
```bash
# Start infrastructure
docker compose up -d postgres redis

# Run integration tests (uses port 5433)
cd backend
pytest app/tests/integration/ -v --tb=short

# Run unit tests (isolated)
pytest app/tests/unit/ -v --tb=short
```

### Local Development (Native PostgreSQL)
```bash
# Assumes PostgreSQL running on port 5432
export TEST_DATABASE_URL="postgresql+asyncpg://kaihle:kaihle@localhost:5432/kaihle_test"
pytest app/tests/integration/ -v
```

### CI Environment
```bash
# GitHub Actions automatically configures services
pytest app/tests/ --cov=app/services --cov-fail-under=90 -v
```

---

## Failure Scenarios and Diagnostics

### Scenario 1: Port 5433 Already in Use
**Symptoms:** Docker compose fails to start postgres container
**Diagnosis:**
```bash
lsof -i :5433  # Find process using port
netstat -tlnp | grep 5433  # Alternative
```
**Resolution:** Stop conflicting process or change host port in docker-compose.yml

### Scenario 2: Tests Cannot Connect to Port 5433
**Symptoms:** `ConnectionRefusedError` during test execution
**Diagnosis:**
```bash
docker compose ps  # Check container status
docker compose logs postgres  # Check database logs
nc -zv localhost 5433  # Test port connectivity
```
**Resolution:** Ensure Docker containers are running and port mapping is correct

### Scenario 3: CI Tests Fail with Connection Error
**Symptoms:** Tests pass locally but fail in CI
**Diagnosis:**
```bash
# CI uses port 5432, verify service container is healthy
# Check CI logs for service startup timing
```
**Resolution:** Ensure health checks and wait conditions are configured

### Scenario 4: Environment Variable Not Applied
**Symptoms:** Tests use wrong database URL
**Diagnosis:**
```bash
echo $TEST_DATABASE_URL  # Verify environment variable
pytest --collect-only  # Check test configuration
```
**Resolution:** Export variable before running tests or update pytest.ini

---

## Success Criteria

1. **Unit Tests**: All configuration parsing tests pass with various port configurations
2. **Integration Tests**: Database connectivity succeeds on both ports 5432 and 5433
3. **Docker Tests**: All services start and communicate correctly with port 5433 mapping
4. **E2E Tests**: Full user flows complete without connection errors
5. **CI/CD Tests**: Pipeline passes with service containers on standard ports

---

## Related Documentation

- [`docs/CONSTITUTION.md`](../../docs/CONSTITUTION.md) - Tech stack and architecture decisions
- [`backend/app/core/database.py`](../../backend/app/core/database.py) - Database engine configuration
- [`backend/app/core/config.py`](../../backend/app/core/config.py) - Settings and environment handling
- [`docker-compose.yml`](../../docker-compose.yml) - Service orchestration
