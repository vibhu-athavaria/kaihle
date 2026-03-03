# M3-1-T1 — Content Curation Engine (with Learning Profile Weighting)
**Milestone:** M3 · **Epic:** M3-1 · **Task:** T1
**Depends on:** M1-2-T2 (subtopic embeddings in pgvector), M0-6-T1 (learning profile API)

---

## User Story
As the system, I want to find the best 2–3 educational resources for a student's gap and rank them based on that student's preferred learning modality.

---

## Files to Create

```
backend/app/ai/content_curator.py
backend/app/ai/sources/youtube.py
backend/app/ai/sources/khan_academy.py
backend/app/ai/sources/static_index.py         # curated fallback list
backend/data/content/static_resource_index.json
backend/tests/unit/test_content_curator.py
backend/tests/integration/test_curation_integration.py
```

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
    Returns top 3 resources for the subtopic, ranked by:
      base_alignment_score × modality_multiplier
    Cached per (subtopic_id, student_id) for 24 hours.
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

### 3. Fetch Candidates from Sources (parallel)
```python
candidates = await asyncio.gather(
    youtube_source.search(subtopic),     # YouTube Data API v3
    khan_source.search(subtopic),        # Khan Academy topic API
    static_source.search(subtopic),      # static_resource_index.json lookup
    return_exceptions=True
)
candidates = flatten([c for c in candidates if not isinstance(c, Exception)])
```

**YouTube query:** `f"{subtopic.subject_name} {subtopic.name} {curriculum_code} tutorial"`
Filter: duration 3–15 minutes, language=English, category=Education

**Khan Academy:** search by subtopic name against Khan topic tree. Return matching exercise + article links.

**Static index:** JSON file of manually curated resources indexed by `subtopic_code`. Fallback when APIs return nothing.

### 4. Score Each Candidate
```python
for resource in candidates:
    # Base: cosine similarity between resource embedding and subtopic.embedding
    resource_embedding = await embed(resource.title + " " + resource.description)
    base_score = cosine_similarity(resource_embedding, subtopic.embedding)

    # Filter: skip if base_score < 0.72
    if base_score < 0.72:
        continue

    # Modality multiplier (v2.1)
    multiplier = 1.0
    if profile:
        if profile.modality_scores.get("visual", 0) > 0.6:
            if resource.resource_type == ResourceType.VIDEO:
                multiplier *= 1.3
        if profile.modality_scores.get("reading_writing", 0) > 0.6:
            if resource.resource_type == ResourceType.ARTICLE:
                multiplier *= 1.3
        if profile.modality_scores.get("kinesthetic", 0) > 0.6:
            if resource.resource_type == ResourceType.INTERACTIVE:
                multiplier *= 1.3
        if profile.modality_scores.get("auditory", 0) > 0.6:
            if resource.resource_type == ResourceType.VIDEO:
                multiplier *= 1.2   # cumulative with visual multiplier

    resource.final_score = base_score * multiplier
```

### 5. Select Top 3 and Cache
```python
top3 = sorted(filtered, key=lambda r: r.final_score, reverse=True)[:3]
await redis.set(cache_key, serialise(top3), ex=86400)  # 24h TTL
return top3
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

- [ ] Student with `visual=1.0` → VIDEO resources ranked above ARTICLE for same base score
- [ ] Student with `reading_writing=1.0` → ARTICLE ranked above VIDEO
- [ ] Student with `kinesthetic=1.0` → INTERACTIVE ranked above VIDEO
- [ ] Student with no learning profile → falls back to base score only, no error, returns 3 resources
- [ ] Resources with base score < 0.72 filtered out
- [ ] YouTube videos outside 3–15 minute range filtered out
- [ ] Cache hit on second call → no API call made (test with mock)
- [ ] One source API fails → other sources still used (exception caught)
- [ ] Returns at most 3 resources

---

## Tests to Write

```python
test_curate_when_visual_profile_then_videos_ranked_first()
test_curate_when_reading_profile_then_articles_ranked_first()
test_curate_when_no_profile_then_base_score_used()
test_curate_when_base_score_below_threshold_then_filtered()
test_curate_when_cached_then_no_api_call()
test_curate_when_youtube_fails_then_other_sources_still_used()
test_curate_when_all_sources_return_low_scores_then_empty_list()
test_curate_returns_max_3_resources()
```
