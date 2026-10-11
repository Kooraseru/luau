# Switch dispatch experiment

## O2 interpreter/native matrix

```sh
python bench/switch/run.py --suite full --opt O2 --native both
```

The default build directory is `build-release`. On this Windows ARM64 host the
runtime reports native support as unavailable and native timings are skipped.
An installed LLVM-MinGW cross compiler was used to create `build-native-x64`:

```sh
cmake -S . -B build-native-x64 -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=x86_64-w64-mingw32-clang -DCMAKE_CXX_COMPILER=x86_64-w64-mingw32-clang++
python bench/switch/run.py --suite full --opt O2 --native both --build-dir build-native-x64
```

The configure command is required once, and again if the build directory is
removed. Put the LLVM-MinGW `bin` directory on PATH first. The runner builds
the configured targets; it does not choose or configure a compiler toolchain.

That executable runs through Windows x64 emulation. Compare interpreter/native
modes within it; do not combine its numbers with ARM64 interpreter results.
`--suite smoke` uses one count per shape and cycling/miss inputs; `--native off`
or `--native only`, `--shapes`, `--iterations`, `--samples`, and `--skip-build`
allow focused runs. The original command without `--suite` remains unchanged.

The generator covers dense/sparse integers, strings, mixed labels, constant
selection, arithmetic, calls, side effects, dynamic labels, small/large switches,
and nesting. Ordinary shapes use 4/16/64/256 cases; small uses 2/4 and large
256/1024. Fixed/cycling/pseudorandom/miss patterns use 4096 precomputed inputs.
An independent Python oracle checks every label, defaults, ordered dynamic-label
visits, and side effects. Each timed sample also checks its expected checksum.
Indexed value tables are included only for pure selection. Dynamic labels skip
both table implementations; the known 1024-elseif parser limit is reported.

`dispatch` and the timed loop are marked native and protected from O2 inlining with the existing
`DebugLuauNoInline` flag. A separate `--native-report` correctness process records
compilation results and actual entries through the native execution gate for
both exact protos. Function-table handlers are also marked native. Timed
processes have no reporting hook. A compiled but unused
proto, unsupported runtime, or interpreter fallback produces no native timing.
This measures native dispatcher entry, not a claim that every operation within
it avoids VM/C call boundaries.

Results, all uncensored samples, logs, source, bytecode disassembly, and native
assembly/IR are saved
under ignored `build/switch/bytecode/suite-<build>-<suite>-<opt>-<native-strategy>/`. `summary.md` compares
medians; `results.csv` provides graph-ready median rows; `results.json` includes the bytecode strategy, native strategy, host and
executable architecture, native status, correctness and failure totals.
Performance candidates above the equivalent if median by 10% are listed for
paired confirmation rather than treated as proven regressions.

The earlier comparison-based local x64 matrix passed **151 correctness pairs**, compiled and entered
all 151 native dispatchers/loops, and completed **1208 timed configurations**
(including equivalent baselines), with zero failures or fallback timings.
Six initial performance candidates were checked in seven alternating paired
rounds. Five disappeared; nested/16/fixed/native remained about 12.4% slower
than its if equivalent. It uses ordinary comparisons, not the new indexed-op
native translation. Raw confirmation samples are saved in
`regression-confirmation.json` beside the full results.

For 100000 random inputs at 64 cases, native constant selection measured
5.034 ms versus 3.763 ms for a value table; interpreter SELECTN measured
3.497 ms versus 5.424 ms. At 1024 dense returning cases, native comparison
lowering measured 7.641 ms versus 3.778 ms for a value table. These x64-emulated
results motivated native indexed lowering; they do not
establish ARM64 hardware performance or justify another VM opcode.

### Native indexed lowering

The default native strategy uses an indexed int16 data load for `SELECTN` and
an indexed branch-slot table for `JUMPXTABLE`. On x64, each slot contains a
five-byte relative jump and three padding bytes; A64 uses one four-byte branch.
Relative branches reuse the assembler's label fixups and avoid absolute pointer
relocations. Every destination remains an explicit IR operand, so control-flow
analysis, register liveness and dead-store elimination see every possible edge.
The branch-slot approach still incurs an indirect branch followed by a direct
branch; it is not a claim of globally optimal machine code.

