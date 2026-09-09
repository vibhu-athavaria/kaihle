"""Unit tests for the shared SubtopicContent visibility predicate.

Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest app/tests/unit/test_subtopic_content_visibility.py -v
"""

import uuid

from sqlalchemy.sql.elements import BooleanClauseList

from app.services.subtopic_content_visibility import visible_scope_clause


def test_visible_scope_clause_when_built_then_top_level_operator_is_or() -> None:
    """The clause must be an OR: curriculum-scope rows are visible independent of school_id."""
    clause = visible_scope_clause(uuid.uuid4())
    assert isinstance(clause, BooleanClauseList)
    assert clause.operator.__name__ == "or_"


def test_visible_scope_clause_when_compiled_then_references_scope_and_school_id_columns() -> None:
    """The generated SQL must constrain on both subtopic_content.scope and .school_id —
    a regression that drops either column from the clause would silently reopen the leak."""
    school_id = uuid.uuid4()
    clause = visible_scope_clause(school_id)
    compiled_sql = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "subtopic_content.scope" in compiled_sql
    assert "subtopic_content.school_id" in compiled_sql
    assert "curriculum" in compiled_sql
    # The default (dialect-agnostic) compiler renders UUID literals without hyphens.
    assert str(school_id).replace("-", "") in compiled_sql


def test_visible_scope_clause_when_two_different_schools_then_produces_different_sql() -> None:
    """Different callers must bind their own school_id — a clause built once and reused across
    callers (e.g. accidentally cached) would silently show everyone the same school's content."""
    clause_a = visible_scope_clause(uuid.uuid4())
    clause_b = visible_scope_clause(uuid.uuid4())
    sql_a = str(clause_a.compile(compile_kwargs={"literal_binds": True}))
    sql_b = str(clause_b.compile(compile_kwargs={"literal_binds": True}))
    assert sql_a != sql_b
