"""Demo organ rule table. NOT NASA-STD-3001 compliance. See docs/SAFETY_ISSUES.md S6.

The deck's numbers are shown as *the deck's claim*, labelled DEMO THRESHOLD. A stale or
missing input yields UNKNOWN / NOT_AVAILABLE, never NOMINAL. No neural risk head exists.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from .actions import (CHECK_SENSOR, CONTACT_FLIGHT_SURGEON, REPEAT_MEASUREMENT,
                      REST_AND_RECHECK, allowed)
from .models import ManualCheck, OrganReading

# Declared validity windows in hours. Demo values, not clinical intervals.
VALIDITY_HOURS = {
    "bp": 4.0, "glucose": 8.0, "temperature": 4.0, "sleep": 24.0,
    "mood": 24.0, "onsd": 72.0, "pvt": 12.0,
}
STALENESS_LAMBDA = 0.15  # tau = exp(-lambda * age_hours); demo decay constant

SYSTEMS = (
    ("head-eyes", "Head & Eyes", "0g fluid shift + cabin CO2 (SANS)", "onsd", "mm",
     "ONSD >= 5.8 mm (deck claim)", 5.8, "ge"),
    ("heart", "Heart & Vessels", "Gravity shift + radiation (CSA vascular)", "bp", "mmHg",
     "Rest BP >= 140/90 mmHg (deck claim)", 140.0, "ge"),
    ("chest-immune", "Chest & Immune", "Space radiation (CSA dosimetry)", "temperature", "degC",
     "Temp >= 38.0 degC (deck claim)", 38.0, "ge"),
    ("metabolic", "Metabolic & Gut", "0g insulin drift (CSA glycemic)", "glucose", "mg/dL",
     "Fasting glucose >= 126 mg/dL (deck claim)", 126.0, "ge"),
    ("bones", "Bones & Muscles", "0g unloading (CSA osteo/renal)", "sleep", "h",
     "Sleep < 4.5 h (deck claim, proxy indicator)", 4.5, "lt"),
    ("brain", "Brain & Sleep", "Isolation + circadian shift", "pvt", "ms",
     "PVT median > 350 ms (deck claim)", 350.0, "gt"),
)


def tau(age_hours: float) -> float:
    return math.exp(-STALENESS_LAMBDA * max(0.0, age_hours))


def age_hours(check: ManualCheck, now: datetime | None = None) -> float | None:
    if not check.recorded_at:
        return None
    try:
        recorded = datetime.fromisoformat(check.recorded_at)
    except ValueError:
        return None
    if recorded.tzinfo is None:
        recorded = recorded.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - recorded).total_seconds() / 3600.0)


def latest_by_kind(checks: list[ManualCheck]) -> dict[str, ManualCheck]:
    out: dict[str, ManualCheck] = {}
    for check in sorted(checks, key=lambda c: c.recorded_at):
        out[check.kind] = check
    return out


def _value_of(check: ManualCheck) -> float | None:
    if check.kind == "bp":
        return check.systolic
    return check.value


def organ_readings(checks: list[ManualCheck], now: datetime | None = None,
                   context: dict | None = None) -> list[OrganReading]:
    """Demo rule table. ``context`` adds the workstation's labelled SIMULATED reference
    channels (CO2, proton dose, water, ARED) and the current gate-compensated HR. Without
    context the original single-indicator behaviour is preserved for the existing tests.
    """
    latest = latest_by_kind(checks)
    readings: list[OrganReading] = []
    for system, label, hazard, kind, unit, threshold_text, limit, op in SYSTEMS:
        check = latest.get(kind)
        if check is None:
            readings.append(OrganReading(
                system=system, label=label, status="NOT_AVAILABLE",
                indicator=f"No {kind} check logged", unit=unit, demo_threshold=threshold_text,
                hazard=hazard, action=allowed(REPEAT_MEASUREMENT),
                evidence="Not available — no crew entry for this indicator.",
            ))
            continue
        age = age_hours(check, now)
        value = _value_of(check)
        t = tau(age) if age is not None else None
        validity = VALIDITY_HOURS.get(kind, 4.0)
        if value is None or age is None:
            readings.append(OrganReading(
                system=system, label=label, status="UNKNOWN", indicator="Incomplete entry",
                unit=unit, demo_threshold=threshold_text, hazard=hazard, staleness_tau=t,
                age_hours=age, action=allowed(REPEAT_MEASUREMENT),
                evidence="Entry missing a value or a timestamp; not scored.",
            ))
            continue
        if age > validity:
            readings.append(OrganReading(
                system=system, label=label, status="UNKNOWN",
                indicator=f"{kind} is stale", value=value, unit=unit,
                demo_threshold=threshold_text, hazard=hazard, staleness_tau=t, age_hours=age,
                action=allowed(REPEAT_MEASUREMENT),
                evidence=(f"Last {kind} is {age:.1f} h old (validity {validity:g} h). "
                          "Stale input is UNKNOWN, never nominal."),
            ))
            continue
        breached = (value >= limit) if op == "ge" else (value > limit if op == "gt" else value < limit)
        if kind == "temperature":
            # A normal 36.8 degC core temperature is not "near" a 38 degC demo fever rule.
            near = 37.5 <= value < limit
        else:
            near = (value >= 0.9 * limit) if op in {"ge", "gt"} else (value <= 1.1 * limit)
        status = "ALERT" if breached else ("WATCH" if near else "NOMINAL")
        action = (CONTACT_FLIGHT_SURGEON if breached
                  else REST_AND_RECHECK if near else REPEAT_MEASUREMENT)
        shown = f"{check.systolic:.0f}/{check.diastolic:.0f}" if check.kind == "bp" and check.diastolic else f"{value:g}"
        readings.append(OrganReading(
            system=system, label=label, status=status, indicator=f"{kind} = {shown} {unit}",
            value=value, unit=unit, demo_threshold=threshold_text, hazard=hazard,
            staleness_tau=t, age_hours=age, action=allowed(action),
            evidence=(f"Crew-entered {kind}, {age:.1f} h old, tau={t:.2f}. "
                      "Compared with a DEMO threshold, not a validated limit."),
        ))
    if context:
        readings = _apply_workstation_context(readings, latest, context, now)
    return readings


def _apply_workstation_context(readings: list[OrganReading], latest: dict[str, ManualCheck],
                               context: dict, now: datetime | None) -> list[OrganReading]:
    """Multi-signal demo rules from the cockpit directive. Every added channel is labelled.
    Never turns UNKNOWN/NOT_AVAILABLE green; a simulated reference channel can raise WATCH/
    ALERT but is explicitly marked SIMULATED in the evidence."""
    by_system = {r.system: r for r in readings}

    def bump(system: str, status: str, indicator: str, evidence: str,
             threshold: str, value: float | None = None, unit: str = "") -> None:
        r = by_system[system]
        rank = {"NOMINAL": 0, "WATCH": 1, "ALERT": 2, "UNKNOWN": 1, "NOT_AVAILABLE": 0}
        # UNKNOWN/NOT_AVAILABLE must not be silently upgraded to NOMINAL by a sim channel.
        if r.status in {"UNKNOWN", "NOT_AVAILABLE"} and status == "NOMINAL":
            return
        if rank.get(status, 0) >= rank.get(r.status, 0):
            r.status = status  # type: ignore[assignment]
            r.indicator = indicator
            r.evidence = evidence
            r.demo_threshold = threshold
            if value is not None:
                r.value = value
                r.unit = unit
            r.action = allowed(CONTACT_FLIGHT_SURGEON if status == "ALERT"
                               else REST_AND_RECHECK if status == "WATCH" else REPEAT_MEASUREMENT)

    co2 = context.get("co2_mmhg")
    if co2 is not None and co2 >= 4.0:
        bump("head-eyes", "ALERT", f"Cabin CO2 = {co2:g} mmHg (SIMULATED)",
             "SIMULATED cabin CO2 reference channel crossed the demo eye/CO2 rule. "
             "Not a measured cabin sensor.", "ONSD >= 5.8 mm OR CO2 >= 4.0 mmHg (deck claim)",
             float(co2), "mmHg")
    proton = context.get("proton_mgy_day")
    if proton is not None and proton > 2.0:
        bump("chest-immune", "ALERT", f"Proton dose = {proton:g} mGy/day (SIMULATED)",
             "SIMULATED radiation reference channel crossed the demo chest/immune rule. "
             "GOES flux is not converted to dose here.", "Temp >= 38 degC OR proton > 2 mGy/day (deck claim)",
             float(proton), "mGy/day")
    hr = context.get("hr_bpm")
    if hr is not None and hr > 115:
        compensated = bool(context.get("hr_suppressed"))
        status = "WATCH" if compensated else "ALERT"
        bump("heart", status, f"HR = {hr:g} bpm" + (" (exercise-compensated)" if compensated else ""),
             "Gate 2 explained this rate by activity; shown as WATCH, not a false alarm."
             if compensated else "Raw HR crossed the demo heart rule and was not exercise-compensated.",
             "BP >= 140/90 mmHg OR HR > 115 bpm (deck claim)", float(hr), "bpm")
    bp = latest.get("bp")
    if bp is not None and bp.diastolic is not None and bp.diastolic >= 90:
        age = age_hours(bp, now)
        if age is not None and age <= VALIDITY_HOURS["bp"]:
            bump("heart", "ALERT", f"BP = {bp.systolic:g}/{bp.diastolic:g} mmHg",
                 "Crew-entered diastolic pressure crossed the demo BP rule.",
                 "BP >= 140/90 mmHg OR HR > 115 bpm (deck claim)", bp.systolic, "mmHg")
    glucose = latest.get("glucose")
    if glucose is not None and glucose.value is not None:
        age = age_hours(glucose, now)
        if age is not None and age <= VALIDITY_HOURS["glucose"] and 100 <= glucose.value < 126:
            bump("metabolic", "WATCH", f"Glucose = {glucose.value:g} mg/dL",
                 "Crew-entered glucose is in the demo impaired-fasting band (100–125 mg/dL).",
                 "Glucose 100–125 WATCH / >=126 ALERT (deck claim)", glucose.value, "mg/dL")
    water = context.get("water_ml")
    ared = context.get("ared_min")
    if water is not None or ared is not None:
        # In the unified cockpit, Bones & Muscles is driven by the countermeasure log,
        # not by the sleep proxy. Sleep belongs to Brain & Sleep.
        r = by_system["bones"]
        low = (water is not None and water < 1400) or (ared is not None and ared < 20)
        r.status = "WATCH" if low else "NOMINAL"  # type: ignore[assignment]
        parts = []
        if water is not None:
            parts.append(f"water {water:g} mL")
        if ared is not None:
            parts.append(f"ARED {ared:g} min")
        r.indicator = " / ".join(parts) + " (crew log)"
        r.value = float(water if water is not None else ared)
        r.unit = "mL" if water is not None else "min"
        r.demo_threshold = "ARED < 20 min OR water < 1400 mL (deck claim)"
        r.evidence = "Crew-entered countermeasure log compared with DEMO references; not treatment advice."
        r.action = allowed(REST_AND_RECHECK if low else REPEAT_MEASUREMENT)
    sleep = latest.get("sleep")
    if sleep is not None and sleep.value is not None:
        age = age_hours(sleep, now)
        if age is not None and age <= VALIDITY_HOURS["sleep"] and sleep.value < 4.5:
            bump("brain", "ALERT", f"Sleep = {sleep.value:g} h",
                 "Crew-entered sleep is below the demo brain/circadian rule.",
                 "Sleep < 4.5 h OR PVT > 350 ms (deck claim)", sleep.value, "h")
    return readings


def min_tau(checks: list[ManualCheck], now: datetime | None = None) -> float | None:
    ages = [age_hours(c, now) for c in latest_by_kind(checks).values()]
    known = [a for a in ages if a is not None]
    return min(tau(a) for a in known) if known else None


def any_stale(checks: list[ManualCheck], now: datetime | None = None) -> bool:
    for check in latest_by_kind(checks).values():
        age = age_hours(check, now)
        if age is None or age > VALIDITY_HOURS.get(check.kind, 4.0):
            return True
    return False


def readiness_streak(checks: list[ManualCheck], now: datetime | None = None) -> dict:
    """Gamified check streak. No clinical meaning whatsoever."""
    now = now or datetime.now(timezone.utc)
    days = set()
    for check in checks:
        age = age_hours(check, now)
        if age is not None:
            days.add((now - timedelta(hours=age)).date().isoformat())
    ordered = sorted(days, reverse=True)
    streak = 0
    cursor = now.date()
    for _ in range(365):
        if cursor.isoformat() in days:
            streak += 1
            cursor = cursor - timedelta(days=1)
        else:
            break
    return {"streak_days": streak, "days_logged": len(ordered),
            "note": "Engagement counter only. No clinical or readiness meaning."}
