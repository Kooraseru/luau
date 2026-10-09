-- Minimal reproducer for dynamic switch-case call dispatch.
local selected = "unset"
local function caseValue(value)
    print("evaluating", value)
    return value
end

assert(type(caseValue) == "function")
switch 3
    case caseValue(1) then selected = "one"
    case caseValue(3) then selected = "three"
    case caseValue(4) then selected = "four"
    else selected = "other"
end
assert(selected == "three", tostring(selected))
print("dynamic case dispatch passed")
