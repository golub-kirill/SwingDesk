# DR-008: Collect the US symbol directory daily under local control

```
date:       2026-08-10
status:     accepted — ratified by the owner 2026-08-10
parameters: none — these are operational network limits, not trading parameters
components: none — the collector records reference data and changes no decision component
evidence:   measurements/directory-file-sizes-2026-08-10.json
supersedes: owner operating choice 2026-08-09 to keep the directory pull manual
implemented_by: tools/daily_run.cmd :: fetch_directory.py
```

## Decision

The existing Windows daily wrapper will invoke the US symbol-directory collector after the trading
scan. The collector is a sidecar: its failure is visible and audited, but the wrapper returns the
scan's saved exit code.

The collector runs only when the ignored local file `.swingdesk-local.json` explicitly contains:

```json
{
  "directory_pull_enabled": true
}
```

A missing file or `false` leaves collection disabled and visible. Invalid JSON or a non-boolean
value refuses collection; no value is coerced and there is no committed enable default.

Normal collection is eligible only on an NYSE trading date, after the latest session has completed.
It downloads the two fixed HTTPS files from `nasdaqtrader.com`, once each per attempt. It may retry
one failed attempt after 60 seconds. A successful session is not fetched again automatically.
Weekends, NYSE holidays, disabled mode and an already-recorded session make zero requests. There is
no automatic historical backfill.

Each response body is capped at **2 MiB**. The cap applies to both `Content-Length` and bytes actually
read and cannot be bypassed. Both files must pass strict UTF-8, exact header and row shape, a valid
final `File Creation Time`, matching completed-session dates, non-empty parse and checksum creation
before either becomes canonical. The source URLs, retry budget, timeouts, cap and staleness levels
live in one committed machine-readable policy and are merge-gated.

The emergency command is explicit and temporary:

```powershell
python tools/fetch_directory.py --emergency-repull --reason "source recovered after malformed first response"
```

It has no daily or lifetime invocation quota. Every command requires a new non-empty reason, makes
one two-file attempt with no internal retry, and is recorded as `FORCED`. It may bypass only the
already-recorded-session guard and the normal retry budget. It does not bypass local disablement,
the NYSE calendar, source allowlist, response cap, validation, process lock or audit.

If a valid same-session snapshot already exists, a successful forced pull appends a replacement and
an append-only supersession record. The previous snapshot remains stored but is no longer canonical.
A failed forced pull changes nothing canonical.

Only validated parsed fields, source timestamps and checksums are stored with a snapshot. Invalid
response bodies are discarded. Each invocation stores at most one compact aggregate audit row:
timestamps, mode and reason, enabled state, attempt count, HTTP request count, received bytes, result
code and successful snapshot id. No raw response archive, dashboard, notification service or second
log is created.

The first session-aware snapshot is a baseline and creates no historical arrival or departure claim.
Subsequent missing NYSE sessions are recorded as gaps, never backdated observations. One consecutive
miss is a log `WARNING`; two or more are `ERROR`. Research claiming continuous survivorship coverage
must query and disclose those gaps.

## Why this one

`nasdaqlisted.txt` and `otherlisted.txt` publish current state, not a public archive. Once a session
passes without a local observation, its exact directory cannot be recovered from those files. The
existing `DirectoryStore.departures()` is therefore useful only from the dates actually collected.

The owner wanted daily evidence without an uncontrolled fetcher. Local enablement keeps the owner in
control; a committed policy and runtime meter bound automatic traffic; explicit forced commands
allow recovery from a dead first pull, a repaired integrity gate or a snapshot later found wrong.
The accepted cap has substantial headroom over the dated HEAD measurement named in the record while
remaining small enough to stop an accidental or hostile response before it is held in memory.

Keeping the collector after the scan prevents reference-data collection from deciding whether the
Track A trading run completes. Keeping it in the same wrapper avoids a second scheduled task, second
credential context and second scheduling surface.

## Alternatives rejected

| Alternative | Why rejected |
|---|---|
| Keep every pull manual | loses forward-only survivorship evidence whenever the owner forgets or is unavailable |
| A separate scheduled task | duplicates scheduling, logon and monitoring state without improving the two-request job |
| Committed enablement | removes the owner's local off switch and makes a clone fetch merely by existing |
| Run before the scan | couples new reference data and network delay to the Track A measurement |
| Fail the scan when collection fails | converts an evidence-sidecar fault into a false trading-run failure |
| Unlimited retry inside one command | can hammer the source without a new human decision |
| A hard quota on explicit forced commands | can block recovery from repeated independent source or gate failures |
| Allow `FORCED` to bypass validation | can promote malformed data into the canonical point-in-time store |
| Preserve invalid response bodies | adds storage and incident data that the system does not need to answer membership questions |
| Reconstruct missed days from the current file | backdates present knowledge and manufactures point-in-time evidence |
| Add a paid historical product | conflicts with the accepted zero-cost data decision and is not the same full-directory snapshot |

## What would overturn this

- The public files gain a verified historical full-snapshot archive. That could support a separately
  labelled backfill path; it would not rewrite existing gaps.
- The source terms, host, schema or delivery mechanism change. Collection stays disabled until the
  allowlist, validator and decision are revised together.
- Measured response growth approaches the 2 MiB cap. A new accepted decision changes the cap after a
  fresh measurement; code does not raise it automatically.
- Daily collection creates a demonstrated operational burden disproportionate to the evidence. The
  owner can turn it off immediately; a new decision would retire or replace this schedule.

## Consequences

1. The machine-readable policy, local example, runtime guard and merge gate land together. A limit
   duplicated as a code default would defeat this decision.
2. `DirectoryStore` must stop replacing a record at the same knowledge instant. Corrections append
   versions and supersession records.
3. Existing pulls remain readable as legacy snapshots but cannot be relabelled with source-session
   dates they never stored.
4. `daily_run.cmd` always logs one `[DIRECTORY]` line after the scan and always exits with the saved
   scan code.
5. CI uses fixtures only. It never calls NASDAQ Trader or writes the real database.
6. Canada remains unresolved and separate. Nothing about this decision extends US evidence to `.TO`.

