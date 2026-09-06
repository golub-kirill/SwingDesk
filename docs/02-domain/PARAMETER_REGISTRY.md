# PARAMETER REGISTRY

**Status:** drafting · **Tier:** 2 (domain) · **Content:** authored — **no course source exists**

**Data:** `registry/parameters.yml` · **Enforced by:** `tools/verify_parameters.py`

---

## 1. Why this document is the most important one in tier 2

The course is a complete governance specification and an **empty parameter specification**. Across
276 audited topic definitions in Modules 45–58 and 88–93, the number containing a parameter not
already in the topic's own title is **zero**. Module 93 — *Итоговая система управления риском* —
states no risk percentage, no open-risk cap and no loss limit. Appendix C says so outright:

> "Риск % задаётся личным планом."

So every threshold in this system is **authored**. The danger is not that an authored value is
wrong — early values will be wrong, and that is expected and recoverable. The danger is that an
authored value **silently acquires the authority of a measurement**: it appears in a report, is
quoted in a decision, and six months later nobody remembers it was a guess.

This registry exists to make that impossible.

**The census lives in `HANDOFF.md` §2**, derived by `python tools/verify_counts.py`. It is not
repeated here: the same figures were carried by six documents and drifted five times, and one
owner is the fix (gate 14).

**Most of the `assumed` values arrived in two blocks** — the fifteen `validation.*` thresholds set by
`DR-007-validation-thresholds.md` (ratified 2026-08-08) and the six portfolio constraints set by
`DR-006-portfolio-risk-block.md` (**proposed**). Ratified still means `assumed`: a decision record
never produces a `validated` value, however it was approved.

**`risk.per_trade_pct` was reserved to the owner, and the owner has set it.** Appendix C
reserves it — *`Риск % задаётся личным планом`* — so no decision record drafts it. ~~It stays
`unset` on purpose … sizing refuses until the owner sets it.~~ **Set 2026-08-11: value 1.0,
status `owner`, and sizing stopped refusing that day.** The reservation is the durable rule;
the status was a fact about a date, and this line kept it for twenty-five days.

The registry shipped at 74, all `unset`, and that sentence stood in this document after twelve of
them had been set. It was caught by an audit rather than by a gate, which is the honest version of
how it was found. The counts above are the ones `python -c` prints from `registry/parameters.yml`
today; treat any hard-coded census in prose as a claim with a date on it.

## 2. Record shape

```yaml
- id: risk.per_trade_pct        # lowercase group.name, unique
  unit: percent of equity       # what the number means
  value: null                   # null == UNSET
  status: unset                 # unset | assumed | owner | validated
  provenance: null              # required once a value exists
  named_in: [Appendix C, M93-T1324]   # where the course names the concept
  note: 'Course states explicitly: "Риск % задаётся личным планом."'
  ui_editable: true             # may the web UI change this
```

`named_in` is mandatory and non-empty. A parameter with no course reference is either invented
scope or a missing citation — both need a human to look, so the linter rejects it.

## 3. Status and provenance

| Status | Meaning | Required provenance |
|---|---|---|
| `unset` | no value; the owning component refuses | `null` |
| `assumed` | a starting value from literature or convention | `assumed:<citation>` |
| `owner` | the owner's own trading plan | `owner` |
| `validated` | survived a pre-registered test | `validated:<evidence-id>` |

These are cross-checked, not just declared: a `null` value must be `unset` with `null` provenance,
and a value must carry provenance matching its status. `assumed` without a citation fails the build.

**`assumed` is not a soft `validated`.** Owner decision D5 permits literature-sourced starting
values, and that is a reasonable way to get moving — but an assumed value has *no evidence behind
it*, and the system says so wherever it is used (§5).

## 4. Unset means refuse, not default

From the module gate, verbatim:

> "Missing, stale, incomplete или contradictory required data означают Research/Watch/Skip/Pause, а
> не догадку."

**— а не догадку. Not a guess.** A component whose parameter is unset returns a coded refusal
(`FAIL_CLOSED_POLICY.md`), not a fallback value. This is why the registry could honestly ship with
every parameter unset: the system is fully functional and simply declines to make decisions it has
no basis for, which is exactly what the course prescribes. **63 of 96 are still unset**, and that
is not a backlog — it is the design working.

There is no `default:` field in the record shape. That absence is deliberate — a default is an
assumed value that forgot to say so.

## 5. Display obligation

Any output — CLI report, web panel, Telegram card — that depends on a parameter with status
`assumed` must **show that**. Not in a footnote; adjacent to the number it produced.

