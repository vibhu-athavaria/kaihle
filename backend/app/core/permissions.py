"""Permission registry and evaluation for fine-grained access control.

All permission keys are defined here as a StrEnum — the single source of truth.
The DB stores permissions as a JSONB dict on users.permissions.
NULL permissions = all defaults apply (open by default, restrict explicitly).
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.user import User


class Permission(StrEnum):
    # School Admin permissions — controlled by Kaihle Admin
    BILLING = "billing"
    USER_MANAGEMENT = "user_management"
    CURRICULUM = "curriculum"
    SCHOOL_SETTINGS = "school_settings"
    ANALYTICS = "analytics"

    # Teacher permissions — controlled by School Admin
    ASSESSMENTS = "assessments"
    LESSON_PLANS = "lesson_plans"
    CONTENT_MANAGEMENT = "content_management"


# Default value for each permission when not explicitly set.
# True  = accessible unless explicitly revoked (standard permissions).
# False = locked unless explicitly granted (future premium/restricted features).
PERMISSION_DEFAULTS: dict[Permission, bool] = {
    Permission.BILLING: True,
    Permission.USER_MANAGEMENT: True,
    Permission.CURRICULUM: True,
    Permission.SCHOOL_SETTINGS: True,
    Permission.ANALYTICS: True,
    Permission.ASSESSMENTS: True,
    Permission.LESSON_PLANS: True,
    Permission.CONTENT_MANAGEMENT: False,  # future premium feature — off by default
}

# Human-readable description of what each permission gates.
# Used in admin UIs and error messages.
PERMISSION_SCOPE: dict[Permission, str] = {
    Permission.BILLING: "View and manage subscription, invoices, and payment status",
    Permission.USER_MANAGEMENT: "Invite, edit, and deactivate users within the school",
    Permission.CURRICULUM: "Assign and remove curriculum programmes from the school",
    Permission.SCHOOL_SETTINGS: "Edit school profile: name, timezone, and contact info",
    Permission.ANALYTICS: "View school-wide mastery reports and usage analytics",
    Permission.ASSESSMENTS: "Create, edit, and publish diagnostic and formative assessments",
    Permission.LESSON_PLANS: "Create, edit, and publish AI-generated lesson plans",
    Permission.CONTENT_MANAGEMENT: "Review and approve AI-generated subtopic content",
}


def has_permission(user: "User", permission: Permission) -> bool:
    """Return True if the user has the given permission.

    Evaluation order:
    1. KAIHLE_ADMIN always has all permissions — explicit bypass.
    2. NULL permissions column → use PERMISSION_DEFAULTS.
    3. Explicit key in user.permissions dict → use that value.
    4. Key absent from dict → fall back to PERMISSION_DEFAULTS.
    """
    from app.models.user import UserRole

    if user.role == UserRole.KAIHLE_ADMIN:
        return True

    default = PERMISSION_DEFAULTS[permission]

    if user.permissions is None:
        return default

    permissions: dict[str, Any] = user.permissions
    return bool(permissions.get(permission, default))
