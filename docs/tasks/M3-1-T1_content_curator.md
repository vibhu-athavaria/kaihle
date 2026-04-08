# M3-1-T1 — Content Curation Engine (with Learning Profile Weighting)
**Milestone:** M3 · **Epic:** M3-1 · **Task:** T1
**Depends on:** M3-0-T1 (subtopic_content table seeded with approved videos), M0-6-T1 (learning profile API)

> **UPDATED April 2026:** Architecture change. Resource retrieval no longer uses
> pgvector cosine similarity or curriculum_chunks. Resources are retrieved from
> `subtopic_content.videos` JSONB array (KaihleAdmin-approved entries only).
> Khan Academy source and static index removed for MVP.
> Modality weighting applies to ordering of approved videos.
> Do NOT implement the old cosine similarity scoring. Do NOT import embedder.py or retriever.py.

---

## User Story
As the system, I want to find the best 1–3 educational videos for a student's gap and
rank them based on that student's preferred learning modality, drawing only from
KaihleAdmin-approved content.

---

## Files to Create / Modify

```
MODIFY  backend/app/ai/content_curator.py          ← rewrite (replaces old stub)
CREATE  backend/tests/unit/test_content_curator.py
CREATE  backend/tests/integration/test_curation_integration.py

REMOVE  backend/app/ai/sources/khan_academy.py     ← delete if it exists
REMOVE  backend/app/ai/sources/static_index.py     ← delete if it exists
REMOVE  backend/data/content/static_resource_index.json ← delete if it exists
```

> Note: `backend/app/ai/sources/youtube.py` is kept — it is used by the seed
> pipeline (M3-0-T1) but NOT called at runtime by this curator. The curator
> reads from the already-seeded `subtopic_content` table.

---

## Main Function

```python
async def curate_resources(
    subtopic: Subtopic,
    student_id: UUID,
    school_id: UUID,
    db: AsyncSession,
    redis: Redis,
) -> list[Resource]:
    """
    Returns top 1-3 approved video resources for the subtopic,
    ordered by modality weighting.
    Cached per (subtopic_id, student_id) for 24 hours.
    Falls back gracefully if no approved resources exist yet.
    """
```

---

## Step-by-Step Logic

### 1. Cache Check
```python
cache_key = f"content:{subtopic.id}:{student_id}"
cached = await redis.get(cache_key)
if cached:
    return parse_resources(cached)
```

### 2. Load Learning Profile
```python
profile = await db.get(StudentLearningProfile, student_id)
# If None → profile = None (handled gracefully in step 4)
```

### 3. Load Approved Videos from subtopic_content
```python
from app.models.subtopic_content import SubtopicContent

content = await db.get(SubtopicContent, subtopic.id)
if not content:
    logger.warning(
        "subtopic_content_missing",
        subtopic_id=str(subtopic.id),
        subtopic_name=subtopic.name,
    )
    return []   # Degrade gracefully — content not yet seeded

approved_videos = content.get_approved_videos()
if not approved_videos:
    logger.info(
        "no_approved_videos",
        subtopic_id=str(subtopic.id),
        pending_count=len([v for v in (content.videos or []) if v.get("status") == "pending"]),
    )
    return []   # KaihleAdmin review pending — degrade gracefully
```

### 4. Apply Modality Weighting
```python
scored = []
for video in approved_videos:
    base_score = _normalise_view_count(video.get("view_count", 0))
    multiplier = 1.0

    if profile:
        # Visual and auditory learners both benefit from video
        if profile.modality_scores.get("visual", 0) > 0.6:
            multiplier *= 1.3
        if profile.modality_scores.get("auditory", 0) > 0.6:
            multiplier *= 1.2   # cumulative with visual multiplier

    video["final_score"] = base_score * multiplier
    scored.append(video)

scored.sort(key=lambda v: v["final_score"], reverse=True)
top_resources = scored[:3]
```

### 5. Convert to Resource objects and Cache
```python
resources = [
    Resource(
        url=v["url"],
        title=v["title"],
        description=v.get("channel", ""),
        resource_type=ResourceType.VIDEO,
        duration_seconds=None,
        source="youtube",
        thumbnail_url=None,
        final_score=v["final_score"],
    )
    for v in top_resources
]

await redis.set(cache_key, serialise(resources), ex=86400)  # 24h TTL
return resources
```

---

## Helper: View Count Normalisation

```python
def _normalise_view_count(view_count: int) -> float:
    """
    Normalise view count to 0.0–1.0 score using log scale.
    1M views → ~1.0, 100K → ~0.83, 10K → ~0.67, 1K → ~0.50
    """
    import math
    if view_count <= 0:
        return 0.0
    return min(1.0, math.log10(max(1, view_count)) / 6.0)
```

---

## Resource Schema

```python
@dataclass
class Resource:
    url: str
    title: str
    description: str
    resource_type: ResourceType   # VIDEO | ARTICLE | INTERACTIVE
    duration_seconds: int | None  # for VIDEO
    source: str                   # "youtube" | "khan_academy" | "static"
    thumbnail_url: str | None
    base_score: float
    final_score: float            # after modality weighting
```

---

## Static Resource Index Format (`static_resource_index.json`)

```json
{
  "algebraic_fractions": [
    {
      "url": "https://www.khanacademy.org/...",
      "title": "Algebraic Fractions — Khan Academy",
      "resource_type": "ARTICLE",
      "source": "khan_academy"
    }
  ]
}
```

---

## Acceptance Criteria

- [ ] Student with `visual=1.0` → video with higher view_count still ranked above lower-count video due to score × 1.3 boost
- [ ] Student with `auditory=1.0` → VIDEO resources get 1.2× boost
- [ ] Student with both `visual=1.0` and `auditory=1.0` → multiplier is cumulative (1.3 × 1.2)
- [ ] Student with `reading_writing=1.0` only → no boost (only VIDEO type in this table)
- [ ] Student with no learning profile → base view_count score used, no error
- [ ] `subtopic_content` row missing → returns empty list, logs WARNING
- [ ] No approved videos for subtopic → returns empty list, logs INFO with pending count
- [ ] Cache hit on second call → no DB call made (test with mock)
- [ ] Returns at most 3 resources
- [ ] All returned resources have `status = 'approved'` — never pending or stale
- [ ] No import of `embedder`, `retriever`, `cosine_similarity`, `khan_academy`, `static_index`

---

## Tests to Write

```python
def test_curate_when_visual_profile_then_multiplier_applied()
def test_curate_when_auditory_profile_then_video_boosted()
def test_curate_when_both_visual_and_auditory_then_multipliers_cumulative()
def test_curate_when_no_profile_then_view_count_score_only()
def test_curate_when_no_subtopic_content_row_then_empty_list_and_warning()
def test_curate_when_no_approved_videos_then_empty_list_and_info_log()
def test_curate_when_cached_then_no_db_call()
def test_curate_returns_max_3_resources()
def test_curate_returns_only_approved_status_videos()
def test_normalise_view_count_when_1M_then_near_1_0()
def test_normalise_view_count_when_zero_then_returns_0()
```
