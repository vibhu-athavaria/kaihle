# M0-10-T14 — User Self-Service Endpoints
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T14
**Authors:** Kramer (engineering) · Pixel (design)
**Depends on:** M0-10-T1 (auth middleware)
**Blocks:** M0-7-T2b, M0-7-T3b, M0-7-T4b (all settings pages need these)
**Effort:** 2–3 hours

> Vidhya note: These are utility endpoints — no specific curriculum context.
> Pixel has input on form UX expectations. Kramer leads implementation.

---

## Pixel — Form UX Requirements

Before writing backend code, note what the settings UI tasks expect from these endpoints so the API shapes align precisely.

**`POST /auth/change-password` — what the UI expects:**
- `204 No Content` on success — UI collapses the form and shows a toast. No response body needed.
- `400` with `detail: "Current password is incorrect"` — exact string — UI displays it inline below the current password field.
- `422` for validation failures (mismatch, too short) — UI displays per-field errors.
- The endpoint must accept `current_password`, `new_password`, `confirm_password`. Validation that new ≠ current, and new = confirm, should happen both client-side and server-side. Never trust client-side only.

**`PATCH /users/me` — what the UI expects:**
- Response body: updated user object including `first_name`, `last_name`, `email`, `role`.
- The UI reads `first_name` and `last_name` from the response to update the displayed name without a refetch.
- `email` must be present in the response (read-only) so the UI can verify it hasn't changed.
- `hashed_password` must NOT be present. Ever. (obvious, but worth stating explicitly in a test)

**`GET /users/me` — what the UI expects:**
- Same shape as `PATCH` response.
- Called on settings page mount to pre-populate name fields.
- Also called by the student app's learning profile section to display the user's name.

---

## Kramer — Engineering Spec

### Files

```
backend/app/schemas/user.py                        ← MODIFY: add UserSelfUpdate, MeResponse
backend/app/schemas/auth.py                        ← MODIFY: add ChangePasswordRequest
backend/app/services/auth_service.py               ← MODIFY: add change_password()
backend/app/services/user_service.py               ← MODIFY: add get_me(), update_me()
backend/app/api/v1/routes/auth.py                  ← MODIFY: add POST /auth/change-password
backend/app/api/v1/routes/users.py                 ← MODIFY: add GET + PATCH /users/me
backend/app/tests/unit/test_user_self_service.py   ← CREATE
backend/app/tests/integration/test_self_service_routes.py ← CREATE
```

### New Schemas

**`schemas/auth.py` — add `ChangePasswordRequest`:**
```python
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

    @model_validator(mode="after")
    def new_differs_from_current(self) -> "ChangePasswordRequest":
        if self.current_password == self.new_password:
            raise ValueError("New password must differ from current password")
        return self
```

**`schemas/user.py` — add `UserSelfUpdate` and `MeResponse`:**
```python
class UserSelfUpdate(BaseModel):
    """Only first_name and last_name are user-updatable."""
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UserSelfUpdate":
        if self.first_name is None and self.last_name is None:
            raise ValueError("At least one field must be provided")
        return self


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    school_id: uuid.UUID | None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
    # NEVER include hashed_password — Pixel: response body drives the UI
```

### Service Methods

**`auth_service.py` — add `change_password()`:**
```python
async def change_password(self, user_id: uuid.UUID, current_password: str, new_password: str) -> None:
    user = await self.db.get(User, user_id)
    if not user:
        raise ValueError("User not found")
    if not verify_password(current_password, user.hashed_password):
        raise ValueError("Current password is incorrect")  # Pixel: exact string — UI matches this
    user.hashed_password = hash_password(new_password)
    await self.db.flush()
```

**`user_service.py` — add `get_me()` and `update_me()`:**
```python
async def get_me(self, user_id: uuid.UUID) -> User:
    user = await self.db.get(User, user_id)
    if not user:
        raise ValueError("User not found")
    return user

async def update_me(self, user_id: uuid.UUID, data: UserSelfUpdate) -> User:
    user = await self.db.get(User, user_id)
    if not user:
        raise ValueError("User not found")
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    # email, role, school_id are NOT updatable here — never touch them
    await self.db.flush()
    return user
```

