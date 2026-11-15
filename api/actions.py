"""The only action strings this system may ever emit.

The concept deck (slide 5) recommends fluid loads, salt, potassium citrate, low-glycemic
rations, blue-light therapy and LBNP. Those are treatment instructions. This prototype has
no clinical validation and must not issue them, so they are removed. See
docs/SAFETY_ISSUES.md S5. `tests_api/test_actions.py` asserts nothing else can escape.
"""

from __future__ import annotations

REPEAT_MEASUREMENT = "Repeat measurement"
REST_AND_RECHECK = "Rest and recheck"
CHECK_SENSOR = "Check sensor"
CONTACT_FLIGHT_SURGEON = "Contact flight surgeon"

ALLOWED_ACTIONS: tuple[str, ...] = (
    REPEAT_MEASUREMENT,
    REST_AND_RECHECK,
    CHECK_SENSOR,
    CONTACT_FLIGHT_SURGEON,
)

# Substrings that would indicate treatment advice leaking back in from the deck.
FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "fluid load", "salt", "potassium", "citrate", "drink", "ml water", "ration",
    "medication", "dose", "mg ", "insulin", "led", "light therapy", "lbnp", "scrubber",
)


def allowed(text: str) -> str:
    """Return the text only if it is on the allow-list; otherwise raise."""
    if text not in ALLOWED_ACTIONS:
        raise ValueError(f"Action {text!r} is not on the allow-list {ALLOWED_ACTIONS}")
    return text


def actions_for(*texts: str) -> list[str]:
    """Deduplicated, allow-listed, stably ordered action list."""
    seen: list[str] = []
    for text in texts:
        checked = allowed(text)
        if checked not in seen:
            seen.append(checked)
    return seen
