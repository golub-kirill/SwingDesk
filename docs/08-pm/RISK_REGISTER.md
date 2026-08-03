# RISK REGISTER

**Status:** drafting · **Tier:** 8 (project management) · **Content:** authored

Risks to the *project*, not to a trade. Each has an owner-visible consequence and either a control
that already exists or an explicit statement that none does.

Entries are rated on **likelihood × what it costs if it lands**, and the rating is the honest one
rather than the reassuring one. Several are `high / accepted` — a risk that has been accepted is
still a risk, and a register that only lists mitigated ones is a comfort document.

---

## 1. Realised — these already happened

Kept at the top because a register of hypotheticals ages badly, and because each of these was found
by a control rather than by luck.

| ID | What happened | Found by | Now controlled by |
|---|---|---|---|
| R1 | ATR reported a validation status its registry row never granted it | the metadata mirror test, written the same day | `test_components.py` pins every component's declared metadata to the course index |
| R2 | `config_hash` covered which parameters were set, not their values — a changed threshold would have been reported as a determinism defect | the replay gate, on its first real case | hash covers values and provenance |
| R3 | A replay fixture had constant true range, making it blind to the ATR period it claimed to pin | trying to make the gate fail on purpose | fixture bars vary on coprime cycles |
| R4 | `reference_data` sat above `market_data`, permitting calendars to import bars | `lint-imports`, first run | layer order corrected; contract enforced |
| R5 | The pipeline sat in `presentation`, unreachable by the replay harness that must drive it | the same contract, second time | `application` layer created |
| R6 | PR-001's analysis scored "cannot answer" as "disagrees", which would have made STRUCTURE look artificially different | a test written before the study ran | pairs compared on the co-decidable subset only |
| R7 | PR-001's first run met the instrument floor and failed the session floor; the runner checked only the first | the sample rule, applied by hand | runner enforces both |
| R8 | Two documents cited sources they had not declared; two `verbatim` quotes had drifted | `verify_transcription.py` | gate 2, on every commit |

**The pattern worth noticing:** every one was found by a gate, a test, or an attempt to break a
gate — none by review. That is the argument for the gates, and it is empirical rather than
aesthetic.

## 2. Open risks

### Data

| ID | Risk | Rating | Control |
|---|---|---|---|
| D-1 | **Survivorship can never be corrected.** No free source serves delisted instruments; owner decision D10 (2026-08-02) reaffirmed the free tier knowing this | **high / accepted** | Mandatory disclosure field on `EvidenceRecord`, unskippable by construction. Quantified per study — PR-002 needs only ~2% of trades missing at −2R to lose its finding |
| D-2 | **Single vendor.** Yahoo is scraped, undocumented, personal-use-only, and can change or stop without notice | **medium / high impact** | Bitemporal store means history already fetched survives the vendor. Nothing else; a second free source is not identified |
| D-3 | **Canada cannot be enumerated.** No free `.TO` symbol directory in hand | **high / accepted** | Every result is reported single-market. `BR-9`'s per-country requirement is unmet and said so, not quietly dropped |
| D-4 | **Intraday history is capped** — `1h` ≈ 725 sessions, `30m` ≈ 60 | **certain / bounded** | `window_ceiling_days` is a disclosure field on the evidence record |
| D-5 | **Symbology gaps.** Share-class and unit symbols (`AMH$G`, `F$B`) fail to fetch — ~2.5% of a sample, and systematically preferred shares and units rather than a random 2.5% | **medium** | Recorded in `DR-003`; no mapping built |

### Evidence

