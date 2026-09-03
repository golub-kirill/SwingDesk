# SwingDesk

Decision-support software for swing trading Canadian and US equities and ETFs. It computes the
charts, indicators, market structure, setups, risk figures, journal and statistics defined by the
owner's 116-file swing-trading course, and records every decision with an audit trail.

**There is no broker integration and no real order is ever placed.** No order that can move the
owner's money, no live venue, no automated execution of anything with capital behind it. The human
makes every trading decision that involves money; this system prepares and records them. No advice
to third parties, no multi-user service.

**What exists is a paper account used as a RESEARCH INSTRUMENT** — owner framing, 2026-09-01, and
the distinction is the point rather than a softening. The purpose is to put this system's own
machinery in front of a real venue's fills, partial fills, rejects and halts instead of a fixture,
so that what it does can be studied. It is a measuring instrument that happens to speak a broker's
protocol, not a route to market.

`CHARTER` A-002 is the ruling that permits it and it is scoped exactly that narrowly: on an account
with no owner capital behind it the system may submit without per-order approval, because the
reason the human-only rule existed — irreversible risk — does not apply there. On anything that can
move money, A-001 stands unchanged and unweakened.

The boundary between the two is a committed host allowlist enforced by a merge gate, because
**a brokerage account object carries no field saying whether it is paper or live** — which host was
called is the only difference there is. `DR-026`, `DR-027` and `DR-028` carry the reasoning and the
guards.

## Status

**The operational loop is closed and gated; the strategy is not known to work.** Those are two
different claims and this project keeps them apart deliberately.

*Closed* means a position can be recorded, evaluated before candidates on every scheduled run,
proposed on, approved by the owner, applied, and settled against what the broker actually did —
end to end, on real bars, first demonstrated 2026-08-17. Since 2026-09-01 the fills in that
sentence can come from the paper account rather than from a line the owner typed: `swingdesk
broker` reads it and reconciles it against this system's own book, reporting disagreement in the
course's own code (`TECH`, *"broker/platform/journal mismatch"*, whose prescribed action is
*"pause new entries"*).

*Not known to work* means the base strategy is negative at measured costs across the whole
admissible universe and **no parameter in this system has ever reached `validated`**. See
`docs/08-pm/EVIDENCE_SUMMARY.md`, which outlives any one session.

**What the evidence actually says about the strategy, as of 2026-08-31.** Two cross-sectional
momentum studies reported nothing, and a measurement taken afterwards found the likely reason: both
held for a month or less, which is inside the window where the literature documents the *opposite*
sign (Jegadeesh 1990; Lehmann 1990), while momentum is documented at three-to-twelve-month holds
(Jegadeesh & Titman 1993). On this project's own store the decile spread rises monotonically with
horizon and separates from zero only at about six months. That measurement is **exploratory** — it
sets no parameter and advances no validation status — and the holding period stays at 20 sessions
by owner ruling. `TODO.md` carries the bounded study that would test the question properly.

Everything that keeps those claims from blurring runs from a single command:

```bash
python tools/check_gates.py
```

The inventory covers provenance, transcription, generated registries, document and study
consistency, architecture, static analysis, golden vectors, tests, determinism, the parallel
worktree census, and — since the venue was wired — that the broker adapter can reach exactly one
allowlisted host and spells no HTTP write verb of its own. See `docs/06-engineering/CI_POLICY.md`
for the derived inventory and a record of what each gate has caught.

## Source of truth

