# PRODUCT SURFACES

**Status:** drafting · **Tier:** 1 (requirements) · **Content:** authored from owner decisions D3, D6

Four surfaces, built in order. This document fixes **what each owns** so that capability does not
get duplicated into three places and then drift apart.

---

## 1. The rule that governs all of them

**No surface owns logic.** Every surface calls the same application services and renders the result.
A rule that exists in the web panel but not the CLI is a defect, not a feature.

This follows from the layer contract (`DEPENDENCY_LAW.md`): `presentation` sits at the top and may
import everything below it, but nothing imports `presentation`. If a surface needs behaviour that
does not exist below it, the behaviour belongs below it.

## 2. Build order (D3)

```
CLI + reports  →  web admin panel  →  Telegram approvals + Firebase push
```

CLI first is not a placeholder. It is the surface the v1 finish line is written against, and it stays
the complete one afterwards.

## 3. What each surface owns

### 3.1 CLI + reports — the complete surface

**Owns:** every capability. Anything the system can do is doable here.

| | |
|---|---|
| Runs | daily scan, universe rebuild, backtest, walk-forward, statistics, weekly review |
| Outputs | dated HTML/PDF reports, the journal, run manifests |
| Reads | everything |
| Writes | everything |

**Requirement:** the v1 finish line is satisfied by this surface alone. If the web panel never
ships, the system is still complete.

### 3.2 Web admin panel — read, inspect, and edit parameters

**Owns:** interactive inspection, and **parameter editing** (D5).

| | |
|---|---|
| Reads | reports, charts, candidates, journal, statistics, component and parameter registries |
| Writes | **parameter values only** |
| Never | runs a decision the CLI cannot run; holds a rule the CLI lacks |

Editing a parameter is not a form submission. Per `PARAMETER_REGISTRY.md` §6 it must:

1. increment the owning component's version;
2. reset that component's validation status;
3. record old value, new value, date and reason;
4. show which strategy cards consume it and are therefore affected.

A UI that changes a threshold without doing all four is a defect — it would let a value change
quietly, which is the one thing the registry exists to prevent.

`ui_editable: false` parameters (`regime.classifier_rule`, `stats.sharpe_convention`,
`exit.ma_cross_semantics`, and the other rule-shaped entries) are **displayed but not editable
here**. They require a spec change and a pre-registration.

### 3.3 Telegram — approval of open-position actions (D6)

**Owns:** the human-judgment loop for actions on open positions — stop moves and partial exits.

Each prompt carries exactly what §3.8 of the production rules requires:

| Element | Why |
|---|---|
| the observation shown to the reviewer | "The record must identify the observation shown to the reviewer" |
| the **bounded** set of choices | "the bounded choice available" |
| the rule that produced the proposal | so an override is visibly an override |
| a required reason on the response | "the decision made, and the reason" |

**Explicitly not** a free-text command channel. A free-text action with no bounded choice set is
non-compliant with the course's human-judgment rule, and it would also be an unlogged decision path.

**Never** places an order (D1, BR-1). The approval records an intent; the human executes at the
broker and reports the fill.

### 3.4 Firebase — push notification only (D4)

**Owns:** getting the owner's attention. Nothing else.

| | |
|---|---|
| Carries | a title, a short body, and a reference id |
| Never carries | market data, journal contents, positions, or decisions |
| Never stores | anything — no data leaves the machine |

~~The notification says *"the daily run finished, 3 candidates"* or *"stop-move proposal pending"*.~~
The content lives locally and is read on a surface that authenticates.

**Corrected 2026-08-16 (`DR-011`), struck through rather than deleted.** The example contradicted
the row directly above it: *"3 candidates"* is a count derived from market data and a summary of
decisions, both of which "Never carries" forbids. Left in place it was a standing instruction to
reintroduce exactly what the rule bans. **The notice carries a terminal status and the run's
reference id** — *"run complete — run-20260817T183001Z-a1b2c3d4"*. Nothing that can be acted on
without opening the report, which is where provenance, validation status and the Untested banner
live.

**Transport, same date, same record.** The push role for *daily run complete* is filled by a
**local desktop notification**, not Firebase — which remains specified here and unbuilt. That
satisfies "no data leaves the machine" by construction rather than by a third party's policy;
`DR-011` §3 carries the comparison. Telegram is **not** used for this event and its column below
is unchanged.

## 4. Notification matrix

| Event | CLI | Report | Telegram | Push |
|---|---|---|---|---|
| Daily run complete | ✓ | ✓ | — | ✓ |
| `Trade` candidate | ✓ | ✓ | — | ✓ |
| Open-position action proposed | ✓ | ✓ | **✓ (approval)** | ✓ |
| `Pause` raised (system-wide) | ✓ | ✓ | ✓ | ✓ |
| Data conflict / staleness | ✓ | ✓ | — | ✓ |
| Weekly review ready | ✓ | ✓ | — | ✓ |
| Parameter changed via UI | ✓ (log) | — | — | — |

`Pause` reaches every surface because it blocks all new decisions and the owner needs to know
immediately.

## 5. What no surface may do

- Place, modify or cancel an order.
- Display a number without its component, provenance and validation status available (BR-8).
- Present an `assumed` parameter's output as a measurement.
- Accept a decision without a reason.
- Show USA and Canada merged in a single regime, index or currency view (BR-9).

## 6. Open items

- [ ] Web authentication. Local-only binding may be sufficient for a single-user tool on one
      machine; if the panel is ever reachable off-host that assumption fails and it needs real auth.
      Decide before the panel ships, not after.
- [ ] Whether the report is HTML, PDF, or HTML with PDF export. The course requires chart capture as
      a decision artifact (`FAIL_CLOSED_POLICY.md` §5), which argues for something archivable.
- [ ] Telegram identity binding — one chat id, verified once, rejecting all others. A stop-move
      approval arriving from an unknown chat must be refused, not acted on.
