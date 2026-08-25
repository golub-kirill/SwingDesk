# UX TASK FLOWS

**Status:** drafting · **Tier:** 7 (UI/UX) · **Content:** `verbatim` + measured against the code

<!-- verbatim-sources: Appendix_T_Professionalnyi_chek_list_treidera_v2.0.pdf -->

**This document does not transcribe Appendix T.** `CHECKLIST_SPEC.md` §4 already does, all 34 items
across 6 phases, and they are parsed into `registry/checklists.yml`. Re-copying them here would be a
third hand-copy of text gate 2 exists to keep singular.

What this adds is the map the transcription cannot: **for each phase of the operator's cadence, what
the system does today, and on which surface.** That map is mostly empty, and the point of writing it
is to show where.

The standard the cadence serves, from Appendix T's opening:

```verbatim
Итоговый стандарт. Торговая система считается профессиональной не потому, что она сложная, а потому, что она полная, измеримая, проверяемая, ограничивает риск и способна ответить «не торговать».
```

Complete, measurable, verifiable, risk-limiting, and **able to answer "do not trade"** — not
complex. Every gap below is measured against that, not against a feature list.

---

## 1. Coverage, as a number

| Phase | Items | Served today | By what |
|---|---|---|---|
| `До недели` — weekend prep | 6 | **1** | `tools/fetch_directory.py`, `tools/refresh_universe.py` |
| `До сессии` — session prep | 6 | **3** | `swingdesk scan` |
| `Перед ордером` — before the order | 6 | **3** | the pre-trade checklist (Appendix E) |
| `Во время позиции` — while held | 5 | **3** | `trade_management.manage`, the position store |
| `После сделки` — after the trade | 6 | **0** | nothing — see §3 |
| `Аварийный контроль` — emergency | 5 | **1** | `docs/runbooks/` |
| **Total** | **34** | **11** | |

**11 of 34.** The number is meant to be read the same way the checklist's 5-of-18 is: a gap in the
system, stated rather than implied.

## 2. The cadence, and where the system sits in it

### `До недели` — the weekend pass

This is the phase the tiered universe refresh serves, and the match is not a coincidence: the
fetch budget forced a weekly/daily split (`ROADMAP.md` §4) and Appendix T had already made one.

| Item | State |
|---|---|
| data and broker reconciled | **half.** The data half is `fetch_directory` + `refresh_universe`. There is no broker integration and there will not be one — D1 makes this decision support, and §4 explains why the *reconciliation* still matters |
| USA/Canada regime determined | **no.** The classifier exists (M30-T0450) and is not wired into the run; and Canada cannot be enumerated at all (`DR-003` gap 1), so the phrase's two halves fail for different reasons |
| sector map, commodities, CADUSD | **no.** `Instrument.sector` is `None` — no free point-in-time sector source is in hand. No FX series |
| open positions and events updated | **half.** Positions: yes, read as-of. Events: no source at all (`EVENT_SPEC.md`) |
| weekly watchlist and risk budget | **half.** The universe selection is the watchlist; the risk budget needs `risk.max_open_risk` and friends, and `DR-006` ratified them on 2026-08-22 — the budget is now computed and enforced (`trade_management/portfolio.py`), while the *weekly* cadence the course asks for is still not a thing this system has |
| no-trade scenarios recorded | **no** |

### `До сессии` — the daily run

The best-served phase, because it is what `swingdesk scan` *is*.

| Item | State |
|---|---|
| overnight / futures / news checked | **no source** |
| **open positions and gaps checked first** | **yes**, and the run records its own step order rather than asserting it (`RunResult.positions_ran_first`) |
| Daily Priority 1 limited | **no.** The course states a limit exists and gives no number. `--limit` caps the universe but that is a *ranking*, not a priority list |
| entry/exit plans and sizes recomputed | **yes** — recomputed every run, never carried forward (E13) |
| alerts set | **no surface.** Telegram is D3 and deliberately later |
| no-trade condition saved | **yes** — `Skip`/`Pause` with a reason code, and the journal counts uncoded refusals |

### `Перед ордером` — the pre-trade checklist

