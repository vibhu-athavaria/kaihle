# app/services/rag/__init__.py
"""
RAG (Retrieval-Augmented Generation) Services.

This package provides services for:
- Curriculum content extraction (Phase 10B)
- Embedding ingestion (Phase 10C)
- Similarity query (Phase 10D)

All services are called ONLY from Celery worker tasks.
"""
