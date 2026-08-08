# VALIDATION PROGRAM

**Status:** drafting · **Tier:** 5 (validation) · **Content:** `verbatim` + authored

<!-- verbatim-sources: Module_74_Forward_test_v4.0.pdf, Module_72_Istoricheskoe_testirovanie_v4.0.pdf -->

**Source of truth:** Module 74 (topics 1105–1114) for the forward-test stage; the nine validation
statuses are transcribed in `COMPONENT_REGISTRY_SPEC.md` §4 and are not repeated here.

This document answers one question: **what does a component have to survive to move from one
validation status to the next**, and what evidence has to exist afterwards.

---

## 1. The ladder

The course supplies nine statuses and applies exactly two of them. Every component imported from the
course starts at `Not Applicable` (1209 topics) or `Untested` (170). **Nothing in the source is
tested.** Any higher status in this system is something the project earned.

| From → To | What earns it | Recorded by |
|---|---|---|
| `Untested` → `Historically Tested` | a backtest that satisfies all nine stages of `BACKTEST_PROTOCOL.md` | evidence record + protocol |
| → `Out-of-Sample Tested` | a result on data the parameters never saw | `WALKFORWARD_SPEC.md` §2, test column |
| → `Walk-Forward Tested` | multiple windows, each with its own `keep/revise/retire` | window records |
| → `Forward Test Running` | the strategy runs live-schedule with no capital at risk | daily runs, journalled |
| → `Forward Tested` | the forward test met its pre-registered criteria | forward-test report |
| → `Rejected` | it failed a required or prohibiting condition | the failing condition, named |
| → `Retired` | withdrawn because the world changed, not because it failed | withdrawal record |

Two things this ladder is **not**:

- It is not a quality scale. Verbatim, `COMPONENT_REGISTRY_SPEC.md` §4 quotes the course: validation
  statuses are not grades, and `Forward Tested` does not mean profitable.
- It is not a queue every component must climb. `Not Applicable` is a legitimate terminal state for a
  definition, and `active` + `Untested` is a legitimate shipping state provided the status is
  displayed wherever the output appears.

## 2. What a forward test actually measures

Topics 1105 and 1112:

> "Форвард-тест проверяет работу правил на новых данных и реальном расписании без риска капитала. Он
> измеряет не только сигналы, но и пропуски, задержки, alerts и качество журнала."
>
> *(A forward test checks the rules on new data and on the real schedule without capital at risk. It
> measures not only signals, but also misses, delays, alerts and journal quality.)*

The second sentence is the one that matters for this project, and it is easy to read past. A forward
test is **not** a backtest that runs forward. It measures four things a backtest structurally cannot:

| Measured | Why a backtest cannot see it |
|---|---|
| `пропуски` — misses | a backtest takes every signal it generates; a real schedule misses some |
| `задержки` — delays | a backtest executes at the bar it decided on |
| `alerts` | a backtest has no notification path to fail |
| `качество журнала` — journal quality | a backtest writes its own journal automatically and perfectly |

So the forward test is the first stage that tests **the system**, not the strategy. That maps
directly onto this project's Track A criteria (`SUCCESS_AND_KILL_CRITERIA.md`): every candidate
leaves with a coded decision, runs reproduce, refusals are legible. Those are forward-test
properties, not backtest properties.

