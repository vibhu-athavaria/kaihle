-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Enable pg_trgm for trigram text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
