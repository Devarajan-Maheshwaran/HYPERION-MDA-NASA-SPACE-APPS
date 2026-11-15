"""Store-and-forward flight-surgeon outbox with delay/blackout release (P0-5).

Packet lifecycle (persisted in SQLite):

    QUEUED_BLACKOUT --(link restored)--> IN_TRANSIT --(delay elapsed)--> DELIVERED
                                     --(surgeon acknowledges)--> ACKNOWLEDGED

The comms delays below are DEMO timers so the loop is observable in a live presentation.
The real one-way light times they stand in for are printed alongside them and are never
claimed to be simulated accurately. No mission network, NASA ION-DTN or agency link exists.

Acknowledgement receipts are hashed into the audit chain. The chain receives the receipt
digest only — never the directive text and never a measurement.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

QUEUED_BLACKOUT = "QUEUED_BLACKOUT"
IN_TRANSIT = "IN_TRANSIT"
DELIVERED = "DELIVERED"
ACKNOWLEDGED = "ACKNOWLEDGED"

COMMS_STATES: tuple[str, ...] = (QUEUED_BLACKOUT, IN_TRANSIT, DELIVERED, ACKNOWLEDGED)

# Letters-only alphabet: packet/receipt ids can never contain a digit run that a
# measurement-leak test could mistake for a leaked clinical value.
_ID_ALPHABET = "abcdefghijkmnpqrstuvwxyz"


def new_id(prefix: str) -> str:
    return f"{prefix}-" + "".join(secrets.choice(_ID_ALPHABET) for _ in range(16))


def digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CommsProfile:
    habitat: str
    label: str
    delay_s: float
    real_world_note: str
    blackout: bool = False


# Demo timers. `real_world_note` keeps the presentation honest about what is compressed.
COMMS_PROFILES: dict[str, CommsProfile] = {
    "station": CommsProfile("station", "ISS Station (0.2 s demo)", 0.2,
                            "Low Earth orbit relay: near-real-time in reality; 0.2 s demo timer."),
    "lunar": CommsProfile("lunar", "Lunar Base (1.3 s demo)", 1.3,
                          "Earth-Moon one-way light time is about 1.3 s; used directly as the demo timer."),
    "transit": CommsProfile("transit", "Mars Transit (12 s demo / 20 min scale)", 12.0,
                            "Stands in for a one-way Mars delay of minutes (deck says 20 min, concept text 14 min;"
                            " neither is sourced here). Compressed to a 12 s demo timer."),
    "rover": CommsProfile("rover", "Surface Rover (blackout queue)", 5.0,
                          "EVA terrain blackout: packets queue until the operator restores the link.",
                          blackout=True),
}


def profile_for(habitat: str) -> CommsProfile:
    return COMMS_PROFILES.get(habitat, COMMS_PROFILES["station"])


def build_sbar(*, organ: str, finding: str, frame: dict[str, Any] | None,
               organs: list[dict[str, Any]], triage: dict[str, Any],
               habitat_label: str, lane: str) -> dict[str, str]:
    """SBAR alert packet. Demo content: observations and allow-listed actions only.

    No treatment instruction is generated. 'Recommendation' restates the allow-listed
    action strings the gate already produced.
    """
    hr = (frame or {}).get("hr_bpm")
    gates = (frame or {}).get("gates", []) or []
    verdicts = "; ".join(f"G{g.get('gate')}={g.get('outcome')}" for g in gates) or "no gate verdict"
    abnormal = [f"{o.get('label')}: {o.get('status')} ({o.get('indicator')})"
                for o in organs if o.get("status") in {"ALERT", "WATCH", "UNKNOWN"}]
    actions = ", ".join(triage.get("actions", [])) or "Repeat measurement"
    return {
        "situation": f"{organ} — {finding}",
        "background": (f"Habitat {habitat_label}. Data lane {lane}. "
                       f"Mission t={float((frame or {}).get('t_s', 0.0)):.0f}s. "
                       f"Raw HR {'unavailable' if hr is None else f'{hr:.0f} bpm'}."),
        "assessment": (f"Deterministic gate verdicts: {verdicts}. "
                       + ("Findings: " + "; ".join(abnormal) if abnormal else "No organ finding listed.")
                       + " Demo rules only; not a validated clinical assessment."),
        "recommendation": f"Allow-listed demo actions: {actions}. Flight-surgeon review requested.",
    }


def enqueue(*, case_id: str, organ: str, finding: str, fingerprint: str, habitat: str,
            sbar: dict[str, str], now_iso: str, now_epoch: float | None = None,
            blackout_override: bool | None = None) -> dict[str, Any]:
    """Create a packet in the correct initial comms state."""
    now_epoch = time.time() if now_epoch is None else now_epoch
    profile = profile_for(habitat)
    blackout = profile.blackout if blackout_override is None else blackout_override
    state = QUEUED_BLACKOUT if blackout else IN_TRANSIT
    return {
        "packet_id": new_id("pkt"), "case_id": case_id, "created_at": now_iso,
        "organ": organ, "finding": finding, "fingerprint": fingerprint, "sbar": sbar,
        "comms_state": state, "habitat": habitat, "delay_s": profile.delay_s,
        "release_at_epoch_s": None if blackout else now_epoch + profile.delay_s,
        "delivered_at": None, "acknowledged_at": None, "receipt": None,
    }


def advance(packets: list[dict[str, Any]], *, now_epoch: float | None = None,
            now_iso: str, blackout: bool = False) -> list[dict[str, Any]]:
    """Move packets along the comms timeline. Returns the packets that changed.

    Pure with respect to the clock: pass `now_epoch` in tests for exact behaviour.
    """
    now_epoch = time.time() if now_epoch is None else now_epoch
    changed: list[dict[str, Any]] = []
    for packet in packets:
        state = packet["comms_state"]
        if state == ACKNOWLEDGED:
            continue
        if state == QUEUED_BLACKOUT:
            if not blackout:
                packet["comms_state"] = IN_TRANSIT
                packet["release_at_epoch_s"] = now_epoch + float(packet["delay_s"])
                changed.append({"packet_id": packet["packet_id"], "comms_state": IN_TRANSIT})
            continue
        if state == IN_TRANSIT:
            if blackout:
                packet["comms_state"] = QUEUED_BLACKOUT
                packet["release_at_epoch_s"] = None
                changed.append({"packet_id": packet["packet_id"], "comms_state": QUEUED_BLACKOUT})
                continue
            release = packet["release_at_epoch_s"]
            if release is not None and now_epoch >= float(release):
                packet["comms_state"] = DELIVERED
                packet["delivered_at"] = now_iso
                changed.append({"packet_id": packet["packet_id"], "comms_state": DELIVERED})
    return changed


def acknowledge_packet(packet: dict[str, Any], *, directive: str, role: str, now_iso: str) -> dict[str, Any]:
    """Attach a signed-shaped acknowledgement receipt. Requires a delivered packet."""
    if packet["comms_state"] != DELIVERED:
        raise ValueError(f"packet is {packet['comms_state']}; only {DELIVERED} packets can be acknowledged")
    receipt = {
        "receipt_id": new_id("rcpt"), "packet_id": packet["packet_id"], "role": role,
        "acknowledged_at": now_iso, "directive": directive,
    }
    receipt["sha256"] = digest({k: v for k, v in receipt.items() if k != "sha256"})
    packet["comms_state"] = ACKNOWLEDGED
    packet["acknowledged_at"] = now_iso
    packet["receipt"] = receipt
    return receipt


def countdown_s(packet: dict[str, Any], now_epoch: float | None = None) -> float | None:
    now_epoch = time.time() if now_epoch is None else now_epoch
    if packet["comms_state"] != IN_TRANSIT or packet["release_at_epoch_s"] is None:
        return None
    return max(0.0, round(float(packet["release_at_epoch_s"]) - now_epoch, 1))


def public_view(packets: list[dict[str, Any]], *, now_epoch: float | None = None) -> list[dict[str, Any]]:
    view = []
    for packet in packets:
        item = {k: v for k, v in packet.items() if k != "case_id"}
        item["countdown_s"] = countdown_s(packet, now_epoch)
        view.append(item)
    return view
