from pathlib import Path

SIZES = [4, 16, 64, 256, 1024]
ITERATIONS = 2_000_000
OUT = Path(__file__).with_name("generated")
OUT.mkdir(parents=True, exist_ok=True)

def body(kind: str, n: int) -> str:
    if kind == "switch":
        dispatch = ["    switch value"]
        for i in range(n):
            dispatch += [f"        case {i} then", f"            result = {i}"]
        dispatch += ["        else", "            result = -1", "    end"]
    else:
        dispatch = []
        for i in range(n):
            prefix = "if" if i == 0 else "elseif"
            dispatch += [f"    {prefix} value == {i} then", f"        result = {i}"]
        dispatch += ["    else", "        result = -1", "    end"]

    return f"""-- generated {kind} benchmark: {n} cases
local clock = os.clock
local result = 0
local checksum = 0
local started = clock()

for i = 1, {ITERATIONS} do
    local value = (i * 73) % {n}
{chr(10).join(dispatch)}
    checksum += result
end

print("{kind}", {n}, clock() - started, checksum)
"""

for n in SIZES:
    for kind in ("switch", "if"):
        (OUT / f"{kind}-{n}.luau").write_text(body(kind, n), newline="\n")

print(f"generated {len(SIZES) * 2} benchmarks in {OUT}")
