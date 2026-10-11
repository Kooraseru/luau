#!/usr/bin/env python3
"""Semantic and performance matrix for switch lowering; native fallback is not a result."""

import argparse
import csv
import json
import os
import platform
import random
import statistics
import struct
import subprocess
import sys
from pathlib import Path

from paths import ROOT, BYTECODE
SHAPES = ("dense", "sparse", "string", "mixed", "value", "arithmetic", "calls", "effects", "dynamic", "small", "large", "nested")
PURE = {"dense", "sparse", "string", "mixed", "value", "small", "large"}
EXECUTION_ENV = None
COMPARISON_NATIVE = False


def literal(value):
    if isinstance(value, bool):
        return str(value).lower()
    return json.dumps(value)


def labels(shape, count):
    if shape == "string":
        return [f"case-{i}" for i in range(count)]
    if shape == "mixed":
        return [False, True] + [f"case-{i}" if i % 2 else i for i in range(2, count)]
    return [i * (17 if shape == "sparse" else 1) - count // 2 for i in range(count)]


def output(shape, i):
    k = (i * 137 + 41) % 30011 - 15000
    if shape == "arithmetic":
        return k + 17 * (i % 7 + 1)
    if shape == "calls":
        return k + 8
    if shape == "nested":
        return k + 1
    return k


def source(shape, count, implementation, pattern, iterations, samples, diagnostic=False):
    keys = labels(shape, count)
    rng = random.Random(7301)
    misses = ["unmatched", count * 20, 0.5]
    input_count = 4096
    inputs = [keys[count // 2]] * input_count if pattern == "fixed" else (
        [keys[i % count] for i in range(input_count)] if pattern == "cycle" else (
            [rng.choice(keys) for _ in range(input_count)] if pattern == "random" else [misses[i % 3] for i in range(input_count)]))
    # Always exercise default, non-number and fractional behavior outside timed loops.
    probes = keys + misses
    expected = [output(shape, keys.index(x)) if x in keys else -19001 for x in probes]
    prefix = "local state, checks = 0, 0\nlocal function label(x) checks += 1 return x end\n"

    def body(i):
        k = output("value", i)
        expr = str(k)
        if shape == "arithmetic":
            expr = f"{k} + y * {i % 7 + 1}"
        elif shape == "calls":
            expr = f"math.floor({k} + y * 0.5)"
        elif shape == "effects":
            return f"state = (state * 33 + {i + 1}) % 1000003; return {k}"
        elif shape == "nested":
            if implementation == "switch":
                return f"switch y % 2 case 0 then return {k} else return {k + 1} end"
            return f"if y % 2 == 0 then return {k} else return {k + 1} end"
        return f"result = {expr}" if shape == "value" else f"return {expr}"

    if implementation in ("table", "function-table"):
        if implementation == "table":
            values = [f"[{literal(key)}] = {output(shape, i)}" for i, key in enumerate(keys)]
            prefix += "local lookup = {" + ",\n".join(values) + "}\n"
        else:
            prefix += "local lookup = {}\n"
            for i, key in enumerate(keys):
                # Compile handlers as well as the dispatcher in native mode.
                # A block per handler keeps large suites below the local register limit.
                tail = "; return result" if shape == "value" else ""
                prefix += f"do\n@native\nlocal function handler(y) local result; {body(i)}{tail} end\nlookup[{literal(key)}] = handler\nend\n"
        code = "local selected = lookup[x]; if selected == nil then return -19001 end; "
        code += "return selected" if implementation == "table" else "return selected(y)"
    else:
        parts = ["local result"]
        if implementation == "switch":
            parts.append("switch x")
        for i, key in enumerate(keys):
            expr = f"label({literal(key)})" if shape == "dynamic" else literal(key)
            head = f"case {expr} then" if implementation == "switch" else f"{'if' if i == 0 else 'elseif'} x == {expr} then"
            parts.append(head + " " + body(i))
        parts += ["else " + ("result = -19001" if shape == "value" else "return -19001"), "end", "return result"]
        code = "\n".join(parts)
    prefix += "@native\n@debugnoinline\nlocal function dispatch(x, y)\n" + code + "\nend\n"
    state = 0
    checks = 0
    for x in probes:
        index = keys.index(x) if x in keys else None
        if shape == "effects" and index is not None:
            state = (state * 33 + index + 1) % 1000003
        if shape == "dynamic":
            checks += index + 1 if index is not None else count
    prefix += "local probes = {" + ",".join(map(literal, probes)) + "}\n"
    prefix += "local expected = {" + ",".join(map(str, expected)) + "}\n"
    prefix += "for i, x in probes do assert(dispatch(x, 17) == expected[i], 'result mismatch at '..i) end\n"
    prefix += f"assert(state == {state} and checks == {checks}, 'observable side effects differ')\nprint('CORRECT')\n"
    prefix += "local inputs = {" + ",".join(map(literal, inputs)) + "}\n"
    prefix += "@native\n@debugnoinline\nlocal function measure(limit) local checksum = 0; for i = 1, limit do checksum += dispatch(inputs[(i - 1) % #inputs + 1], 17) end; return checksum end\n"
    if diagnostic:
        return prefix + "measure(1)\n"
    prefix += f"measure({iterations}); measure({iterations})\n"
    outputs = [output(shape, keys.index(x)) if x in keys else -19001 for x in inputs]
    expected_sum = sum(outputs) * (iterations // len(inputs)) + sum(outputs[:iterations % len(inputs)])
    prefix += f"for i = 1, {samples} do local start = os.clock(); local sum = measure({iterations}); local elapsed = os.clock() - start; assert(sum == {expected_sum}, 'timed checksum differs'); print('TIME', elapsed, sum) end\n"
    return prefix


def execute(args, log):
    args = list(map(str, args))
    args.insert(1, "--fflags=DebugLuauNoInline=true,DebugLuauSwitchComparisonNative=" + str(COMPARISON_NATIVE).lower())
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=120, env=EXECUTION_ENV)
    status = f"\nProcess exit: {result.returncode} (0x{result.returncode & 0xffffffff:08X})\n" if result.returncode else ""
    log.write_text(result.stdout + result.stderr + status, encoding="utf-8")
    return result


def executable_machine(path):
    with path.open("rb") as executable:
        if executable.read(2) == b"MZ":
            executable.seek(60)
            offset = struct.unpack("<I", executable.read(4))[0]
            executable.seek(offset + 4)
            machine = struct.unpack("<H", executable.read(2))[0]
            return {0x8664: "x64", 0xAA64: "ARM64"}.get(machine, hex(machine))
    return "unknown"


def execution_environment(build, vm):
    environment = os.environ.copy()
    cache = build / "CMakeCache.txt"
    if sys.platform == "win32" and cache.exists():
        # Cross compiler host DLLs can have a different architecture from its output.
        machine = executable_machine(vm)
        triple = {"x64": "x86_64-w64-mingw32", "ARM64": "aarch64-w64-mingw32"}.get(machine)
        for line in cache.read_text(encoding="utf-8").splitlines():
            if line.startswith("CMAKE_CXX_COMPILER:") and triple:
                toolchain = Path(line.split("=", 1)[1]).parent.parent
                runtime = toolchain / triple / "bin"
                if runtime.is_dir():
                    environment["PATH"] = str(runtime) + os.pathsep + environment.get("PATH", "")
                break
    return environment


def main(argv=None):
    global EXECUTION_ENV, COMPARISON_NATIVE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("full", "smoke"), default="full")
    parser.add_argument("--opt", choices=("O1", "O2"), default="O2")
    parser.add_argument("--native", choices=("both", "off", "only"), default="both")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build-release")
    parser.add_argument("--iterations", type=int, default=100000)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--shapes", nargs="+", choices=SHAPES, default=SHAPES)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--native-strategy", choices=("indexed", "comparison"), default="indexed")
    options = parser.parse_args(argv)
    if options.samples < 1 or options.iterations < 1:
        parser.error("samples and iterations must be positive")
    COMPARISON_NATIVE = options.native_strategy == "comparison"
    build = options.build_dir.resolve()
    if not (build / "CMakeCache.txt").is_file():
        parser.error(f"Build directory is not configured: {build}. Configure it with cmake first; see bench/switch/README.md.")
    suffix = ".exe" if sys.platform == "win32" else ""
    vm, compiler = build / ("luau" + suffix), build / ("luau-compile" + suffix)
    if not options.skip_build:
        subprocess.run(["cmake", "--build", str(build), "--target", "Luau.Repl.CLI", "Luau.Compile.CLI", "-j", "4"], check=True)
    EXECUTION_ENV = execution_environment(build, vm)
    # Catch loader failures once, before generating an entire matrix of failures.
    for executable in (compiler, vm):
        probe = subprocess.run([str(executable), "--help"], cwd=ROOT, text=True, capture_output=True, env=EXECUTION_ENV)
        if probe.returncode:
            print(f"Cannot start {executable}: exit 0x{probe.returncode & 0xffffffff:08X}\n{probe.stdout}{probe.stderr}", file=sys.stderr)
            return 1
    directory = BYTECODE / ("suite-" + build.name + "-" + options.suite + "-" + options.opt + "-" + options.native_strategy)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "results.json").unlink(missing_ok=True)
    rows = []
    failures = []
    checked = []
    for shape in options.shapes:
        sizes = (2, 4) if shape == "small" else ((256, 1024) if shape == "large" else (4, 16, 64, 256))
        if options.suite == "smoke":
            sizes = (sizes[-1] if shape == "small" else (256 if shape == "large" else 64),)
        implementations = ["switch", "if", "function-table"] + (["table"] if shape in PURE else [])
        if shape == "dynamic":
            implementations = ["switch", "if"]
        patterns = ("fixed", "cycle", "random", "miss") if options.suite == "full" else ("cycle", "miss")
        for count in sizes:
            for implementation in implementations:
                name = f"{shape}-{count}-{implementation}"
                diagnostic = directory / (name + "-check.luau")
                diagnostic.write_text(source(shape, count, implementation, "cycle", options.iterations, options.samples, True), encoding="utf-8")
                disassembly = execute([compiler, "--text", "-" + options.opt, diagnostic], directory / (name + ".bytecode.txt"))
                if disassembly.returncode:
                    known_limit = implementation == "if" and count == 1024 and "recursion" in disassembly.stderr.lower()
                    rows.append(dict(shape=shape, count=count, implementation=implementation, status="parser-limit" if known_limit else "compile-failed"))
                    if not known_limit:
                        failures.append(name + ": compile failed")
                    continue
                strategy = "SELECTN" if "SELECTN" in disassembly.stdout else ("JUMPXTABLE" if "JUMPXTABLE" in disassembly.stdout else ("guarded-tree" if "JUMPIFNOTNUMBER" in disassembly.stdout else "comparisons"))
                if implementation in ("table", "function-table"):
                    strategy = "indexed-value-table" if implementation == "table" else "function-table"
                interp = execute([vm, "-" + options.opt, diagnostic], directory / (name + ".correctness.log"))
                if interp.returncode or "CORRECT" not in interp.stdout:
                    failures.append(name + ": interpreter correctness failed")
                    continue
                checked.append(dict(shape=shape, count=count, implementation=implementation, interpreter=True))
                native = None
                if options.native != "off":
                    backend = "x64_ms" if executable_machine(vm) == "x64" and sys.platform == "win32" else (
                        "x64" if executable_machine(vm) == "x64" else "a64")
                    assembly = execute([compiler, "--codegen", "--target=" + backend, "-" + options.opt, diagnostic],
                                       directory / (name + ".native.txt"))
                    check = execute([vm, "-" + options.opt, "--codegen", "--native-report", diagnostic], directory / (name + ".native.log"))
                    witnesses = [line.split("\t") for line in check.stderr.splitlines() if line.startswith("NATIVE\t")]
                    target = [w for w in witnesses if w[2] == "dispatch"]
                    compiled = any(w[3] == "1" for w in target)
                    entered = any(int(w[4]) > 0 for w in target)
                    loop = [w for w in witnesses if w[2] == "measure"]
                    loop_compiled = any(w[3] == "1" for w in loop)
                    loop_entered = any(int(w[4]) > 0 for w in loop)
                    unsupported = "not supported in current configuration" in check.stderr
                    native = dict(requested=True, supported=not unsupported, compiled=compiled and loop_compiled, executed=entered and loop_entered,
                                  dispatch_compiled=compiled, dispatch_entered=entered, loop_compiled=loop_compiled, loop_entered=loop_entered,
                                  offline_backend=backend, offline_generated=assembly.returncode == 0 and "skipping (can't lower)" not in assembly.stdout,
                                  compilation=[line for line in check.stderr.splitlines() if line.startswith(("NATIVE_COMPILE", "NATIVE_FAILURE"))],
                                  status="unsupported" if unsupported else ("executed" if compiled and entered and loop_compiled and loop_entered else "fallback"))
                    if check.returncode or "CORRECT" not in check.stdout:
                        failures.append(name + ": native correctness failed")
                        continue
                    checked[-1]["native"] = native
                for pattern in patterns:
                    target_file = directory / (name + "-" + pattern + ".luau")
                    target_file.write_text(source(shape, count, implementation, pattern, options.iterations, options.samples), encoding="utf-8")
                    modes = ["interpreter"] if options.native != "only" else []
                    if native and native["supported"] and native["executed"] and native["compiled"]:
                        modes.append("native")
                    if not modes:
                        rows.append(dict(shape=shape, count=count, implementation=implementation, pattern=pattern, native=native, status="skipped"))
                    for mode in modes:
                        result = execute([vm, "-" + options.opt] + (["--codegen"] if mode == "native" else []) + [target_file], directory / (name + "-" + pattern + "-" + mode + ".log"))
                        measurements = [line.split() for line in result.stdout.splitlines() if line.startswith("TIME\t")]
                        if result.returncode or len(measurements) != options.samples:
                            failures.append(name + ": " + mode + " timing failed")
                            continue
                        timings = [float(m[1]) * 1000 for m in measurements]
                        rows.append(dict(shape=shape, count=count, implementation=implementation, pattern=pattern, mode=mode,
                                         bytecode_strategy=strategy, native_strategy=("comparison-tree" if COMPARISON_NATIVE else ("indexed-int16-load" if strategy == "SELECTN" else "indexed-branch-slots")) if strategy in ("SELECTN", "JUMPXTABLE") else strategy,
                                         native=native, correct=True, milliseconds=timings, median_ms=statistics.median(timings)))
                print(name, strategy, native["status"] if native else "interpreter", flush=True)
                report = dict(host=platform.platform(), host_machine=platform.machine(), target_machine=executable_machine(vm),
                              build=str(build), options=vars(options) | {"build_dir": str(build)}, correctness=checked,
                              results=rows, failures=failures)
                (directory / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    timings = [r for r in rows if r.get("correct")]
    grouped = {}
    for row in timings:
        grouped.setdefault((row["shape"], row["count"], row["pattern"], row["mode"]), {})[row["implementation"]] = row
    regressions = []
    for key, implementations in grouped.items():
        if "switch" in implementations and "if" in implementations:
            ratio = implementations["switch"]["median_ms"] / implementations["if"]["median_ms"]
            if ratio > 1.10:
                regressions.append(dict(shape=key[0], count=key[1], pattern=key[2], mode=key[3], switch_over_if=ratio))
    native_checks = [c["native"] for c in checked if "native" in c]
    summary = dict(correctness_passed=len(checked), native_requested=len(native_checks),
                   native_compiled=sum(c["supported"] and c["compiled"] for c in native_checks),
                   native_executed=sum(c["supported"] and c["executed"] for c in native_checks),
                   native_unsupported=sum(not c["supported"] for c in native_checks),
                   native_fallback=sum(c["supported"] and not c["executed"] for c in native_checks),
                   timed_configurations=len(timings), failures=len(failures), regression_candidates=len(regressions))
    report = dict(host=platform.platform(), host_machine=platform.machine(), target_machine=executable_machine(vm),
                  build=str(build), options=vars(options) | {"build_dir": str(build)}, correctness=checked,
                  summary=summary, regression_candidates=regressions, results=rows, failures=failures)
    (directory / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    fields = ("shape", "count", "implementation", "pattern", "mode", "bytecode_strategy", "native_strategy", "median_ms")
    with (directory / "results.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(timings)
    print("Summary:", json.dumps(summary))
    lines = ["# Switch matrix", "", f"Host: {report['host_machine']}; executable: {report['target_machine']}.",
             "Windows x64 execution on an ARM64 host uses emulation; compare modes within this executable.", "",
             f"Native SELECTN/JUMPXTABLE strategy: {options.native_strategy}.", "",
             "Dispatch inlining is disabled; timings exclude instrumentation, parsing, compilation, and two warmups.",
             "All samples are retained. Random inputs use a fixed seed and 4096 precomputed entries.", "",
             "```json", json.dumps(summary, indent=2), "```", "",
             "Regressions are candidates exceeding the equivalent if/elseif median by 10%; they require paired confirmation.", "",
             "| Shape | Cases | Pattern | Mode | Switch ms | If ms | Value table ms |", "|---|---:|---|---|---:|---:|---:|"]
    for key, implementations in grouped.items():
        cells = [f"{implementations[k]['median_ms']:.4f}" if k in implementations else "â€”" for k in ("switch", "if", "table")]
        lines.append("| " + " | ".join(map(str, key)) + " | " + " | ".join(cells) + " |")
    (directory / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Results and disassembly:", directory)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
