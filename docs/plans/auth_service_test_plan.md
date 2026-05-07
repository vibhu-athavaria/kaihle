# Test Plan: auth_service.py

## Overview
This test plan covers unit tests for `backend/app/services/auth_service.py` to improve coverage from 52% to 80%+.

## Test Pattern
Follow the existing pattern from `test_school_service.py`:
- Use `pytest` with `pytest-asyncio`
- Mock `AsyncSession` with `MagicMock`
- Name tests: `test_<method>_when_<condition>_then_<expected>`

## Required Fixtures
```python
@pytest.fixture
def mock_db() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session

@pytest.fixture
def auth_service(mock_db: MagicMock) -> AuthService:
    return AuthService(mock_db)
```

## Test Cases by Method

### 1. register() (lines 31-65)

| Test Case | Condition | Expected |
|-----------|-----------|----------|
| `test_register_when_valid_data_then_user_created` | Valid email, password, role | Returns RegisterResponse with user_id, email, role |
| `test_register_when_duplicate_email_raises_value_error` | Email already exists in school | Raises ValueError("Email already registered") |
| `test_register_when_duplicate_email_in_different_school_then_succeeds` | Same email, different school_id | User created successfully |
| `test_register_when_no_school_then_global_check` | school_id=None | Checks email globally (no school_id filter) |
| `test_register_when_kaihle_admin_role_then_global_check` | role=KaihleAdmin, school_id=None | Checks email globally |

### 2. login() (lines 67-91)

| Test Case | Condition | Expected |
|-----------|-----------|----------|
| `test_login_when_valid_credentials_then_returns_tokens` | Valid email + password | Returns LoginResponse with access_token, refresh_token |
| `test_login_when_invalid_password_raises_value_error` | Wrong password | Raises ValueError("Invalid credentials") |
| `test_login_when_user_not_found_raises_value_error` | Email not in DB | Raises ValueError("Invalid credentials") |
| `test_login_when_inactive_user_raises_value_error` | is_active=False | Raises ValueError("Account is inactive") |
| `test_login_when_user_without_password_raises_value_error` | hashed_password=None | Raises ValueError("Invalid credentials") |

### 3. send_magic_link() (lines 93-107)

| Test Case | Condition | Expected |
|-----------|-----------|----------|
| `test_send_magic_link_when_valid_active_user_then_sends_email` | Active user exists | Calls _send_magic_link_email, stores token |
| `test_send_magic_link_when_user_not_found_then_returns_silently` | No user with email | Returns None (silent - security) |
| `test_send_magic_link_when_inactive_user_then_returns_silently` | User exists but is_active=False | Returns None (silent - security) |

### 4. verify_magic_link() (lines 109-160)

| Test Case | Condition | Expected |
|-----------|-----------|----------|
| `test_verify_magic_link_when_valid_token_then_returns_tokens` | Valid unexpired magic link token | Returns LoginResponse with new tokens |
| `test_verify_magic_link_when_invalid_token_raises_error` | Malformed token | Raises InvalidTokenError |
| `test_verify_magic_link_when_wrong_token_type_raises_error` | Token is not magic_link type | Raises InvalidTokenError("Not a magic link token") |
| `test_verify_magic_link_when_token_already_used_raises_error` | used_at != None | Raises InvalidTokenError("Token invalid or already used") |
| `test_verify_magic_link_when_token_expired_raises_error` | expires_at < now | Raises InvalidTokenError("Token invalid or already used") |
| `test_verify_magic_link_when_user_not_found_raises_error` | User deleted after token creation | Raises InvalidTokenError("User not found") |

### 5. refresh_access_token() (lines 162-184)

| Test Case | Condition | Expected |
|-----------|-----------|----------|
| `test_refresh_access_token_when_valid_token_then_returns_new_access` | Valid refresh token | Returns TokenResponse with new access_token |
| `test_refresh_access_token_when_token_not_found_raises_error` | Token hash not in DB | Raises InvalidTokenError("Refresh token invalid or expired") |
| `test_refresh_access_token_when_token_already_used_raises_error` | used_at != None | Raises InvalidTokenError("Refresh token invalid or expired") |
| `test_refresh_access_token_when_token_expired_raises_error` | expires_at < now | Raises InvalidTokenError("Refresh token invalid or expired") |
| `test_refresh_access_token_when_user_not_found_raises_error` | User deleted after token | Raises InvalidTokenError("User not found") |

### 6. logout() (lines 186-197)

| Test Case | Condition | Expected |
|-----------|-----------|----------|
| `test_logout_when_valid_token_then_marks_used` | Valid refresh token | Sets auth_token.used_at, calls flush |
| `test_logout_when_token_not_found_then_does_nothing` | Token not in DB | No error, no flush |

### 7. _get_active_user_by_email() (lines 199-205) - Helper

| Test Case | Condition | Expected |
|-----------|-----------|----------|
| `test_get_active_user_by_email_when_found_and_active_returns_user` | User exists, is_active=True | Returns User |
| `test_get_active_user_by_email_when_not_found_raises_error` | Email not in DB | Raises ValueError("Invalid credentials") |
| `test_get_active_user_by_email_when_inactive_raises_error` | User exists, is_active=False | Raises ValueError("Account is inactive") |

## Mocking Requirements

### Core Security Functions (mock in each test)
- `app.core.security.create_access_token`
- `app.core.security.generate_refresh_token`
- `app.core.security.store_refresh_token`
- `app.core.security.create_magic_link_token`
- `app.core.security.hash_token`
- `app.core.security.store_magic_link_token`
- `app.core.security.decode_token`

### Database Mocks
- `mock_db.scalar()` - For SELECT queries returning single result
- `mock_db.get()` - For get_by_id queries
- `mock_db.execute()` - For complex queries
- `mock_db.add()` - For inserts
- `mock_db.flush()` - For flushing

## Coverage Target
- Primary goal: Cover all 5 public methods + logout
- Helper method _get_active_user_by_email covered via login tests
- _send_magic_link_email - can be mocked, no direct testing needed

## File Location
Create: `backend/app/tests/unit/test_auth_service.py`
