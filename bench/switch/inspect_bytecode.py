#!/usr/bin/env python3
"""Summarize -O2 bytecode for switch and table dispatch benchmarks."""

import argparse
import collections
import re
from pathlib import Path

SIZES = (4, 16, 64, 256, 1024)
KINDS = ("switch", "function-table", "table", "if")
FUNCTION = re.compile(r"^Function \d+ \(([^)]+)\):$")
OPCODE = re.compile(r"^([A-Z][A-Z0-9_]*)\b")


def dispatch_instructions(source):
    active = False
    function_found = False
    insns = []
    for line in source.splitlines():
        header = FUNCTION.match(line)
        if header:
            active = header.group(1) == "test"
            function_found |= active
            continue
        if active:
            match = OPCODE.match(re.sub(r"^L\d+: ", "", line))
            if match:
                insns.append((match.group(1), line))
    if not function_found:
        raise ValueError("Missing test function in disassembly")
    start = next(i for i, (op, _) in enumerate(insns) if op == "MODK")
    end = next(i for i in range(start + 1, len(insns)) if re.search(r"(?:^|: )ADD R1 R1 R0$", insns[i][1]))
    return insns, insns[start + 1:end]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bytecode-dir", default="switch-bytecode")
    parser.add_argument("--output", default="switch-bytecode/comparison.md")
    args = parser.parse_args()
    folder = Path(args.bytecode_dir)
    rows = [
        "# Switch bytecode comparison (-O2)",
        "",
        "Static opcode counts from the dispatch region between value computation and checksum update; these are **not** counts of dynamically executed instructions.",
        "Function-table setup also creates one closure per case, outside the measured dispatch loop.",
        "",
        "| Cases | Variant | Dispatch instructions | Numeric guards | Equality tests | Ordered tests | Table reads | Calls |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    regions = {}
    for size in SIZES:
        for kind in KINDS:
            path = folder / f"{kind}-{size}.txt"
            if size == 1024 and kind == "if":
                continue
            if not path.exists():
                raise SystemExit(f"Missing disassembly: {path}")
            all_insns, dispatch = dispatch_instructions(path.read_text(encoding="utf-8"))
            regions[(size, kind)] = all_insns
            counts = collections.Counter(op for op, _ in dispatch)
            eq = sum(n for op, n in counts.items() if op.startswith("JUMPXEQK") or op in ("JUMPIFEQ", "JUMPIFNOTEQ"))
            ordered = sum(counts[op] for op in ("JUMPIFLT", "JUMPIFNOTLT", "JUMPIFLE", "JUMPIFNOTLE"))
            reads = sum(counts[op] for op in ("GETTABLE", "GETTABLEKS", "GETTABLEN"))
            calls = counts["CALL"] + counts["CALLFB"]
            rows.append(f"| {size} | {kind} | {len(dispatch)} | {counts['JUMPIFNOTNUMBER']} | {eq} | {ordered} | {reads} | {calls} |")

    rows += ["", "## Dispatch excerpts", "", "The switch tree excerpt is truncated; full disassemblies are saved alongside this report.", ""]
    for size in (16, 64, 1024):
        for kind in ("switch", "function-table", "table"):
            insns = regions[(size, kind)]
            start = next(i for i, (op, _) in enumerate(insns) if op == "MODK")
            excerpt = [line for _, line in insns[start:start + (20 if kind == "switch" else 10)]]
            rows.extend((f"### {kind}-{size}", "", "```text", *excerpt, "```", ""))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Bytecode comparison: {output}")


if __name__ == "__main__":
    main()
