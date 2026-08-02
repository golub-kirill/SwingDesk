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

**Current census: 74 parameters, all `unset`.**

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
(`FAIL_CLOSED_POLICY.md`), not a fallback value. This is why the registry can honestly ship with all
74 unset: the system is fully functional and simply declines to make decisions it has no basis for,
which is exactly what the course prescribes.

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

## 7. What the 74 cover

| Group | Count | Notes |
|---|---|---|
| `risk.*` | 16 | including `risk.per_trade_pct`, all portfolio caps, both loss limits, and both ladders |
| `screen.*` / `watchlist.*` | 19 | all 16 M33 filters plus watchlist size, eviction and daily priority |
| `exit.*` | 15 | every ATR/Chandelier/Donchian/percentage/holding parameter, plus slot resolution order |
| `regime.*` / `rs.*` | 8 | includes `regime.classifier_rule` — see below |
| `stats.*` | 8 | Sharpe/Sortino/Recovery conventions, breakeven win rate, both scales |
| `data.*` | 2 | freshness and staleness windows |
| `validation.*` | 8 | IS/OOS split, walk-forward window, embargo, forward-test minimums, go-live |

**Three entries are not numbers but missing rules**, and they are the largest authored work in the
project:

- `regime.classifier_rule` — the course defines 11 regimes and a matrix of what each permits, and
  names the inputs (direction, ATR, ADX, participation), but **no rule produces the label**. The
  entire strategy-selection matrix depends on it.
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