### Route Handlers

**Register `GET /users/me` and `PATCH /users/me` BEFORE `/{user_id}` paths** — FastAPI will match `/me` as a UUID string if the parameterised route comes first.

```python
# routes/auth.py
@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: ChangePasswordRequest, current_user: CurrentUser = Depends(require_full_access), db: AsyncSession = Depends(get_db)) -> None:
    service = AuthService(db)
    try:
        await service.change_password(current_user.id, body.current_password, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# routes/users.py — add BEFORE /{user_id} routes
@router.get("/me", response_model=MeResponse)
async def get_me(current_user: CurrentUser = Depends(require_full_access), db: AsyncSession = Depends(get_db)) -> MeResponse:
    service = UserService(db)
    user = await service.get_me(current_user.id)
    return MeResponse.model_validate(user)

@router.patch("/me", response_model=MeResponse)
async def update_me(body: UserSelfUpdate, current_user: CurrentUser = Depends(require_full_access), db: AsyncSession = Depends(get_db)) -> MeResponse:
    service = UserService(db)
    try:
        user = await service.update_me(current_user.id, body)
        return MeResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

### Unit Tests

```python
class TestChangePassword:
    async def test_correct_current_password_updates_hash(...)
    async def test_wrong_current_password_raises_value_error_with_exact_message(...)
    # Pixel: "Current password is incorrect" — exact string matched by UI
    async def test_schema_confirm_mismatch_raises_validation_error(...)
    async def test_schema_same_as_current_raises_validation_error(...)

class TestUpdateMe:
    async def test_first_name_only_updates_first_last_unchanged(...)
    async def test_both_names_updates_both(...)
    async def test_email_not_in_update_schema(...)
    async def test_empty_body_raises_validation_error(...)
```

### Integration Tests

```python
class TestChangePasswordRoute:
    async def test_correct_current_then_204(...)
    async def test_wrong_current_then_400_with_detail(...)  # Pixel: exact "incorrect" text
    async def test_mismatch_then_422(...)
    async def test_unauthenticated_then_401(...)
    async def test_password_setup_scoped_token_then_403(...)
    async def test_works_for_all_roles(...)  # teacher, student, school_admin, parent

class TestUsersMeRoute:
    async def test_get_me_returns_user_data(...)
    async def test_get_me_never_returns_hashed_password(...)  # Pixel: security
    async def test_patch_me_updates_name_returns_updated_user(...)
    async def test_patch_me_cannot_change_email(...)
    async def test_patch_me_empty_body_422(...)
    async def test_me_route_not_confused_with_uuid_route(...)  # Kramer: route ordering
```

### API Endpoint Map Update

Add to `docs/API_ENDPOINT_TASK_MAP.md`:

| `POST /auth/change-password` | ✅ Built | `M0-10/M0-10-T14` | Any authenticated role; full-access JWT required |
| `GET /users/me` | ✅ Built | `M0-10/M0-10-T14` | Any role |
| `PATCH /users/me` | ✅ Built | `M0-10/M0-10-T14` | first_name + last_name only |

---

## Acceptance Criteria

- [ ] `POST /auth/change-password` → 204 for correct password (Kramer)
- [ ] `POST /auth/change-password` → 400 with `"Current password is incorrect"` exact string (Pixel)
- [ ] `POST /auth/change-password` → 422 for mismatch / same as current (Kramer)
- [ ] `POST /auth/change-password` → 403 for password-setup scoped token (Kramer)
- [ ] `GET /users/me` → 200 with user data, no `hashed_password` field (Pixel)
- [ ] `PATCH /users/me` → updates first_name/last_name, email unchanged (Kramer)
- [ ] `PATCH /users/me` → 422 for empty body (Kramer)
- [ ] `/me` routes registered before `/{user_id}` routes (Kramer)
- [ ] Works for all 5 roles (Kramer)
- [ ] `mypy app/` passes with zero errors (Kramer)
