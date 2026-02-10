# app/services/llm_service.py
import os
import json
import re
import random
import logging
import unicodedata
from typing import Dict, Any, Optional
from app.core.config import settings

import httpx

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.openai_api_key = settings.OPENAI_API_KEY
        self.gemini_api_key = settings.GEMINI_API_KEY


    def _safe_parse_gemini_response(self, raw_text: str):
        """
        Cleans noisy Gemini JSON output and safely parses it into a Python dict.
        Returns None if parsing fails after cleanup.
        """
        try:
            # Remove Markdown formatting (```json ... ```)
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()

            # Normalize Unicode (remove invisible / weird chars)
            cleaned = unicodedata.normalize("NFKD", cleaned)
            cleaned = re.sub(r"[^\x00-\x7F]+", " ", cleaned)  # keep ASCII only

            # Remove stray characters after closing brackets
            cleaned = re.sub(r']\s*[^,\]}]*', ']', cleaned)
            cleaned = re.sub(r'}\s*[^}]*$', '}', cleaned)

            # Fix trailing commas
            cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)

            # Parse JSON
            return json.loads(cleaned)

        except Exception as e:
            print("Could not parse Gemini JSON directly. Raw text:")
            print(raw_text)
            print(f"Parser error: {e}")
            return None


    # ---------------------
    # Question generation
    # ---------------------
    async def generate_question(
        self, subject: str, grade_level: str, topic: Optional[str], difficulty_level: str, student_profile: Optional[Dict[str, Any]] = None, meta_tags: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Returns validated dict keys:
        - question_text, question_type, options (optional), correct_answer, subject, subtopic, difficulty_level, learning_objectives, description, prerequisites
        """

        if self.provider == "mock":
            choices = ["A", "B", "C", "D"]
            correct = random.choice(choices)
            return {
                "question_text": f"Mock: {subject} ({topic}) - difficulty {difficulty_level}",
                "question_type": "multiple_choice",
                "options": choices,
                "correct_answer": correct,
                "subject": subject,
                "subtopic": topic,
                "difficulty_level": difficulty_level,
                "learning_objectives": ["Mock objective"],
                "description": "Mock description",
                "prerequisites": ["Basic knowledge"],
                "meta_tags": {"mock": True},
                "canonical_form": f"MOCK_{subject.upper()}_{topic.upper() if topic else 'GENERAL'}",
                "problem_signature": {
                    "subject": subject,
                    "topic": topic or "General",
                    "subtopic": topic or "General",
                    "concept": "mock_concept",
                    "operation": "mock_op",
                    "grade_level": grade_level,
                    "difficulty": difficulty_level
                }
            }

        student_info = ""
        if student_profile:
            student_info = f"""
            STUDENT PROFILE FOR PERSONALIZATION:
            Personalize the question based on the student's learning profile: {json.dumps(student_profile)}
            Adapt the question style, examples, or context to match their preferences and needs.
            """

        meta_info = ""
        if meta_tags:
            meta_info = f"""
            META TAGS GUIDANCE:
            Incorporate these meta tags into the question generation: {json.dumps(meta_tags)}
            """

        prompt = f"""
            Generate EXACTLY 1 {subject} assessment question for Grade {grade_level} with difficulty '{difficulty_level}'.
            Follow ALL rules strictly and output STRICT JSON ONLY (no extra text).
            {student_info}
            {meta_info}

            RULES:
            1. The question MUST be appropriate for Grade {grade_level}.
            2. The subject MUST be exactly: {subject}. No cross-subject content.
            3. The question MUST reflect the difficulty level '{difficulty_level}'.
            4. The question type MUST be one of: 'MCQ' or 'True/False'.

            5. If question_type = 'MCQ':
            - Provide exactly 4 answer options.
            - The correct_answer MUST match exactly one option.

            6. If question_type = 'True/False':
            - Omit 'options'.
            - correct_answer MUST be 'True' or 'False'.

            7. The question MUST be relevant to this topic: {topic or "General"}.

            8. Include:
            - a clear 'description' of what the question assesses.
            - 1–2 learning_objectives.
            - prerequisites array (skills needed).
            - meta_tags: a dict with relevant tags based on student profile and question (e.g., {{"learning_style": "visual", "interest": "stories"}})

            9. MUST generate a deterministic 'canonical_form'.
            Examples:
                Math:
                PERIMETER_RECTANGLE(L=8,W=3)
                SOLVE_LINEAR_EQUATION(Ax+B=C)
                English:
                READING_THEME(PASSAGE=HASH123)
                VOCAB_CONTEXT(WORD=reluctant,PARA=2)
                Science:
                BIOLOGY_CELL_FUNCTION(MITOCHONDRIA)
                PHYSICS_SPEED(D=20,T=4)
                Humanities:
                HISTORY_EVENT_DATE(WWII_END)
                GEOGRAPHY_RIVER_LONGEST()
            - It MUST be compact, uppercase, no spaces unless inside text.

            10. MUST generate a 'problem_signature' JSON summarizing the conceptual category.
            Example:
            {{
                "subject": "Math",
                "topic": "Geometry",
                "subtopic": "Area & Perimeter",
                "concept": "perimeter_rectangle",
                "operation": "calculate",
                "grade_level": "6",
                "difficulty": "easy"
            }}

            OUTPUT STRICT JSON ONLY (no prose):
            {{
            "question_text": "",
            "question_type": "",
            "options": [],
            "correct_answer": "",
            "subject": "",
            "subtopic": "",
            "difficulty_level": "",
            "learning_objectives": [],
            "description": "",
            "prerequisites": [],
            "meta_tags": {{}},
            "canonical_form": "",
            "problem_signature": {{}},
            }}
        """

        logger.debug("LLM Question Prompt: %s", prompt)
        print("LLM Question Prompt: ", prompt)

        if self.provider == "openai":
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)

                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an educational question generator."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=400,
                )
                text = resp.choices[0].message["content"]
                data = json.loads(text)
                return data
            except Exception as e:
                logger.exception("Failed to generate or parse OpenAI question")
                raise

        elif self.provider == "gemini":
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"parts": [{"text": json.dumps(prompt)}]}],
                }

                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    print("Gemini response:", resp.text)
                    resp.raise_for_status()
                    data = resp.json()

                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                    .strip()
                )
                # --- Clean up Markdown code fences ---

                try:
                    logger.debug("LLM Question Prompt: %s", text)
                    return self._safe_parse_gemini_response(text)
                except json.JSONDecodeError:
                    logger.warning("⚠️ Could not parse Gemini JSON directly. Raw text:\n%s", text)
                    # Fallback: wrap raw text in a basic dict
                    return {"question_text": text, "question_type": "open", "options": [], "correct_answer": "", "subject": subject, "subtopic": topic or "General", "difficulty_level": difficulty_level, "learning_objectives": [], "description": "Fallback description", "prerequisites": [], "meta_tags": {}, "canonical_form": "", "problem_signature": {}}
            except Exception as e:
                logger.exception("Failed to generate or parse Gemini question")
                raise

        else:
            raise NotImplementedError(f"LLM provider {self.provider} not implemented")

    # ---------------------
    # Answer scoring
    # ---------------------
    async def score_answer(self, question: Dict[str, Any], student_answer: str) -> Dict[str, Any]:
        """
        Return: { is_correct: bool, score: float (0-1), feedback: str }
        """
        if self.provider == "mock":
            correct = str(question.get("correct_answer", "")).strip().lower()
            ans = (student_answer or "").strip().lower()
            is_correct = False
            if question.get("question_type") == "multiple_choice":
                is_correct = ans == correct.lower()
            else:
                is_correct = correct and (correct in ans)
            return {
                "is_correct": bool(is_correct),
                "score": 1.0 if is_correct else 0.0,
                "feedback": "Correct!" if is_correct else "Not quite — review the concept.",
            }

        grading_prompt = (
            "Grade the student's answer. "
            f"Question: {question.get('question_text')}\n"
            f"Correct answer: {question.get('correct_answer')}\n"
            f"Student answer: {student_answer}\n"
            "Output only JSON with keys: {is_correct: bool, score: float, feedback: str}"
        )

        if self.provider == "openai":
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an objective grader."},
                        {"role": "user", "content": grading_prompt},
                    ],
                    max_tokens=256,
                )
                text = resp.choices[0].message["content"]
                return json.loads(text)
            except Exception:
                logger.exception("OpenAI grading parse error")
                raise

        elif self.provider == "gemini":
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {"contents": [{"parts": [{"text": grading_prompt}]}]}

                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                    .strip()
                )
                return json.loads(text)
            except Exception:
                logger.exception("Gemini grading parse error")
                raise

        raise NotImplementedError(f"LLM provider {self.provider} not implemented")

    # ---------------------
    # Study plan generation
    # ---------------------
    async def generate_study_plan(
        self, mastery_map: Dict[str, float], subject: str, grade_level: str, top_n: int = 5
    ) -> Dict[str, Any]:
        if self.provider == "mock":
            items = sorted(mastery_map.items(), key=lambda x: x[1])[:top_n]
            lessons = []
            for week, (topic, score) in enumerate(items, start=1):
                lessons.append(
                    {
                        "title": f"Practice {topic}",
                        "topic": topic,
                        "suggested_duration_mins": 20,
                        "week": week,
                        "details": f"Work through fundamentals of {topic}. 3 practice problems, 1 short quiz.",
                    }
                )
            return {
                "summary": f"Focus on {', '.join([t for t, _ in items])}",
                "lessons": lessons,
            }

        study_prompt = (
            f"Generate a {subject} study plan for {grade_level} student. "
            f"Mastery map: {json.dumps(mastery_map)}. Focus on weakest {top_n} topics. "
            "Return JSON: {summary: str, lessons: [{title, topic, suggested_duration_mins, week, details}]}"
        )

        if self.provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": study_prompt}],
                max_tokens=512,
            )
            return json.loads(resp.choices[0].message["content"])

        elif self.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": study_prompt}]}]}

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            return json.loads(text)

        raise NotImplementedError(f"LLM provider {self.provider} not implemented")


# Singleton
llm_service = LLMService()