The requirements source is the course at
`C:\Users\User\Desktop\swing-trading setup\Swing_Trading_Course_Fixed\Swing_Trading_Course_Charts_Layout_Fixed_Verified\`
(116 PDFs plus `VERIFICATION_MANIFEST.json`), governed by
`C:\Users\User\Desktop\swing-trading setup\Course_Production_Rules_v3.8.md`.

Measured facts about that source, established by full text extraction — not assumed:

| | |
|---|---|
| Topics | **1379**, each with a stable component ID (`M26-T0393-v5.0`) |
| Claim types | Definition 916 · Operational Course Rule 173 · Untested Hypothesis 124 · Derived Observation 121 · Inference 45 |
| Computable components | **~460** (everything that is not a Definition) |
| Validation status | `Not Applicable` 1209 · `Untested` 170 · **tested: 0** |
| Numeric thresholds supplied by the course | **effectively none** — across 276 audited topic definitions, the count containing a parameter not already in their own title is 0 |
| Arithmetic supplied by the course | Appendix C (11 risk formulas) and Appendix D (11 statistics formulas) only |
| Schema supplied by the course | Appendix G — a 12-entity ER model with column lists |

**The consequence, stated plainly:** the course is a complete *governance and taxonomy*
specification and an empty *parameter* specification. Every threshold in this system is authored,
not inherited. Every parameter therefore carries a provenance and a status, and no component is
ever displayed as more validated than it is.

**And a course rule is not evidence.** `AGENTS.md` §16 (owner instruction) settles what a sentence
in the course licenses: it names something worth looking at, and it never stands as the reason a
threshold has its value. Published work supplies method, calibration and known limitations; only a
pre-registered study against this universe moves a parameter to `validated`.

## Scope

- Markets: Canada + US equities and ETFs. **They are never merged** — separate calendars, indexes
  and currencies, and the paper venue serves only one of them, which the reconciliation reports as
  *out of scope* rather than as a missing position.
- Timeframes: context `1Y` / `3M` (windows over daily bars) → decision `1D` → confirmation/trigger
  `1H` → execution `30m`. Lower frames refine a setup; they never invent one. Each resolution is
  fetched and stored independently — deriving `1H` from `30m` would cap hourly history at 60
  trading days when ~725 are available (`ADR-0001`).
- Storage: local databases for bars, the directory, positions, classifications and the journal.
  Nothing leaves the machine except the two requests named below.
- Outbound network: the daily symbol directory (`DR-008`) and the paper broker (`ADR-0005`). Both
  have their limits — hosts, timeouts, byte caps, retry budgets — in committed, merge-gated policy
  files rather than in code, so changing one is a commit a reviewer sees.
- Notification: a **local desktop notice** (`DR-011`, 2026-08-16). Firebase is specified in
  `PRODUCT_SURFACES` §3.4 and **unbuilt**; the record explains why local is stronger on §3.4's own
  terms — "no data leaves the machine" is satisfied by construction rather than by a third party's
  policy.
- Surfaces: **CLI + reports, built.** `swingdesk scan` runs the day; `swingdesk pending` /
  `respond` carry the owner's approval of open-position actions on the CLI rather than Telegram
  (`DR-011`); `swingdesk broker` reads the paper account and reconciles it. A web admin panel and
  Telegram remain specified and unbuilt.

## The paper venue, and the eight things that stop it

Submission is **stopped by default** and every guard below is independent — none of them can
compensate for another, which is `FAIL_CLOSED_POLICY.md` §3 applied to the one surface here that
acts on the world.

1. **One allowlisted host**, with the live venue named as forbidden and compared as a hostname.
   This is the whole paper/live boundary, and gate 39 fails the build on a second entry.
2. **A kill switch that is a file the owner creates**, outside this repository. Absent, unreadable,
   or missing its marker all mean stopped. A switch that defaults to on is not a switch, and one
   that fails open is the inversion `DR-025` records this project paying for once already.
3. **`access.write_enabled` in the committed policy** — one line, one commit, one reviewer.
4. **A single chokepoint in the code.** Every write goes through one function that consults the
   other three first, and the gate reads the syntax tree to prove no second path exists.
5. **The ratified caps, applied across one run's own output** (`DR-027` §10). The screen's cutoff
   picks who is *eligible* — normally about a hundred names; `risk.max_concurrent_positions` (4),
   `risk.max_open_risk` (4R) and `risk.max_sector_risk` (2R) pick who is *taken*, in the card's own
   ranked order. Without it a single evening would have sent **114 orders and 103.5R**, measured.
6. **The venue is asked what it already holds, before anything is added** (`DR-027` §11). Any
   symbol the account is exposed to — a position *or* a resting order — that this system's book
   does not carry stops submission with the course's `TECH`, whose action is *"pause new entries"*.
   The caps are measured against the book, so a book that does not describe reality bounds nothing.
   **An order this system itself sent is the exception** (`DR-032`): identified by an id in our own
   journal, never by the shape of one, it does not halt the run — and is counted against the caps
   instead, because exempting it from both would let the evening's retry pass add four more names
   on top of four already resting.
7. **The book and the venue must describe the same positions** (`DR-035`), which is the same
   question asked the other way round. A stop leg firing overnight closes a position at the venue
   and nothing records it, so the caps would count it for ever and the machine would stop trading
   after four stop-outs without a word.
8. **`k.drawdown_pause`, the only ratified `live` criterion** (`DR-034`). Peak-to-trough drawdown of
   account equity including open positions marked to market, against an owner-set 20 percent. A
   breach pauses new entries; a drawdown that cannot be *measured* pauses them too. Reducing size
   per the risk-off ladder stays the owner's — `risk.risk_off_ladder` is `unset`.

Guards 5 to 8 are not boundary guards; the first four answer *may this system write here at all*
and cannot answer *how many*, *against what book*, or *how far down*. `DR-031` is what keeps 6 from being a permanent halt: an entry this
system placed records itself from the fill, taking the price from the venue and the stop from our
own journal.

The keys are the owner's and live only in the environment (`SECURITY.md` §2.1). This repository is
public and holds none.

**Operating it day to day** — arming, disarming, reading the evening's log, and the one message
that needs a person — is `docs/runbooks/README.md` §7.

## Layout

```
docs/        the document set, by tier (see docs/README.md)
registry/    generated data and committed policy: course index, components, parameters, network limits
golden/      frozen fixtures: component vectors and replay cases
src/         bounded contexts, one package each
tools/       generators, verification scripts, and the gate runner
tests/
```

## Language

English throughout — documents, code, and UI. The course's controlled vocabulary
(`STAGE`, `LAYER`, `CLAIM TYPE`, `VALIDATION`, `Trade/Watch/Skip/Pause`, the skip and error codes)
is used verbatim and is never translated or paraphrased.

**This governs artifacts, not conversation.** `AGENTS.md` §13 records an owner instruction about the
language an agent replies in, which changes nothing that lands in the repository. If the two ever
appear to disagree, this rule wins for anything committed.
