" polykybd.vim - report Vim's mode to PolyKybdHost, so the PolyKybd keycaps
" show the keys of that mode.  See :help polykybd.
"
" One file for Vim and Neovim. Only the network send differs: Vim opens a raw
" channel (ch_open), Neovim a libuv TCP handle (lua/polykybd.lua). Both are
" non-blocking, and every error is ignored, so Vim never waits on the host and
" says nothing when it is not running.
"
" What is sent, to 127.0.0.1 only:
"   {"app": "vim", "url": "vim://<mode>", "focused": true|false,
"    "pid": <this process>, "input_age": <seconds since the last input>}
" No file name, buffer text or title.

if exists('g:loaded_polykybd')
  finish
endif
if has('nvim')
  if !has('nvim-0.7')
    finish
  endif
elseif !has('patch-8.2.3430') || !has('channel') || !has('timers')
  " ModeChanged arrived in 8.2.3430.
  finish
endif
let g:loaded_polykybd = 1

let g:polykybd_enabled = get(g:, 'polykybd_enabled', 1)
let g:polykybd_port = get(g:, 'polykybd_port', 50164)
let g:polykybd_token = get(g:, 'polykybd_token', '')

" The host keeps a report for 8 s, so a keep-alive every 3 s.
let s:KEEPALIVE_MS = 3000

let s:last_input = reltime()
let s:focused = 1
let s:sent_url = ''
let s:sent_focused = -1

" mode(1) -> the mode name in the URL. Operator-pending and the CTRL-O
" variants of Normal mode (no, niI ...) are Normal; Select mode has its own
" set, because a printable key there replaces the selection; the hit-enter and confirm prompts (r, rm, r?) and a running shell
" command (!) count as the command line.
function! s:Mode() abort
  let l:c = mode(1)[0]
  if l:c ==# 'n'
    return 'normal'
  elseif index(['v', 'V', "\<C-V>"], l:c) >= 0
    return 'visual'
  elseif index(['s', 'S', "\<C-S>"], l:c) >= 0
    return 'select'
  elseif l:c ==# 'i'
    return 'insert'
  elseif l:c ==# 'R'
    return 'replace'
  elseif l:c ==# 't'
    return 'terminal'
  endif
  return 'cmdline'
endfunction

function! s:Request(url, focused) abort
  let l:report = {
        \ 'app': 'vim',
        \ 'url': a:url,
        \ 'focused': a:focused ? v:true : v:false,
        \ 'pid': getpid(),
        \ 'input_age': reltimefloat(reltime(s:last_input)),
        \ }
  if !empty(g:polykybd_token)
    let l:report.token = g:polykybd_token
  endif
  let l:body = json_encode(l:report)
  return 'POST /report HTTP/1.1' . "\r\n"
        \ . 'Host: 127.0.0.1:' . g:polykybd_port . "\r\n"
        \ . 'Content-Type: application/json' . "\r\n"
        \ . 'Content-Length: ' . strlen(l:body) . "\r\n"
        \ . 'Connection: close' . "\r\n\r\n"
        \ . l:body
endfunction

" One request at a time. The host serves each connection on its own thread,
" so two reports sent together (Esc, then v) could arrive in either order and
" leave the older mode on the keys. A report made while one is in flight
" waits in s:pending, and a newer one replaces it.
let s:seq = 0                   " number of the last request opened
let s:inflight = -1             " number of the request in flight, or -1
let s:inflight_since = reltime()
let s:pending = ''

function! s:Done(seq) abort
  if a:seq != s:inflight
    return
  endif
  let s:inflight = -1
  if s:pending !=# ''
    let l:next = s:pending
    let s:pending = ''
    call s:Open(l:next, 0)
  endif
endfunction

function! s:OnReply(channel, seq) abort
  try
    call ch_close(a:channel)
  catch
  endtry
  call s:Done(a:seq)              " close_cb does not run after ch_close()
endfunction

