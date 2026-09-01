"""The kill switch, and it is stopped until the owner says otherwise.

`DR-027` §4.2. A file the owner creates in the data directory - never in this repository, because a
switch that ships in a commit is a release rather than a switch.

**Every path through this module that is not an explicit, readable, correctly-marked file returns
STOPPED**, and that is the whole design:

  - no write permission in the policy -> stopped
  - the file does not exist -> stopped
  - the file cannot be read -> stopped
  - the file is empty, or does not carry the marker -> stopped

**A switch that defaults to ON is not a kill switch**, and one that fails open is the inversion this
project has already paid for once: `DR-025` §2.1 records a guard whose refusal ADMITTED the
candidate, so "fail closed" read correct and behaved backwards. Here the polarity is the ordinary
one and it is checked rather than assumed - `test_armed.py` asserts the stopped answer for each of
the four causes separately, because a switch that is stopped for the wrong reason is a switch
nobody can debug on the evening it matters.

The remedy for a machine submitting something it should not is deleting one file. That is the
reason this is a file and not a flag inside a command: a flag is only ever as available as the next
release.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from swingdesk.broker.policy import WritePolicy


@dataclass(frozen=True, slots=True)
class Arming:
    """Whether submission is permitted, and why - the reason travels either way.

    `reason` is populated when armed as well as when stopped. A log line saying only *stopped* is
    one the owner cannot act on, and a log line saying only *armed* is one nobody can audit.
    """

    armed: bool
    reason: str

    @property
    def stopped(self) -> bool:
        return not self.armed


#: What a client gets when nobody made an arming decision. The safe state is the one you reach by
#: forgetting, which is the only kind of safe default worth having.
STOPPED = Arming(False, "no arming decision was made; submission is stopped by default")


def read(data_dir: Path, write: WritePolicy | None) -> Arming:
    """Is submission armed? Anything short of an explicit yes is `no`.

    `data_dir` is the directory the command was given, so the switch sits with the stores it
    governs and is covered by the same `.gitignore`.
    """
    if write is None:
        return Arming(False, "the committed policy grants no write permission (access.write_enabled)")

    switch = data_dir / write.kill_switch_file
    if not switch.exists():
        return Arming(
            False,
            f"{switch} does not exist. Submission is stopped until the owner arms it by writing "
            f"{write.armed_marker!r} into that file.",
        )

    try:
        content = switch.read_text(encoding="utf-8", errors="replace")
    except OSError as unreadable:
        # A switch that cannot be read is stopped, never assumed-armed. This is the branch where a
        # fail-open default would be invisible: nothing is wrong with the account, nothing is wrong
        # with the venue, and the machine would trade.
        return Arming(False, f"{switch} could not be read ({unreadable}); submission is stopped")

    if write.armed_marker not in content:
        return Arming(
            False,
            f"{switch} does not carry {write.armed_marker!r}; submission is stopped. An empty or "
            f"accidental file does not arm anything.",
        )

    return Arming(True, f"armed by {switch}")
