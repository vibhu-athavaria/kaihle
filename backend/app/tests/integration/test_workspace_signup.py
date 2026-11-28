"""Integration tests for self-serve workspace signup (plan slice S3a).

POST /auth/signup/workspace creates a workspace school, its owner (role TEACHER), the chosen
curriculum subscription and a password-setup magic link, in one transaction. It is behind
WORKSPACE_SIGNUP_ENABLED, off by default.
"""

import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.models.curriculum import Curriculum
from app.models.school import School, SchoolCurriculum, SchoolType
from app.models.user import TeacherProfile, User, UserRole
from app.tests.integration.conftest import make_auth_header

SIGNUP_URL = "/api/v1/auth/signup/workspace"


@pytest.fixture
def signup_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "workspace_signup_enabled", True)


@pytest.fixture
def sent_emails() -> Generator[AsyncMock, None, None]:
    with patch("app.services.workspace_service.EmailService.send", new=AsyncMock()) as send:
        yield send


def _body(curriculum: Curriculum, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "teacher",
        "first_name": "Ana",
        "last_name": "Lim",
        "email": f"ana-{uuid.uuid4().hex[:8]}@example.com",
        "country": "Singapore",
        "timezone": "Asia/Singapore",
        "city": "Singapore",
        "curriculum_id": str(curriculum.id),
    }
    body.update(overrides)
    return body


async def _school_count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(School)) or 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "school_type"),
    [("teacher", SchoolType.TEACHER_WORKSPACE), ("family", SchoolType.FAMILY)],
)
async def test_signup_workspace_when_valid_then_creates_workspace_owner_and_curriculum(
    client: AsyncClient,
    db_session: AsyncSession,
    test_curriculum: Curriculum,
    signup_enabled: None,
    sent_emails: AsyncMock,
    kind: str,
    school_type: str,
) -> None:
    body = _body(test_curriculum, kind=kind)

    response = await client.post(SIGNUP_URL, json=body)

    assert response.status_code == 202
    owner = await db_session.scalar(select(User).where(User.email == body["email"]))
    assert owner is not None
    assert owner.role == UserRole.TEACHER
    assert owner.is_active is True
    school = await db_session.get(School, owner.school_id)
    assert school is not None
    assert school.type == school_type
    assert school.owner_user_id == owner.id
    assert school.status == "active"
    assert school.slug.startswith("ws-")
    assert school.country == "Singapore"
    assert school.city == "Singapore"
    assert school.timezone == "Asia/Singapore"
    subscription = await db_session.scalar(select(SchoolCurriculum).where(SchoolCurriculum.school_id == school.id))
    assert subscription is not None
    assert subscription.curriculum_id == test_curriculum.id
    assert subscription.is_primary is True
    assert await db_session.scalar(select(TeacherProfile).where(TeacherProfile.user_id == owner.id)) is not None
    sent_emails.assert_awaited_once()


@pytest.mark.asyncio
async def test_signup_workspace_when_valid_then_magic_link_scope_is_password_setup(
    client: AsyncClient,
    db_session: AsyncSession,
    test_curriculum: Curriculum,
    signup_enabled: None,
    sent_emails: AsyncMock,
) -> None:
    body = _body(test_curriculum)

    response = await client.post(SIGNUP_URL, json=body)

    assert response.status_code == 202
    call = sent_emails.await_args
    assert call is not None
    ctx = call.kwargs["ctx"]
    token = parse_qs(urlparse(str(ctx["verify_url"])).query)["token"][0]
    payload = decode_token(token)
    owner = await db_session.scalar(select(User).where(User.email == body["email"]))
    assert owner is not None
    assert payload["scope"] == "password_setup"
    assert payload["sub"] == str(owner.id)
    assert call.kwargs["to"] == body["email"]


@pytest.mark.asyncio
async def test_signup_workspace_when_name_omitted_then_derived_from_owner(
    client: AsyncClient,
    db_session: AsyncSession,
    test_curriculum: Curriculum,
    signup_enabled: None,
    sent_emails: AsyncMock,
) -> None:
    body = _body(test_curriculum, kind="family")

    await client.post(SIGNUP_URL, json=body)

    owner = await db_session.scalar(select(User).where(User.email == body["email"]))
    assert owner is not None
    school = await db_session.get(School, owner.school_id)
    assert school is not None
    assert school.name == "Lim family"


