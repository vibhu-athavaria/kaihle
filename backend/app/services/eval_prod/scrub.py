"""Best-effort PII scrubber for production-output evaluation (MLH-T18 slice 3, decision D8).

Text from `llm_usage_events` is scrubbed here BEFORE any judge sees it. This is a pure
module: no database, no environment, no logging. The caller loads the names (see
`sampler.load_scrub_names`) and passes them in.

What it removes, in this order, replacing with fixed tokens:
  email addresses -> [EMAIL]      phone numbers (international and local formats) -> [PHONE]
  URLs -> [URL]                   long digit runs (ID-like) -> [ID]
  the school name, then the display-name tokens of the school's users -> [NAME]
  (case-insensitive, whole word only).

FAIL CLOSED. After replacement the PII patterns are run again over the result. Any hit, or
any exception inside the scrubber, raises `ScrubFailedError`; the row is then skipped and
counted (`skipped_scrub_failed_count`) and is never sent on unscrubbed.

BEST-EFFORT LIMITS. This control is deliberately described as best-effort because the
text may have been written by minors. It cannot reliably catch free-text locations
("I live near the old market in ..."), relatives' or friends' names that are not accounts
in the school, nicknames, or personal circumstances described in prose. It also errs the
other way: a digit run of six or more is replaced even when it is maths, and a name token
that is also a common word is replaced wherever it appears as a whole word. The admin UI
states these limits plainly.

Error messages never contain the text being scrubbed.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class ScrubFailedError(Exception):
    """Scrubbing could not be confirmed. The message never contains the text."""


class _Substitutor(Protocol):
    def sub(self, repl: str, string: str) -> str: ...


EMAIL_TOKEN = "[EMAIL]"
PHONE_TOKEN = "[PHONE]"
URL_TOKEN = "[URL]"
ID_TOKEN = "[ID]"
NAME_TOKEN = "[NAME]"

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"']*[^\s<>\"'.,;:!?)\]]", re.IGNORECASE)
# International (+CC ...) or national-trunk (leading 0) numbers: 2-4 digit groups split by
# optional space/dash/dot. Covers +62/+60/+66/+84/+63/+65 and local 08xx/01x/09xx styles.
_PHONE = re.compile(r"(?<![\w+])(?:\+\d{1,3}[\s.-]?|0)\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){2,3}(?!\w)")
_LONG_DIGITS = re.compile(r"\d{6,}")

_STEPS: tuple[tuple[_Substitutor, str], ...] = (
    (_EMAIL, EMAIL_TOKEN),
    (_PHONE, PHONE_TOKEN),
    (_URL, URL_TOKEN),
    (_LONG_DIGITS, ID_TOKEN),
)
# The same classes of PII, re-checked on the output. Names are not rechecked: whether a
# given token is "a name" cannot be decided without the same list that was just applied.
_RESIDUAL_PATTERNS: tuple[re.Pattern[str], ...] = (_EMAIL, _PHONE, _URL, _LONG_DIGITS)

_MIN_NAME_TOKEN_LENGTH = 2


def _name_pattern(person_names: Sequence[str], school_name: str | None) -> re.Pattern[str] | None:
    """One whole-word, case-insensitive alternation: school-name phrase first, then tokens."""
    alternatives: list[str] = []
    if school_name and school_name.strip():
        words = [re.escape(w) for w in school_name.split()]
        alternatives.append(r"\s+".join(words))
    tokens = {
        token.lower()
        for name in person_names
        for token in re.split(r"\s+", name.strip())
        if len(token) >= _MIN_NAME_TOKEN_LENGTH
    }
    # Longest first so a long token is never pre-empted by a shorter prefix of itself.
    alternatives.extend(re.escape(t) for t in sorted(tokens, key=lambda t: (-len(t), t)))
    if not alternatives:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)", re.IGNORECASE)


def scrub_text(text: str, *, person_names: Sequence[str] = (), school_name: str | None = None) -> str:
    """Return `text` with PII-like content replaced; raise `ScrubFailedError` if unconfirmed."""
    try:
        out = text
        for pattern, token in _STEPS:
            out = pattern.sub(token, out)
        name_pattern = _name_pattern(person_names, school_name)
        if name_pattern is not None:
            out = name_pattern.sub(NAME_TOKEN, out)
        residual = any(p.search(out) for p in _RESIDUAL_PATTERNS)
    except Exception as exc:
        # Deliberately broad and deliberately silent about the cause: the exception text may
        # quote the input. Fail closed with only the class name.
        raise ScrubFailedError(f"scrubber raised {type(exc).__name__}") from None
    if residual:
        raise ScrubFailedError("PII pattern still present after replacement")
    return out


@dataclass(frozen=True)
class ScrubInput:
    """One sampled event's text plus the names to mask in it."""

    event_id: UUID
    prompt_text: str | None
    response_text: str
    person_names: tuple[str, ...]
    school_name: str | None


@dataclass(frozen=True)
class ScrubbedEvent:
    event_id: UUID
    prompt_text: str | None
    response_text: str


@dataclass(frozen=True)
class ScrubBatch:
    scrubbed: list[ScrubbedEvent]
    skipped_scrub_failed_count: int


def scrub_events(items: Sequence[ScrubInput]) -> ScrubBatch:
    """Scrub every item; a row whose scrubbing fails is dropped and counted, never passed on."""
    scrubbed: list[ScrubbedEvent] = []
    skipped = 0
    for item in items:
        try:
            prompt = (
                scrub_text(item.prompt_text, person_names=item.person_names, school_name=item.school_name)
                if item.prompt_text is not None
                else None
            )
            response = scrub_text(item.response_text, person_names=item.person_names, school_name=item.school_name)
        except ScrubFailedError:
            skipped += 1
            continue
        scrubbed.append(ScrubbedEvent(item.event_id, prompt, response))
    return ScrubBatch(scrubbed=scrubbed, skipped_scrub_failed_count=skipped)
