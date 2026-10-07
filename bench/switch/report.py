#!/usr/bin/env python3
# This file is part of the Luau programming language and is licensed under MIT License; see LICENSE.txt for details

import argparse
import json
import statistics
from pathlib import Path

KINDS = ("if", "switch", "table", "function-table")
LABELS = {"if": "if/elseif", "switch": "switch", "table": "value table", "function-table": "function table"}


def load(path):
    data = json.loads(Path(path).read_text())
    rows = {}
    for result_set in data:
        if not result_set:
            continue
        result = result_set[0]
        name = result[3]
        values = result[4]
        if not values or "-" not in name:
            continue
        kind, cases = name.rsplit("-", 1)
        if kind in KINDS and cases.isdigit():
            rows[(int(cases), kind)] = statistics.median(values)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Write a Markdown summary for switch benchmark results")
    parser.add_argument("results", nargs="?", default="switch-results.json")
    parser.add_argument("--graph", default="switch-results.png")
    parser.add_argument("--output", default="switch-results.md")
    args = parser.parse_args()

    rows = load(args.results)
    sizes = sorted({cases for cases, _ in rows})

    out = [
        "# Switch dispatch benchmark",
        "",
        "Generated with Luau's upstream `bench/bench.py` harness. Values are medians in milliseconds; lower is better.",
        "",
        "| Cases | if/elseif | switch | value table | function table |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]

    for cases in sizes:
        cells = [str(cases)]
        for kind in KINDS:
            value = rows.get((cases, kind))
            cells.append("N/A" if value is None else f"{value:.3f} ms")
        out.append("| " + " | ".join(cells) + " |")

    graph = Path(args.graph)
    if graph.exists():
        out.extend(("", "## Graph", "", f"![Switch benchmark results]({graph.name})"))

    Path(args.output).write_text("\n".join(out) + "\n", newline="\n")
    print(args.output)


if __name__ == "__main__":
    main()