Served by Appendix E, and its coverage is already reported per candidate: **5 of 18** machine-
answerable. `Price не Late` maps to E08, which is `unavailable` because the run has no trigger and
no maximum entry — so "is this entry late?" is not computable, not merely unchecked.

### `Во время позиции` — while a position is held

| Item | State |
|---|---|
| stop is not widened | **yes** — enforced, not advised |
| adding only on a separate setup with a total-risk check | **no.** No add path exists |
| **No Action is permitted** | **yes** — `ActionKind.HOLD` is a recorded decision, not an absence of one. The course is explicit that doing nothing must be recordable, and an unrecordable non-action is under-reported by construction |
| management action has a rule and a timestamp | **yes** — append-only, `proposed_at`, monotonic sequence |
| event / sector / market changes monitored | **no** — same three missing sources as above |

### `После сделки` — after the trade

**Zero of six.** Fills, costs, screenshots, R/MFE/MAE/slippage, outcome vs decision quality, error
code and process score, version statistics — none of it exists live.

This is the largest single gap in the system and it is structural rather than incidental: every item
needs *executed* fills, and D1 means this system never executes. The trades happen in the owner's
broker, and nothing imports them back. `MFE`/`MAE`/`net_r` are computed in the backtest engine and
have no live counterpart.

### `Аварийный контроль` — emergency control

| Item | State |
|---|---|
| manual list of positions/stops/targets available | **no.** `FAIL_CLOSED_POLICY.md` row 2 requires a printable fallback that works with the system down. It does not exist |
| broker is the source of actual positions | **stated, not enforced** — see §4 |
| stale data or mismatch blocks new trades | **half.** Stale data blocks (fail-closed on deciding). Mismatch cannot be detected without the broker |
| critical violation activates Pause | **partially** — `Pause` exists as a decision state; nothing classifies a violation as critical |
| return only by recorded criteria | **yes** — the runbooks carry verbatim return conditions |

## 3. The two structural gaps

Everything above reduces to two, and both are consequences of decisions already taken rather than
things anyone forgot.

**No post-trade loop (D1).** The system proposes; the owner executes elsewhere; nothing comes back.
So the whole `После сделки` phase, and `Broker — источник фактических позиций`, are unreachable
without an import path the charter does not scope. Worth stating plainly: **this system cannot
measure its own live performance**, and no amount of UX work changes that.

**No event, sector or FX sources (D8/D10).** Six of the 34 items name one of these. All three are
sourcing problems on a free tier, not modelling ones.

## 4. What "broker reconciliation" still means here

Two Appendix T items name the broker as authoritative. It is tempting to mark them out of scope
because D1 forbids execution — but that is the wrong reading. **Authority over what is true and
authority over what to do are different things.** The broker knows the positions; this system knows
what it proposed. A mismatch means the journal is wrong about the world, and the journal must yield.

Today the position store is populated by hand, so the mismatch is undetectable rather than absent.
Recorded here so that a future manual reconciliation step is understood as *closing a known hole*
rather than adding a feature.

## 5. Surfaces

| Phase | Surface today | Surface intended |
|---|---|---|
| weekend prep | two CLI tools | web admin (D3) |
| session prep | `swingdesk scan` | web admin + Telegram push (D3) |
| before the order | printed checklist in the run report | web admin |
| while held | proposals in the run report | **Telegram approvals (D6)** — the owner answers, the system never acts |
| after the trade | — | — |
| emergency | `docs/runbooks/` | printable, must work with the system down |

The v1 surface is the CLI (`PRODUCT_SURFACES.md` §3.1), and everything in the right-hand column is
G7. Nothing in this document argues for building it sooner.

## 6. Open items

- [ ] `Daily Priority 1 ограничен` needs a number, and the course gives none. It is a parameter
      awaiting a decision record, not a missing feature.
- [ ] The printable emergency list is required by `FAIL_CLOSED_POLICY.md` and does not exist. It is
      the cheapest item in the whole table and the only one whose absence is a **safety** gap rather
      than a capability gap.
- [ ] Whether a manual position-reconciliation step belongs in v1. §4 argues the hole is real; the
      charter is silent on closing it by hand.
