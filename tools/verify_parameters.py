"""Enforce the parameter-registry contract.

The course supplies no numeric thresholds, so every threshold in this system is authored. The risk
is not that a value is wrong - it is that a value silently acquires the authority of a measurement.
These checks make that impossible: a parameter cannot carry a value without saying where it came
from, and an unset parameter cannot be mistaken for a default.

Checks:
  1. Every entry has id, unit, value, status, provenance, named_in, read_by, ui_editable.
  7. `read_by` names the code that CONSUMES the value, and it resolves - `module:symbol`, imported
     and checked, exactly the way `implements` is resolved in the component registry. `none` is the
     honest alternative and is counted rather than hidden.

     Added 2026-08-18, and the measurement that bought it: **23 parameters carried a value that no
     line of code read**, fourteen of them from `DR-007` alone. The registry recorded where the
     course MENTIONS a concept (`named_in`) and where the value CAME FROM (`provenance`), and
     nothing at all about whether anything consumed it. Three separate findings in one week -
     the exit policy, the staleness gate, the corporate-actions gate - were all the same shape:
     specified, implemented or not, and wired to nothing. A ratified decision that reaches no code
     is a decision that did not happen, and until this field existed there was no way to see it.
  2. Ids are unique and namespaced (`group.name`).
  3. status is one of unset | assumed | owner | validated, and agrees with value/provenance:
       - value null            <=> status unset  and provenance null
       - status assumed        =>  provenance starts with 'assumed:' and cites a source
       - status owner          =>  provenance is 'owner'
       - status validated      =>  provenance starts with 'validated:' and cites an evidence id
  4. named_in is non-empty - a parameter with no course reference is either invented scope or a
     missing citation, and both need a human to look.
  5. A provenance citing a decision record (`assumed:DR-NNN`) resolves to a file in docs/decisions/.
     A citation nobody can follow is not a citation, and a DR id is the easiest thing in this
     registry to mistype or to leave pointing at a document that was never written.
  6. A parameter that CODE READS AS A NUMBER holds a number. Prose values are legitimate and
     deliberate here - `regime.classifier_rule` and `costs.commission_model` describe rules rather
     than quantities - so the rule is not "values are numeric". It is that the ones `decimal_value`
     is called on must parse, because there the failure is an uncaught InvalidOperation in the
     decision path rather than a coded refusal. Found the hard way: DR-006 set
     `risk.max_position_value` to "25% of account.equity - 2500 at the current value", which reads
     correctly and would have raised inside `size_long` the moment `risk.per_trade_pct` was set.

Usage:
    python tools/verify_parameters.py [--registry PATH]
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO / "registry" / "parameters.yml"

REQUIRED_FIELDS = ("id", "unit", "value", "status", "provenance", "named_in", "read_by",
                   "ui_editable")
VALID_STATUS = ("unset", "assumed", "owner", "validated")
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
DECISION_REF = re.compile(r"\b(DR-\d{3})\b")
DECISIONS_DIR = REPO / "docs" / "decisions"
SRC = REPO / "src"

#: Parameter ids passed to `ParameterRegistry.decimal_value`, scraped from the source rather than
#: listed here - a hand-kept list would drift the first time a call site moved.
NUMERIC_CALL = re.compile(r'decimal_value\(\s*"([a-z][a-z0-9_.]*)"')


def decision_record_exists(reference: str) -> bool:
    return any(DECISIONS_DIR.glob(f"{reference}-*.md"))


#: The `status:` line of a decision record's header block.
DECISION_STATUS = re.compile(r"^status:\s*(?P<status>\S+)", re.MULTILINE)


def status_from_text(text: str) -> str | None:
    """The first word of a decision record's `status:`, or None when it has no such line.

    Only the first word: the accepted ones carry a ratification clause after it ("accepted -
    ratified by the owner 2026-08-08") and the distinction that matters here is `proposed` against
    everything else. Split out from the file read so it can be tested on a string.
    """
    match = DECISION_STATUS.search(text)
    return match.group("status").rstrip(",;") if match else None


def decision_record_status(reference: str) -> str | None:
    """The status of `DR-NNN`, or None when there is no such record."""
    for path in sorted(DECISIONS_DIR.glob(f"{reference}-*.md")):
        status = status_from_text(path.read_text(encoding="utf-8"))
        if status is not None:
            return status
    return None


def numerically_read_ids() -> set[str]:
    """Every parameter id the code asks for as a Decimal."""
    return {
        match
        for path in SRC.rglob("*.py")
        for match in NUMERIC_CALL.findall(path.read_text(encoding="utf-8"))
    }


def load_entries(path: Path) -> list[dict[str, Any]]:
    try:
        import yaml
    except ModuleNotFoundError:
        print(
            "PyYAML is required for this check. It is the only non-stdlib dependency in tools/;\n"
            "install it into the project environment (pip install pyyaml).",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("parameters") or []


def reader_failure(entry: dict[str, Any]) -> str | None:
    """`None` when `read_by` resolves, or is the explicit `none`.

    Mirrors `verify_decisions.py`'s `implemented_by` / `implementation: none` pair, which caught a
    false implementation claim on its first run. A field checked only for presence is the defect
    this project keeps finding under other names; this one is imported and looked up.
    """
    label = entry.get("id", "<no id>")
    reader = entry.get("read_by")
    if reader is None:
        return f"{label}: no `read_by`. Name the code that consumes it, or write `none`"
    if reader == "none":
        return None
    if not isinstance(reader, str) or ":" not in reader:
        return f"{label}: `read_by` must be 'module:symbol' or 'none', got {reader!r}"

    module_path, _, symbol = reader.partition(":")
    try:
        module = importlib.import_module(module_path)
    except Exception as error:  # noqa: BLE001 - the message is the point
        return f"{label}: `read_by` cannot import {module_path} ({error})"
    if not hasattr(module, symbol):
        return f"{label}: `read_by` names {module_path}:{symbol}, which has no {symbol!r}"
    return None


def check(entries: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    seen: set[str] = set()

    for index, entry in enumerate(entries):
        label = entry.get("id") or f"<entry {index}>"

        missing = [f for f in REQUIRED_FIELDS if f not in entry]
        if missing:
            failures.append(f"{label}: missing required field(s) {missing}")
            continue

        if not ID_PATTERN.match(entry["id"]):
            failures.append(f"{label}: id must be lowercase 'group.name'")
        if entry["id"] in seen:
            failures.append(f"{label}: duplicate id")
        seen.add(entry["id"])

        status = entry["status"]
        value = entry["value"]
        provenance = entry["provenance"]

        if status not in VALID_STATUS:
            failures.append(f"{label}: status {status!r} not in {VALID_STATUS}")
            continue

        if value is None:
            if status != "unset":
                failures.append(f"{label}: value is null but status is {status!r}, expected 'unset'")
            if provenance is not None:
                failures.append(f"{label}: value is null but provenance is set")
        else:
            if status == "unset":
                failures.append(f"{label}: has a value but status is 'unset'")
            if not provenance:
                failures.append(f"{label}: has a value but no provenance")
            elif status == "assumed" and not re.match(r"^assumed:\s*\S+", str(provenance)):
                failures.append(
                    f"{label}: status 'assumed' requires provenance 'assumed:<citation>', "
                    f"got {provenance!r}"
                )
            elif status == "owner" and str(provenance).strip() != "owner":
                failures.append(f"{label}: status 'owner' requires provenance 'owner'")
            elif status == "validated" and not re.match(r"^validated:\s*\S+", str(provenance)):
                failures.append(
                    f"{label}: status 'validated' requires provenance 'validated:<evidence-id>'"
                )

        for reference in DECISION_REF.findall(str(provenance or "")):
            if not decision_record_exists(reference):
                failures.append(
                    f"{label}: provenance cites {reference}, and no docs/decisions/{reference}-*.md "
                    f"exists"
                )

        failure = reader_failure(entry)
        if failure:
            failures.append(failure)

        if not entry["named_in"]:
            failures.append(f"{label}: named_in is empty - cite the course topic or mark as authored")

    # 6. Values that code reads as numbers must be numbers.
    numeric = numerically_read_ids()
    for entry in entries:
        value = entry.get("value")
        if entry.get("id") not in numeric or value is None:
            continue
        try:
            Decimal(str(value))
        except InvalidOperation:
            failures.append(
                f"{entry['id']}: read by decimal_value() and its value {str(value)[:40]!r} is not a "
                f"number. Put the unit in `unit:` - a prose value here raises inside the decision "
                f"path instead of returning a coded refusal."
            )

    return failures


#: Statuses that make a criterion binding. Same set `verify_criteria.py` uses; a criterion still
#: being drafted makes no claim on the code.
_BINDING = frozenset({"ratified", "owner-set"})


def _criterion_citations(registry_path: Path) -> dict[str, list[str]]:
    """Parameter id -> the binding criteria that cite it. Empty if `criteria.yml` is unreadable.

    Reads the criteria beside the parameters rather than taking a path, because the two registries
    always live together and a criteria file found somewhere else would describe a different tree.
    """
    import yaml

    path = registry_path.parent / "criteria.yml"
    if not path.is_file():
        return {}
    try:
        criteria = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(criteria, dict):
        return {}

    citations: dict[str, list[str]] = {}
    for items in criteria.values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("status") not in _BINDING:
                continue
            text = " ".join(
                str(item.get(field, ""))
                for field in ("criterion", "trigger", "value", "measured_by", "action", "note")
            )
            for parameter_id in set(re.findall(r"\b[a-z_]+\.[a-z_0-9]+\b", text)):
                citations.setdefault(parameter_id, []).append(str(item.get("id")))
    return citations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()

    registry_path = args.registry
    entries = load_entries(args.registry)
    failures = check(entries)

    by_status: dict[str, int] = {}
    for entry in entries:
        by_status[entry.get("status", "?")] = by_status.get(entry.get("status", "?"), 0) + 1

    print(f"parameters: {len(entries)}")
    for status in VALID_STATUS:
        if status in by_status:
            print(f"  {status:<10} {by_status[status]}")

    # The number this field exists to make visible. A parameter with a VALUE and no reader is a
    # decision that was ratified and never reached the code - the shape behind the exit policy, the
    # staleness gate and the corporate-actions gate, all found within one week of each other. It is
    # NOT a failure: many are legitimately ahead of the consumer that will read them. It is a
    # measurement, and it was invisible until it was printed.
    orphans = [e for e in entries
               if e.get("read_by") == "none" and e.get("status") != "unset"]
    if orphans:
        print("")
        print(f"{len(orphans)} parameter(s) carry a VALUE that no code reads - decided, not wired.")
        print("Not a failure; a standing measurement:")
        by_provenance: dict[str, int] = {}
        for entry in orphans:
            key = str(entry.get("provenance"))
            by_provenance[key] = by_provenance.get(key, 0) + 1
        for provenance, count in sorted(by_provenance.items(), key=lambda kv: -kv[1]):
            print(f"  {count:>3}  {provenance}")

        # The subset that is NOT merely ahead of its consumer. A parameter cited by a RATIFIED
        # criterion and read by nothing means that criterion cannot fire - the criterion is real,
        # its threshold is set, and no code compares anything to it.
        #
        # Gate 3g cannot see this and says so in its own docstring: it checks that a criterion's
        # inputs EXIST, not that its logic discriminates. Existence and enforceability are different
        # claims, exactly as `named_in` and `read_by` are (section 7).
        #
        # FOUND 2026-08-24 by reading the registry by hand, which is the detection method
        # REQ-VALIDATION-001 says does not scale: `k.drawdown_pause` is ratified, scope `live`, its
        # threshold `validation.max_allowable_drawdown` is owner-set at 20, and nothing in `src/`
        # computes realised drawdown at all. It was the ONLY live criterion, so it was all of them.
        cited = _criterion_citations(registry_path)
        blocked = sorted({e["id"] for e in orphans} & set(cited))
        if blocked:
            print("")
            print(f"  of those, {len(blocked)} is/are cited by a RATIFIED criterion, which "
                  f"therefore cannot fire:")
            for parameter_id in blocked:
                print(f"    {parameter_id}  <- {', '.join(cited[parameter_id])}")

    # A second standing measurement, added 2026-08-25: a value whose only authority is a record
    # nobody ratified.
    #
    # Gate 1 check 5 already requires an `assumed:DR-NNN` citation to RESOLVE to a file. Nothing
    # asked whether that file was ever accepted, and `TODO.md` §4 records the shape in prose - four
    # records "proposed since 08-02, used as evidence". A proposed record constrains nothing, which
    # is the reasoning `DR-020` states about its own status, so a parameter resting on one is
    # carrying a number with no owner behind it.
    #
    # Reported rather than failed, deliberately. Ratifying a record is the owner's act and no agent
    # may take it (`AGENTS.md` §14), so a gate that went red here would demand a decision it cannot
    # get and would be bypassed - `CI_POLICY.md` §3. The same reasoning gate 1 already applies to
    # the orphan block above: a measurement that was invisible until it was printed.
    unratified: list[tuple[str, str, str]] = []
    for entry in entries:
        provenance = str(entry.get("provenance") or "")
        if not provenance.startswith("assumed:"):
            continue
        for reference in DECISION_REF.findall(provenance):
            record_status = decision_record_status(reference)
            if record_status is not None and record_status.startswith("proposed"):
                unratified.append(
                    (str(entry["id"]), reference, record_status)
                )
    if unratified:
        print("")
        print(f"{len(unratified)} parameter(s) rest on a decision record still `proposed` - a value "
              f"whose only authority is a record nobody ratified.")
        print("Not a failure; ratifying is the owner's act. A standing measurement:")
        for parameter_id, reference, _ in sorted(unratified):
            print(f"  {parameter_id:45s} <- {reference}")

    unset = by_status.get("unset", 0)
    if unset:
        print(
            f"\n{unset} parameter(s) unset. Components owning them return a coded refusal "
            f"rather than a default - see docs/02-domain/FAIL_CLOSED_POLICY.md."
        )

    if failures:
        print(f"\n{len(failures)} FAILURES", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\nparameter registry contract satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
