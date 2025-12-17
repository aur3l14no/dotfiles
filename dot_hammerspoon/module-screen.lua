require("module-config")
require("module-util")

-- Core functions

local function moveToRelScreen(win, rel, showNotify)
  local toScreen = win:screen()
  if rel == 1 then
    toScreen = toScreen:next()
  elseif rel == -1 then
    toScreen = toScreen:previous()
  end

  if win:isFullscreen() then
    win:setFullScreen(false)
    hs.timer.doAfter(1, function()
      win:moveToScreen(toScreen)
    end)
    hs.timer.doAfter(1, function()
      win:setFullScreen(true)
    end)
  else
    -- hack: strangely, using moveToScreen will not maintain correct size
    local unitRect = win:screen():toUnitRect(win:frame())
    win:setFrame(toScreen:fromUnitRect(unitRect))
    win:setFrame(toScreen:fromUnitRect(unitRect))
    -- win:moveToScreen(toScreen)
  end

  if showNotify then
    hs.alert.show("Move " .. win:application():name() .. " to " .. toScreen:name())
  end
end

-- Keybindings

hs.hotkey.bind(hyper, ",", function()
  moveToRelScreen(hs.window.focusedWindow(), -1, true)
end)

hs.hotkey.bind(hyper, ".", function()
  moveToRelScreen(hs.window.focusedWindow(), 1, true)
end)
