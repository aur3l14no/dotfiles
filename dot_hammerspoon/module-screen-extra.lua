require("module-config")
require("module-util")

local log = hs.logger.new("SCREEN", "debug")

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

-- local function moveAllWindowsTo(screenName, showNotify)
--   local wins = hs.window.allWindows()
--   local screen = hs.screen.findByName(screenName)

--   if screen then
--     for i = 1, #wins do
--       local win = wins[i]
--       win:moveToScreen(screen)
--     end
--   end
-- end

-- screen.uuid -> pos
local lastMousePosOnScreen = {}

-- Move mouse to next/prev screen
-- Also focus the frontmost window (using hs.window.orderedWindows) on that screen
-- The mouse position is reset to where it was last time on that screen
-- (remembered at the last time mouse **teleported** out of that screen)
-- or a position with same width/height percentage
local function focusScreen(rel)
  local focusedWin = hs.window.focusedWindow()
  local focusedScreen = focusedWin:screen()
  local mousePos = hs.mouse.getRelativePosition()
  -- (NOW ALWAYS!) only remember mouse position when mouse screen == focused window screen
  local mouseScreen = hs.mouse.getCurrentScreen()
  if true or focusedScreen == mouseScreen then
    lastMousePosOnScreen[mouseScreen:getUUID()] = mousePos
  end

  local targetScreen = mouseScreen
  if rel == 1 then
    targetScreen = mouseScreen:next()
  elseif rel == -1 then
    targetScreen = mouseScreen:previous()
  end

  -- Move cursor
  local prevPos = lastMousePosOnScreen[targetScreen:getUUID()]
  if prevPos then
    -- to previous position on target screen
    hs.mouse.setRelativePosition(prevPos, targetScreen)
  else
    -- to center on target screen
    local center = targetScreen:frame().center - targetScreen:frame().topleft
    hs.mouse.setRelativePosition(center, targetScreen)
  end
  -- Focus the top window on target screen
  for _, win in ipairs(hs.window.orderedWindows()) do
    if win:screen() == targetScreen then
      win:focus()
      break
    end
  end
end

-- Keybindings

hs.hotkey.bind(hyper, "tab", function()
  focusScreen(1)
end)

hs.hotkey.bind(super, "tab", function()
  focusScreen(-1)
end)

hs.hotkey.bind(hyper, ",", function()
  moveToRelScreen(hs.window.focusedWindow(), -1, true)
end)

hs.hotkey.bind(hyper, ".", function()
  moveToRelScreen(hs.window.focusedWindow(), 1, true)
end)

-- Reset mouse position memory every time screen layout is changed
screenWatcher = hs.screen.watcher.new(function()
  log.d("Screen layout changed")
  lastMousePosOnScreen = {}
end)
screenWatcher:start()