| ID | Risk | Rating | Control |
|---|---|---|---|
| E-1 | **The strategy has no edge.** PR-005 measured the base trigger at +0.028R ungated and −0.123R under cost stress; three of four studies refuted their hypothesis | **high / this is the project's central risk** | None available — this is what the validation programme is *for*. `k.programme_exhausted` is the named kill criterion, and reaching it is a legitimate outcome |
| E-2 | **Parameter invention** — a guessed number acquiring the authority of a measurement | **was high, now controlled** | Every parameter carries provenance; `unset` yields a coded refusal, never a default; `assumed` requires a citation; only pre-registered evidence reaches `validated`; a cited `DR-NNN` must resolve to a real file |
| E-3 | **Cross-study data snooping** — testing variants of a refuted idea until one passes | **medium** | `PREREG_TEMPLATE` §0 requires a refutation-*family* check, not an exact-lever check. Weak: it depends on the author searching honestly |
| E-4 | **Clustered trades inflate significance.** Dozens of instruments fire on the same session; a trade-level permutation understates the null | **realised in PR-002** | Date-block permutation added post-hoc, and it discriminates — one variant passed the weak null and failed the strong one. **Not yet part of any registered decision rule** |
| E-5 | **Multiple comparisons.** Four studies, several arms each, no correction applied | **medium** | Stability requirements (cost stress, holdout, second null) instead of an adjusted p-value. Defensible and not equivalent; `PREREG_TEMPLATE` §6 records the debt |
| E-6 | **One test window, one regime mixture.** PR-002's test period is 755 sessions of a mostly rising market | **medium** | Stated in the report. No control; more history would need instruments with longer histories, which biases toward survivors |

### Build

| ID | Risk | Rating | Control |
|---|---|---|---|
| B-1 | **Solo project, no second reviewer.** Every finding above was caught by a machine because there is nobody else to catch it | **certain / structural** | 9 merge gates from one command; gates that are themselves tested for the ability to fail |
| B-2 | **Component activation drifts from its definition.** `breadth` and `regime` were used by a reported study with no golden vectors — `specified`, not `active`, while `regime.classifier_rule` was already `validated` | **realised, closed 2026-08-02** | Vectors added for both. The underlying exposure remains until gate 11 makes activation mechanical (`ROADMAP.md` N4) — it was found by counting, and counting does not scale to 460 components |
| B-3 | **Documentation drifts from code.** 25 documents, several already found stale | **medium** | Gates 2, 3 and 3b cover transcription, the course index and the FRD. Nothing covers authored prose |
| B-4 | **Scope creep into the course's 1379 topics.** ~460 are computable and 7 are built | **medium** | The v1 finish line requires *no* particular component to exist. Catalogue growth is G6, deliberately after the machinery |

### Governance

| ID | Risk | Rating | Control |
|---|---|---|---|
| G-1 | **A study's result changes what the owner wants tested next** — the ordinary way pre-registration erodes | **medium** | Amendments are appended and dated; an amendment after seeing data downgrades a study to exploratory. Every amendment so far was made before any data was seen and says so |
| G-2 | **`assumed` values quietly becoming load-bearing.** 9 parameters carry assumed values today | **medium** | Every number computed from them is marked assumption-derived where it appears (`uses_assumed_parameters`). The count is reported daily and is a project-health signal |
| G-3 | **The timebox passes without a decision.** `k.project_timebox` was 2 months to G5 — met — and no next timebox is set | **open** | None. `ROADMAP.md` §8 flags it |

## 3. Risks deliberately not carried

| | Why |
|---|---|
| Order-execution failure, broker outage, fat-finger | The system never places orders (`CHARTER.md` §3). The entire surface is absent by design |
| Multi-user data leakage, GDPR, tenant isolation | Single-user, single machine, no service |
| Market-data redistribution liability | Nothing is redistributed; the non-goal is explicit and legal rather than architectural |
| Model drift in an ML sense | No model is trained. The one fitted object is a pair of thresholds, fitted on train and frozen |

## 4. Review

This register is reviewed when a study reports, a gate catches something, or an owner decision
changes a constraint — not on a calendar. Three of the eight realised entries above came from a
single day's work, so a monthly cadence would have recorded them as history rather than as risks.