Numeric tag, unsigned offset bounds and exact round-trip comparison preserve
miss behavior. Bounds are checked before converting back to a number so that
out-of-range misses avoid that work. The original subject must equal the
converted integer, rejecting fractions, NaN and infinities even when a conversion
sentinel happens to be a valid label. The interpreter compares the reconstructed label against
the original subject, fixing the same tiny-fraction rounding bug in both indexed
handlers. No new VM opcode or bytecode format is needed.

Use `--native-strategy comparison` to retain the previous native comparison
lowering in the same binary, with separate output artifacts. After a full run,
alternate both strategies and confirm slowdown candidates with:

```sh
python bench/switch/compare_native.py --results build/switch/bytecode/suite-build-native-x64-full-O2-indexed/results.json --previous build/switch/bytecode/suite-build-native-x64-full-O2/results.json
```

This saves paired samples and ratios in `paired-comparison.json` and `.csv`.
An indexed/comparison ratio below one favors indexed dispatch. The comparison
flag changes native lowering only; interpreter bytecode remains identical.

Final local validation passed 151 correctness/native execution checks and 1208
timing configurations with no failures or native fallbacks. Both full unit suites
passed: x64 5535 tests/36469 assertions, ARM64 5532 tests/36412 assertions.
Seven alternating process rounds covered 64 paired configurations; none of the
switch/if slowdown candidates from the current or previous run remained above 10%.

For random hits, indexed native selection reduced time versus comparison lowering
by 56.6% at 64 cases and 63.5% at 256 cases. Native dense dispatch improved 14.4%
at 64 random cases and 34.3% at 1024 random cases. These are paired median ratios
on the emulated x64 executable, not ARM64 hardware performance claims.

The comparison tree retains a best case: the fixed probe hits its first pivot.
Indexed value selection at 256 cases is 11.2% slower there, and dense/64 cycling
is 10.8% slower than comparison lowering. Retaining the comparison override makes
those tradeoffs measurable. The default preserves comparisons for small switches,
uses indexed selection for eligible constant assignments, and indexed dispatch for
dense control flow; sparse and dynamic matching retain their existing strategies.
This reduces dense dispatch's dependence on case count; it does not establish a
universally optimal strategy for every hit distribution.

## Current value-selection result

At `-O2`, eligible switches now use the experimental `SELECTN` instruction:
24 or more distinct dense int32 labels, with every case and an explicit default
assigning a signed 16-bit integer constant to the same local. The span is capped
at 4,096 and must be at least 50% occupied. Negative-zero outputs, noninteger or
larger outputs, booleans/strings/nil, calls, extra statements, dynamic/duplicate
labels, upvalue destinations, debug level 2 and coverage retain ordinary dispatch.

`SELECTN` preserves the existing number, range and exact-integer checks. It reads
the selected inline integer value and writes the destination directly, then
continues after the payload. Holes and invalid subjects select the default.
No table object, case-body branch, or rejoin instruction is needed. Its inline
`LOADN` words are **data, not dynamically executed instructions**.

The instruction requires this fork's **bytecode version 16**. Version-15 and
upstream VMs reject that bytecode. Native CodeGen lowers it through indexed int16 selection; bytecode
graph rewriting still explicitly declines functions containing it. This machine's Windows ARM64 CLI
reports that native execution is unsupported, so the historical performance claims below
are interpreter claims. The new matrix also validates an x64 JIT executable
running under Windows emulation; those results are kept separate. General side-effectful case bodies still use
`JUMPXTABLE`, the numeric tree, or ordered comparisons.

Local alternating baseline/candidate trials used seven paired process rounds,
two warmups and five uncensored samples per process, with identical precomputed
inputs and shuffled non-affine output constants. For 500,000 iterations:

| 64-case workload | Before | SELECTN | Runtime reduction |
| --- | ---: | ---: | ---: |
| Cycling hits | 18.33 ms | 5.86 ms | 68.0% |
| Pseudorandom hits | 18.24 ms | 5.93 ms | 67.5% |
| Negative-key pseudorandom hits | 18.16 ms | 5.89 ms | 67.6% |
| 90% misses | 7.64 ms | 5.50 ms | 28.1% |

All seven paired rounds favored SELECTN on these workloads. The 16-case and
sparse controls changed by less than 3%. Serialized 64-case dispatch bytecode
shrunk from 1,063 to 417 bytes; combined compilation/loading of 200 such chunks
measured 11.78 -> 10.74 ms. Raw local artifacts are in
`build/switch/bytecode/optimization-probes/`; the ignored checklist at
`build/switch/switch-optimization-checklist.md` records the hypotheses, rejected prototypes
and acceptance gates. These timings do not establish a universal optimum.

The ordinary benchmark runner also exercises this lowering. The historical
measurements below predate SELECTN and explain how the general dispatch
thresholds were chosen; use the newly generated `build/switch/switch-results.md` for current
main-harness measurements.

## Local dispatch diagnostics

`python bench/switch/diagnostic.py` generates 36 controlled 64-case workloads and
six dense-switch cutoff probes (8, 16, 24, 32, 48 and 64 cases) and three sparse
probes (24, 32 and 48 cases) in
`build/switch/diagnostic-generated/`. Run them with:

```bash
python bench/bench.py --folder build/switch/diagnostic-generated --vm "build-release/luau.exe -O2" --filename build/switch/switch-diagnostic --absolute
```

The controlled workloads compare dense switch dispatch, value-table lookup,
sparse numeric switch dispatch (the guarded comparison tree), and a baseline
that computes the answer without dispatch. Each uses constant
value selection, runtime arithmetic, or a `math.floor` call, with cycling,
fixed, or pseudorandom case hits. The sparse tree evaluates `value * 101` as
its subject, so its timings include that multiplication. The pseudorandom
input uses high bits from a deterministic LCG; its sequence is reproducible.
All three hit distributions read a precomputed 4,096-element input array through
the same loop, so input generation no longer confounds comparisons between
distributions. Baseline timings include the same input reads and checksum work.
`math.floor` uses the builtin FASTCALL path; it is not a general user-function call.
Generated inputs and results are local artifacts ignored by Git.

`python bench/switch/rejoin.py` generates a second set of 18 workloads in
`build/switch/rejoin-generated/`. Benchmark them with the same command, using
that folder and `--filename build/switch/switch-rejoin`. Both forms call a 64-case dispatch
function. The `rejoin` form assigns within each case, then performs a runtime
addition and returns after the switch; the `direct` form performs the same
addition and returns within each case. The runtime addition prevents the
compiler from turning the shared continuation into per-case returns.

The benchmarks compare `if/elseif`, experimental `switch`, value-table lookup, and function-table dispatch at 4, 16, 64, 256, and 1024 cases.

From the repository root, after configuring the Release build once, run:

```bash
python bench/switch/run.py
```

The runner builds `Luau.Repl.CLI`, `Luau.UnitTest`, and `Luau.Compile.CLI` without building the unrelated ARM64 FASTCALL-failing targets. It runs the full unit-test suite and `bench/switch/regression.luau` semantic checks, generates 20 test inputs, disassembles the switch variants, and benchmarks them using Luau's existing `bench/bench.py` harness with `-O2`.

The runner generates:

- `build/switch/switch-results.md`: self-contained results table, Base64-embedded PNG graph, and inline text bytecode dumps for all switch sizes. Upload this one file for review.
- `build/switch/switch-results.json` and `build/switch/switch-results.png`: raw measurements and standalone chart.
- `build/switch/bytecode/switch-{4,16,64,256,1024}.txt`: individual readable compiler output.

The upstream benchmark harness can exit successfully even when cases fail. The runner validates measurements before publishing the report. The 1024-case `if/elseif` benchmark currently hits the parser recursion-depth limit; this single known failure is reported rather than silently reducing the case count. Any other missing result fails the run.

This experiment measures VM dispatch under Windows ARM64 when run on CLANGARM64. Results should not be generalized to other architectures without additional measurement.

