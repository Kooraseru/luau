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


-- A 64-way all-numeric switch exercises the optimized dispatch at -O2.
-- Non-number subjects must miss without invoking numeric comparison metamethods.
local function largeNumericSwitch(value)
    local selected = -1
    switch value
    case 0 then selected = 0
    case 1 then selected = 1
    case 2 then selected = 2
    case 3 then selected = 3
    case 4 then selected = 4
    case 5 then selected = 5
    case 6 then selected = 6
    case 7 then selected = 7
    case 8 then selected = 8
    case 9 then selected = 9
    case 10 then selected = 10
    case 11 then selected = 11
    case 12 then selected = 12
    case 13 then selected = 13
    case 14 then selected = 14
    case 15 then selected = 15
    case 16 then selected = 16
    case 17 then selected = 17
    case 18 then selected = 18
    case 19 then selected = 19
    case 20 then selected = 20
    case 21 then selected = 21
    case 22 then selected = 22
    case 23 then selected = 23
    case 24 then selected = 24
    case 25 then selected = 25
    case 26 then selected = 26
    case 27 then selected = 27
    case 28 then selected = 28
    case 29 then selected = 29
    case 30 then selected = 30
    case 31 then selected = 31
    case 32 then selected = 32
    case 33 then selected = 33
    case 34 then selected = 34
    case 35 then selected = 35
    case 36 then selected = 36
    case 37 then selected = 37
    case 38 then selected = 38
    case 39 then selected = 39
    case 40 then selected = 40
    case 41 then selected = 41
    case 42 then selected = 42
    case 43 then selected = 43
    case 44 then selected = 44
    case 45 then selected = 45
    case 46 then selected = 46
    case 47 then selected = 47
    case 48 then selected = 48
    case 49 then selected = 49
    case 50 then selected = 50
    case 51 then selected = 51
    case 52 then selected = 52
    case 53 then selected = 53
    case 54 then selected = 54
    case 55 then selected = 55
    case 56 then selected = 56
    case 57 then selected = 57
    case 58 then selected = 58
    case 59 then selected = 59
    case 60 then selected = 60
    case 61 then selected = 61
    case 62 then selected = 62
    case 63 then selected = 63
    else selected = -2
    end
    return selected
end

for i = 0, 63 do
    check(largeNumericSwitch(i), i)
end
for _, value in {"10", true, false, {}, 0.5, -1, 64, math.huge} do
    check(largeNumericSwitch(value), -2)
end
check(largeNumericSwitch(0 / 0), -2)

-- A sparse 64-way integer range has holes, negative labels, and no accidental
-- first-match collisions. It also exercises the tree fallback for large switches.
local function sparseNumericSwitch(value)
    local selected = -100
    switch value
    case -64 then selected = -32
    case -62 then selected = -31
    case -60 then selected = -30
    case -58 then selected = -29
    case -56 then selected = -28
    case -54 then selected = -27
    case -52 then selected = -26
    case -50 then selected = -25
    case -48 then selected = -24
    case -46 then selected = -23
    case -44 then selected = -22
    case -42 then selected = -21
    case -40 then selected = -20
    case -38 then selected = -19
    case -36 then selected = -18
    case -34 then selected = -17
    case -32 then selected = -16
    case -30 then selected = -15
    case -28 then selected = -14
    case -26 then selected = -13
    case -24 then selected = -12
    case -22 then selected = -11
    case -20 then selected = -10
    case -18 then selected = -9
    case -16 then selected = -8
    case -14 then selected = -7
    case -12 then selected = -6
    case -10 then selected = -5
    case -8 then selected = -4
    case -6 then selected = -3
    case -4 then selected = -2
    case -2 then selected = -1
    case 0 then selected = 0
    case 2 then selected = 1
    case 4 then selected = 2
    case 6 then selected = 3
    case 8 then selected = 4
    case 10 then selected = 5
    case 12 then selected = 6
    case 14 then selected = 7
    case 16 then selected = 8
    case 18 then selected = 9
    case 20 then selected = 10
    case 22 then selected = 11
    case 24 then selected = 12
    case 26 then selected = 13
    case 28 then selected = 14
    case 30 then selected = 15
    case 32 then selected = 16
    case 34 then selected = 17
    case 36 then selected = 18
    case 38 then selected = 19
    case 40 then selected = 20
    case 42 then selected = 21
    case 44 then selected = 22
    case 46 then selected = 23
    case 48 then selected = 24
    case 50 then selected = 25
    case 52 then selected = 26
    case 54 then selected = 27
    case 56 then selected = 28
    case 58 then selected = 29
    case 60 then selected = 30
    case 62 then selected = 31
    else selected = -101
    end
    return selected
end

for i = -32, 31 do
    check(sparseNumericSwitch(i * 2), i)
end
for _, value in {-65, -63, -1, 1, 63, 64, "0", false, {}, math.huge} do
    check(sparseNumericSwitch(value), -101)
end
check(sparseNumericSwitch(0 / 0), -101)

-- The type guard must be intrinsic, not a Lua call to a mutable global.
local originalType = type
type = function()
    error("switch must not call type")
end
check(largeNumericSwitch("5"), -2)
check(largeNumericSwitch(5), 5)
type = originalType

print("switch dispatch regression checks passed")
