# Phase 0 — API + React workstation design (spec B)

**Status: design record.** The user directed "build the remaining project asap, go with B", so this
document is delivered *with* the implementation rather than as a blocking approval gate. Open
decisions are listed in §7 with the choice taken and how to reverse it.

Reference: `HYPERION_MDA.pdf` (NASA Space Apps 2026, Challenge 4). The deck is a **concept**, not a
specification of tested behaviour. `docs/REQUIREMENTS-TRACEABILITY.md` already maps every deck claim
to what exists. This build implements the *workstation shell, deterministic gates and honest data
lanes*; it does **not** implement the deck's neural risk heads, Flower/Opacus training, or on-chain
ledger, and it does not adopt the deck's clinical thresholds as validated.

---

## 1. Layering rule (hard constraint)

```
web/ (React)  ──HTTP──►  api/ (FastAPI composition layer)
                              │  imports read-only
                              ▼
        src/hyperion_mda/  ← existing lanes, UNCHANGED
        ├── NASA lab:   osdr_source → osdr_cmp → engine
        ├── SIMULATED:  sim_wearable → adapters
        ├── RECORDED:   physionet_source → wfdb_reader → physionet_adapter
        ├── FL toy:     fl_sim
        └── registry:   signal_registry
```

- No lane imports another lane. No lane imports `api`. Existing `tests/test_demo_lanes.py`
  lane-separation assertions must stay green.
- `api/` lives **outside** `src/hyperion_mda/` so `pyproject.toml` package-data and
  `tests/test_packaging.py` are untouched.
- Nothing in `src/`, `tests/` or `experiments/` is modified by this work.

## 2. Route map

### HTTP API (`/api`)

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/api/health` | any | Liveness, version, which lanes are available |
| GET | `/api/session` | any | Current role, subject, habitat, lane, calibration state |
| POST | `/api/session` | any | Switch role / subject / habitat / lane (demo-grade auth) |
| GET | `/api/lanes` | any | Lane availability + provenance, never fabricated |
| GET | `/api/registry` | any | 49 channels from `signal_registry`, value-free |
| GET | `/api/subjects` | any | Demo subjects and their calibration status |
| GET | `/api/organs` | crew, surgeon | 6-system demo rule table status for the active subject |
| GET | `/api/scenarios` | any | Scenario catalogue (deterministic, labelled) |
| POST | `/api/scenarios/{id}/start` | ops, crew | Start a scenario stream |
| POST | `/api/stream/stop` | ops, crew | Stop the active stream |
| GET | `/api/stream/state` | any | Latest frame + gate verdicts (poll fallback) |
| GET | `/api/stream/events` | any | SSE live frames |
| POST | `/api/calibration/{subject}` | ops | Compute per-person rest calibration from a labelled window |
| DELETE | `/api/calibration/{subject}` | ops | Revert to uncalibrated (gates return UNKNOWN) |
| POST | `/api/manual` | crew, surgeon | Log a manual check (BP, glucose, temp, sleep, mood, ONSD) |
| GET | `/api/manual/{subject}` | crew, surgeon | Manual history + staleness τ per check |
| POST | `/api/pvt` | crew | Submit a 15 s reaction-test result |
| GET | `/api/alerts` | surgeon, ops | Active alerts + holds |
| POST | `/api/alerts/{id}/ack` | surgeon | Acknowledge with a note (audited) |
| GET | `/api/audit` | surgeon, ops, researcher | Hash-chain audit entries |
| GET | `/api/audit/verify` | any | Re-verify the SHA-256 chain |
| GET | `/api/research/m6` | researcher, surgeon | Read-only committed M6 results |
| GET | `/api/lab/osd575` | surgeon, researcher | Verified NASA lab rows, or `Not available` |

### Frontend routes

| Path | Role | View |
|---|---|---|
| `/` | any | Redirect to the role's home |
| `/crew` | crew | Body map, live vitals, gate badges, readiness shield |
| `/crew/checks` | crew | Manual entry + PVT reaction test |
| `/surgeon` | flight-surgeon | Alert queue, subject tiles, acknowledge |
| `/ops` | ops | Lane health, scenario runner, calibration, sensor quality |
| `/research` | researcher | M6 results, registry, provenance, audit chain |

## 3. API contract (shapes)

Every response carries `lane`, `provenance` and `generated_at`. Every measurement carries
`status ∈ {OK, UNKNOWN, NOT_AVAILABLE, STALE, FAILED}`. **`UNKNOWN` is never rendered green.**

```ts
Frame {
  t_s: number; lane: Lane; subject_id: string; habitat: Habitat;
  hr_bpm: number | null; activity_norm: number | null;   // dimensionless, per-person
  sqi: { kurtosis: number|null; slew: number|null; calibrated: boolean };
  gates: { g1: GateVerdict; g2: GateVerdict; g3: GateVerdict };
  residual_bpm: number | null; conformal_upper: number | null;
  state: WorkflowState; suppressed: boolean; suppression_reason: string | null;
  non_rate_flags: string[];                             // never suppressed
}
GateVerdict { gate: 1|2|3; outcome: "PASS"|"BLOCK"|"HOLD"|"UNKNOWN";
              reason: string; evidence: Record<string, number|string|boolean|null> }
