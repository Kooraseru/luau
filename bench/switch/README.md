# Switch dispatch experiment

This experiment uses Luau's existing benchmark harness instead of a custom timing runner.

The generated cases compare linear `if/elseif`, the experimental `switch`, direct value-table lookup, and function-table dispatch at 4, 16, 64, 256, and 1024 cases.

Generate the benchmark inputs:

```bash
python bench/switch/generate.py
```

Build a Release VM:

```bash
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target Luau.Repl.CLI
```

Run the benchmark with the upstream harness:

```bash
python bench/bench.py --folder bench/switch/generated --vm "../build-release/luau.exe -O2" --filename switch-results --absolute
```

`bench.py` performs the repeated measurements, outlier handling, CPU-affinity behavior, JSON output, statistics, and PNG graph using the same machinery as Luau's existing VM benchmarks.

Optionally create a compact Markdown report from the harness JSON:

```bash
python bench/switch/report.py switch-results.json
```

This produces `switch-results.md` and embeds `switch-results.png` when the graph exists.

The 1024-case inputs are intentionally a stress case. If an implementation exceeds a compiler/parser limit, that failure should be reported rather than silently reducing the case count.
