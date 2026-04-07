"""Integration tests for RAG retriever.

Tests cover:
- get_relevant_chunks returns top_k chunks sorted by similarity
- similarity_search filters by threshold
- similarity_search with real embeddings (@pytest.mark.slow)

Run with: pytest backend/app/tests/integration/test_rag_retriever.py -v
Run slow tests: pytest backend/app/tests/integration/test_rag_retriever.py -v -m slow
Skip slow tests: pytest backend/app/tests/integration/test_rag_retriever.py -v -m "not slow"
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.retriever import CurriculumRetriever
from app.models.curriculum import (
    Curriculum,
    CurriculumChunk,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
)


@pytest.fixture
async def curriculum_fixture(db_session: AsyncSession) -> Curriculum:
    """Create a test curriculum."""
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Cambridge Lower Secondary",
        code="cambridge_lower",
        description="Cambridge Lower Secondary",
        is_active=True,
    )
    db_session.add(curriculum)
    await db_session.commit()
    return curriculum


@pytest.fixture
async def subject_fixture(db_session: AsyncSession) -> Subject:
    """Create a test subject."""
    subject = Subject(
        id=uuid.uuid4(),
        name="Mathematics",
        code="MATH",
        description="Math subject",
        is_active=True,
    )
    db_session.add(subject)
    await db_session.commit()
    return subject


@pytest.fixture
async def grade_fixture(db_session: AsyncSession) -> Grade:
    """Create a test grade."""
    grade = Grade(
        id=uuid.uuid4(),
        name="Grade 7",
        level=7,
        is_active=True,
    )
    db_session.add(grade)
    await db_session.commit()
    return grade


@pytest.fixture
async def curriculum_topic_fixture(
    db_session: AsyncSession,
    curriculum_fixture: Curriculum,
    subject_fixture: Subject,
    grade_fixture: Grade,
) -> CurriculumTopic:
    """Create a test curriculum topic."""
    topic_id = uuid.uuid4()
    from app.models.curriculum import Topic

    topic = Topic(
        id=topic_id,
        name="Algebra",
        canonical_code="MATH-ALG",
        is_active=True,
    )
    db_session.add(topic)
    await db_session.flush()

    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum_fixture.id,
        subject_id=subject_fixture.id,
        grade_id=grade_fixture.id,
        topic_id=topic_id,
        is_active=True,
    )
    db_session.add(ct)
    await db_session.commit()
    return ct


@pytest.fixture
async def subtopic_with_embedding(
    db_session: AsyncSession,
    curriculum_topic_fixture: CurriculumTopic,
) -> Subtopic:
    """Create a subtopic with an embedding for testing."""
    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=curriculum_topic_fixture.id,
        name="Quadratic Equations",
        canonical_code="MATH-ALG-G7-01",
        learning_objective="Solve quadratic equations by factorization",
        embedding=[0.1] * 768,
        is_active=True,
    )
    db_session.add(subtopic)
    await db_session.commit()
    return subtopic


@pytest.fixture
async def chunks_with_embeddings(
    db_session: AsyncSession,
    subtopic_with_embedding: Subtopic,
    curriculum_topic_fixture: CurriculumTopic,
) -> list[CurriculumChunk]:
    """Create 5 curriculum chunks with embeddings for testing."""
    ct = curriculum_topic_fixture

    chunks = []
    for i in range(5):
        base_value = 0.1 + (i * 0.01)
        chunk = CurriculumChunk(
            id=uuid.uuid4(),
            subtopic_id=subtopic_with_embedding.id,
            curriculum_id=ct.curriculum_id,
            subject_id=ct.subject_id,
            content=f"Content about quadratic equations - section {i + 1}",
            chunk_index=i,
            token_count=100 + i * 10,
            source_file="test_curriculum.pdf",
            embedding=[base_value] * 768,
        )
        chunks.append(chunk)
        db_session.add(chunk)

    await db_session.commit()
    return chunks


@pytest.mark.asyncio
async def test_get_relevant_chunks_when_valid_subtopic_then_returns_3_chunks(
    db_session: AsyncSession,
    chunks_with_embeddings: list[CurriculumChunk],
    subtopic_with_embedding: Subtopic,
) -> None:
    """Test that get_relevant_chunks returns the top_k most similar chunks.

    Seeds 5 chunks with embeddings → retriever returns top 3.
    """
    retriever = CurriculumRetriever(db_session)

    result = await retriever.get_relevant_chunks(
        subtopic_id=subtopic_with_embedding.id,
        top_k=3,
    )

    assert len(result) == 3
    for chunk in result:
        assert chunk.subtopic_id == subtopic_with_embedding.id


@pytest.mark.asyncio
async def test_get_relevant_chunks_when_no_matching_chunks_then_empty_list(
    db_session: AsyncSession,
    curriculum_topic_fixture: CurriculumTopic,
) -> None:
    """Test that get_relevant_chunks returns empty list when no chunks exist."""
    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=curriculum_topic_fixture.id,
        name="Unrelated Topic",
        canonical_code="MATH-UNR-G7-01",
        learning_objective="Test learning objective",
        embedding=[0.5] * 768,
        is_active=True,
    )
    db_session.add(subtopic)
    await db_session.commit()

    retriever = CurriculumRetriever(db_session)

    result = await retriever.get_relevant_chunks(
        subtopic_id=subtopic.id,
        top_k=3,
    )

    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_relevant_chunks_when_subtopic_has_no_embedding_then_empty(
    db_session: AsyncSession,
    curriculum_topic_fixture: CurriculumTopic,
    chunks_with_embeddings: list[CurriculumChunk],
) -> None:
    """Test that get_relevant_chunks returns empty when subtopic has no embedding."""
    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=curriculum_topic_fixture.id,
        name="No Embedding Subtopic",
        canonical_code="MATH-NO-EMB-G7-01",
        learning_objective="Test",
        embedding=None,
        is_active=True,
    )
    db_session.add(subtopic)
    await db_session.commit()

    retriever = CurriculumRetriever(db_session)

    result = await retriever.get_relevant_chunks(
        subtopic_id=subtopic.id,
        top_k=3,
    )

    assert len(result) == 0


@pytest.mark.asyncio
async def test_similarity_search_when_query_matches_then_returns_chunks(
    db_session: AsyncSession,
    curriculum_topic_fixture: CurriculumTopic,
    chunks_with_embeddings: list[CurriculumChunk],
) -> None:
    """Test that similarity_search returns chunks above the similarity threshold."""
    ct = curriculum_topic_fixture

    mock_embedding = [0.15] * 768

    with patch("app.ai.rag.retriever.litellm_embed", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_embedding

        retriever = CurriculumRetriever(db_session)

        result = await retriever.similarity_search(
            query_text="quadratic equations",
            curriculum_id=ct.curriculum_id,
            subject_id=ct.subject_id,
            top_k=5,
            threshold=0.5,
        )

        assert len(result) <= 5


@pytest.mark.asyncio
async def test_similarity_search_when_below_threshold_then_filtered_out(
    db_session: AsyncSession,
    curriculum_topic_fixture: CurriculumTopic,
    chunks_with_embeddings: list[CurriculumChunk],
) -> None:
    """Test that similarity_search filters out chunks below the threshold."""
    ct = curriculum_topic_fixture

    very_different_embedding = [0.99] * 768

    with patch("app.ai.rag.retriever.litellm_embed", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = very_different_embedding

        retriever = CurriculumRetriever(db_session)

        result = await retriever.similarity_search(
            query_text="completely unrelated topic",
            curriculum_id=ct.curriculum_id,
            subject_id=ct.subject_id,
            top_k=5,
            threshold=0.8,
        )

        assert len(result) == 0


@pytest.mark.asyncio
async def test_similarity_search_when_no_chunks_exist_then_empty_list(
    db_session: AsyncSession,
    curriculum_topic_fixture: CurriculumTopic,
) -> None:
    """Test that similarity_search returns empty list when no chunks exist."""
    mock_embedding = [0.5] * 768

    with patch("app.ai.rag.retriever.litellm_embed", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_embedding

        retriever = CurriculumRetriever(db_session)

        result = await retriever.similarity_search(
            query_text="some query",
            curriculum_id=curriculum_topic_fixture.curriculum_id,
            subject_id=curriculum_topic_fixture.subject_id,
            top_k=5,
            threshold=0.5,
        )

        assert len(result) == 0


@pytest.mark.slow
@pytest.mark.asyncio
async def test_similarity_search_when_query_algebraic_equations_then_similarity_above_0_7(
    db_session: AsyncSession,
    curriculum_topic_fixture: CurriculumTopic,
    subtopic_with_embedding: Subtopic,
) -> None:
    """Test similarity search with real embeddings on algebraic content.

    This test requires actual LLM API calls and is marked as slow.
    Skip with: pytest -m "not slow"
    """
    ct = curriculum_topic_fixture

    chunks = []
    algebraic_content = [
        "A quadratic equation is of the form ax^2 + bx + c = 0 where a, b, c are constants.",
        "The quadratic formula x = (-b ± √(b²-4ac)) / 2a gives the roots of a quadratic equation.",
        "Factorization of quadratic expressions involves finding two binomials that multiply to give the original expression.",
        "The discriminant b² - 4ac determines the nature of roots in a quadratic equation.",
        "Graphically, quadratic equations represent parabolas that open upwards or downwards.",
    ]

    for i, content in enumerate(algebraic_content):
        chunk = CurriculumChunk(
            id=uuid.uuid4(),
            subtopic_id=subtopic_with_embedding.id,
            curriculum_id=ct.curriculum_id,
            subject_id=ct.subject_id,
            content=content,
            chunk_index=i,
            token_count=len(content.split()) * 2,
            source_file="algebra_test.pdf",
            embedding=None,
        )
        chunks.append(chunk)
        db_session.add(chunk)

    await db_session.flush()

    embedder_texts = [c.content for c in chunks]
    from app.ai.rag.embedder import CurriculumEmbedder

    embedder = CurriculumEmbedder()

    embeddings = await embedder.embed_texts(embedder_texts)

    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding

    await db_session.commit()

    retriever = CurriculumRetriever(db_session)

    result = await retriever.similarity_search(
        query_text="algebraic equations solving quadratic",
        curriculum_id=ct.curriculum_id,
        subject_id=ct.subject_id,
        top_k=3,
        threshold=0.7,
    )

    assert len(result) > 0
    for chunk in result:
        assert chunk.embedding is not None
