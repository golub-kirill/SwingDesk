# Session handoff — 2026-08-24

**Read `HANDOFF.md` first, then `TODO.md`.** This covers only what changed in the session that built
the sector and correlation caps, the split guard, and two calibrations. Delete it once §1 is
actioned.

**It replaces `SESSION-HANDOFF-2026-08-23.md`**, deleted rather than edited as its own header
instructed. Nothing in it lived only there: the partially-pinned-clock rule went to `AGENTS.md` §12
when the 08-22 file was retired, and everything else is in `DR-006`, `DR-016` or `TODO.md`.

---

## 1. The first thing to check, and it is not code

**Did the scheduled run survive Monday 2026-08-24?**

```bash
python tools/verify_schedule.py
```

That is gate 26, added 2026-08-23. It was **red** when this was written: both passes last ran
2026-08-21 and both exited 1 on the `initial_costs_per_share` schema drift `AGENTS.md` §12 records.
`positions.duckdb` carries the column again, so **Monday's 18:30 and 19:30 passes are the first that
can get past it — the repair is unverified in production until then.**

- **Green** → the four-day outage is genuinely closed and `a.run_completes` starts counting for real.
- **Still red** → read `data/daily_run.log`; the gate exists so this is visible instead of being a
  stack trace nobody opens between sessions.

**This matters more than any remaining code.** `a.run_completes` needs **20 consecutive clean
sessions** and stands at 0/20. Everything else on the v1 finish line is a session or two of work;
twenty sessions cannot be hurried.

## 2. What was built, in one place

All six of `DR-006`'s portfolio constraints now reach code, and the corporate-actions gate is half
built. Full records in `DR-006` §11–§16 and `DR-016` §8–§9.

| | |
|---|---|
| Correlation cap | `derived_observations/correlation.py` + `portfolio.assess_correlation`, step 6b |
| Sector cap | `reference_data/classification.py` + `portfolio.assess_sector`, step 6c |
| Split guard | `manage.split_guard`, in the held-position path **before** the freshness check |
| Gate 26 | `tools/verify_schedule.py` — asks the machine about the scheduled tasks |
| Calibrations | `tools/measure_sector_cap.py`, `measure_correlation_cap.py`, `measure_revisions.py` |

**The classification store is populated**: 1,148 of 1,148 admitted names, zero vendor failures.
Top it up after bar coverage grows — the pass is incremental, unclassified names queue first:

```bash
python tools/refresh_classifications.py --universe --budget 1200
```

## 3. Four things a fresh session must not get wrong

- **An UNSET parameter and an UNMEASURABLE input fail in opposite directions.** Unset refuses every
  candidate and names the parameter; a pair that could not be correlated, an instrument that could
  not be classified, or a split that could not be checked all **admit** and report `unavailable`.
  `DR-006` §3 forbids the second from becoming the first. Both test files keep them apart on
  purpose; if a change makes them behave alike, the tests are what will say so.
- **`conftest.make_bars` gives every instrument the SAME closes**, so any two fixture instruments
  correlate at exactly **r = 1.00**. `make_bars(zigzag=True)` is the second path and the two measure
  about **-0.03** apart. A test about capacity or ordering that puts a held name on the walking path
  is testing correlation instead, whatever its name says.
- **`actions_fetcher` defaults to None**, which reads the store without fetching. That is what keeps
  the suite offline; production wires `vendor_yahoo.fetch_actions` in `cli.py` and a test asserts it.
- **Both stores are read as-of and filled by DIFFERENT passes.** Reading the classification store at
  the bar store's knowledge time hides every classification pulled since the last bar refresh — on a
  first run, all of them. `pipeline.py` reads both at the RUN's clock; a tool that did otherwise
  reported zero classified over a store holding 1,148.

## 4. On the owner — three rulings, all with measurements under them

None is blocking, and all three are fine left `assumed`: `DR-014` makes this paper-only, so nothing
they govern is spending real money today.

| | recommendation | where |
|---|---|---|
| `data.revision_epsilon` | keep 0.001, **scope it to `close`** — over all four price fields it raises ~94 `Critical` per evening, over `close` alone it fires zero times | `DR-016` §8.4 |
| correlation cap | keep the refusal; the size adjustment is unnecessary rather than unauthored | `DR-006` §15.4 |
| `risk.max_sector_risk` | keep 2R; 1.33R would refuse half of every book | `DR-006` §14.4, §16.4 |

Also open and unchanged: `DR-017` (ADTV lag), `account.fx_rate_cad` (needs a source and an as-of),
`data.staleness_action_threshold` (a ruling or an explicit retirement).

## 5. What the next engineering session could pick up

Ranked by what actually moves the finish line rather than by size.

1. **The write-time revision comparison** — the only half of `DR-016` still unbuilt, and the only
   half its parameter gates. Waits on §4's first ruling.
2. **Component activation.** `CHARTER.md` §4 requires every displayed number to trace to a
   registered component with a validation status, and **1 of 465** is `active`. Six are `specified`
   and awaiting activation (`TODO.md` §6). This is the largest single gap on the ratified finish
   line.
3. **The 12 journalled runs recorded against a dirty tree**, which cannot be replayed from their SHA
   and therefore hold `a.reproducible` short of its own definition.
4. **Bar coverage at 28.3%.** It bounds any wider study, and it is the one item that is pure
   throughput — `tools/refresh_universe.py --budget 500`, repeatedly.

## 6. Before you start

```bash
git worktree list && git branch -a
```

Run the gates with `PYTHONPATH=$PWD/src`. From a worktree, gates 23, 24 and 26 correctly report
`UNAVAILABLE`; point them at the real stores with
`SWINGDESK_DATA=C:/PycharmProjects/SwingDesk/data` when you need the runtime figures.

**Track A restarted 2026-08-22 and this session moved decision output again** — `pipeline.py` is
frozen under `DR-015` §3, so the counter resets, and it already read 0. Derive it with
`python tools/track_a_streak.py` from the MAIN checkout, never from a line in a document.
