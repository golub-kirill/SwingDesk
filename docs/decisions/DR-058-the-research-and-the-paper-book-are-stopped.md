# DR-058: the research and the paper book are stopped - no strategy found here beats holding the index after tax

```
date:            2026-09-28
status:          accepted — ruled by the owner 2026-09-28: offered "stop", "freeze until sixty
                 paper sessions" or "keep digging", the owner chose to stop, and to switch off
                 every scheduled task
parameters:      none
components:      none new
implemented_by:  tools/verify_schedule.py :: STOPPED_BY
```

## 1. What was ruled

1. **No new study is registered.** The search for a return source this project can trade is closed.
   `tools/trial_budget.py` prints the count of trials spent; nothing adds to it.
2. **`DR-055`'s proof (2), sixty clean paper sessions, is abandoned rather than failed.** It measures
   execution, and execution can only lower a return. It could not have produced the edge §2 finds
   missing.
3. **Every scheduled task is switched off.** Nothing in this repository runs by itself any more.
4. **No real money was ever placed by this project, and none will be.** `DR-055`'s rule held to the end.
5. **The owner will look for a different way to earn.** That is not a decision this record makes.

## 2. Why - measured, not argued

The main hypothesis (`DR-055`: `IJR` and `VB` held through each night, `SPY` through each day) is the
only thing this project ever found that beat holding the index. Its registered result is
`docs/prereg/results/PR-040.json`, with the breakdown in `PR-040-attribution.json`. The after-tax
reading is `docs/decisions/measurements/after-tax-2026-09-27.json`:

| geometric excess of the book over holding `SPY`, a year | value |
|---|---|
| 2016-2026, before tax, at the auction prices (`PR-040`'s verdict: `ACCEPT`) | +4.39% [+0.95, +8.30] |
| last 48 months, before tax | **+0.73% [−4.90, +6.18]** |
| last 12, 24 and 36 months, before tax | −1.64%, −0.72%, −0.05% |
| last 48 months, half a cent a share worse than the auction | −1.41% |
| last 48 months, after tax at the owner's 20-30%, either treatment | **−1.09% to −4.69%** |

**The decade's margin belongs to an old market.** The year 2021 alone carries about 40% of it
(`EVIDENCE_SUMMARY` §39). Over the market this rule would trade in (`AGENTS.md` §19), the margin is
indistinguishable from zero before tax and negative after it. That holds at the owner's rate, in the
regular taxable account the owner ruled it would run in (`DR-057`).

**The other open directions could not see an edge of a plausible size.** Overnight momentum on single
stocks had a minimum detectable effect of 13.0 points a year
(`docs/decisions/measurements/overnight-momentum-power-2026-09-27.json`). Canadian funds were
reconnoitred at about 6 to 13 points a year in scratch and never registered. **A study that cannot
see less than six points a year is a lottery ticket, not a measurement.**

## 3. What was switched off, and what was left to finish

The Windows Task Scheduler on the owner's machine, 2026-09-28 at about 16:10 CT (`schtasks /change`,
reversible with `/enable`):

| task | state |
|---|---|
| `SwingDesk daily run`, `SwingDesk second pass` (`CARD-001`) | disabled |
| `SwingDesk coverage pass`, `SwingDesk classification pass` | disabled |
| `SwingDesk re-measurement pass` | disabled |
| `SwingDesk night close` (`CARD-002`'s buy) | disabled |
| `SwingDesk night exit` | runs once more, 2026-09-28 18:10, then ends (trigger end 2026-09-29) |
| `SwingDesk day protect` | runs once more, 2026-09-29 08:40, then ends (trigger end 2026-09-30) |

**Why two passes were left running once.** The night close of 2026-09-28 had already bought the book's
first real paper night. The exit pass lodges its market-on-open sells, and it also buys one last day
leg of `SPY`. The morning pass lodges that leg's market-on-close sell. After the close of 2026-09-29
the card holds nothing. **The reconciliation of those sells is never journalled**, because the close
pass that journals it is off. The venue is the authority on what the account holds.

**`CARD-001`'s four open paper positions were not closed.** They are small, and each carries its
bracket at the venue, so the venue exits them by itself. The book that tracks them is frozen at
2026-09-28.

**Gate 26 reads the stop.** `STOPPED_BY` names this record. With it set, a disabled task is the ruling
working and not a fault. A crash, or a missed trigger on a task still scheduled, stays a failure.

## 4. The one measurement from the paper account, recorded because it would be lost otherwise

The first real paper night, 2026-09-28. `IJR`'s market-on-close buy filled all 346 shares at 137.37.
**`VB`'s filled 71 of 165 at 286.62, and the venue expired the rest.** A closing-auction order on the
paper venue can fill in part. `lodge_exit` sells exactly what filled, so this was handled correctly.
But a book sized to the close is not what the paper account ends up holding, and anyone resuming
`CARD-002` should know that before reading a paper session as the book.

## 5. How to resume, if the owner ever wants to

Nothing was deleted. Re-enable the tasks with `schtasks /change /tn "<task>" /enable`, move the two
end dates forward with `/ed`, and set `STOPPED_BY` to `None`. Then read `HANDOFF.md`. A resumed study still needs its own registration
(`PREREG_TEMPLATE.md`); this record re-opens nothing by being reversed.