@pytest.mark.asyncio
async def test_signup_workspace_when_email_already_registered_then_same_202_and_nothing_created(
    client: AsyncClient,
    db_session: AsyncSession,
    test_curriculum: Curriculum,
    user: User,
    signup_enabled: None,
    sent_emails: AsyncMock,
) -> None:
    before = await _school_count(db_session)

    response = await client.post(SIGNUP_URL, json=_body(test_curriculum, email=user.email))

    # Same status and body as a new signup, so the endpoint cannot be used to probe for accounts.
    assert response.status_code == 202
    new_signup = await client.post(SIGNUP_URL, json=_body(test_curriculum))
    assert response.json() == new_signup.json()
    assert await _school_count(db_session) == before + 1  # only the second, new signup
    assert sent_emails.await_count == 1


@pytest.mark.asyncio
async def test_signup_workspace_when_flag_off_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
    test_curriculum: Curriculum,
    sent_emails: AsyncMock,
) -> None:
    before = await _school_count(db_session)

    response = await client.post(SIGNUP_URL, json=_body(test_curriculum))

    assert response.status_code == 404
    assert await _school_count(db_session) == before
    sent_emails.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [{"kind": "school"}, {"kind": "SCHOOL_ADMIN"}, {"timezone": "Mars/Olympus"}, {"email": "not-an-email"}],
)
async def test_signup_workspace_when_invalid_body_then_422(
    client: AsyncClient,
    test_curriculum: Curriculum,
    signup_enabled: None,
    sent_emails: AsyncMock,
    overrides: dict[str, str],
) -> None:
    response = await client.post(SIGNUP_URL, json=_body(test_curriculum, **overrides))

    assert response.status_code == 422
    sent_emails.assert_not_awaited()


@pytest.mark.asyncio
async def test_signup_workspace_when_curriculum_unknown_then_400_and_nothing_created(
    client: AsyncClient,
    db_session: AsyncSession,
    signup_enabled: None,
    sent_emails: AsyncMock,
) -> None:
    before = await _school_count(db_session)
    body = _body(Curriculum(id=uuid.uuid4()))

    response = await client.post(SIGNUP_URL, json=body)

    assert response.status_code == 400
    assert await _school_count(db_session) == before
    assert await db_session.scalar(select(User).where(User.email == body["email"])) is None
    sent_emails.assert_not_awaited()


@pytest.mark.asyncio
async def test_signup_workspace_when_curriculum_inactive_then_400(
    client: AsyncClient,
    db_session: AsyncSession,
    test_curriculum: Curriculum,
    signup_enabled: None,
    sent_emails: AsyncMock,
) -> None:
    test_curriculum.is_active = False
    await db_session.commit()

    response = await client.post(SIGNUP_URL, json=_body(test_curriculum))

    assert response.status_code == 400
    sent_emails.assert_not_awaited()


@pytest.mark.asyncio
async def test_signup_workspace_when_concurrent_signup_takes_email_then_same_202(
    client: AsyncClient,
    test_curriculum: Curriculum,
    signup_enabled: None,
) -> None:
    # The unique index on users.email catches the race the pre-check cannot; the caller sees
    # the same response as any other signup.
    race = IntegrityError("INSERT INTO users", {}, Exception("users_email_unique"))
    with patch("app.api.v1.routes.auth.sign_up_workspace", new=AsyncMock(side_effect=race)):
        response = await client.post(SIGNUP_URL, json=_body(test_curriculum))

    assert response.status_code == 202
    assert "message" in response.json()


# ── POST /auth/register is KAIHLE_ADMIN only (plan decision D7) ──────────────


@pytest.mark.asyncio
async def test_register_when_unauthenticated_then_401_or_403(client: AsyncClient, school: School) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"anon-{uuid.uuid4().hex[:8]}@example.com",
            "password": "a-long-enough-pass",
            "role": "SCHOOL_ADMIN",
            "school_id": str(school.id),
            "first_name": "Anon",
            "last_name": "Caller",
        },
    )

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_register_when_caller_not_kaihle_admin_then_403(
    client: AsyncClient, school: School, school_admin: User, teacher: User, student: User
) -> None:
    for caller in (school_admin, teacher, student):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"x-{uuid.uuid4().hex[:8]}@example.com",
                "password": "a-long-enough-pass",
                "role": "TEACHER",
                "school_id": str(school.id),
                "first_name": "X",
                "last_name": "Y",
            },
            headers=make_auth_header(caller),
        )

        assert response.status_code == 403, caller.role
