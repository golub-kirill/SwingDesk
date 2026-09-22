"""Which function actually asks the registry for each parameter, recorded rather than read.

`registry/parameters.yml` carries `read_by` on every entry, and `tools/verify_parameters.py` checks
it the only way a linter can: it imports `module:symbol` and confirms the symbol exists. **Existing
is not reading.** A pointer at a function that never asks for the value resolves perfectly and
sends the next reader to a body that does not contain the id.

Text search cannot close the gap either, and it fails in BOTH directions:

  * `sizing.costs_per_share` builds the id with an f-string - `f"risk.costs_bp_{suffix}"` - so the
    literal `risk.costs_bp_usd` appears nowhere, and a text check calls a correct pointer wrong.
  * `account.equity`'s bare name `equity` appears in `size_long` as an ordinary local, so a text
    check called a WRONG pointer right. `size_long` calls `allowed_risk`, which is what reads it.

The stack does not guess. This runs the suite with `ParameterRegistry.use` recording the nearest
`swingdesk.*` frame above it, and prints every parameter whose recorded caller is not among the
ones `read_by` names.

**What it measured on 2026-09-21, its first run.** 32 of 113 parameters are asked for anywhere in
the suite. FOUR of those named a function that never asked:

  * `validation.max_allowable_drawdown` said `cli:_drawdown_now`; `cli:_submit` reads it. The note
    on the entry had said "NOT read by the decision path, deliberately... measurement, not
    enforcement" since 2026-08-30, and `DR-034` reversed that on 2026-09-03 - a breach halts every
    submission. Eighteen days of the registry describing the opposite of the code.
  * `account.equity` said `sizing:size_long`; it is read by `sizing:allowed_risk` AND
    `cli:_drawdown_now` - the risk denominator and the drawdown baseline, two jobs. Naming one hid
    the kill switch's dependence on it.
  * `risk.per_trade_pct` said `sizing:size_long`; `sizing:allowed_risk` reads it.
  * `management.proposal_expiry_days` said `cli:_expiry`, an ALIAS import; the function lives in
    `pending_view:expiry`.

**Run it on the WHOLE suite.** A slice accuses live pointers: `--tests tests/test_correlation.py`
reports `universe.adtv_lag_sessions` as naming a reader that never asked, and both
`universe.rule_from_registry` and `pipeline._adtv_lag` genuinely read it - that slice only exercises
the second. The output of a partial run is "not exercised here", never "wrong".

**Not a gate.** It needs the whole suite, which is eleven minutes, and a parameter nothing exercises
is reported as unexercised rather than as a failure - that is a coverage fact, not a false claim.
Run it when the registry's readers change, and after any change to who reads what.

Usage:
    python tools/measure_parameter_readers.py [--tests tests] [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

#: The recorder, written to a temporary directory and loaded with `-p`. It lives here as a string
#: rather than as a file in `tools/` because it is not a tool: it is only ever meaningful inside a
#: pytest process, and a module that patches a class on import is a trap sitting in a tools folder.
PLUGIN = '''
import atexit, inspect, json, os
from collections import defaultdict

OUT = os.environ["SWINGDESK_READER_LOG"]
seen = defaultdict(set)


def pytest_configure(config):
    from swingdesk.platform.parameters import ParameterRegistry

    original = ParameterRegistry.use

    def recording(self, parameter_id):
        frame = inspect.currentframe().f_back
        while frame is not None:
            module = frame.f_globals.get("__name__", "")
            if module.startswith("swingdesk.") and module != "swingdesk.platform.parameters":
                seen[parameter_id].add(f"{module}:{frame.f_code.co_name}")
                break
            frame = frame.f_back
        return original(self, parameter_id)

    ParameterRegistry.use = recording
    atexit.register(lambda: open(OUT, "w", encoding="utf-8").write(
        json.dumps({k: sorted(v) for k, v in seen.items()}, indent=1)))
'''


def entries() -> list[dict[str, Any]]:
    loaded = yaml.safe_load((REPO / "registry" / "parameters.yml").read_text(encoding="utf-8"))
    return list(loaded["parameters"])


def claimed_readers(entry: dict[str, Any]) -> set[str]:
    """The `module:symbol` names an entry claims. `none` claims nothing, which is not a failure."""
    reader = str(entry.get("read_by") or "none")
    if reader in {"none", "None", ""}:
        return set()
    return {part.strip() for part in reader.split(",")}


def record(tests: str) -> dict[str, list[str]]:
    """Run the suite with the recorder attached and return what asked for what."""
    with tempfile.TemporaryDirectory() as work:
        plugin_dir = Path(work)
        (plugin_dir / "_swingdesk_reader_log.py").write_text(PLUGIN, encoding="utf-8")
        log = plugin_dir / "reads.json"
        env = dict(os.environ)
        env["SWINGDESK_READER_LOG"] = str(log)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(plugin_dir), str(REPO / "src"), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
        print(f"running {tests} with the recorder attached - this takes about eleven minutes")
        subprocess.run(
            [sys.executable, "-m", "pytest", tests, "-q", "-p", "_swingdesk_reader_log"],
            cwd=REPO, env=env, check=False)
        if not log.exists():
            raise SystemExit("the recorder wrote nothing - did the suite start at all?")
        return dict(json.loads(log.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", default="tests", help="what to run (default: the whole suite)")
    parser.add_argument("--json", type=Path, help="write the recording here as well")
    args = parser.parse_args()

    asked = record(args.tests)
    by_id = {entry["id"]: entry for entry in entries()}
    if args.json:
        args.json.write_text(json.dumps(asked, indent=1), encoding="utf-8")

    wrong: list[tuple[str, str, list[str]]] = []
    for parameter_id, callers in sorted(asked.items()):
        entry = by_id.get(parameter_id)
        if entry is None:
            wrong.append((parameter_id, "NOT IN THE REGISTRY AT ALL", callers))
            continue
        if not (claimed_readers(entry) & set(callers)):
            wrong.append((parameter_id, str(entry.get("read_by") or "none"), callers))

    print(f"\n{len(asked)} of {len(by_id)} parameters were asked for anywhere in {args.tests}")
    unexercised = sorted(set(by_id) - set(asked))
    print(f"{len(unexercised)} were never asked for - a coverage fact, not a failure")
    print(f"\n{len(wrong)} name a reader that never asked:\n")
    for parameter_id, claim, callers in wrong:
        print(f"  {parameter_id}")
        print(f"     read_by  : {claim}")
        print(f"     asked by : {', '.join(callers)}\n")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