function! s:Open(request, wait_ms) abort
  let s:seq += 1
  let l:seq = s:seq
  try
    let l:ch = ch_open('127.0.0.1:' . g:polykybd_port, {
          \ 'mode': 'raw', 'waittime': a:wait_ms,
          \ 'callback': {ch, msg -> s:OnReply(ch, l:seq)},
          \ 'close_cb': {ch -> s:Done(l:seq)},
          \ })
    if ch_status(l:ch) ==# 'open'
      let s:inflight = l:seq
      let s:inflight_since = reltime()
      call ch_sendraw(l:ch, a:request)
    endif
  catch
    " The host is not running, or the port is wrong: say nothing.
  endtry
endfunction

" wait_ms: 0 for every report but the last one at exit, which waits for the
" one in flight and then for its own connect, so it reaches the host before
" Vim is gone.
function! s:Post(request, wait_ms) abort
  if has('nvim')
    try
      call luaeval('require("polykybd").send(_A[1], _A[2], _A[3])',
            \ [g:polykybd_port, a:request, a:wait_ms])
    catch
    endtry
    return
  endif
  " A host that never answers must not stop reporting for good.
  if s:inflight != -1 && reltimefloat(reltime(s:inflight_since)) > 2.0
    let s:inflight = -1
  endif
  if s:inflight != -1 && a:wait_ms > 0
    let l:waited = 0
    while s:inflight != -1 && l:waited < a:wait_ms
      sleep 10m                   " lets the channel callbacks run
      let l:waited += 10
    endwhile
    let s:inflight = -1
  endif
  if s:inflight != -1
    let s:pending = a:request
  else
    " This report is newer than any waiting one (left over from a request that
    " timed out); s:Done() must not send the older one after it.
    let s:pending = ''
    call s:Open(a:request, a:wait_ms)
  endif
endfunction

function! s:Send(url, focused, ...) abort
  let l:force = get(a:, 1, 0)
  if !g:polykybd_enabled && !l:force
    return
  endif
  let s:sent_url = a:url is v:null ? '' : a:url
  let s:sent_focused = a:focused
  call s:Post(s:Request(a:url, a:focused), get(a:, 2, 0))
endfunction

function! s:Report() abort
  call s:Send('vim://' . s:Mode(), s:focused)
endfunction

function! s:OnModeChanged() abort
  let s:last_input = reltime()
  let l:url = 'vim://' . s:Mode()
  if l:url !=# s:sent_url || s:sent_focused != s:focused
    call s:Send(l:url, s:focused)
  endif
endfunction

function! s:OnFocus(gained) abort
  let s:focused = a:gained
  if a:gained
    " Coming back to this window is input: with several editors open the host
    " follows the one with the newest input.
    let s:last_input = reltime()
  endif
  call s:Report()
endfunction

function! s:OnTimer(timer) abort
  if s:focused
    call s:Report()
  endif
endfunction

function! s:Toggle() abort
  let g:polykybd_enabled = !g:polykybd_enabled
  if g:polykybd_enabled
    call s:Report()
    echo 'PolyKybd mode reporting on'
  else
    " One last report, so the keyboard leaves this mode's overlay now.
    call s:Send(v:null, 0, 1)
    echo 'PolyKybd mode reporting off'
  endif
endfunction

command! -bar PolyKybdToggle call s:Toggle()

augroup polykybd
  autocmd!
  autocmd ModeChanged * call s:OnModeChanged()
  " Input time only: each of these is one assignment.
  autocmd CursorMoved,CursorMovedI,TextChanged,TextChangedI,InsertCharPre *
        \ let s:last_input = reltime()
  autocmd FocusGained * call s:OnFocus(1)
  autocmd FocusLost * call s:OnFocus(0)
  if exists('##VimSuspend')
    autocmd VimSuspend * call s:Send('vim://' . s:Mode(), 0)
    autocmd VimResume * call s:OnFocus(1)
  endif
  autocmd VimLeavePre * call s:Send(v:null, 0, 0, 200)
  autocmd VimEnter * call s:Report()
augroup END

call timer_start(s:KEEPALIVE_MS, function('s:OnTimer'), {'repeat': -1})
if v:vim_did_enter
  call s:Report()
endif
