"""`python -m secondshift.config show` — what resolved, and where it came from.

Separate from `config.py` so the module the whole system imports stays free of
argument parsing and printing. The command is the diagnostic of last resort: it
has to answer on a machine where the database is missing, the brain is not
cloned and nothing is reachable, so it opens none of them.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .config import Resolved, resolve_all


def _render(rows: Sequence[Resolved]) -> str:
    """Aligned name, value and origin. Wide enough for the longest name."""
    name_width = max(len(r.setting.name) for r in rows)
    value_width = min(48, max(len(r.display) for r in rows))
    lines = [
        f"{'SETTING'.ljust(name_width)}  {'VALUE'.ljust(value_width)}  WHERE FROM",
        f"{'-' * name_width}  {'-' * value_width}  {'-' * 10}",
    ]
    for row in rows:
        marker = " !" if row.error else ""
        lines.append(
            f"{row.setting.name.ljust(name_width)}  "
            f"{row.display.ljust(value_width)}  {row.where}{marker}"
        )
    problems = [r for r in rows if r.error]
    if problems:
        lines.append("")
        for row in problems:
            lines.append(f"! {row.setting.name}: {row.error}")
    shell = [r for r in rows if r.setting.shell_only]
    if shell:
        lines.append("")
        lines.append(
            "Read by shell, not by Python: "
            + ", ".join(r.setting.name for r in shell)
        )
    return "\n".join(lines)


def show(argv: Sequence[str] | None = None, *, stream=None) -> int:
    """Print the resolved view. Zero when everything resolved, one when not.

    Non-zero is what lets a deploy gate on this. The two failure modes it
    reports are a malformed configuration file and a required setting that
    resolved to nothing — both of which used to be visible only as a downstream
    symptom naming the wrong cause.
    """
    parser = argparse.ArgumentParser(prog="python -m secondshift.config")
    parser.add_argument("command", choices=["show"])
    parser.parse_args(list(argv) if argv is not None else None)

    out = sys.stdout if stream is None else stream
    rows = resolve_all()
    print(_render(rows), file=out)

    unresolved = [r for r in rows if r.setting.required and not r.value]
    malformed = [r for r in rows if r.error]
    for row in unresolved:
        print(f"! {row.setting.name} is required and did not resolve", file=out)
    return 1 if (unresolved or malformed) else 0


def main(argv: Sequence[str] | None = None) -> int:
    return show(argv)
