# Switch dispatch experiment

The benchmarks compare `if/elseif`, experimental `switch`, value-table lookup, and function-table dispatch at 4, 16, 64, 256, and 1024 cases.

From the repository root, after configuring the Release build once, run:

```bash
git pull --ff-only origin master && python bench/switch/run.py
```

The runner builds `Luau.Repl.CLI`, `Luau.UnitTest`, and `Luau.Compile.CLI` without building the unrelated ARM64 FASTCALL-failing targets. It runs the full unit-test suite, generates 20 test inputs, disassembles the switch variants, and benchmarks them using Luau's existing `bench/bench.py` harness with `-O2`.

The runner generates:

- `switch-results.md`: self-contained results table, Base64-embedded PNG graph, and inline text bytecode dumps for all switch sizes. Upload this one file for review.
- `switch-results.json` and `switch-results.png`: raw measurements and standalone chart.
- `switch-bytecode/switch-{4,16,64,256,1024}.txt`: individual readable compiler output.

The upstream benchmark harness can exit successfully even when cases fail. The runner validates measurements before publishing the report. The 1024-case `if/elseif` benchmark currently hits the parser recursion-depth limit; this single known failure is reported rather than silently reducing the case count. Any other missing result fails the run.

This experiment measures VM dispatch under Windows ARM64 when run on CLANGARM64. Results should not be generalized to other architectures without additional measurement.
