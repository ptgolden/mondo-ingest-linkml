"""What is wrong with an extract: every problem of a build, reported together.

Each names the term and the slot, and gives the value as the source wrote it. For a
source read with SPARQL the two say which query it came from: <slot>.rq, or terms.rq
for a single-valued slot.
"""

from dataclasses import astuple, dataclass


@dataclass(frozen=True, order=True)
class Problem:
    """One thing wrong with an extract."""

    term: str
    """Its id as stated, or "(metadata)"."""

    slot: str
    value: str
    problem: str


class Problems(Exception):
    """Everything wrong with an extract. As text, a line for each problem, in columns,
    and their number."""

    def __init__(self, problems: list[Problem]):
        self.problems = sorted(set(problems))

    def __str__(self) -> str:
        rows = [astuple(problem) for problem in self.problems]
        widths = [max(len(row[column]) for row in rows) for column in range(3)]
        lines = ["  ".join([*(cell.ljust(width) for cell, width in zip(row, widths)), row[3]]) for row in rows]
        return "\n".join([*lines, f"{len(rows)} problems"])