## Dispatch optimization guardrails

The fallback compiler emits a linear chain of equality comparisons. A balanced numeric tree must not use an ordinary numeric less-than test on arbitrary Luau subjects: `switch "x"` with numeric labels must safely miss those labels, not raise a comparison error or invoke an ordering metamethod. The numeric guard is intrinsic in the forked VM; native CodeGen now preserves the same semantics using tag guards and numeric comparison IR. Preserve source-order evaluation of dynamic case expressions, first-match behavior for duplicates, non-integer numbers, NaN, and contextual identifiers.

## Experimental optimized numeric dispatch

At optimization level `-O2`, large sparse switches containing distinct, finite numeric constant case values use a balanced comparison tree rather than source-order linear comparisons. Dense integer cases use direct jump-table dispatch unless they qualify for SELECTN value selection. Other switches, including all dynamic case expressions, mixed value types, and duplicate numeric labels, retain the previous dispatch implementation.

The numeric tree uses the experimental `LOP_JUMPIFNOTNUMBER` opcode to avoid numeric ordering comparisons on strings, tables, booleans, nil, and other nonnumeric subjects. This is a **fork-specific bytecode extension**: bytecode emitted by this branch for optimized switches is **not compatible with unmodified Luau VMs**. Do not merge upstream or publish bytecode using this instruction without an explicit opcode/versioning compatibility plan and integration in native CodeGen and other bytecode consumers.

`run.py` runs semantic regressions at `-O1` and `-O2`, then verifies that the generated `-O2` disassembly contains SELECTN for the constant-number benchmarks containing 64 or more cases. The switch optimization has not been validated on all architectures.

## Bytecode comparison

The benchmark runner disassembles every successful variant at `-O2` and writes `build/switch/bytecode/comparison.md`. The report compares static opcode counts in the loop dispatch region for switch, function-table, value-table, and if/elseif, plus short instruction excerpts. These static counts are **not** dynamic VM instruction counts. Full disassemblies are written to the gitignored `build/switch/bytecode/` directory.

## Experimental indexed bytecode dispatch (fork only)

At `-O2`, dense integer switches with at least 24 unique labels (span no
larger than 4,096 and at least 50% occupied) lower to `LOP_JUMPXTABLE`. The
instruction uses an integral-number bounds check and an in-bytecode run of
`LOP_JUMPX` branch slots, allowing direct case-body dispatch without closure
allocation. Sparse or noninteger numeric cases use the guarded comparison tree;
dynamic and mixed-type cases use the original ordered evaluation.

Bytecode containing this opcode is emitted as **version 15** and requires this
fork's VM; older Luau bytecode loaders must reject it. Bytecode graph rewriting still declines
protos containing indexed dispatch. Native CodeGen handles the numeric guard,
models all table successors, skips inline data, and lowers table dispatch to
balanced numeric comparisons on x64 and A64. Native indexed loads/indirect
jumps are not implemented by this initial lowering.

## Why the compiler selects these strategies

Known primitive subjects are selected at compile time when the relevant case
labels are also primitive constants. Selection stops at the first match, so
duplicates retain first-match behavior. An unknown or nonprimitive expression
before the match retains ordinary dispatch and its observable effects.

Otherwise, the subject is evaluated once. Eligible constant-number assignments
use SELECTN as described above. At `-O2`, other distinct dense integer labels use
direct indexed dispatch: selection is constant time, with bounds and integer
checks retained in the VM. The compiler patches each case's slot directly from
its recorded key, making slot construction O(cases + span) instead of scanning
every slot for every case. Case bodies and their control-flow joins keep their
existing semantics.

Sparse switches with at least 32 distinct finite numeric constants use a guarded
balanced tree. Equality at each pivot preserves immediate matches there.
Once a partition contains at most 16 labels, a short equality chain replaces
further pivot loads and ordering branches. This combines bounded tree depth
with the cheaper equality instruction near the leaves. Nonnumeric subjects
bypass ordering completely; numeric misses, including NaN, reach the default.

