#!/usr/bin/env python3
# This file is part of the Luau programming language and is licensed under MIT License; see LICENSE.txt for details

import argparse
import base64
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
    parser.add_argument("--bytecode-dir", default="switch-bytecode")
    args = parser.parse_args()

    rows = load(args.results)
    sizes = (4, 16, 64, 256, 1024)
    if not rows:
        raise SystemExit("No successful benchmark measurements found")

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
        encoded = base64.b64encode(graph.read_bytes()).decode("ascii")
        out.extend(("", "## Graph", "", f"![Switch benchmark results](data:image/png;base64,{encoded})"))

    bytecode_dir = Path(args.bytecode_dir)
    dumps = [bytecode_dir / f"switch-{size}.txt" for size in sizes if (bytecode_dir / f"switch-{size}.txt").is_file()]
    if dumps:
        out.extend(("", "## Switch bytecode", ""))
        for dump in dumps:
            out.extend((f"### {dump.stem}", "", "```text", dump.read_text().rstrip(), "```", ""))

    Path(args.output).write_text("\n".join(out) + "\n", newline="\n")
    print(args.output)


if __name__ == "__main__":
    main()
