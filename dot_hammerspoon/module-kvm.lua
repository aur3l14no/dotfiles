--- Software KVM.
--- Emitting signal to switch external monitor's input source when specified USB device is connected.

local log = hs.logger.new("USBKVM", "info")

local M1DDC_PATH = "/Users/y/bin/m1ddc"

-- Solution 1. When specific USB device is connected, use m1ddc/lunar to send DDC signal to switch monitor's input

-- local function handler(event)
--   log.d(hs.inspect(event))
--   local triggerProductID = 21033
--   if event["eventType"] == "added" and event["productID"] == triggerProductID then
--     if hs.execute(M1DDC_PATH .. " get input") == "15\n" then
--       hs.execute(M1DDC_PATH .. " set input 17")
--       hs.caffeinate.declareUserActivity()
--     end
--   elseif event["eventType"] == "removed" and event["productID"] == triggerProductID then
--     if hs.execute(M1DDC_PATH .. " get input") == "17\n" then
--       hs.execute(M1DDC_PATH .. " set input 15")
--     end
--   end
-- end

-- Solution 2. Monitor has KVM. But macOS won't wake up even when display is connected.
-- Therefore we detect connection of monitor-attached USB devices and wake up.
-- Note that this solution requires other machines can issue `input switch` to monitor.

-- When USB Hub (ULT-unite) (29264) is connected, wake up
-- When MSI (16292) is connected, wake up
local function handler(event)
  log.d(hs.inspect(event))
  if event["eventType"] == "added" and event["productID"] == 16292 then
    log.i("Detected MSI connection, waking up")
    hs.caffeinate.declareUserActivity()
  end
end

kvmUSBWatcher = hs.usb.watcher.new(handler)
kvmUSBWatcher:start()

hs.hotkey.bind('ctrl+option+shift', '\\', function()
  log.i('Switching to HDMI 1')
  hs.execute('/Users/y/.local/bin/lunar set input hdmi1')
end)
