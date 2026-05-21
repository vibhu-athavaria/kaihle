"""Unit tests for the permissions module."""

import uuid
from unittest.mock import MagicMock

from app.core.permissions import PERMISSION_DEFAULTS, Permission, has_permission
from app.models.user import User, UserRole


def _make_user(role: UserRole, permissions: dict | None = None) -> User:
    """Build a minimal User mock for permission tests."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.role = role
    user.permissions = permissions
    return user


class TestHasPermission:
    def test_has_permission_when_kaihle_admin_then_always_true(self) -> None:
        user = _make_user(UserRole.KAIHLE_ADMIN, permissions={"billing": False})
        assert has_permission(user, Permission.BILLING) is True

    def test_has_permission_when_kaihle_admin_no_permissions_then_always_true(self) -> None:
        user = _make_user(UserRole.KAIHLE_ADMIN, permissions=None)
        assert has_permission(user, Permission.USER_MANAGEMENT) is True

    def test_has_permission_when_null_permissions_then_returns_default_true(self) -> None:
        user = _make_user(UserRole.SCHOOL_ADMIN, permissions=None)
        assert has_permission(user, Permission.BILLING) is True

    def test_has_permission_when_null_permissions_then_returns_default_false_for_content_management(self) -> None:
        user = _make_user(UserRole.TEACHER, permissions=None)
        assert has_permission(user, Permission.CONTENT_MANAGEMENT) is False

    def test_has_permission_when_permission_explicitly_false_then_returns_false(self) -> None:
        user = _make_user(UserRole.SCHOOL_ADMIN, permissions={"billing": False})
        assert has_permission(user, Permission.BILLING) is False

    def test_has_permission_when_permission_explicitly_true_then_returns_true(self) -> None:
        user = _make_user(UserRole.TEACHER, permissions={"content_management": True})
        assert has_permission(user, Permission.CONTENT_MANAGEMENT) is True

    def test_has_permission_when_key_absent_from_dict_then_falls_back_to_default(self) -> None:
        # permissions dict exists but doesn't contain the key
        user = _make_user(UserRole.SCHOOL_ADMIN, permissions={"billing": False})
        # user_management not in dict — should fall back to PERMISSION_DEFAULTS[USER_MANAGEMENT] = True
        assert has_permission(user, Permission.USER_MANAGEMENT) is True

    def test_has_permission_when_empty_permissions_dict_then_all_defaults_apply(self) -> None:
        user = _make_user(UserRole.SCHOOL_ADMIN, permissions={})
        assert has_permission(user, Permission.BILLING) is True
        assert has_permission(user, Permission.USER_MANAGEMENT) is True
        assert has_permission(user, Permission.CONTENT_MANAGEMENT) is False

    def test_has_permission_when_multiple_keys_set_then_evaluates_each_independently(self) -> None:
        user = _make_user(
            UserRole.SCHOOL_ADMIN,
            permissions={"billing": False, "user_management": True},
        )
        assert has_permission(user, Permission.BILLING) is False
        assert has_permission(user, Permission.USER_MANAGEMENT) is True
        assert has_permission(user, Permission.ANALYTICS) is True  # falls back to default


class TestPermissionDefaults:
    def test_permission_defaults_when_checked_then_all_standard_permissions_default_true(self) -> None:
        standard = [
            Permission.BILLING,
            Permission.USER_MANAGEMENT,
            Permission.CURRICULUM,
            Permission.SCHOOL_SETTINGS,
            Permission.ANALYTICS,
            Permission.ASSESSMENTS,
            Permission.LESSON_PLANS,
        ]
        for permission in standard:
            assert PERMISSION_DEFAULTS[permission] is True, f"{permission} should default to True"

    def test_permission_defaults_when_checked_then_content_management_defaults_false(self) -> None:
        assert PERMISSION_DEFAULTS[Permission.CONTENT_MANAGEMENT] is False

    def test_permission_registry_when_checked_then_all_enum_values_have_a_default(self) -> None:
        for permission in Permission:
            assert permission in PERMISSION_DEFAULTS, f"{permission} missing from PERMISSION_DEFAULTS"


class TestPermissionEnum:
    def test_permission_enum_when_used_as_string_then_matches_stored_key(self) -> None:
        assert Permission.BILLING.value == "billing"
        assert Permission.USER_MANAGEMENT.value == "user_management"
        assert Permission.CONTENT_MANAGEMENT.value == "content_management"

    def test_permission_enum_when_used_as_dict_key_then_matches_raw_string(self) -> None:
        permissions = {"billing": False}
        assert permissions.get(Permission.BILLING) is False
