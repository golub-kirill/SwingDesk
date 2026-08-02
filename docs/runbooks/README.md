# RUNBOOKS

**Status:** drafting · **Tier:** 6 (engineering)

<!-- verbatim-sources: Module_33_Skrinery_v5.0.pdf -->

One procedure per row of the fail-closed degradation table (`FAIL_CLOSED_POLICY.md` §2). The course
specifies the manual process **and** the return condition for each; these expand them into steps.

Kept as one file rather than five. They are read under pressure by one person on one machine, and
finding the right section in one document beats finding the right file among five.

**Rule for all of them:** the return condition is not a judgement call. It is the course's, it is
quoted verbatim in each section, and the system stays in its degraded state until the condition is
demonstrably met.

---

## 1. No data, or data in doubt

```verbatim
Остановить новые решения; использовать второй источник и последний валидный snapshot.
Freshness, symbol/currency, corporate actions и event time подтверждены.
```

**Symptoms:** fetch failures, `DATA` refusals across many instruments, staleness beyond the window,
a spike in source conflicts.

**Steps**
1. Stop. No new decisions — the run is already refusing, so do not override it.
2. Identify scope: one instrument, one vendor, or everything. The health report's refusal section
   answers this.
3. Check the second source (Questrade) on a sample. Agreement means the primary is at fault;
   disagreement on both means look upstream.
4. If needed, work from the last valid snapshot — it exists by construction
   (`POINT_IN_TIME_SPEC.md` §5). Mark any output as snapshot-based.
5. **Open positions are still managed.** A data failure must never lock you out of managing risk on
   capital already committed.

**Return:** all four named gates pass — freshness, symbol/currency, corporate actions, event time
(`DATA_QUALITY_SPEC.md` §1). Not three of four.

## 2. Broker or platform failure

```verbatim
Открыть ручной список positions/shares/stops/targets/events; управлять через доступный резервный канал.
Позиции и ордера reconciled; protective orders подтверждены.
```

**Steps**
1. Print the manual position list — instruments, shares, stops, targets, upcoming events. **This
   must work with the system down**, which is why it is generated after every run rather than on
   demand.
2. Manage through whatever channel is available: broker phone, mobile app, alternate terminal.
3. Record every action taken outside the system, with timestamps, for later entry.

**Return:** positions and orders reconciled against the broker, protective orders confirmed live.
**The broker is authoritative for positions**, not the journal (Appendix T) — where they disagree,
the journal is corrected.

## 3. Screener or automation failure

```verbatim
Использовать ограниченный ручной universe и checklist; автоматические сигналы считать недействительными.
Logs проверены, причина устранена, повторный run совпал с контрольным.
```

**Steps**
1. Treat every automated signal from the affected run as **invalid** — not suspect, invalid.
2. Fall back to a small manual universe with the pre-trade checklist (Appendix E, 18 items).
3. Diagnose from the run manifest and logs.

**Return:** the strictest in the set — a **re-run must match a control run**. This is why
`DETERMINISM_SPEC.md` exists as a spec rather than an aspiration; without byte-identical
reproducibility this return condition cannot be satisfied at all.

## 4. Risk or rule unclear

```verbatim
Статус Watch/Skip; новый ордер запрещён.
Полная карточка и risk snapshot заполнены без предположений.
```

**Symptoms:** an unset parameter, a component refusing, a strategy card with an incomplete field, a
situation the rules do not cover.

**Steps**
1. The candidate is `Watch` or `Skip`. It is never `Trade`.
2. Record which field or rule is missing — that record is what turns the gap into a work item.
3. If a parameter is unset, it goes in `registry/parameters.yml` with a citation, not into the code
   as a literal.

**Return:** the card and risk snapshot are complete **without assumptions**. A field filled with a
plausible guess does not satisfy this — that is the meaning of `без предположений`.

## 5. Violation or loss of control

```verbatim
Pause или reduced risk по risk-off ladder.
Review завершён и выполнены
формальные критерии возврата.
```

*The return condition is checked as two fragments because the PDF's multi-line row label is
interleaved into this cell by text extraction. The cell reads `Review завершён и выполнены
формальные критерии возврата.`; the extracted stream reads `Review завершён и выполнены` +
`я потеря контроля` + `формальные критерии возврата.` The same splice affects this row wherever it
is quoted.*

**Symptoms:** a `Critical` error code, a loss limit breached, a losing streak, or the honest
recognition of not being in a state to decide well.

**Steps**
1. `Pause`. This is system-wide, not per candidate (`DECISION_STATE_MACHINE.md` §1).
2. Apply the risk-off ladder. **Currently unquantified** — `risk.risk_off_ladder` is `unset`, so
   until it has a value this step is a judgement call and should be recorded as one.
3. Complete the review before anything resumes.

**Return:** review complete and the **formal, pre-recorded** criteria met. Criteria written after
the event do not count — that is the same rule that governs `criteria.yml`.

---

## Standing rules

- **The manual list must always exist.** Generated after every run, printable, valid with the
  system down.
- **A degraded state is recorded**, not remembered. It goes in the journal with its trigger and its
  return condition.
- **Return conditions are demonstrated, not asserted.** Each of the five is a checkable fact.
- **Open-position management survives every scenario.** Every runbook above leaves it reachable.

## Open items

- [ ] `risk.risk_off_ladder` needs values before §5 is executable as written.
- [ ] The manual position list needs a format and a generation step in the daily run.
- [ ] Whether entering a degraded state should notify (`PRODUCT_SURFACES.md` §4 sends `Pause`
      everywhere; the other four states are quieter).
