-- Diagnose import generation inside inlined calls, independently of switch.
local function caseValue(value)
    print("evaluating", value)
    return value
end

assert(type(caseValue) == "function")
assert(caseValue(3) == 3)
print("ordinary inlining passed")
