# DR-026: An "order" in `D1` means one that moves real money, so a paper venue is not the thing it forbids

```
date:            2026-08-31
status:          accepted — the D1 reading ruled by the owner 2026-08-31. §5 is NOT ruled and is
                 not part of this record; it needs its own decision
parameters:      none. No threshold is introduced and none is needed
components:      none new. Places swingdesk.broker (ADR-0005)
implemented_by:  src/swingdesk/broker/policy.py :: def check_method
                 also registry/broker_policy.yml and tools/verify_broker_policy.py (gate 39)
built:           2026-08-31
```

## 1. What was asked, and what was ruled

The owner instructed on 2026-08-31 that Alpaca paper trading be wired so strategies and guesses can
be tested against a real venue. `TODO.md` §6b raised the obstacle: `D1` says this system never
places orders, and `ActionKind`'s own docstring says *"Nothing here has an execute verb."*

The owner ruled:

> *"treat выставление заявок as not a crossing rules, because its not a real money. Order only
> means the real one."*

**That reading is coherent with `D1`'s own stated reason, which is why it is recorded as an
interpretation rather than as an amendment.** `CHARTER.md` §3 gives the reason in the same row as
the non-goal: *"Removes the largest irreversible-risk surface entirely."* A paper venue has no
irreversible-risk surface. The rule and the ruling agree about what the rule was for.

## 2. The decision

**`D1`, `BR-1` and `SECURITY.md` §3 forbid an order that can move the owner's money. A submission
to a paper venue with no owner capital behind it is not that order.**

Three things follow immediately and all three are already true in the tree:

1. **The paper/live boundary is a committed allowlist, not a habit.** Measured against Alpaca's API
   reference 2026-08-31: **the account object carries no field saying whether an account is paper
   or live.** `id`, `status`, `currency`, `equity` and `trading_blocked` are identical in both, so
   there is nothing in any response this software could check. **Which host was called is the only
   difference that exists.** `registry/broker_policy.yml` therefore carries exactly one host, names
   the live host under `forbidden_hosts`, and gate 39 fails the build on either being wrong.
2. **Alpaca's own `APCA_API_BASE_URL` override is deliberately not read.** An environment variable
   that can redirect this software at a live brokerage is a boundary one shell export wide.
3. **Nothing in the tree can write today, and that is structural rather than promised.** The policy
   permits `GET` only, `policy.check_method` refuses at the call, and gate 39 reads
   `src/swingdesk/broker/` from the syntax tree for any URL or any of `POST`/`PUT`/`PATCH`/`DELETE`.
   Verified by planting a `POST` literal and watching the gate go red (`AGENTS.md` §10.8).

## 3. What this record does NOT do

**It does not touch three constraints whose stated reason is not money, and this is the load-bearing
half of the record.** The owner's ruling answers `D1`, whose reason is irreversible risk. These
three give different reasons, and none of them mentions capital:

| | Where | Its stated reason |
|---|---|---|
| **No automated trading of any kind** | `CHARTER.md` §3 non-goal | *"The course requires documented human judgment at named points (§3.8). An autonomous path would violate its own governance model."* |
| **The final trading decision is human-only** | `CHARTER.md` A-001 §1 | *"Absolute, and stronger than a non-goal because it admits no configuration."* It extends `D1` from placing to **deciding**. |
| **An agent that trades is excluded** | `CHARTER.md` A-001 §2 | *"directly, on a schedule, or by any delegation — excluded by the charter, not by configuration."* |

**So paper money removes the risk argument and leaves the governance argument standing.** A system
that submits a paper order **the owner approved** satisfies all four constraints, because the human
made the decision and the machine only carried it. A system that submits an order *because the scan
produced a candidate* satisfies `D1` under this ruling and still fails all three of the above.

That distinction is not a technicality and it is not this record's to resolve — see §5.

## 4. What a write path must carry before it exists

Recorded now so the next session does not re-derive it, and so that "wire up ordering" is visibly
a decision rather than a wiring task:

1. **A decision record of its own**, naming which of §3's three constraints it rests on.
2. **`access.write_enabled: true` in the committed policy** — which `policy.load` refuses today,
   deliberately, because the code it governs cannot write. Flipping it is a commit a reviewer sees.
3. **Per-order human approval through the existing mechanism.** `swingdesk respond POS-N SEQ
   --approve --reason "…"` already writes the owner's reason and the moment they answered into the
   append-only response table (`AGENTS.md` §14, `DR-013` §2.2). A paper order gated on that record
   is the shape §3's three constraints already permit.
4. **A kill switch that is not a code change** — one file or one environment variable the owner can
   set to stop submission, checked before every request.
5. **A `client_order_id` this system sets.** Today the venue reports an order id and a symbol, and
   `contracts.position.Fill` settles a `position_id` and an approved `sequence`; nothing in a
   venue's answer carries either, so `broker.reconcile` reports unmatched executions and refuses to
   guess which action they settle. **A wrong join there would write evidence against a plan that
   did not produce it, which is the `HINDSIGHT` control turned inside out.** Only an id this system
   chose closes that, and only the write path can choose one.
6. **Bracket submission, if the stop is to be readable.** A broker's answer cannot construct a
   `Position` — the venue knows symbol, quantity and average entry and does **not** know the stop,
   which is what `RISK_SPEC.md` §2 denominates every `R` in. A stop leg placed with the entry is
   the only way that fact exists at the venue at all.

## 5. The question this record does NOT answer, and it is the owner's

**May the system submit a paper order that no human approved order-by-order?**

`D1` no longer blocks it. `CHARTER.md` §3's automated-trading non-goal and A-001 §1–§2 still do,
and their reason is the course's governance model rather than the size of the loss. Answering it
means either accepting that the approval step stays — which is cheap, since the mechanism exists
and the book is empty — or amending A-001, which is a charter amendment and says so in its own
text: *"admits no configuration."*

**Nothing is being built against either answer until it is given.** `TODO.md` carries it.

## 6. What would overturn §2

Real money reaching the venue by any route: a live key pair in the environment the policy names, a
second entry in the allowlist, or a funded paper account being made live in place. All three are
`DR-014`'s subject, and the first is the one no gate can see — a key is a value, and this
repository never holds one.
