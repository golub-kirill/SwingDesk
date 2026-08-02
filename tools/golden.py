"""Golden vector gate (CI_POLICY gate 8, TEST_STRATEGY 3).

    python tools/golden.py              check every vector
    python tools/golden.py --rehash     register hand-authored vectors, leaving expected untouched
    python tools/golden.py --regenerate rewrite expected from the implementation - a version bump

`--regenerate` is not a way to fix a red build. It is the second step of a deliberate behaviour
change, and the commit that carries it must also carry the version bump and the decision record.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.validation import golden  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="golden")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--rehash", action="store_true",
                      help="record hashes for vectors on disk; does not touch expected values")
    mode.add_argument("--regenerate", action="store_true",
                      help="rewrite expected values from the current code; requires a version bump")
    args = parser.parse_args(argv)

    if args.rehash:
        for name in golden.rehash():
            print(f"  registered {name}")
        print("manifest hashes updated; expected values untouched")
        return 0

    if args.regenerate:
        changed = golden.regenerate()
        for name in changed:
            print(f"  rewrote {name}")
        print(
            f"{len(changed)} vector(s) changed.\n"
            "This is a behaviour change. The same commit must bump the component version, carry a "
            "decision record, and reset the component's validation status "
            "(COMPONENT_REGISTRY_SPEC 6)."
        )
        return 0

    failures = golden.verify()
    for failure in failures:
        print(f"  {failure}")
    vectors = sum(
        len(list((golden.GOLDEN_ROOT / component).glob("*.json")))
        for component in golden.IMPLEMENTATIONS
    )
    print(f"--- golden vectors: {'PASS' if not failures else 'FAIL'} "
          f"({vectors} vectors, {len(golden.IMPLEMENTATIONS)} component(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
