#!/usr/bin/env python3
"""Alternate native indexed/comparison runs and confirm switch/if slowdown candidates."""

import argparse
import csv
import json
import statistics
from pathlib import Path

import suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--rounds", type=int, default=7)
    args = parser.parse_args()
    if args.rounds < 3:
        parser.error("use at least three paired rounds")
    report = json.loads(args.results.read_text(encoding="utf-8"))
    directory = args.results.parent
    build = Path(report["build"])
    vm = build / "luau.exe"
    suite.EXECUTION_ENV = suite.execution_environment(build, vm)
    comparisons = []
    for row in report["results"]:
        if row.get("mode") == "native" and row.get("implementation") == "switch" and row["bytecode_strategy"] in ("SELECTN", "JUMPXTABLE"):
            comparisons.append(("lowering", row))
    candidates = report["regression_candidates"]
    if args.previous:
        candidates += json.loads(args.previous.read_text(encoding="utf-8"))["regression_candidates"]
    seen = set()
    for row in candidates:
        key = (row["shape"], row["count"], row["pattern"], row["mode"])
        if key not in seen:
            seen.add(key)
            comparisons.append(("switch-vs-if", row))
    results = []
    for kind, row in comparisons:
        samples = {"indexed": [], "comparison" if kind == "lowering" else "if": []}
        alternatives = list(samples)
        name = f"{kind}-{row['shape']}-{row['count']}-{row['pattern']}-{row['mode']}"
        for round_ in range(args.rounds):
            for alternative in alternatives if round_ % 2 == 0 else reversed(alternatives):
                suite.COMPARISON_NATIVE = alternative == "comparison"
                implementation = "if" if alternative == "if" else "switch"
                source = directory / f"{row['shape']}-{row['count']}-{implementation}-{row['pattern']}.luau"
                command = [vm, "-O2"] + (["--codegen"] if row["mode"] == "native" else []) + [source]
                run = suite.execute(command, directory / f"paired-{name}-{alternative}-{round_}.log")
                times = [float(line.split()[1]) * 1000 for line in run.stdout.splitlines() if line.startswith("TIME\t")]
                if run.returncode or len(times) != report["options"]["samples"]:
                    raise RuntimeError(f"Failed paired run: {name}, {alternative}")
                samples[alternative].append(statistics.median(times))
        ratios = [a / b for a, b in zip(samples[alternatives[0]], samples[alternatives[1]])]
        result = dict(kind=kind, shape=row["shape"], count=row["count"], pattern=row["pattern"], mode=row["mode"],
                      comparator=alternatives[1], indexed_ms=statistics.median(samples[alternatives[0]]),
                      comparator_ms=statistics.median(samples[alternatives[1]]),
                      median_ratio=statistics.median(ratios), paired_ratios=ratios, samples_ms=samples)
        results.append(result)
        print(name, f"indexed/{alternatives[1]}={result['median_ratio']:.3f}", flush=True)
        (directory / "paired-comparison.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    fields = ("kind", "shape", "count", "pattern", "mode", "comparator", "indexed_ms", "comparator_ms", "median_ratio")
    with (directory / "paired-comparison.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


if __name__ == "__main__":
    main()
