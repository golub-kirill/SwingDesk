"""Determinism replay gate (CI_POLICY gate 9, DETERMINISM_SPEC 7).

    python tools/replay.py                   replay every stored case
    python tools/replay.py --record <dir>    run a case and freeze the manifest it produced

Recording is bootstrapping. It freezes current behaviour as the reference, so it can prove
behaviour has not changed since - not that it was right to begin with.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.validation import replay as harness  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="replay")
    parser.add_argument("--record", type=Path, default=None,
                        help="case directory to run and freeze")
    args = parser.parse_args(argv)

    if args.record:
        result = harness.record(args.record)
        print(f"recorded {result.case}: output_hash {result.actual}")
        print(f"  calendar {result.manifest.calendar_version} · "
              f"config {result.manifest.config_hash} · "
              f"components {result.manifest.component_versions}")
        if result.manifest.code_dirty:
            print("  note: recorded from a dirty working tree")
        return 0

    failures = harness.verify()
    for failure in failures:
        print(f"  {failure}")
    cases = sum(1 for p in harness.REPLAY_ROOT.iterdir() if (p / "case.json").exists())
    print(f"--- determinism replay: {'PASS' if not failures else 'FAIL'} ({cases} case(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
