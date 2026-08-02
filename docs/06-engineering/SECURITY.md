# SECURITY

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored

Threat model for a single-user, local, offline-first tool. Most of what a hosted system needs does
not apply here; what remains is specific and worth doing properly.

---

## 1. What is actually at risk

| Asset | Exposure | Consequence if lost |
|---|---|---|
| **Broker API credentials** | Questrade refresh token, second-source only | account access — the highest-consequence secret in the system |
| Vendor API keys | any paid or keyed feed | quota theft, account suspension |
| Firebase service credentials | push only | ability to send notifications as this app |
| Journal and positions | local | reveals holdings and strategy |
| The course PDFs | local | owner's own material |

**One asset dominates.** A brokerage refresh token grants account access. Everything else is
inconvenience.

## 2. Rules for secrets

1. **Environment variables or an OS keyring. Never a file in the repo, never an argument.**
   Command-line arguments appear in shell history and process listings.
2. **`.gitignore` covers `.env`, `*.key`, `serviceAccount*.json`, `firebase-adminsdk*.json`** —
   already in place, and defence in depth rather than the primary control.
3. **Masked at the log handler**, not at each call site. A rule requiring every caller to remember
   is a rule that fails on the first hurried commit.
4. **Never in an error message, a traceback, a report, or a Telegram card.**
5. **Never in a manifest.** Run manifests record config *hashes*, not config values
   (`DETERMINISM_SPEC.md` §5) — this is one reason why.
6. **Questrade refresh tokens are single-use.** Each exchange returns a new one; the old one dies.
   A token that has been pasted anywhere is spent and must be regenerated.

## 3. What the system must never do

- **Place, modify or cancel an order.** `BR-1`, and the reason the broker credential is
  read-only-by-use even though the API is not read-only by scope.
- **Ask for a password.** No flow in this system needs one.
- **Send data off-machine.** Firebase carries a title and a reference id, never content
  (`PRODUCT_SURFACES.md` §3.4).
- **Log a request URL with credentials in the query string.** Questrade's OAuth exchange puts the
  refresh token in the query — that URL must never be logged.

That last one is specific and easy to get wrong: a generic "log the request URL on failure" handler
would leak the token precisely when something is going wrong and logging is most verbose.

## 4. Telegram

The approval channel is a control surface — it changes stops and takes partial exits
(`PRODUCT_SURFACES.md` §3.3).

| Rule | Reason |
|---|---|
| One chat id, verified once, pinned in config | an approval from any other chat is refused, not acted on |
| The bot token is a secret under §2 | it authenticates as the bot |
| Approvals are bounded choices, never free text | a free-text command channel is an unlogged code path |
| Every approval is journalled with its prompt | an action with no record did not happen |

## 5. Web panel

Deferred until the panel exists, decided before it ships:

- Bind to loopback only unless there is a reason not to.
- If it is ever reachable off-host, loopback-only stops being a control and real authentication is
  required. **The panel writes parameters** — it is not a read-only surface.

## 6. Dependencies

- Lockfile pinned; upgrades are deliberate.
- Three runtime dependencies today (`pydantic`, `pandas-market-calendars`, `pyyaml`), each carrying
  the ADR that introduced it. A small surface is a security property, not just an aesthetic one.
- `yfinance` is unofficial and scrapes a consumer site. Treat its output as untrusted input:
  validate shapes and ranges rather than assuming them.

## 7. Open items

- [ ] Keyring vs `.env`. A keyring is better for the broker token; `.env` is simpler for the rest.
      Likely both, split by consequence.
- [ ] Whether the Questrade token is stored at all, or supplied per invocation. Single-use rotation
      means storing it requires writing the new one back — which is a secret written to disk by the
      program.
- [ ] Telegram chat-id verification flow.