This is the same requirement §3.7 of the production rules places on validation status:

> "Validation statuses are not grades."

A number computed from assumed thresholds is not a measurement, and the surface that presents it
must not let it look like one.

## 6. Changing a value

From §3.7, verbatim:

> "Editing a threshold after seeing results creates a new rule version and resets any validation
> claim that depended on the earlier frozen definition."

So a parameter change is **never** an in-place edit of a live thing:

1. the owning component's version increments;
2. that component's validation status resets to `Untested`;
3. every strategy card pinning that component either re-tests or stays pinned to the earlier
   version (`LIFECYCLE_AND_LAYERS.md` §5);
4. the change is recorded with its date, old value, new value and reason.

This is what makes D5's "editable from the web UI" safe. The UI may change a value; it may not
change it *quietly*. `ui_editable: false` marks parameters that are rules rather than numbers
(`regime.classifier_rule`, `stats.sharpe_convention`, `exit.ma_cross_semantics`) — those require a
spec change and a pre-registration, not a form field.

## 7. What the parameters cover

Counted from `registry/parameters.yml` on 2026-08-03. Three rows were stale and five groups were
missing entirely when this was audited — the table had been written at 74 parameters and never
recounted.

| Group | Count | Notes |
|---|---|---|
| `risk.*` | 16 | including `risk.per_trade_pct`, all portfolio caps, both loss limits, and both ladders |
| `screen.*` / `watchlist.*` | 19 | all 16 M33 filters plus watchlist size, eviction and daily priority |
| `exit.*` | 15 | every ATR/Chandelier/Donchian/percentage/holding parameter, plus slot resolution order |
| `validation.*` | 15 | IS/OOS split, walk-forward window, embargo, forward-test minimums, go-live |
| `stats.*` | 8 | Sharpe/Sortino/Recovery conventions, breakeven win rate, both scales |
| `regime.*` / `rs.*` | 7 | includes `regime.classifier_rule`, which was the one `validated` entry until 2026-08-16 and is `assumed:PR-002` now — see below |
| `data.*` | 6 | freshness, staleness, revision tolerance |
| `universe.*` | 3 | the DR-003 liquidity rule: price floor, ADTV floor, history floor |
| `account.*` · `costs.*` · `pivot.*` · `atr.*` | 7 | equity and currency; commission and slippage model; pivot left/right; ATR period |
| **Total** | see `HANDOFF.md` §2 | by status, likewise |

**Three entries are not numbers but missing rules**, and they are the largest authored work in the
project:

- `regime.classifier_rule` — the course names 11 regimes and the inputs (direction, ATR, ADX,
  participation) but **no rule produces the label**. This entry is `assumed:PR-002`; it was
  `validated:PR-002` and the project's only validated parameter until 2026-08-16, when PR-002's
  verdict was corrected to `INCONCLUSIVE` (§6 required both countries; the runner never encoded that
  condition). **There are now zero validated parameters.** It covers **one axis of three**
  (breadth), and its registry note carries the bound that ~2% of trades missing at −2R would erase
  the finding.

  An earlier draft of this bullet said the course also defines "a matrix of what each regime
  permits" and that the strategy-selection matrix depended on this parameter. **`REGIME_SPEC.md`
  §3 established that the matrix does not exist** — topic 451 carries the course's strongest
  claim type and one sentence of content, and no mapping is enumerated anywhere. Corrected here
  because two documents disagreeing about whether a source artefact exists is worse than either
  of them being wrong alone.
- `screen.trend_definition`, `screen.breakout_definition`, `screen.pullback_definition`,
  `screen.contraction_definition` — the four concepts the course teaches most extensively and never
  quantifies.
- `stats.sharpe_convention` — periodicity, series construction, risk-free rate, annualisation. A
  wrong choice here silently inflates the number rather than failing loudly.

Each of these requires a pre-registration before activation, not just a value.

## 8. Open items

- [ ] Seed `assumed` values per D5, with citations. Highest-leverage first: `risk.per_trade_pct`,
      `exit.atr_period`, the liquidity filters.
- [ ] Decide whether `assumed` values are permitted in a **backtest** at all, or only in live
      screening. A backtest tuned on assumed thresholds and then reported as evidence is the
      overfitting path; pre-registration is the control.
- [ ] Wire `verify_parameters.py` into CI alongside the transcription checker.
- [ ] Cross-check: every `named_in` reference should resolve to a real component id in
      `registry/course_index.yml`. Not yet enforced.
