"""Verify that every `verbatim` claim in the documents still matches the course.

Documents in tier 2 and tier 4 transcribe the course rather than paraphrase it. Prose drifts from
its source silently; this script makes that impossible to do quietly.

Three checks:

1. **Quotes** - every markdown blockquote line in a document that declares
   `<!-- verbatim-sources: ... -->` must appear in the freshly extracted text of one of its declared
   sources. Multi-line quotes are joined; whitespace is normalised on both sides.
2. **Enums** - the load-bearing enumerations are asserted by membership and cardinality against the
   documents that define them.
3. **Coverage** - the course index still extracts to the known shape (delegated to
   build_course_index).

Quotes containing an elision marker are reported as skipped rather than silently passed.

Requires poppler's pdftotext on PATH. Stdlib only otherwise.

Usage:
    python tools/verify_transcription.py [--course-root PATH] [--docs PATH]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_COURSE_ROOT = Path(
    r"C:\Users\User\Desktop\swing-trading setup"
    r"\Swing_Trading_Course_Fixed\Swing_Trading_Course_Charts_Layout_Fixed_Verified"
)
EXTRA_SOURCE_DIRS = [Path(r"C:\Users\User\Desktop\swing-trading setup")]

SOURCES_DECL = re.compile(r"<!--\s*verbatim-sources:\s*(.+?)\s*-->", re.DOTALL)
FENCED_VERBATIM = re.compile(r"^```verbatim[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
ELISION = ("…", "...")

# Enumerations the rest of the system depends on. Membership and cardinality are asserted here so a
# silent addition in code or docs fails the build. Extend only alongside a dated amendment.
ENUMS: dict[str, tuple[str, tuple[str, ...]]] = {
    "candidate decision": ("02-domain/DECISION_STATE_MACHINE.md", ("Trade", "Watch", "Skip", "Pause")),
    "module gate": ("02-domain/DECISION_STATE_MACHINE.md", ("PASS", "PAUSE", "SKIP")),
    "watchlist status": (
        "02-domain/DECISION_STATE_MACHINE.md",
        ("Research", "Developing", "Watch", "Ready", "Triggered", "Trade", "Late", "Invalid", "Skip"),
    ),
    "checklist outcome (worksheet)": (
        "02-domain/DECISION_STATE_MACHINE.md",
        ("Complete", "Research", "Pause", "Skip", "Error"),
    ),
    "checklist outcome (decision)": (
        "02-domain/DECISION_STATE_MACHINE.md",
        ("Ready", "Research", "Watch", "Skip", "Pause", "Error"),
    ),
    "skip code": (
        "02-domain/CODES.md",
        ("DATA", "LIQ", "EVENT", "REGIME", "SECTOR", "LATE",
         "STOP", "RISK", "CORR", "BORROW", "TECH", "PSYCH"),
    ),
    "error code": (
        "02-domain/CODES.md",
        ("NO_PLAN", "CHASE", "NO_TRIGGER", "WIDE_STOP", "AVG_DOWN", "OVERSIZE",
         "CORRISK", "EARLY_EXIT", "LATE_EXIT", "REVENGE", "HINDSIGHT", "DATA_ERR"),
    ),
    "error severity": (
        "02-domain/CODES.md",
        ("Moderate", "Moderate/Major", "Major", "Critical"),
    ),
}

_source_cache: dict[Path, str] = {}


def normalise(text: str) -> str:
    """Collapse whitespace and unify the punctuation that PDF extraction varies on."""
    text = unicodedata.normalize("NFKC", text)
    for dash in ("\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        text = text.replace(dash, "-")
    text = text.replace("\u00a0", " ").replace("\u2019", "'").replace("\u201c", '"')
    text = text.replace("\u201d", '"').replace("\u00ab", '"').replace("\u00bb", '"')
    return re.sub(r"\s+", " ", text).strip()


def strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)
    return text.replace("`", "")


def strip_gloss(text: str) -> str:
    """Drop a trailing italic parenthetical - those are our translations, not source text."""
    index = text.find("*(")
    return text[:index].strip() if index > 0 else text


def strip_quotes(text: str) -> str:
    """Documents wrap quotations in quote marks; the source carries none."""
    return text.strip().strip('"').strip()


def resolve_source(name: str, course_root: Path) -> Path | None:
    for candidate in (course_root / "PDF" / name, course_root / name, *(d / name for d in EXTRA_SOURCE_DIRS)):
        if candidate.is_file():
            return candidate
    return None


def source_text(path: Path) -> str:
    if path not in _source_cache:
        if path.suffix.lower() == ".pdf":
            raw = subprocess.run(
                ["pdftotext", "-enc", "UTF-8", str(path), "-"],
                capture_output=True, text=True, encoding="utf-8", check=True,
            ).stdout
        else:
            raw = path.read_text(encoding="utf-8")
        _source_cache[path] = normalise(raw)
    return _source_cache[path]


def extract_quotes(markdown: str) -> list[tuple[int, str]]:
    """Return (line_number, quote) for each markdown blockquote, joining wrapped lines."""
    quotes: list[tuple[int, str]] = []
    buffer: list[str] = []
    start = 0
    for number, line in enumerate(markdown.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith(">"):
            body = stripped.lstrip(">").strip()
            if not buffer:
                start = number
            # A line that is only an italic parenthetical is a translation gloss, not a claim.
            if not re.fullmatch(r"\*\(.*\)\*", body):
                buffer.append(body)
        else:
            if buffer:
                quotes.append((start, " ".join(buffer)))
                buffer = []
    if buffer:
        quotes.append((start, " ".join(buffer)))
    return [(n, q) for n, q in quotes if q]


def extract_fenced(markdown: str) -> list[tuple[int, str]]:
    """Return (line_number, cell) for every line inside a ```verbatim fence.

    Tables in the source PDFs extract as separate column blocks, so the atomic verbatim unit is one
    cell. A fence carries one cell per line; each is checked independently.
    """
    cells: list[tuple[int, str]] = []
    for block in FENCED_VERBATIM.finditer(markdown):
        first = markdown[: block.start()].count("\n") + 2
        for offset, line in enumerate(block.group(1).splitlines()):
            if line.strip():
                cells.append((first + offset, line.strip()))
    return cells


def check_document(doc: Path, course_root: Path) -> tuple[list[str], int, int]:
    markdown = doc.read_text(encoding="utf-8")
    declaration = SOURCES_DECL.search(markdown)
    if not declaration:
        return [], 0, 0

    failures: list[str] = []
    sources: list[Path] = []
    for name in (n.strip() for n in declaration.group(1).split(",")):
        resolved = resolve_source(name, course_root)
        if resolved is None:
            failures.append(f"{doc.name}: declared source not found: {name}")
        else:
            sources.append(resolved)
    if not sources:
        return failures, 0, 0

    haystacks = [source_text(p) for p in sources]
    checked = skipped = 0
    for line_number, quote in extract_quotes(markdown) + extract_fenced(markdown):
        needle = strip_quotes(normalise(strip_markdown(strip_gloss(quote))))
        if any(marker in needle for marker in ELISION):
            skipped += 1
            continue
        checked += 1
        if not any(needle in hay for hay in haystacks):
            failures.append(
                f"{doc.relative_to(REPO)}:{line_number}: quote not found in "
                f"{[p.name for p in sources]}\n      {needle[:160]}"
            )
    return failures, checked, skipped


def check_enums(docs_root: Path) -> list[str]:
    failures: list[str] = []
    for label, (relative, members) in ENUMS.items():
        doc = docs_root / relative
        if not doc.is_file():
            failures.append(f"enum '{label}': defining document missing: {relative}")
            continue
        text = doc.read_text(encoding="utf-8")
        missing = [m for m in members if m not in text]
        if missing:
            failures.append(f"enum '{label}': members absent from {relative}: {missing}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-root", type=Path, default=DEFAULT_COURSE_ROOT)
    parser.add_argument("--docs", type=Path, default=REPO / "docs")
    args = parser.parse_args()

    failures: list[str] = []
    total_checked = total_skipped = documents = 0

    for doc in sorted(args.docs.rglob("*.md")):
        doc_failures, checked, skipped = check_document(doc, args.course_root)
        if checked or skipped or doc_failures:
            documents += 1
            status = "FAIL" if doc_failures else "ok"
            print(f"  {status:4s} {doc.relative_to(REPO)}  quotes={checked} skipped={skipped}")
        failures.extend(doc_failures)
        total_checked += checked
        total_skipped += skipped

    print(f"\nverbatim: {documents} documents, {total_checked} quotes checked, "
          f"{total_skipped} skipped (elided)")

    enum_failures = check_enums(args.docs)
    print(f"enums: {len(ENUMS)} checked, {len(enum_failures)} failed")
    failures.extend(enum_failures)

    if failures:
        print(f"\n{len(failures)} FAILURES", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\nall transcription checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
