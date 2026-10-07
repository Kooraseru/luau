from pathlib import Path

SIZES = [4, 16, 64, 256]
ITERATIONS = 2_000_000
KINDS = ("if", "switch", "table", "function-table")
OUT = Path(__file__).with_name("generated")
OUT.mkdir(parents=True, exist_ok=True)

def dispatch(kind: str, n: int) -> list[str]:
    if kind == "switch":
        lines = ["    switch value"]
        for i in range(n):
            lines += [f"        case {i} then", f"            result = {i}"]
        return lines + ["        else", "            result = -1", "    end"]

    if kind == "if":
        lines = []
        for i in range(n):
            prefix = "if" if i == 0 else "elseif"
            lines += [f"    {prefix} value == {i} then", f"        result = {i}"]
        return lines + ["    else", "        result = -1", "    end"]

    if kind == "table":
        return ["    result = lookup[value] or -1"]

    if kind == "function-table":
        return ["    result = handlers[value]()"]

    raise ValueError(kind)

def body(kind: str, n: int) -> str:
    setup = ""
    if kind == "table":
        entries = ", ".join(f"[{i}] = {i}" for i in range(n))
        setup = f"local lookup = {{{entries}}}\n"
    elif kind == "function-table":
        entries = ", ".join(f"[{i}] = function() return {i} end" for i in range(n))
        setup = f"local handlers = {{{entries}}}\n"

    return f"""-- generated {kind} benchmark: {n} cases
local clock = os.clock
local result = 0
local checksum = 0
{setup}local started = clock()

for i = 1, {ITERATIONS} do
    local value = (i * 73) % {n}
{chr(10).join(dispatch(kind, n))}
    checksum += result
end

print("{kind}", {n}, clock() - started, checksum)
"""

for n in SIZES:
    for kind in KINDS:
        (OUT / f"{kind}-{n}.luau").write_text(body(kind, n), newline="\n")

print(f"generated {len(SIZES) * len(KINDS)} benchmarks in {OUT}")
