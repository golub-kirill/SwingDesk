"""Gate 20's index check: the table and the records must tell an owner the same thing.

Added 2026-09-15, after the two disagreed and the owner was told two decisions they had already
made were still waiting on them. The gate read every record header and never the table.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import verify_decisions as gate

ROW = "| `{id}` | a question | a decision | nothing | {status} |"


def _index(*rows: tuple[str, str]) -> str:
    """An index section shaped like the real one, carrying the given (id, status cell) rows."""
    head = ("## 5. Index\n\n| ID | The question it answers | Decision | Sets | Status |\n"
            "|---|---|---|---|---|\n")
    return head + "\n".join(ROW.format(id=rid, status=status) for rid, status in rows) + "\n"


def test_a_status_word_is_read_out_of_the_prose_beside_it() -> None:
    """Rows carry their verdict in prose - dates, counts, caveats - and the word is what matters."""
    rows = gate.index_statuses(_index(
        ("DR-001", "**accepted — ratified 2026-09-14**"),
        ("DR-002", "**proposed — binds a real account**"),
        ("DR-003", "**superseded by `DR-010`**"),
    ))
    assert rows == {"DR-001": "accepted", "DR-002": "proposed", "DR-003": "superseded"}


def test_a_line_that_is_not_a_row_is_not_read() -> None:
    assert gate.index_statuses("prose about `DR-001` and a table that is not here") == {}


def test_the_disagreement_that_cost_a_wrong_answer_is_caught() -> None:
    """THE REGRESSION. `DR-003` and `DR-006` read `accepted` in their headers since August while the
    index still said `proposed`, and the project answered the owner from the index."""
    failures = gate.disagreements(
        {"DR-003": "accepted — ratified by the owner 2026-08-23", "DR-006": "accepted — fully"},
        {"DR-003": "proposed", "DR-006": "proposed"},
    )
    assert len(failures) == 2
    assert all("accepted" in failure and "proposed" in failure for failure in failures)
    assert "DR-003" in failures[0] and "DR-006" in failures[1], "sorted, so the output is stable"


def test_agreement_is_silent() -> None:
    assert gate.disagreements(
        {"DR-001": "accepted — ratified 2026-09-14", "DR-002": "proposed, awaiting the owner"},
        {"DR-001": "accepted", "DR-002": "proposed"},
    ) == []


def test_a_record_the_index_does_not_carry_is_a_failure() -> None:
    [failure] = gate.disagreements({"DR-044": "accepted"}, {})
    assert "DR-044" in failure and "no row" in failure


def test_a_row_with_no_record_is_a_failure() -> None:
    [failure] = gate.disagreements({}, {"DR-099": "accepted"})
    assert "DR-099" in failure and "no record file" in failure


def test_the_committed_index_agrees_with_every_committed_record() -> None:
    """The live check, on the real files: this is the state the gate now holds."""
    records = {
        path.name[:6]: gate.parse_header(path.read_text(encoding="utf-8")).get("status", "")
        for path in sorted(gate.DECISIONS.glob("DR-*.md"))
    }
    assert records, "there are decision records to check"
    rows = gate.index_statuses(gate.INDEX.read_text(encoding="utf-8"))
    assert gate.disagreements(records, rows) == []
