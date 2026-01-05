# Kaihle  
**AI-powered learning infrastructure for schools and families**

---

## Overview

Kaihle is an AI-driven learning platform that helps schools deliver **personalized, curriculum-aligned education** while reducing teacher workload.

Kaihle handles curriculum structuring, adaptive learning paths, and continuous assessment so that **teachers can focus on mentorship** and schools can spend more time on life skills, creativity, and real-world learning.

The platform can be used by:
- **Schools** (as a core learning engine for teachers)
- **Parents/Families** (as a guided learning system with mentor oversight)

---

## The Problem

Modern education struggles with:
- Heavy teacher workload from lesson planning
- One-size-fits-all pacing for diverse learners
- Limited time for life skills and experiential learning
- Fragmented tools that don’t adapt to individual students

Existing LMSs manage content, but they do not **personalize learning at scale**.

---

## What Kaihle Does

Kaihle acts as a **learning engine** underneath a school or home learning environment.

### Core capabilities:
- Generates **curriculum-aligned learning paths** based on:
  - Academic standards (CBSE, IB, IGCSE, etc.)
  - Student learning style and interests
  - Ongoing progress and mastery

- Breaks curriculum into:
  - Micro-concepts
  - Adaptive exercises
  - Continuous formative assessments

- Dynamically adjusts difficulty, pace, and sequencing

- Provides teachers with **mentor dashboards** showing:
  - Student progress
  - Learning gaps
  - Intervention opportunities

Teachers guide and coach.  
Kaihle handles structure and personalization.

---

## Design Principles

- **Teachers are mentors, not content creators**
- **AI stays invisible** (learning paths, not algorithms)
- **Learning should take less time, not more**
- **Human judgment always overrides automation**

---

## High-Level Architecture

Frontend (React + Vite)
|
Backend API (FastAPI)
|
AI Layer (LLM + rules)
|
Database (PostgreSQL / Supabase)



## Technology Stack

### Frontend
- React
- TypeScript
- Vite

### Backend
- Python
- FastAPI
- REST + streaming APIs

### AI Layer
- LLMs (local or hosted via Ollama)
- Prompt templates + structured prompting
- Validation and deterministic logic on top of LLM output

### Database & Auth
- PostgreSQL
- Supabase (auth, storage, database)

---

## Key Modules

- **Curriculum Engine** – maps standards to concepts and learning units  
- **Adaptive Learning Engine** – adjusts pacing and difficulty per student  
- **Assessment System** – diagnostic and formative assessments  
- **Mentor Dashboard** – progress insights and intervention tools  
- **Parent View** – simple, outcome-focused progress tracking  

---

## What Kaihle Is Not

- ❌ Not a content marketplace  
- ❌ Not a traditional LMS  
- ❌ Not a teacher-replacement system  

Kaihle is **infrastructure**, not a shortcut.

---

## Status

- Actively under development
- Architecture-first approach
- Open to contributors interested in education, AI systems, and human-centered design

---

## Vision

Kaihle aims to become the **default learning engine behind modern schools** — quietly improving learning while keeping humans at the center.
