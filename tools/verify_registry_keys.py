"""Gate 40: no registry YAML file contains a duplicate key, because YAML drops one silently.

**What paid for it, 2026-09-01.** `registry/parameters.yml` carried TWO `note:` keys on
`screen.trend_definition` and two on `regime.classifier_rule`. YAML keeps the LAST one, so in both
cases the long, load-bearing note was **invisible to every tool that loads the registry** while
sitting in plain sight to anyone reading the file. What was dropped:

  - `screen.trend_definition` — *"STAYS UNSET BY EVIDENCE, and the family is CLOSED"*, the record of
    two refuted pre-registrations, and the sentence that prescribes how a value may ever be set
    there: **by owner preference, provenance `owner`, never `validated:`**. An LLM council read the
    file and cited that note; a tool reading the same file could not have seen it.
  - `regime.classifier_rule` — the 2026-08-16 downgrade from `validated:` to `assumed:`, the
    survivorship bound that quantifies how the result could be an artefact, and the sentence
    **"THE PROJECT NOW HAS ZERO VALIDATED PARAMETERS and that is the honest count."**

Nothing was wrong on the day either note was written. Both broke when a LATER edit appended a second
key, and the failure is silent by design: YAML's spec permits last-wins, `yaml.safe_load` does not
warn, and every gate kept passing over a registry that had quietly lost two of its most important
sentences.

**And the danger is not limited to prose.** The same mechanism would drop a duplicated `value`,
`provenance` or `read_by` without a word — a parameter could carry two values and the system would
silently use the second.

**Why a gate and not a review rule.** A duplicate key is an EXACT token, which is the standard
`AGENTS.md` §12 sets for a gate over a file: *"a gate over prose needs an exact token, or it becomes
noise"*. There is nothing to interpret here. Either a mapping names a key twice or it does not.

    python tools/verify_registry_keys.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, NamedTuple

import yaml

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
REGISTRY = REPO / "registry"


class _Duplicate(NamedTuple):
    path: str
    line: int
    key: str
    first_line: int


def _duplicates(path: Path) -> list[_Duplicate]:
    """Every key named twice inside one mapping, anywhere in the document.

    Implemented by overriding the mapping constructor rather than by parsing the text: an indented
    `key:` inside a block scalar is not a key, and a regex would report those. The loader already
    knows the difference.
    """
    found: list[_Duplicate] = []

    class Detector(yaml.SafeLoader):
        pass

    def _mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> Any:
        seen: dict[Any, int] = {}
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            line = key_node.start_mark.line + 1
            if key in seen:
                found.append(_Duplicate(path.as_posix(), line, str(key), seen[key]))
            seen[key] = line
        return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

    Detector.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)
    yaml.load(path.read_text(encoding="utf-8"), Detector)
    return found


def main() -> int:
    if not REGISTRY.is_dir():
        print(f"  {REGISTRY} does not exist")
        return 1

    files = sorted(REGISTRY.glob("*.yml"))
    failures: list[_Duplicate] = []
    for path in files:
        try:
            failures += _duplicates(path)
        except yaml.YAMLError as error:
            print(f"  {path.name}: will not parse - {error}")
            return 1

    for duplicate in failures:
        print(
            f"  {duplicate.path}:{duplicate.line}: {duplicate.key!r} is named twice in one mapping "
            f"(first at line {duplicate.first_line}). YAML keeps the LAST one and drops the other "
            f"WITHOUT WARNING, so whatever is above is invisible to every tool that loads this file."
        )

    print(f"\nregistry keys: {len(files)} file(s) read, {len(failures)} duplicate(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
