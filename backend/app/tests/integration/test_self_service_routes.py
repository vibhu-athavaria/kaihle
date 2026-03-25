# Integration tests for self-service endpoints:
# POST /auth/change-password, GET /users/me, PATCH /users/me
# Naming: test_<what>_when_<condition>_then_<expected>

import uuid

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password

# ==============================================================================
# Helper
# ==============================================================================


def make_auth_header(user_id: uuid.UUID, school_id: uuid.UUID | None, role: str) -> dict[str, str]:
    """Create a full-access JWT Authorization header for testing."""
    token = create_access_token(
        user_id=user_id,
        school_id=school_id,
        role=role,
    )
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Change Password Endpoint Tests
# ==============================================================================


class TestChangePasswordRoute:
    """Tests for POST /api/v1/auth/change-password."""

    @pytest.mark.asyncio
    async def test_change_password_when_correct_current_then_204(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """When current password is correct, change-password returns 204."""
        from app.models.user import User, UserRole

        # Create user with known password
        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("OldPass123!"),
            first_name="Test",
            last_name="User",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "OldPass123!",
                "new_password": "NewPass456!",
                "confirm_password": "NewPass456!",
            },
            headers=headers,
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_change_password_when_wrong_current_then_400(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """When current password is wrong, change-password returns 400."""
        from app.models.user import User, UserRole

        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("CorrectPass123!"),
            first_name="Test",
            last_name="User",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "WrongPassword!",
                "new_password": "NewPass456!",
                "confirm_password": "NewPass456!",
            },
            headers=headers,
        )
        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_change_password_when_mismatch_then_422(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """When new_password and confirm_password mismatch, returns 422."""
        from app.models.user import User, UserRole

        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("OldPass123!"),
            first_name="Test",
            last_name="User",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "OldPass123!",
                "new_password": "NewPass456!",
                "confirm_password": "DifferentPass!",
            },
            headers=headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_change_password_when_no_auth_then_401(
        self,
        client: AsyncClient,
    ) -> None:
        """When no Authorization header, returns 401."""
        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "OldPass123!",
                "new_password": "NewPass456!",
                "confirm_password": "NewPass456!",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_change_password_works_for_all_roles(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """change-password works for TEACHER, SCHOOL_ADMIN, and other roles."""
        from app.models.user import User, UserRole

        for role in [UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PARENT]:
            user = User(
                id=uuid.uuid4(),
                school_id=school.id,
                email=f"test-{role.value}-{uuid.uuid4().hex[:8]}@example.com",
                hashed_password=hash_password("OldPass123!"),
                first_name="Test",
                last_name="User",
                role=role,
                is_active=True,
            )
            db_session.add(user)
            await db_session.commit()

            headers = make_auth_header(user.id, school.id, user.role)

            response = await client.post(
                "/api/v1/auth/change-password",
                json={
                    "current_password": "OldPass123!",
                    "new_password": f"NewPassFor{role.value}!",
                    "confirm_password": f"NewPassFor{role.value}!",
                },
                headers=headers,
            )
            assert response.status_code == 204


# ==============================================================================
# GET /users/me Endpoint Tests
# ==============================================================================


class TestUsersMeRoute:
    """Tests for GET /api/v1/schools/{school_id}/users/me."""

    @pytest.mark.asyncio
    async def test_get_me_returns_user_data(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """GET /me returns the authenticated user's own data."""
        from app.models.user import User, UserRole

        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email="me-test@example.com",
            hashed_password=hash_password("SomePass123!"),
            first_name="Jane",
            last_name="Doe",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        response = await client.get(
            f"/api/v1/schools/{school.id}/users/me",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me-test@example.com"
        assert data["first_name"] == "Jane"
        assert data["last_name"] == "Doe"
        assert data["role"] == "TEACHER"

    @pytest.mark.asyncio
    async def test_get_me_never_returns_hashed_password(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """GET /me response must not contain hashed_password field."""
        from app.models.user import User, UserRole

        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email="nopassword-test@example.com",
            hashed_password=hash_password("SomePass123!"),
            first_name="No",
            last_name="Password",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        response = await client.get(
            f"/api/v1/schools/{school.id}/users/me",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "hashed_password" not in data
        assert "password" not in data

    @pytest.mark.asyncio
    async def test_get_me_includes_school_id(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """GET /me includes school_id in response."""
        from app.models.user import User, UserRole

        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email="schoolid-test@example.com",
            hashed_password=hash_password("SomePass123!"),
            first_name="School",
            last_name="IdTest",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        response = await client.get(
            f"/api/v1/schools/{school.id}/users/me",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["school_id"] == str(school.id)

    @pytest.mark.asyncio
    async def test_get_me_without_auth_then_401(
        self,
        client: AsyncClient,
        school,
    ) -> None:
        """GET /me without auth returns 401."""
        response = await client.get(f"/api/v1/schools/{school.id}/users/me")
        assert response.status_code == 401


# ==============================================================================
# PATCH /users/me Endpoint Tests
# ==============================================================================


class TestPatchUsersMeRoute:
    """Tests for PATCH /api/v1/schools/{school_id}/users/me."""

    @pytest.mark.asyncio
    async def test_patch_me_updates_first_name(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """PATCH /me with first_name updates the user's first_name."""
        from app.models.user import User, UserRole

        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"patch-first-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("SomePass123!"),
            first_name="Original",
            last_name="LastName",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        response = await client.patch(
            f"/api/v1/schools/{school.id}/users/me",
            json={"first_name": "Updated"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "LastName"

    @pytest.mark.asyncio
    async def test_patch_me_updates_last_name(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """PATCH /me with last_name updates the user's last_name."""
        from app.models.user import User, UserRole

        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"patch-last-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("SomePass123!"),
            first_name="FirstName",
            last_name="Original",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        response = await client.patch(
            f"/api/v1/schools/{school.id}/users/me",
            json={"last_name": "Updated"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "FirstName"
        assert data["last_name"] == "Updated"

    @pytest.mark.asyncio
    async def test_patch_me_cannot_change_email(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """PATCH /me does not accept email field (not in UserSelfUpdate schema)."""
        from app.models.user import User, UserRole

        original_email = f"noemail-{uuid.uuid4().hex[:8]}@example.com"
        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=original_email,
            hashed_password=hash_password("SomePass123!"),
            first_name="No",
            last_name="Email",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        response = await client.patch(
            f"/api/v1/schools/{school.id}/users/me",
            json={"email": "hacker@example.com", "first_name": "Changed"},
            headers=headers,
        )
        # email should be ignored; only first_name should be updated
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Changed"
        assert data["email"] == original_email

    @pytest.mark.asyncio
    async def test_patch_me_empty_body_then_422(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """PATCH /me with empty body returns 422 (validation error)."""
        from app.models.user import User, UserRole

        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"empty-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("SomePass123!"),
            first_name="Empty",
            last_name="Body",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        response = await client.patch(
            f"/api/v1/schools/{school.id}/users/me",
            json={},
            headers=headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_me_without_auth_then_401(
        self,
        client: AsyncClient,
        school,
    ) -> None:
        """PATCH /me without auth returns 401."""
        response = await client.patch(
            f"/api/v1/schools/{school.id}/users/me",
            json={"first_name": "Hacker"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_route_not_confused_with_uuid_route(
        self,
        client: AsyncClient,
        db_session,
        school,
    ) -> None:
        """GET /me should not be matched as /{user_id} where user_id='me'."""
        from app.models.user import User, UserRole

        # Create a teacher
        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"me-route-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("SomePass123!"),
            first_name="Me",
            last_name="Route",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = make_auth_header(user.id, school.id, user.role)

        # Request to /users/me should work
        response = await client.get(
            f"/api/v1/schools/{school.id}/users/me",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Me"

        # Request to /users/me with PATCH should also work
        response = await client.patch(
            f"/api/v1/schools/{school.id}/users/me",
            json={"first_name": "UpdatedMe"},
            headers=headers,
        )
        assert response.status_code == 200
