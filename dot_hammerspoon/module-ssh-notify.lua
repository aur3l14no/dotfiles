-- Stream macOS unified log events from /usr/libexec/sshd-session and show a
-- top-right banner whenever an inbound SSH session is accepted.

local KNOWN_KEYS = {
  ["SHA256:y93Hj+oRsOmtT1W0gR5wq0QTkv8abEuKwiRYaKRZgcU"] = "groves",
  ["SHA256:2ImB/ba3YNEmjGcbYPW8ewKeHQIfbwrNZvBhC4ZuemM"] = "john-macbook",
  ["SHA256:1dwseCJx7sZkhjmeQ0G6+9B0MsIcYYlQIolvl40iPF4"] = "fusco-thinkbook",
  ["SHA256:81IPlqdJAvFnn+NAzbU8tttkJwYf3PXVJ8/VdTdqqdU"] = "murph-troy",
  ["SHA256:eAmi0asTIvjYqcTZ9Y/1B98uQ6bV0q7B87HXXQixb8Q"] = "admin-backup",
  ["SHA256:gw31aSENiGYs0nCSIbMPn5sb5yRjdFJn/SwUl5DB+x0"] = "Termius",
  ["SHA256:fYtM9UiRvv447m+J8ub6iKrb8IStYl7wVyuaHHIIaqY"] = "codex-ios",
}

local DEBOUNCE_SECONDS = 30
local PREDICATE = table.concat({
  'process == "sshd-session"',
  'senderImagePath == "/usr/libexec/sshd-session"',
  'eventMessage BEGINSWITH "Accepted "',
}, " AND ")

if _G.__ssh_notify then
  _G.__ssh_notify.stopping = true
  if _G.__ssh_notify.retryTimer then
    _G.__ssh_notify.retryTimer:stop()
    _G.__ssh_notify.retryTimer = nil
  end
  if _G.__ssh_notify.task and _G.__ssh_notify.task:isRunning() then
    _G.__ssh_notify.task:terminate()
  end
end

local state = {
  stopping = false,
  task = nil,
  retryTimer = nil,
  buf = "",
  lastSeen = {},
}
_G.__ssh_notify = state

local function handleLine(line)
  local method, user, peerIp, port, rest =
    line:match("Accepted (%S+) for (%S+) from (%S+) port (%d+)(.*)")
  if not method then
    return
  end

  local fp = rest and rest:match("(SHA256:%S+)") or nil
  local keyName = fp and KNOWN_KEYS[fp] or nil
  local dedupKey = peerIp .. "|" .. (fp or method)
  local now = os.time()

  if state.lastSeen[dedupKey] and (now - state.lastSeen[dedupKey]) < DEBOUNCE_SECONDS then
    return
  end
  state.lastSeen[dedupKey] = now

  local title = keyName and "SSH Login" or "SSH Login (Unknown Key)"
  local subTitle = string.format("%s@%s ← %s:%s", user, hs.host.localizedName(), peerIp, port)
  local info = keyName and string.format("Key: %s (%s)", keyName, method)
    or string.format("UNKNOWN KEY: %s (%s)", fp or "none", method)

  hs.notify.new({
    title = title,
    subTitle = subTitle,
    informativeText = info,
    withdrawAfter = 15,
  }):send()
end

local function startWatcher()
  if state.stopping then
    return
  end
  state.buf = ""
  state.task = hs.task.new(
    "/usr/bin/log",
    function()
      state.task = nil
      if not state.stopping then
        state.retryTimer = hs.timer.doAfter(5, startWatcher)
      end
    end,
    function(_, stdOut, _)
      if not stdOut or #stdOut == 0 then
        return true
      end
      state.buf = state.buf .. stdOut
      while true do
        local nl = state.buf:find("\n", 1, true)
        if not nl then
          break
        end
        local line = state.buf:sub(1, nl - 1)
        state.buf = state.buf:sub(nl + 1)
        handleLine(line)
      end
      return true
    end,
    { "stream", "--info", "--style", "compact", "--predicate", PREDICATE }
  )
  if state.task then
    state.task:start()
  end
end

startWatcher()