Module 74's own topic list says the same thing — `Проверка ордеров` (1108), `Проверка
психологической нагрузки` (1109), `Проверка реального проскальзывания` (1110), `Ведение полного
журнала` (1111). Four of the ten topics are about the operator and the plumbing.

## 3. The three prohibitions on drawing conclusions

Verbatim, M74/M75:

> "Запрещено делать вывод по малой выборке, смешивать стратегии или оценивать процесс только по P&L."
>
> *(Drawing a conclusion from a small sample, mixing strategies, or evaluating the process by P&L
> alone is prohibited.)*

Each has a concrete consequence here:

1. **Small sample.** A verdict requires `stats.min_sample_for_verdict` to be set and met. Unset means
   the system reports the measurement and **refuses the verdict** — it does not quietly report a
   Sharpe ratio computed on eleven trades.
2. **Mixing strategies.** Results are reported per strategy version, never pooled across strategies.
   Pooling is how a working strategy and a broken one average into a mediocre one that looks
   acceptable.
3. **P&L alone.** Process quality is a separate measurement from outcome. The course keeps a process
   score for exactly this reason, and Appendix S makes process the gate rather than profit
   (`GO_LIVE_GATES.md` §4).

## 4. The evidence a claim requires

Verbatim, the `Доказательство` line attached to every validation topic in M72–M74:

> "Protocol, code/data version, trade log, OOS/walk-forward report и paper/live gate."

Mapped onto artefacts this system produces:

| Required | Artefact |
|---|---|
| Protocol | the pre-registration (`PREREG_TEMPLATE.md`), written before the run |
| code/data version | the run manifest: commit hash, config hash, snapshot id, component versions |
| trade log | the journal, append-only |
| OOS/walk-forward report | window records per `WALKFORWARD_SPEC.md` §2 |
| paper/live gate | the go-live record per `GO_LIVE_GATES.md` |

All five exist or are specified. The one with no automation yet is the first, and it is the one that
has to come first chronologically — which is the whole point of §5.

## 5. Pre-registration is not optional here

The course does not use the word, but it requires the thing three times over: Appendix J's first
stage fixes version, universe, dates, costs and sample size **before** the run; Appendix K records
the `Selection rule` alongside the parameters; and the prohibition on `data snooping` has no meaning
unless the hypothesis predates the result.

This project therefore treats a study without a pre-registration as **not evidence** — the same
status as a survivorship-biased backtest. See `PREREG_TEMPLATE.md`.

## 6. Current state

Honest, and short:

Restated 2026-08-08; the previous version of this table predated the studies.

| | |
|---|---|
| Components implemented | 7 · 6 with golden vectors · **0 at `active`** — five blocked by an `unset` parameter |
| Components above `Untested` | **0** — every row is still the status the course shipped it with |
| Studies reported | 3 (`PR-001` REJECT, `PR-005` REJECT, `PR-002` ACCEPT), plus one post-hoc survivorship bound carrying no verdict |
| Pre-registrations written | 3; three more named and unwritten (`PR-001b`, `PR-003`, `PR-004`) |
| Decision records | 4 (`DR-001` Sharpe convention, `DR-002` process score, `DR-003` liquidity rule, `DR-004` cost model) |
| Parameters at `assumed` | 24 of 96, 15 of them pending ratification (`DR-005`) · `validated` 1 (`regime.classifier_rule`, from PR-002) |

The four largest authored gaps — the regime classifier, the trend / breakout / pullback / contraction
definitions, the Sharpe convention, and the per-strategy exit mapping — are each a parameter or rule
this system must author, and each therefore needs a pre-registration before a value is chosen. They
are listed as `unset` in `registry/parameters.yml` today, which is the correct state for them: unset
is not a gap in the documentation, it is the documentation working.

## 7. Open items

- [x] ~~Order of the first studies~~ — **settled by running them.** The trend definitions went first
      (PR-001, then PR-005 on its result), the regime classifier third (PR-002). The argument for
      putting the classifier first still holds for the *next* strategy study, since the regime
      breakdown `WALKFORWARD_SPEC.md` §2 requires depends on it.
- [x] ~~Whether a component may advance while survivorship remains unmet~~ — **yes, with a mandatory
      disclosure** (owner, 2026-08-02). Enforced as a required field on `EvidenceRecord`; the nine
      statuses stay exactly as the course defines them, and the qualification rides on the record
      rather than on a tenth status.
- [ ] Where the forward test runs. It needs the real schedule, which means the scheduled daily run
      must be reliable before the forward test can measure anything about it.
