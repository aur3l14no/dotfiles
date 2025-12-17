-- Paste clipboard as keystrokes!
function emulateKeystroke(c, delay)
  hs.timer.doAfter(delay, function()
    hs.eventtap.keyStrokes(c)
  end)
end
hs.hotkey.bind({ "cmd", "alt", "ctrl", "shift" }, "V", function()
  local contents = hs.pasteboard.getContents()
  local delay = 0.1
  local t = 0
  for i = 1, #contents do
    local c = contents:sub(i, i)
    emulateKeystroke(c, t)
    t = t + delay
  end
end)

-- Print foremost window info
hs.hotkey.bind({ "cmd", "alt", "ctrl" }, "W", function()
  local window = hs.window.frontmostWindow()
  Print(window)
  Print(window:application())
  Print(window:application():bundleID())
end)

function Print(x)
  -- hs.console.printStyledtext(x)
  print(hs.inspect(x))
end

function Notify(msg)
  alert = hs.notify.new({ title = "Hammerspoon", informativeText = msg })
  alert:withdrawAfter(3):send()
end

function timeit(fn, times)
  local t = os.clock()
  if times == nil then
    times = 1
  end
  for i = 1, times do
    fn()
  end
  return (os.clock() - t) / times
end

function map(f, t)
  local o = {}
  for i = 1, #t do
    o[#o + 1] = f(t[i])
  end
  return o
end

function contains(table, val)
  for i = 1, #table do
    if table[i] == val then
      return true
    end
  end
  return false
end