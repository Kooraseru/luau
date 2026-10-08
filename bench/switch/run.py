#!/usr/bin/env python3
# This file is part of the Luau programming language and is licensed under MIT License; see LICENSE.txt for details

"""Build, validate, benchmark, and export the experimental switch implementation."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIZES = (4, 16, 64, 256, 1024)
KINDS = ("if", "switch", "table", "function-table")
EXPECTED = {(size, kind) for size in SIZES for kind in KINDS}
# The upstream parser rejects the 1024-branch elseif chain due to recursion depth.
KNOWN_LIMIT = (1024, "if")


def run(*args):
    print(f"\n$ {' '.join(map(str, args))}", flush=True)
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def main():
    exe = ".exe" if sys.platform == "win32" else ""
    build = ROOT / "build-release"
    vm = build / f"luau{exe}"
    compiler = build / f"luau-compile{exe}"
    unit_tests = build / f"Luau.UnitTest{exe}"
    output = ROOT / "switch-results"
    bytecode = ROOT / "switch-bytecode"
    bytecode.mkdir(exist_ok=True)

    run("cmake", "--build", build, "--target", "Luau.Repl.CLI", "Luau.UnitTest", "Luau.Compile.CLI", "-j", "4")
    run(unit_tests)
    run(sys.executable, "bench/switch/generate.py")

    for size in SIZES:
        target = bytecode / f"switch-{size}.txt"
        print(f"Disassembling switch-{size} -> {target.name}", flush=True)
        with target.open("w", encoding="utf-8") as out:
            subprocess.run(
                [str(compiler), "--text", "-O2", f"bench/switch/generated/switch-{size}.luau"],
                cwd=ROOT, stdout=out, check=True,
            )

    # The upstream harness can exit 0 even when individual benchmarks fail.
    # Remove old outputs so an unsuccessful run cannot reuse a stale graph.
    for extension in (".json", ".png", ".md"):
        (ROOT / f"switch-results{extension}").unlink(missing_ok=True)

    run(
        sys.executable, "bench/bench.py",
        "--folder", "bench/switch/generated",
        "--vm", f"{vm.as_posix()} -O2",
        "--filename", str(output),
        "--absolute",
    )

    measurements = json.loads((ROOT / "switch-results.json").read_text())
    observed = set()
    for group in measurements:
        if not group:
            continue
        result = group[0]
        if len(result) < 5 or not isinstance(result[4], list) or not result[4]:
            continue
        name = result[3]
        kind, sep, size = name.rpartition("-")
        if sep and size.isdigit():
            observed.add((int(size), kind))

    missing = EXPECTED - observed
    unexpected = missing - {KNOWN_LIMIT}
    unknown = observed - EXPECTED
    if unexpected or unknown:
        raise SystemExit(f"Unexpected benchmark results: missing={sorted(unexpected)}, extra={sorted(unknown)}")
    if missing:
        print(f"Known compiler limitation: {sorted(missing)}", flush=True)

    if not (ROOT / "switch-results.png").is_file():
        raise SystemExit("Benchmark graph was not generated")
    run(sys.executable, "bench/switch/report.py", "switch-results.json")

    report = ROOT / "switch-results.md"
    print(f"\nReport: {report}", flush=True)
    print(f"Benchmarks: {len(observed)}/{len(EXPECTED)} successful", flush=True)
    print(f"Bytecode: {bytecode}", flush=True)


if __name__ == "__main__":
    main()
