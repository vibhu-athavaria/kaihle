"""Shared visibility predicate for SubtopicContent reads.

Every query that serves SubtopicContent to a non-KaihleAdmin viewer (a teacher or a student)
must use this so a school boundary is never a query-by-query judgment call (CONSTITUTION Rule 3).

KaihleAdmin routes bypass this entirely per Rule 12 — they intentionally see all schools'
content (that's the Course Content Review queue's whole purpose).
"""

import uuid

from sqlalchemy import ColumnElement, and_, or_

from app.models.subtopic_content import SubtopicContent


def visible_scope_clause(school_id: uuid.UUID) -> ColumnElement[bool]:
    """True for curriculum-scope rows (global) or the caller's own school-scope rows.

    A school-scope row with school_id NULL never matches — that state should not exist for
    scope='school' rows, and this clause does not treat it as globally visible.
    """
    return or_(
        SubtopicContent.scope == "curriculum",
        and_(SubtopicContent.scope == "school", SubtopicContent.school_id == school_id),
    )
