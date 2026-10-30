-- polykybd.lua - the Neovim transport of plugin/polykybd.vim.
--
-- Sends one HTTP request to PolyKybdHost on 127.0.0.1 over a libuv TCP handle
-- and closes it. Nothing here blocks: the connect, write and read run in the
-- event loop, and every error just closes the handle. Only the last report at
-- exit waits (wait_ms), so it reaches the host before Neovim is gone.
--
-- One request at a time. The host serves each connection on its own thread,
-- so two reports sent together (Esc, then v) could arrive in either order and
-- leave the older mode on the keys. A report made while one is in flight
-- waits in `pending`, and a newer one replaces it.

local M = {}

local uv = vim.uv or vim.loop

-- A request that has not finished after this is abandoned.
local TIMEOUT_MS = 2000

local busy = false
local pending = nil

local function start(port, request)
  local tcp = uv.new_tcp()
  if not tcp then
    return
  end
  busy = true
  local timer = uv.new_timer()
  local done = false

  local function finish()
    if done then
      return
    end
    done = true
    if timer and not timer:is_closing() then
      timer:stop()
      timer:close()
    end
    if not tcp:is_closing() then
      tcp:close()
    end
    busy = false
    if pending then
      local p = pending
      pending = nil
      start(p[1], p[2])
    end
  end

  if timer then
    timer:start(TIMEOUT_MS, 0, finish)
  end

  local ok = pcall(tcp.connect, tcp, "127.0.0.1", port, function(err)
    if err then
      return finish()
    end
    tcp:write(request, function(werr)
      if werr then
        return finish()
      end
      -- The host answers and closes (Connection: close); EOF ends it.
      tcp:read_start(function(rerr, data)
        if rerr or not data then
          finish()
        end
      end)
    end)
  end)
  if not ok then
    finish()
  end
end

function M.send(port, request, wait_ms)
  if busy then
    pending = { port, request }
  else
    start(port, request)
  end
  if wait_ms and wait_ms > 0 then
    vim.wait(wait_ms, function()
      return not busy and pending == nil
    end, 10)
  end
end

return M
