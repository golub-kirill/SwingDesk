"""Is this series current enough to decide on? (`DATA_QUALITY_SPEC` §2.1, `DR-015`).

The rule has been specified since the data-quality spec was written, and `calendar.sessions_behind`
has implemented the measurement correctly the whole time. What was missing was the number, and
`DR-015` supplies it: `data.freshness_window = 2` sessions. This module is the verdict that turns
the measurement into an outcome the decision path can act on.

**The window is a stopping rule, not a tolerance, and that is the part most likely to be misread**
(`DR-015` §2.1). A refetch is triggered by ANY staleness - `sessions_behind > 0` - not by reaching
the window. The window decides when to stop trying and drop the instrument. A Monday run against a
series ending Friday is ONE session behind, so it refetches before it computes anything; the window
would only matter if Monday's refetch failed and Tuesday's had too.

**Sessions, never calendar days.** Friday's bar on Monday is one session old and three calendar days
old. Counting days would declare the whole universe stale every Monday and refuse it
(`AGENTS.md` §3).

**This is not a theoretical gap.** Measured against the 2026-08-17 scheduled run before the gate was
built: of 1152 evaluated candidates, **67 (5.8%) ended the run one session behind** - their last
stored bar was Friday 08-14 while the last completed session was Monday 08-17. Every one of them was
sized and left on `Watch` against a stale close, and the report said `completeness clean` for all of
them, correctly: §2.2 looks for holes INSIDE the stored window, and a series that simply stops early
has no hole. Staleness and completeness are different questions, which is why the spec asks both.

Pure: no I/O, no clock, no registry read except the one explicit `window()` lookup. `as_of` is
passed in, never taken from the wall clock, so a replay measures freshness as of the run it replays.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from swingdesk.contracts.reference import Exchange
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import calendar as cal

#: The parameter this module exists to consume. `registry/parameters.yml` names this module back,
#: through `read_by`, and gate 1 imports and resolves it - so the two can never drift into the
#: "decided, but wired to nothing" state that `AGENTS.md` §7 was written for.
PARAMETER = "data.freshness_window"


class Verdict(Enum):
    """What the decision path should do about this series' age."""

    FRESH = "fresh"
    """Level with the last completed session. Proceed."""

    STALE = "stale"
    """Behind, but short of the window. Refetch, and refuse if it is still behind afterwards."""

    DROPPED = "dropped"
    """At or past the window. Stop trying - do not refetch, do not decide."""


@dataclass(frozen=True, slots=True)
class Assessment:
    """How far behind a series is, and what that means under the ruled window."""

    sessions_behind: int
    verdict: Verdict
    window: int
    last_bar: date

    @property
    def reason(self) -> str:
        """The text that travels on the refusal. One wording, used by every caller.

        Says the count AND the window, because "stale" alone tells the owner nothing about whether
        the system will recover on its own tomorrow.
        """
        sessions = "session" if self.sessions_behind == 1 else "sessions"
        if self.verdict is Verdict.DROPPED:
            return (
                f"data is {self.sessions_behind} {sessions} behind the last completed session "
                f"(last bar {self.last_bar}), at or past the {self.window}-session window "
                f"{PARAMETER} allows; the instrument is dropped from this run rather than refetched"
            )
        return (
            f"data is {self.sessions_behind} {sessions} behind the last completed session "
            f"(last bar {self.last_bar}) and a refetch did not bring it current"
        )


def window(registry: ParameterRegistry) -> int:
    """`data.freshness_window`, or `ParameterUnset` naming it.

    Deliberately NOT defaulted. An unset window makes every instrument refuse, which is loud and
    correct - the same fail-closed shape `pipeline._exit_policy` takes, and the same reason: a
    plausible invented number is the silent default this registry exists to prevent.
    """
    value, _ = registry.int_value(PARAMETER)
    return value


def assess(exchange: Exchange, last_bar: date, as_of: datetime, allowed: int) -> Assessment:
    """Measure the series' age and rule on it.

    `allowed` is passed rather than read, so the registry is touched once per run instead of once
    per instrument, and so this function stays testable without one.
    """
    behind = cal.sessions_behind(exchange, last_bar, as_of)
    if behind == 0:
        verdict = Verdict.FRESH
    elif behind >= allowed:
        verdict = Verdict.DROPPED
    else:
        verdict = Verdict.STALE
    return Assessment(sessions_behind=behind, verdict=verdict, window=allowed, last_bar=last_bar)
