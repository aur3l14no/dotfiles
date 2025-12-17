require("module-config")

local caffeinateTrayIcon = hs.menubar.new()

local function caffeinateSetIcon(state)
  caffeinateTrayIcon:setIcon(hs.configdir .. "/assets/" .. (state and "caffeinate-on.pdf" or "caffeinate-off.pdf"))
end

local function toggleCaffeinate()
  local sleepStatus = hs.caffeinate.toggle("displayIdle")
  if sleepStatus then
    Notify("System never sleep")
  else
    Notify("System will sleep when idle")
  end

  caffeinateSetIcon(sleepStatus)
end

hs.hotkey.bind(hyper, "=", toggleCaffeinate)
caffeinateTrayIcon:setClickCallback(toggleCaffeinate)
caffeinateSetIcon(false)
