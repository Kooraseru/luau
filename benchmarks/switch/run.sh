#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

python benchmarks/switch/generate.py
cmake --build build --target Luau.Repl.CLI Luau.Compile.CLI

RESULTS="benchmarks/switch/results.csv"
SUMMARY="benchmarks/switch/summary.csv"
TMPDIR_BENCH=$(mktemp -d)
trap 'rm -rf "$TMPDIR_BENCH"' EXIT

printf "kind,cases,opt,run,seconds,checksum\n" > "$RESULTS"

run_group() {
    local opt="$1"
    local n="$2"
    local kind="$3"
    local outfile="$TMPDIR_BENCH/$opt-$n-$kind.csv"

    : > "$outfile"
    for run in 1 2 3 4 5; do
        out=$(./build/luau.exe -O"$opt" "benchmarks/switch/generated/$kind-$n.luau")
        seconds=$(awk '{print $3}' <<< "$out")
        checksum=$(awk '{print $4}' <<< "$out")
        printf "%s,%s,%s,%s,%s,%s\n" "$kind" "$n" "$opt" "$run" "$seconds" "$checksum" >> "$outfile"
    done
}

pids=()
for opt in 0 1 2; do
    for n in 4 16 64 256; do
        for kind in if switch table function-table; do
            run_group "$opt" "$n" "$kind" &
            pids+=("$!")
        done
    done
done

status=0
for pid in "${pids[@]}"; do
    wait "$pid" || status=1
done
(( status == 0 )) || exit "$status"

for opt in 0 1 2; do
    for n in 4 16 64 256; do
        for kind in if switch table function-table; do
            cat "$TMPDIR_BENCH/$opt-$n-$kind.csv" >> "$RESULTS"
        done
    done
done

python - "$RESULTS" "$SUMMARY" <<'PY'
import csv
import statistics
import sys
from collections import defaultdict

source, destination = sys.argv[1:3]
groups = defaultdict(list)
checksums = defaultdict(set)

with open(source, newline="") as f:
    for row in csv.DictReader(f):
        key = (int(row["opt"]), int(row["cases"]), row["kind"])
        groups[key].append(float(row["seconds"]))
        checksums[(int(row["opt"]), int(row["cases"]))].add(row["checksum"])

for key, values in checksums.items():
    if len(values) != 1:
        raise SystemExit(f"checksum mismatch for O{key[0]}, {key[1]} cases: {sorted(values)}")

rows = []
for (opt, cases, kind), values in sorted(groups.items()):
    rows.append({
        "opt": opt,
        "cases": cases,
        "kind": kind,
        "median_ms": statistics.median(values) * 1000,
        "min_ms": min(values) * 1000,
        "max_ms": max(values) * 1000,
    })

with open(destination, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["opt", "cases", "kind", "median_ms", "min_ms", "max_ms"])
    writer.writeheader()
    writer.writerows(rows)

for opt in range(3):
    print(f"\n-O{opt}")
    print(f"{'cases':>5}  {'if':>10}  {'switch':>10}  {'table':>10}  {'func-table':>10}")
    print("-" * 55)
    by_case = defaultdict(dict)
    for row in rows:
        if row["opt"] == opt:
            by_case[row["cases"]][row["kind"]] = row["median_ms"]

    for cases in sorted(by_case):
        r = by_case[cases]
        print(
            f"{cases:>5}  "
            f"{r['if']:>9.3f}ms  "
            f"{r['switch']:>9.3f}ms  "
            f"{r['table']:>9.3f}ms  "
            f"{r['function-table']:>9.3f}ms"
        )

print(f"\nraw:     {source}")
print(f"summary: {destination}")
PY
