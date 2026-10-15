"""Unit tests for the production-evaluation scrubber (MLH-T18 slice 3).

The scrubber is pure: no DB, no globals. Every test passes names in explicitly.
"""

import re
import uuid
from typing import Any

import pytest

from app.services.eval_prod import scrub
from app.services.eval_prod.scrub import ScrubFailedError, ScrubInput, scrub_events, scrub_text


def test_scrub_when_email_present_then_replaced_with_email_token() -> None:
    assert scrub_text("write to kid.name+1@example.co.uk now") == "write to [EMAIL] now"


@pytest.mark.parametrize(
    "number",
    [
        "+62 812 3456 7890",
        "+60 12-345 6789",
        "+66 81 234 5678",
        "+84 90 123 4567",
        "+63 917 123 4567",
        "+65 9123 4567",
        "081234567890",
    ],
)
def test_scrub_when_phone_in_regional_formats_then_replaced(number: str) -> None:
    assert scrub_text(f"call me on {number} please") == "call me on [PHONE] please"


def test_scrub_when_url_present_then_replaced() -> None:
    out = scrub_text("see https://example.com/a?b=1 and www.example.org/x ok")
    assert out == "see [URL] and [URL] ok"


def test_scrub_when_known_user_name_present_then_replaced_case_insensitively_whole_word_only() -> None:
    out = scrub_text("Then SITI told budi that Siti-Aminah agreed", person_names=["Siti Aminah", "Budi"])
    assert out == "Then [NAME] told [NAME] that [NAME]-[NAME] agreed"


def test_scrub_when_name_is_substring_of_another_word_then_not_replaced() -> None:
    text = "The Marketplace was marked and Amanda arrived"
    assert scrub_text(text, person_names=["Mark", "Man"]) == text


def test_scrub_when_school_name_present_then_replaced() -> None:
    out = scrub_text("I study at sunrise   Academy of Bali.", school_name="Sunrise Academy of Bali")
    assert out == "I study at [NAME]."


def test_scrub_when_long_digit_run_then_replaced() -> None:
    assert scrub_text("student number 20240012345 is mine") == "student number [ID] is mine"


def test_scrub_when_no_pii_then_text_unchanged() -> None:
    text = "Solve 3x + 2 = 11, so x = 3. Photosynthesis uses 6 CO2 and 12 H2O."
    assert scrub_text(text) == text


def test_scrub_when_residual_pii_after_replacement_then_raises_scrub_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    # A residual check that matches a token the scrubber itself emits simulates a pattern
    # the replacement pass missed.
    monkeypatch.setattr(scrub, "_RESIDUAL_PATTERNS", (re.compile(r"\[EMAIL\]"),))
    with pytest.raises(ScrubFailedError):
        scrub_text("mail a@b.co")


def test_scrub_when_a_step_raises_then_wrapped_as_scrub_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        def sub(self, repl: str, text: str) -> str:
            raise RuntimeError("secret raw text must not leak")

    monkeypatch.setattr(scrub, "_STEPS", ((Boom(), "[X]"),))
    with pytest.raises(ScrubFailedError) as exc:
        scrub_text("anything")
    assert "secret raw text" not in str(exc.value)


def test_scrub_when_name_list_empty_then_still_scrubs_pattern_pii() -> None:
    assert scrub_text("a@b.co", person_names=[], school_name=None) == "[EMAIL]"


def test_scrub_when_name_tokens_blank_or_one_char_then_ignored() -> None:
    assert scrub_text("a b c", person_names=["", "  ", "A"]) == "a b c"


def test_scrub_module_docstring_when_read_then_states_best_effort_limits() -> None:
    doc = (scrub.__doc__ or "").lower()
    assert "best-effort" in doc
    assert "cannot" in doc and "location" in doc and "relatives" in doc


def test_scrub_events_when_one_row_fails_then_skipped_counted_and_others_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good, bad = uuid.uuid4(), uuid.uuid4()
    real = scrub.scrub_text

    def flaky(text: str, **kwargs: Any) -> str:
        if "BAD" in text:
            raise ScrubFailedError("nope")
        return real(text, **kwargs)

    monkeypatch.setattr(scrub, "scrub_text", flaky)
    batch = scrub_events(
        [
            ScrubInput(good, "hi a@b.co", "reply 0812345678901", ("Ann",), None),
            ScrubInput(bad, "BAD", "x", (), None),
        ]
    )
    assert [r.event_id for r in batch.scrubbed] == [good]
    assert batch.scrubbed[0].prompt_text == "hi [EMAIL]"
    assert batch.scrubbed[0].response_text == "reply [PHONE]"
    assert batch.skipped_scrub_failed_count == 1


def test_scrub_events_when_prompt_is_none_then_prompt_stays_none() -> None:
    batch = scrub_events([ScrubInput(uuid.uuid4(), None, "ok", (), None)])
    assert batch.scrubbed[0].prompt_text is None
    assert batch.skipped_scrub_failed_count == 0