Small switches, duplicate labels, dynamic case expressions, mixed types and
nonfinite labels retain ordered equality dispatch. This preserves first-match
behavior and source-order evaluation of side effects.

The cutoffs are measured tradeoffs for this interpreter and machine, not proof
of a universal optimum. Native CodeGen currently uses comparison IR even when
the bytecode selects SELECTN or JUMPXTABLE. The matrix records both choices;
interpreter thresholds therefore do not imply optimal native strategy choices.

### Historical dispatch-strategy measurements (before SELECTN)

The saved baseline executable was built before these changes. The following
are paired average times for two million dispatches, measured with the existing
harness on Windows ARM64. The sparse probes use the same precomputed input reads
in both executables. Full measurements are local JSON artifacts in
`build/switch/bytecode/final-comparison.json` and `build/switch/bytecode/cutoff-comparison.json`.

| Workload | Before | After | Runtime reduction |
| --- | ---: | ---: | ---: |
| Dense 24-case value selection | 84.08 ms | 54.01 ms | 35.8% |
| Dense 32-case value selection | 106.03 ms | 54.84 ms | 48.3% |
| Dense 48-case value selection | 151.55 ms | 54.25 ms | 64.2% |
| Sparse 32-case value selection, cycling | 118.31 ms | 96.91 ms | 18.1% |
| Sparse 48-case value selection, cycling | 163.62 ms | 108.08 ms | 33.9% |
| Sparse 64-case arithmetic, cycling | 139.91 ms | 120.41 ms | 13.9% |
| Sparse 64-case `math.floor`, cycling | 149.08 ms | 126.18 ms | 15.4% |
| Sparse 64-case value selection, random | 148.82 ms | 132.24 ms | 11.1% |

Leaves of 4, 8 and 16 labels were compared; 16 was fastest in the measured
64-case cycling, fixed and random probes. Pivot equality remains in the final
implementation so those labels can still match immediately. Small-switch
dispatch is retained below the new cutoffs. Trials that changed the VM's integer
guard or combined numeric assignment and join during dispatch did not show a
reliable gain and were removed.

The earlier fixed/cycling/random probes generated their inputs differently
inside the timed loop. Their total-time differences do not isolate branch
prediction. The corrected diagnostics use identical input reads; the interpreter
also branches to opcode handlers rather than a unique native address for each
source case. No claim about branch prediction follows from these timings alone.

Before SELECTN, the corrected 64-case diagnostics produced the following medians, including
the same input reads and checksum updates in each variant:

| Cycling workload | No dispatch | Value table | Dense switch |
| --- | ---: | ---: | ---: |
| Value selection | 19.58 ms | 39.50 ms | 77.06 ms |
| Arithmetic | 25.30 ms | 37.82 ms | 76.54 ms |
| `math.floor` | 33.77 ms | 46.99 ms | 82.18 ms |

Fixed/cycling/random dense value selection measured 74.07/77.06/75.35 ms with
matched input reads. The earlier large gap between distributions disappears.
The earlier arithmetic near-parity result also does not persist here; it must
not be treated as a general dispatch result. These small case bodies still
favor value lookup, and the timings do not isolate each remaining VM cost.
The latest original harness also measured function-table-64 at 47.87 ms versus
switch-64 at 54.60 ms, so switch does not universally beat function tables.

Historical validation: 5,529 unit tests and 36,211 assertions passed. Semantic regressions
passed at `-O1` and `-O2`, and all 45 diagnostics and 18 rejoin workloads completed. The original
runner produced 19 successful workloads; only its documented 1,024-case
`if/elseif` parser limit failed. That earlier compiler-only phase introduced no
new opcode. Current SELECTN validation passed 5,530 tests and 36,249 assertions,
plus the expanded semantic regressions at O1/O2. Its main runner produced 19
successful workloads, with only the same documented if-1024 parser limit.

## Local artifact layout

All generated sources, reports, disassembly, and the optimization checklist live
under `build/switch/`, covered by Luau's original `/build/` ignore rule. Maintained
runners and handwritten regression sources remain in `bench/switch/`. No
switch-specific ignore rules are needed. Existing build directories are unchanged.