WorkflowState = "NOMINAL"|"SENSOR_ISSUE"|"CONTEXT_COMPENSATED"|"CREW_CHECK"|"SURGEON_ALERT"|"UNKNOWN"
```

Full field-level contract: `docs/API-CONTRACT.md` (generated from the Pydantic models).

## 4. Component tree

```
<App>  RoleProvider · SessionProvider · StreamProvider(SSE)
 └ <AppShell>            persistent LaneBadge + disclaimer footer + role switcher
    ├ <CrewConsole>
    │   ├ <BodyMap> (6 clickable systems, status chips, UNKNOWN≠green)
    │   ├ <VitalsChart> (Recharts: raw HR, exercise-adjusted residual, conformal band)
    │   ├ <GateBadges> (G1/G2/G3 live verdict + evidence popover)
    │   ├ <ActionCard> (allowed action text only)
    │   └ <ReadinessShield> (check streak, no clinical meaning)
    ├ <CrewChecks>  <ManualEntryForm/> <PVTTest/> <StalenessTable/>
    ├ <SurgeonQueue> <AlertList/> <SubjectTiles/> <AckDialog/>
    ├ <OpsConsole>  <LaneHealth/> <ScenarioRunner/> <CalibrationPanel/> <AuditTable/>
    └ <ResearchView> <M6Results/> <RegistryTable/> <ProvenancePanel/>
```

UI primitives are shadcn-style local components (`web/src/components/ui/*`): `button`, `card`,
`badge`, `tabs`, `dialog`, `table`, `input`, `select`, `toast`. No runtime UI-kit dependency.

## 5. Scenario design (deterministic, never tuned to make gates pass)

| ID | Purpose | Expected honest outcome |
|---|---|---|
| `rest-nominal` | Quiet baseline | NOMINAL when calibrated; UNKNOWN when not |
| `exercise-false-alarm` | HR≈148 with high activity | G2 BLOCKs the rate alarm **only** if calibrated and below the hard ceiling |
| `exercise-with-arrhythmia` | Same + irregular-rhythm flag | **Never suppressed** — non-rate flag passes through |
| `sensor-artifact` | Spike/slew corruption | G1 quarantines → SENSOR_ISSUE, "Check sensor" |
| `true-rest-tachycardia` | High HR, low activity | SURGEON_ALERT |
| `hard-ceiling` | HR above hard ceiling during exercise | Alert regardless of activity |
| `hold-timeout` | Suppression persists past the hold limit | Escalates to SURGEON_ALERT |
| `stale-manual` | Old manual exam drives risk | G3 HOLD → CREW_CHECK, not a ground alarm |
| `uncalibrated` | No per-person calibration | All gates UNKNOWN, nothing green |

Scenarios are generated from fixed formulas, labelled `SIMULATED` or `INJECTED`. They are
**not** astronaut data and are never written into the NASA lane.

## 6. Test plan

- **Python** (`tests_api/`, stdlib `unittest` + FastAPI `TestClient`): contract shapes; role
  guards; gate truth table (incl. every safety invariant); calibration required; hash-chain
  tamper detection; scenario determinism; lane separation still holds; no clinical advice strings.
- **Existing suites**: `tests/` and `experiments/m6/tests/` must stay green, unchanged.
- **Web**: `tsc --noEmit` strict, `vite build`, Vitest unit tests for status colour mapping
  (UNKNOWN never green), staleness maths, and action-text allow-list.
- **Smoke**: a script that boots the API, drives a scenario end-to-end over HTTP, and asserts the
  SSE stream, a gate block, an alert, an ack and a verified audit chain.

## 7. Open decisions (choice taken; how to reverse)

1. **Gate-1 threshold** — ships **uncalibrated**. No default kurtosis cutoff. Reverse only with a
   documented calibration study; see `docs/SAFETY_ISSUES.md`.
2. **Activity measure** — per-person scale-normalised (dimensionless), **not** ENMO in g. The
   PhysioNet accelerometer is uncalibrated, so a g-based cutoff would be invented.
3. **Organ thresholds** — demo rule table, labelled `DEMO`. Not NASA-STD-3001 compliance.
4. **Action text** — allow-list of four strings. The deck's fluid/salt/medication advice is
   **removed**; it is treatment advice and out of scope.
5. **Audit** — local SHA-256 hash chain, **not** a blockchain. No Solidity, no web3.
6. **Auth** — demo-grade role switcher, no passwords. Documented as such in the UI and README.
7. **Neural/FL/DP** — not implemented. M6 results are shown read-only as the real measured evidence.
