"""The generated command reference, and the four ways it could be quietly incomplete.

A reference that silently drops a command is worse than no reference: it is a document an operator
trusts. Each of these fails on a different way to lose one, and none of them raises on its own.

* **a command whose parser is built differently** — the CLI builds its sub-parsers inside `main`,
  so this reads the syntax tree. A pattern that matched only one shape would drop the rest.
* **a flag with no `help=`** — dropping it makes the reference wrong in the direction that hides
  work. Eleven CLI arguments had none when this was written.
* **an f-string or computed help** — the literal parts are still worth printing.
* **a tool with no parser at all** — a module that is imported rather than invoked is not a
  command, and listing it would send somebody to run a library.

No store, no network. Every fixture is source text written here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def build():
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(
        "_build_commands", REPO / "tools" / "build_commands.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


CLI_SOURCE = '''
"""A fake CLI."""
import argparse


def main():
    parser = argparse.ArgumentParser(prog="swingdesk")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="run the daily pipeline")
    scan.add_argument("tickers", nargs="*", help="e.g. AAPL")
    scan.add_argument("--submit", action="store_true", help="place this run's orders")
    scan.add_argument("--data", type=Path, default="data")
    broker = sub.add_parser("broker", help="read the paper account")
    broker.add_argument("--as-of", default=None, help="ISO instant")
'''


def test_every_subcommand_is_found_and_sorted(build, tmp_path):
    """The CLI builds its sub-parsers inside `main`, so there is no parser object to introspect
    without running it. Sorted, so the generated block does not churn on an unrelated edit."""
    found = build.cli_commands(write(tmp_path, "cli.py", CLI_SOURCE))
    assert [c.name for c in found] == ["swingdesk broker", "swingdesk scan"]
    assert found[1].summary == "run the daily pipeline"


def test_a_flag_with_no_help_is_listed_rather_than_dropped(build, tmp_path):
    """The direction that hides work. `--data` carried no help on all eight real commands, and a
    generator that dropped it would have reported a tidier CLI than the one that exists."""
    scan = next(c for c in build.cli_commands(write(tmp_path, "cli.py", CLI_SOURCE))
                if c.name == "swingdesk scan")
    flags = {a.names[0]: a.described for a in scan.arguments}
    assert "--data" in flags
    assert flags["--data"] == " (default: data)"
    assert flags["--submit"] == "place this run's orders"


def test_a_positional_is_listed_beside_the_options(build, tmp_path):
    scan = next(c for c in build.cli_commands(write(tmp_path, "cli.py", CLI_SOURCE))
                if c.name == "swingdesk scan")
    assert [(a.names, a.described) for a in scan.arguments if a.names == ("tickers",)] == [
        (("tickers",), "e.g. AAPL")
    ]


def test_a_tool_with_a_parser_is_a_command_and_one_without_is_not(build, tmp_path):
    """A module that is imported rather than invoked is not a command. Listing it would send
    somebody to run a library."""
    invocable = write(tmp_path, "invocable.py", '''
"""Does a thing. And a second paragraph that must not reach the summary."""
import argparse
parser = argparse.ArgumentParser(prog="invocable")
parser.add_argument("--loud", action="store_true", help="say more")
''')
    library = write(tmp_path, "library.py", '"""No parser here."""\nX = 1\n')
    command = build.tool_command(invocable)
    assert command is not None
    assert command.name == "python tools/invocable.py"
    assert command.summary == "Does a thing. And a second paragraph that must not reach the summary."
    assert [(a.names, a.described) for a in command.arguments] == [(("--loud",), "say more")]
    assert build.tool_command(library) is None


def test_an_f_string_help_keeps_its_literal_parts(build, tmp_path):
    """Computed help is common in this repository - several tools interpolate a threshold. Dropping
    the whole string because part of it is computed would lose the sentence that explains the flag.
    """
    source = '''
"""T."""
import argparse
LIMIT = 4
parser = argparse.ArgumentParser(prog="t")
parser.add_argument("--cap", help=f"at most {LIMIT} of them, and no more")
'''
    command = build.tool_command(write(tmp_path, "t.py", source))
    # One space, not two: each literal fragment is whitespace-collapsed and then joined, so the
    # gap the interpolation left does not become a double space in the rendered table.
    assert [(a.names, a.described) for a in command.arguments] == [
        (("--cap",), "at most of them, and no more")
    ]


def test_the_rendered_block_is_bounded_by_markers_a_gate_can_find(build):
    """`--check-only` replaces what sits between them, so a block without both markers would be
    appended a second time on every run."""
    block = build.render([], [])
    assert block.startswith(build.BEGIN)
    assert block.endswith(build.END)


def test_the_repository_block_is_current(build):
    """Gate 45 in miniature, so a stale README fails here too rather than only in the suite."""
    readme = build.README.read_text(encoding="utf-8")
    assert build.BEGIN in readme and build.END in readme
    cli = build.cli_commands(build.CLI)
    tools = [
        command for command in (build.tool_command(p) for p in sorted(build.TOOLS.glob("*.py")))
        if command is not None
    ]
    assert build.render(cli, tools) in readme


def test_every_cli_argument_carries_help(build):
    """Not a property of the generator - a property of the CLI, which the generator made visible.
    Eleven arguments had none on 2026-09-07 and the reference printed them as empty."""
    bare = [
        (command.name, flags)
        for command in build.cli_commands(build.CLI)
        for flags, described in ((a.shown, a.described) for a in command.arguments)
        if not described.strip()
    ]
    assert not bare, f"CLI arguments with no help= and no default: {bare}"


def test_a_required_option_is_spelled_into_the_command_line(build, tmp_path):
    """Gate 31 reads every `python tools/...` a document names and checks the tool would accept it.
    A reference showing a bare `probe_paper_order.py` tells a reader to run something that exits 2,
    and the gate caught exactly that when this block was first generated.
    """
    source = '''
"""P."""
import argparse
parser = argparse.ArgumentParser(prog="p")
parser.add_argument("--symbol", required=True, help="a REAL ticker")
parser.add_argument("--limit", required=True, help="the price")
parser.add_argument("--quiet", action="store_true", help="optional")
'''
    command = build.tool_command(write(tmp_path, "p.py", source))
    assert command.invocation == "python tools/p.py --symbol --limit"
    assert "**(required)**" in dict(
        (a.names[0], a.shown) for a in command.arguments)["--symbol"]
    assert "**(required)**" not in dict(
        (a.names[0], a.shown) for a in command.arguments)["--quiet"]


def test_required_is_DATA_and_not_a_marker_parsed_back_out_of_a_string(build, tmp_path):
    """The bug this refactor removed. The first version folded `(required)` into the flag text and
    parsed it back to build the command line, which rendered as
    `--symbol` **(required)** --limit` in the table. A field cannot do that."""
    source = '''
"""P."""
import argparse
parser = argparse.ArgumentParser(prog="p")
parser.add_argument("--symbol", required=True, help="x")
'''
    argument = build.tool_command(write(tmp_path, "p.py", source)).arguments[0]
    assert argument.required is True
    assert argument.names == ("--symbol",)
    assert "required" not in argument.described


# --- grouping: sixty-five rows in one table is an inventory, not a reference ---------------------


def test_the_four_kinds_are_derived_and_a_gate_tool_is_not_an_operator_tool(build):
    """Two rules that a prefix alone gets wrong, in opposite directions.

    `verify_reproducible.py` and `verify_submission_guards.py` start with `verify_` and are NOT
    registered as gates - a classifier keyed on the name would file them with the implementations
    nobody types. And every `build_*` IS gate-registered as `--check-only`, so a classifier keyed
    on registration would hide the generators an operator runs to regenerate. Order decides.
    """
    gates = build.gate_registered()
    assert "verify_open_work.py" in gates
    assert "verify_reproducible.py" not in gates
    assert build.classify("verify_open_work.py", gates) == build.GATE
    assert build.classify("verify_reproducible.py", gates) == build.OPERATOR
    assert build.classify("run_pr014.py", gates) == build.RESEARCH_KIND
    assert build.classify("measure_short_leg.py", gates) == build.RESEARCH_KIND
    assert build.classify("build_state.py", gates) == build.GENERATOR
    assert build.classify("refresh_universe.py", gates) == build.OPERATOR


def test_the_operator_count_is_what_the_heading_promises(build):
    """The heading says how many are things you type. If the grouping and the count came from two
    different places they would disagree the first time a tool was added."""
    tools = [
        command for command in (build.tool_command(p) for p in sorted(build.TOOLS.glob("*.py")))
        if command is not None
    ]
    operator = [c for c in tools if c.kind == build.OPERATOR]
    block = build.render([], tools)
    assert f"of which {len(operator)} are things you type" in block
    assert f"#### {build.OPERATOR} — {len(operator)}" in block


def test_every_tool_lands_in_exactly_one_group(build):
    """A tool in no group vanishes from the reference; one in two is listed twice. Neither raises."""
    tools = [
        command for command in (build.tool_command(p) for p in sorted(build.TOOLS.glob("*.py")))
        if command is not None
    ]
    block = build.render([], tools)
    for command in tools:
        assert block.count(f"| `{command.invocation}` |") == 1, command.name
    assert sum(
        block.count(f"#### {kind} — ")
        for kind in (build.OPERATOR, build.GENERATOR, build.GATE, build.RESEARCH_KIND)
    ) == len({c.kind for c in tools})
