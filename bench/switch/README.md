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

The fallback compiler emits a linear chain of equality comparisons. A balanced numeric tree must not use an ordinary numeric less-than test on arbitrary Luau subjects: `switch "x"` with numeric labels must safely miss those labels, not raise a comparison error or invoke an ordering metamethod. The numeric guard is intrinsic in the forked VM; native CodeGen must decline these experimental opcodes until it can preserve the same semantics. Preserve source-order evaluation of dynamic case expressions, first-match behavior for duplicates, non-integer numbers, NaN, and contextual identifiers.

## Experimental optimized numeric dispatch

At optimization level `-O2`, large sparse switches containing distinct, finite numeric constant case values use a balanced comparison tree rather than source-order linear comparisons. Dense integer cases use direct jump-table dispatch instead. Other switches, including all dynamic case expressions, mixed value types, and duplicate numeric labels, retain the previous dispatch implementation.

The numeric tree uses the experimental `LOP_JUMPIFNOTNUMBER` opcode to avoid numeric ordering comparisons on strings, tables, booleans, nil, and other nonnumeric subjects. This is a **fork-specific bytecode extension**: bytecode emitted by this branch for optimized switches is **not compatible with unmodified Luau VMs**. Do not merge upstream or publish bytecode using this instruction without an explicit opcode/versioning compatibility plan and integration in native CodeGen and other bytecode consumers.

`run.py` runs semantic regressions at `-O1` and `-O2`, then verifies that the generated `-O2` disassembly contains the indexed-dispatch opcode for dense numeric benchmarks containing 64 or more cases. Benchmark results must still be measured; the switch optimization has not been validated on all architectures.

## Bytecode comparison

The benchmark runner disassembles every successful variant at `-O2` and writes `switch-bytecode/comparison.md`. The report compares static opcode counts in the loop dispatch region for switch, function-table, value-table, and if/elseif, plus short instruction excerpts. These static counts are **not** dynamic VM instruction counts. Full disassemblies are written to the gitignored `switch-bytecode/` directory.

## Experimental indexed bytecode dispatch (fork only)

At `-O2`, dense integer switches with at least 64 unique labels (span no
larger than 4,096 and at least 50% occupied) lower to `LOP_JUMPXTABLE`. The
instruction uses an integral-number bounds check and an in-bytecode run of
`LOP_JUMPX` branch slots, allowing direct case-body dispatch without closure
allocation. Sparse or noninteger numeric cases use the guarded comparison tree;
dynamic and mixed-type cases use the original ordered evaluation.

Bytecode containing this opcode is emitted as **version 15** and requires this
fork's VM; older Luau bytecode loaders must reject it. Native CodeGen and
bytecode graph rewriting currently decline protos that contain `JUMPXTABLE`; native CodeGen also declines the numeric guard opcode,
allowing those functions to run in the interpreter instead of generating
incorrect native or rewritten code. This is deliberately experimental and
not an upstream-ready implementation.
