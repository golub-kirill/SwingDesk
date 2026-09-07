"""Gate 44, and the fact that it binds nothing today is exactly why it needs these.

**A gate whose only evidence is a green run on a repository where nothing is in scope has not been
tested — it has been observed not firing.** All twelve pre-registrations predate the rule, so the
live suite exercises the exempt branch and nothing else. Every fixture here builds its own
`docs/prereg` in a temporary directory.

The four ways this gate could be useless and none of them raises:

* it never fails, because the required pattern matches something every document has;
* it fails on the exempt ones, which would make the rule unlandable and get it deleted;
* it treats the boundary date as `>=` or `>` inconsistently with what the rule says;
* it accepts the header line as present when it is empty after the colon.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

BOUND = """# PREREG: does it?

```
id:            PR-999
date:          2026-09-08
author:        somebody
status:        registered
```

## 3. Prediction
"""

EXEMPT = BOUND.replace("2026-09-08", "2026-08-01")
BOUNDARY = BOUND.replace("2026-09-08", "2026-09-07")
STATED = BOUND + "\nminimum detectable effect: 4% a year, from PR-014's interval half-width.\n"
POWER_FLOOR = BOUND + "\n**power floor**: 50 points end to end, registered before any number.\n"
EMPTY = BOUND + "\nminimum detectable effect:\n"


@pytest.fixture
def gate(tmp_path, monkeypatch):
    monkeypatch.setenv("SWINGDESK_ROOT", str(tmp_path))
    (tmp_path / "docs" / "prereg").mkdir(parents=True)
    spec = importlib.util.spec_from_file_location(
        "_minimum_effect", REPO / "tools" / "verify_minimum_effect.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, tmp_path / "docs" / "prereg"


def write(where: Path, name: str, body: str) -> None:
    (where / name).write_text(body, encoding="utf-8")


def test_a_study_registered_after_the_rule_and_silent_about_power_FAILS(gate):
    """The whole point. If this passes, the gate is decoration."""
    module, prereg = gate
    write(prereg, "PR-999-silent.md", BOUND)
    assert module.main() == 1


def test_the_same_study_passes_once_it_names_the_number(gate):
    module, prereg = gate
    write(prereg, "PR-999-stated.md", STATED)
    assert module.main() == 0


def test_power_floor_is_the_same_obligation_under_another_name(gate):
    """`PR-015` called it a power floor and it is what prompted the rule. Renaming a thing does not
    make it a different obligation, and refusing the word would push the next study to invent a
    third one."""
    module, prereg = gate
    write(prereg, "PR-999-floor.md", POWER_FLOOR)
    assert module.main() == 0


def test_a_header_line_with_nothing_after_the_colon_does_not_satisfy_it(gate):
    """The cheapest way to pass a token check is to write the token. `\\S` after the separator is
    what stops that being enough."""
    module, prereg = gate
    write(prereg, "PR-999-empty.md", EMPTY)
    assert module.main() == 1


def test_a_study_registered_before_the_rule_is_exempt_and_does_not_fail_it(gate):
    """If the rule failed the twelve documents that predate it, it could not be landed without
    either editing registered documents or downgrading them - so it would be deleted instead."""
    module, prereg = gate
    write(prereg, "PR-001-old.md", EXEMPT)
    assert module.main() == 0


def test_the_boundary_day_itself_is_exempt(gate):
    """The rule was made on 2026-09-07 and binds studies registered AFTER it. `PR-015` is dated
    that day, is already reported, and states its resolving power under the other name - so an
    off-by-one here would either downgrade a reported study or silently excuse the next one."""
    module, prereg = gate
    write(prereg, "PR-015-boundary.md", BOUNDARY)
    assert module.main() == 0
    assert module.RULED_ON.isoformat() == "2026-09-07"


def test_an_undated_pre_registration_fails_rather_than_slipping_through(gate):
    """Not knowing when a document was written is not a reason to excuse it. The exempt branch is
    the only way to pass without the line, and it needs a date to reach."""
    module, prereg = gate
    write(prereg, "PR-999-undated.md", "# PREREG\n\n```\nid: PR-999\n```\n")
    assert module.main() == 1


def test_the_exempt_ones_are_listed_and_not_swallowed(gate, capsys):
    """"Exempt" and "not checked" are the same outcome and different claims - the distinction
    `trial_budget.py` already draws between UNDECLARED and zero."""
    module, prereg = gate
    write(prereg, "PR-001-old.md", EXEMPT)
    module.main()
    printed = capsys.readouterr().out
    assert "PR-001-old.md" in printed
    assert "exempt" in printed
