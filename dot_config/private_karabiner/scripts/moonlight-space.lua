-- Called by Karabiner through Hammerspoon IPC, without synthesizing a hotkey.
return function(direction)
    assert(direction == -1 or direction == 1, "Direction must be -1 or 1")
    local spaces = hs.spaces
    local current = spaces.focusedSpace()
    local screen = assert(spaces.spaceDisplay(current))
    local ordered = assert(spaces.spacesForScreen(screen))

    for index, id in ipairs(ordered) do
        if id == current then
            local target = ordered[index + direction]
            if not target then return false, "Already at the edge" end
            local ok, err = spaces.gotoSpace(target)
            if not ok then
                hs.alert.show("Space 切换失败：" .. tostring(err))
            end
            return ok, err
        end
    end
    error("Current Space is missing from its display")
end
