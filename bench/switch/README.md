# Switch dispatch experiment

The benchmarks compare `if/elseif`, experimental `switch`, value-table lookup, and function-table dispatch at 4, 16, 64, 256, and 1024 cases.

From the repository root, after configuring the Release build once, run:

```bash
git pull --ff-only origin master && python bench/switch/run.py
```

The runner builds `Luau.Repl.CLI`, `Luau.UnitTest`, and `Luau.Compile.CLI` without building the unrelated ARM64 FASTCALL-failing targets. It runs the full unit-test suite and `bench/switch/regression.luau` semantic checks, generates 20 test inputs, disassembles the switch variants, and benchmarks them using Luau's existing `bench/bench.py` harness with `-O2`.

The runner generates:

- `switch-results.md`: self-contained results table, Base64-embedded PNG graph, and inline text bytecode dumps for all switch sizes. Upload this one file for review.
- `switch-results.json` and `switch-results.png`: raw measurements and standalone chart.
- `switch-bytecode/switch-{4,16,64,256,1024}.txt`: individual readable compiler output.

The upstream benchmark harness can exit successfully even when cases fail. The runner validates measurements before publishing the report. The 1024-case `if/elseif` benchmark currently hits the parser recursion-depth limit; this single known failure is reported rather than silently reducing the case count. Any other missing result fails the run.

This experiment measures VM dispatch under Windows ARM64 when run on CLANGARM64. Results should not be generalized to other architectures without additional measurement.

## Dispatch optimization guardrails

The current compiler emits a linear chain of equality comparisons. A balanced numeric tree must not use an ordinary numeric less-than test on arbitrary Luau subjects: `switch "x"` with numeric labels must safely miss those labels, not raise a comparison error or invoke an ordering metamethod. Until an exact, non-observable numeric type guard is available, retain the equality-based fallback. Preserve source-order evaluation of dynamic case expressions, first-match behavior for duplicates, non-integer numbers, NaN, and contextual identifiers.

## Experimental optimized numeric dispatch

At optimization level `-O2`, switches with at least 16 distinct, finite numeric constant case values now use a balanced comparison tree rather than source-order linear comparisons. Other switches, including all dynamic case expressions, mixed value types, and duplicate numeric labels, retain the previous dispatch implementation.

The numeric tree uses the experimental `LOP_JUMPIFNOTNUMBER` opcode to avoid numeric ordering comparisons on strings, tables, booleans, nil, and other nonnumeric subjects. This is a **fork-specific bytecode extension**: bytecode emitted by this branch for optimized switches is **not compatible with unmodified Luau VMs**. Do not merge upstream or publish bytecode using this instruction without an explicit opcode/versioning compatibility plan and integration in native CodeGen and other bytecode consumers.

`run.py` runs semantic regressions at `-O1` and `-O2`, then verifies that the generated `-O2` disassembly contains the guard opcode for numeric benchmark switches containing 16 or more cases. Benchmark results must still be measured; the switch optimization has not been validated on all architectures.
