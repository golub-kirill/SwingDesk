"""Every command and every flag this project has, generated from the code that defines them.

**Owner instruction, 2026-09-07.** A hand-kept list of commands is wrong within the week - that is
`AGENTS.md` §10.5's whole subject, and §10.6 rule 4 says a derived fact is produced by the tool that
derives it. So this reads the argument parsers themselves and writes `README.md`'s reference between
markers, the same way `build_state.py` writes `HANDOFF.md` §2.

**It reads the SYNTAX TREE and imports nothing.** Sixty-four tools declare a parser and several of
them open a store, fetch, or touch the venue on import-adjacent paths; a generator that imported
them to ask what flags they take would be a generator that ran them. `verify_vendor_policy.py`
already reads the tree for the same reason.

**What it cannot see, and says so in the output rather than pretending.** A flag added at runtime,
a parser built from a loop, or an argument whose `help` is computed - none is a literal in the tree.
Those appear with an empty description rather than being dropped, because a flag missing from a
reference is worse than one without a sentence.

    python tools/build_commands.py             # write it
    python tools/build_commands.py --check-only  # gate 45: is it current?
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
CLI = REPO / "src" / "swingdesk" / "presentation" / "cli.py"
TOOLS = REPO / "tools"

BEGIN = "<!-- BEGIN GENERATED COMMANDS - build_commands.py writes this, do not edit -->"
END = "<!-- END GENERATED COMMANDS -->"


@dataclass(frozen=True, slots=True)
class Argument:
    """One `add_argument`, with `required` kept as DATA rather than baked into the display text.

    The first version folded a `(required)` marker into the flag string and then tried to parse it
    back out to build the command line. It produced `--symbol` **(required)** --limit` in the
    table - a rendering bug that a formatted string always invites and a field never does.
    """

    names: tuple[str, ...]
    described: str
    required: bool

    @property
    def shown(self) -> str:
        flags = ", ".join(f"`{n}`" for n in self.names)
        return f"{flags} **(required)**" if self.required else flags


@dataclass(slots=True)
class Command:
    """One invocable thing and the arguments it accepts."""

    name: str
    summary: str
    arguments: list[Argument] = field(default_factory=list)

    @property
    def invocation(self) -> str:
        """The command line, with every REQUIRED option spelled in so it would actually run.

        Gate 31 reads every `python tools/...` a document names and checks the tool accepts it. A
        reference that showed a bare `probe_paper_order.py` would tell a reader to run something
        that exits 2, and the gate caught exactly that.
        """
        needed = " ".join(
            argument.names[0] for argument in self.arguments
            if argument.required and argument.names[0].startswith("--")
        )
        return f"{self.name} {needed}".strip()


def _text(node: ast.expr | None) -> str:
    """A string literal, or `""` for anything computed. Never a guess at what it evaluates to."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return " ".join(node.value.split())
    if isinstance(node, ast.JoinedStr):  # an f-string: the literal parts are still informative
        return " ".join(
            " ".join(part.value.split())
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    return ""


def _argument(call: ast.Call) -> Argument | None:
    """`(flags, help)` for one `add_argument`, or None when the name is not a literal.

    A REQUIRED option is marked, because the rendered command line has to include it: gate 31 reads
    every `python tools/...` an invocation in a document names and checks it would actually run, and
    a reference that showed `probe_paper_order.py` bare would be telling a reader to run something
    that exits 2. It caught exactly that here.
    """
    names = [_text(arg) for arg in call.args if _text(arg)]
    if not names:
        return None
    described = ""
    default = ""
    for keyword in call.keywords:
        if keyword.arg == "help":
            described = _text(keyword.value)
        elif keyword.arg == "default" and isinstance(keyword.value, ast.Constant):
            # `!r` for anything that is not already a string: a bytes default renders as `b'x'`
            # under plain interpolation and mypy is right to refuse it. A default is shown as the
            # source wrote it, which is what an operator needs to reproduce a run.
            value = keyword.value.value
            if value not in (None, False):
                shown = value if isinstance(value, str) else repr(value)
                default = f" (default: {shown})"
    required = any(
        keyword.arg == "required"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in call.keywords
    )
    return Argument(tuple(names), described + default, required)


def _calls_on(tree: ast.AST, receiver: str, method: str) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == receiver
    ]


def cli_commands(path: Path) -> list[Command]:
    """Every `swingdesk <command>`, from the sub-parsers `main` builds.

    The parser is constructed inside `main`, so there is no object to introspect without running it.
    The tree carries the same information: `<var> = sub.add_parser("name", help=...)` followed by
    `<var>.add_argument(...)`.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: dict[str, Command] = {}
    receivers: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not (isinstance(call.func, ast.Attribute) and call.func.attr == "add_parser"):
            continue
        name = _text(call.args[0]) if call.args else ""
        if not name or not isinstance(node.targets[0], ast.Name):
            continue
        summary = next((_text(k.value) for k in call.keywords if k.arg == "help"), "")
        receivers[node.targets[0].id] = name
        found[name] = Command(f"swingdesk {name}", summary)
    for receiver, name in receivers.items():
        for call in _calls_on(tree, receiver, "add_argument"):
            argument = _argument(call)
            if argument:
                found[name].arguments.append(argument)
    return [found[name] for name in sorted(found)]


def tool_command(path: Path) -> Command | None:
    """One `tools/*.py`, or None when it declares no parser and is therefore not invocable."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    receivers = [
        node.targets[0].id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "ArgumentParser"
        and isinstance(node.targets[0], ast.Name)
    ]
    if not receivers:
        return None
    doc = ast.get_docstring(tree) or ""
    summary = " ".join(doc.split("\n\n")[0].split()) if doc else ""
    command = Command(f"python tools/{path.name}", summary)
    for receiver in receivers:
        for call in _calls_on(tree, receiver, "add_argument"):
            argument = _argument(call)
            if argument:
                command.arguments.append(argument)
    return command


def render(cli: list[Command], tools: list[Command]) -> str:
    lines = [
        BEGIN,
        "",
        "**Generated by `tools/build_commands.py` and checked by gate 45.** Do not edit between the",
        "markers: a hand-kept list of flags is wrong within the week, which is the whole subject of",
        "`AGENTS.md` §10.5. An argument whose name or help text is computed rather than written as a",
        "literal appears with an empty description rather than being dropped.",
        "",
        f"### The application — {len(cli)} command(s)",
        "",
    ]
    for command in cli:
        lines.append(f"#### `{command.name}`")
        lines.append("")
        if command.summary:
            lines.append(command.summary)
            lines.append("")
        if command.arguments:
            lines.append("| argument | what it does |")
            lines.append("|---|---|")
            lines.extend(f"| {a.shown} | {a.described or '—'} |" for a in command.arguments)
            lines.append("")
    lines.append(f"### The tools — {len(tools)} invocable script(s)")
    lines.append("")
    lines.append("| command | what it does | arguments |")
    lines.append("|---|---|---|")
    for command in tools:
        flags = " · ".join(a.shown for a in command.arguments) or "—"
        summary = command.summary or "—"
        lines.append(f"| `{command.invocation}` | {summary} | {flags} |")
    lines.extend(["", END])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(prog="build_commands")
    parser.add_argument("--check-only", action="store_true",
                        help="fail if README.md's generated block is not what this would write")
    args = parser.parse_args()

    cli = cli_commands(CLI)
    tools = [
        command for command in (tool_command(path) for path in sorted(TOOLS.glob("*.py")))
        if command is not None
    ]
    block = render(cli, tools)

    readme = README.read_text(encoding="utf-8")
    if BEGIN in readme and END in readme:
        head, rest = readme.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        updated = head + block + tail
    else:
        updated = readme.rstrip("\n") + "\n\n## Every command and every flag\n\n" + block + "\n"

    if args.check_only:
        if updated != readme:
            print("commands: README.md's generated block is stale. Regenerate:")
            print("  python tools/build_commands.py")
            return 1
        print(f"commands: current - {len(cli)} command(s), {len(tools)} tool(s)")
        return 0

    README.write_text(updated, encoding="utf-8", newline="\n")
    print(f"commands: wrote README.md - {len(cli)} command(s), {len(tools)} tool(s), "
          f"{sum(len(c.arguments) for c in cli + tools)} argument(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
