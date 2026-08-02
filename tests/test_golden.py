"""Golden vectors, and proof that the gate guarding them can actually fail.

A gate that cannot be made to fail is theatre, so three of these four tests deliberately break
something and assert the breakage is reported. They operate on a copy of the vector tree - never on
the committed one.
"""

from __future__ import annotations

import json
import shutil

import pytest

from swingdesk.derived_observations import atr
from swingdesk.validation import golden

COMPONENT = atr.COMPONENT


@pytest.fixture
def vectors(tmp_path):
    """A writable copy of the committed vector tree."""
    root = tmp_path / "components"
    shutil.copytree(golden.GOLDEN_ROOT, root)
    return root


def test_vectors_hold() -> None:
    """The committed vectors recompute exactly. This is the gate itself."""
    assert golden.verify() == []


def test_every_vector_is_registered() -> None:
    """A vector on disk but not in the manifest is unhashed, and therefore unguarded."""
    manifest = json.loads((golden.GOLDEN_ROOT / "manifest.json").read_text(encoding="utf-8"))
    on_disk = {path.name for path in (golden.GOLDEN_ROOT / COMPONENT).glob("*.json")}
    assert on_disk == set(manifest["components"][COMPONENT]["vectors"])
    assert on_disk, "the component claims vectors; it must have some"


def test_gate_catches_an_edited_vector(vectors) -> None:
    """Editing a vector without rehashing is caught. This is the anti-tampering check."""
    path = vectors / COMPONENT / "gap_up.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["expected"][-1] = "99.99"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    failures = golden.verify(vectors)
    assert any("content changed" in failure for failure in failures)


def test_gate_catches_changed_behaviour(vectors) -> None:
    """Recomputation is real, not an identity.

    Changing an *input* while rehashing - the shape a genuine behaviour change takes - must surface
    as a value mismatch rather than passing because the file agrees with itself.
    """
    path = vectors / COMPONENT / "gap_up.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["bars"][-1][2] = "120.00"  # widen the gap: high 110.00 -> 120.00, so TR 10 -> 20
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    golden.rehash(vectors)

    failures = golden.verify(vectors)
    assert any("gap_up.json[15]" in failure for failure in failures)


def test_gate_catches_an_unregistered_vector(vectors) -> None:
    """A new case must be registered, or it is guarded by nothing."""
    shutil.copy(vectors / COMPONENT / "flat_bars.json", vectors / COMPONENT / "unregistered.json")

    failures = golden.verify(vectors)
    assert any("not in the manifest" in failure for failure in failures)


def test_gate_catches_a_version_drift(vectors, monkeypatch) -> None:
    """A component version that moved without its vectors moving is a blocking failure."""
    monkeypatch.setattr(atr, "VERSION", atr.VERSION + 1)

    failures = golden.verify(vectors)
    assert any("version bump" in failure for failure in failures)
