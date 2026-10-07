#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
python benchmarks/switch/generate.py
cmake --build build --target Luau.Repl.CLI Luau.Compile.CLI

printf "kind,cases,opt,run,seconds,checksum\n"
for opt in 0 1 2; do
  for n in 4 16 64 256; do
    for kind in if switch table; do
      for run in 1 2 3 4 5; do
        out=$(./build/luau.exe -O"$opt" "benchmarks/switch/generated/$kind-$n.luau")
        seconds=$(printf "%s\n" "$out" | awk '{print $3}')
        checksum=$(printf "%s\n" "$out" | awk '{print $4}')
        printf "%s,%s,%s,%s,%s,%s\n" "$kind" "$n" "$opt" "$run" "$seconds" "$checksum"
      done
    done
  done
done
