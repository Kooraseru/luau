-- Regression coverage for optimizing Luau switch dispatch.
-- Keep these observable semantics unchanged when rewriting dispatch.

local function check(actual, expected)
    assert(actual == expected, tostring(actual) .. " ~= " .. tostring(expected))
end

local evaluations = 0
local function subject(value)
    evaluations += 1
    return value
end

local selected = "unset"
switch subject(2)
    case 1 then selected = "one"
    case 2 then selected = "two"
    else selected = "other"
end
check(selected, "two")
check(evaluations, 1)

-- Numeric ordering must never make a nonnumber subject throw.
for _, value in {"2", false, {}, 2.5, -1, 99} do
    selected = "unset"
    switch value
        case 0 then selected = "zero"
        case 1 then selected = "one"
        case 2 then selected = "two"
        case 3 then selected = "three"
        case 4 then selected = "four"
        else selected = "other"
    end
    check(selected, "other")
end

-- First match wins, including duplicates.
switch 7
    case 7 then selected = "first"
    case 7 then selected = "second"
    else selected = "other"
end
check(selected, "first")

-- Dynamic expressions must retain source-order evaluation and short-circuit.
local order = {}
local function caseValue(value)
    table.insert(order, value)
    return value
end

switch 3
    case caseValue(1) then selected = "one"
    case caseValue(3) then selected = "three"
    case caseValue(4) then selected = "four"
    else selected = "other"
end
check(selected, "three")
check(table.concat(order, ","), "1,3")

-- Static cases separated by a dynamic case may not be reordered across it.
order = {}
switch 5
    case 1 then selected = "one"
    case caseValue(5) then selected = "dynamic"
    case 5 then selected = "static"
    else selected = "other"
end
check(selected, "dynamic")
check(table.concat(order, ","), "5")

-- Equality is strict across number/string/bool/nil types.
switch "3"
    case 3 then selected = "number"
    case "3" then selected = "string"
    else selected = "other"
end
check(selected, "string")

switch nil
    case false then selected = "false"
    case nil then selected = "nil"
    else selected = "other"
end
check(selected, "nil")

-- Fractional and negative numbers, including a numeric miss.
switch -2.5
    case -3 then selected = "negative integer"
    case -2.5 then selected = "fraction"
    else selected = "other"
end
check(selected, "fraction")

local nan = 0 / 0
switch nan
    case nan then selected = "nan"
    else selected = "other"
end
check(selected, "other")

-- Contextual keywords remain usable identifiers.
local case = 8
local switch = {case = case}
check(switch.case, 8)

print("switch dispatch regression checks passed")
