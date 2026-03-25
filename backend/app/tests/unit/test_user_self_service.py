# Tests for user self-service schemas and auth change-password functionality.
# Naming: test_<what>_when_<condition>_then_<expected>

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.auth import ChangePasswordRequest
from app.schemas.user import MeResponse, UserSelfUpdate

# ==============================================================================
# ChangePasswordRequest Schema Tests
# ==============================================================================


class TestChangePasswordRequestSchema:
    """Tests for ChangePasswordRequest schema validation."""

    def test_passwords_match_and_different_then_valid(self) -> None:
        """When passwords match and new differs from current, schema is valid."""
        result = ChangePasswordRequest(
            current_password="OldPass123!",
            new_password="NewPass456!",
            confirm_password="NewPass456!",
        )
        assert result.current_password == "OldPass123!"
        assert result.new_password == "NewPass456!"

    def test_passwords_mismatch_then_validation_error(self) -> None:
        """When new_password and confirm_password mismatch, raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="OldPass123!",
                new_password="NewPass456!",
                confirm_password="Different789!",
            )
        errors = exc_info.value.errors()
        assert any(
            "confirm_password" in str(e.get("loc", [])) or "Passwords do not match" in e.get("msg", "") for e in errors
        )

    def test_new_same_as_current_then_validation_error(self) -> None:
        """When new_password equals current_password, raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="SamePass123!",
                new_password="SamePass123!",
                confirm_password="SamePass123!",
            )
        errors = exc_info.value.errors()
        assert any("new_password" in str(e.get("loc", [])) or "must differ" in e.get("msg", "").lower() for e in errors)

    def test_new_password_too_short_then_validation_error(self) -> None:
        """When new_password is shorter than 8 chars, raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="OldPass123!",
                new_password="Short1!",
                confirm_password="Short1!",
            )
        errors = exc_info.value.errors()
        assert any("new_password" in str(e.get("loc", [])) or "min_length" in e.get("type", "") for e in errors)


# ==============================================================================
# UserSelfUpdate Schema Tests
# ==============================================================================


class TestUserSelfUpdateSchema:
    """Tests for UserSelfUpdate schema validation."""

    def test_first_name_only_then_valid(self) -> None:
        """When only first_name is provided, schema is valid."""
        result = UserSelfUpdate(first_name="Jane")
        assert result.first_name == "Jane"
        assert result.last_name is None

    def test_last_name_only_then_valid(self) -> None:
        """When only last_name is provided, schema is valid."""
        result = UserSelfUpdate(last_name="Doe")
        assert result.last_name == "Doe"
        assert result.first_name is None

    def test_both_names_then_valid(self) -> None:
        """When both first_name and last_name are provided, schema is valid."""
        result = UserSelfUpdate(first_name="Jane", last_name="Doe")
        assert result.first_name == "Jane"
        assert result.last_name == "Doe"

    def test_email_not_in_schema_then_ignored(self) -> None:
        """MeResponse intentionally excludes email field - email cannot be changed via /me."""
        # UserSelfUpdate does not have email field - this is by design per task spec
        result = UserSelfUpdate(first_name="Jane")
        assert not hasattr(result, "email")

    def test_empty_body_then_validation_error(self) -> None:
        """When neither first_name nor last_name is provided, raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            UserSelfUpdate()
        errors = exc_info.value.errors()
        assert any("at least one of first_name or last_name" in e.get("msg", "").lower() for e in errors)

    def test_empty_string_first_name_then_validation_error(self) -> None:
        """When first_name is empty string, raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            UserSelfUpdate(first_name="")
        errors = exc_info.value.errors()
        assert any("at least one of first_name or last_name" in e.get("msg", "").lower() for e in errors)

    def test_whitespace_only_first_name_then_validation_error(self) -> None:
        """When first_name is whitespace only, raises ValidationError after stripping."""
        with pytest.raises(ValidationError) as exc_info:
            UserSelfUpdate(first_name="   ")
        errors = exc_info.value.errors()
        assert any("at least one of first_name or last_name" in e.get("msg", "").lower() for e in errors)


# ==============================================================================
# MeResponse Schema Tests
# ==============================================================================


class TestMeResponseSchema:
    """Tests for MeResponse schema validation."""

    def test_hashed_password_not_in_response(self) -> None:
        """MeResponse intentionally excludes hashed_password field for security."""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        result = MeResponse(
            id=user_id,
            email="jane@example.com",
            first_name="Jane",
            last_name="Doe",
            role="teacher",
            school_id=school_id,
            is_active=True,
        )
        assert not hasattr(result, "hashed_password")
        assert result.email == "jane@example.com"

    def test_all_required_fields_present(self) -> None:
        """MeResponse includes all expected user fields."""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        result = MeResponse(
            id=user_id,
            email="jane@example.com",
            first_name="Jane",
            last_name="Doe",
            role="teacher",
            school_id=school_id,
            is_active=True,
        )
        assert result.id == user_id
        assert result.email == "jane@example.com"
        assert result.first_name == "Jane"
        assert result.last_name == "Doe"
        assert result.role == "teacher"
        assert result.school_id == school_id
        assert result.is_active is True
