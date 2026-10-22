"""How long a newly focused window must stay in front before the keyboard
switches to it. One value for the core's window tick, the tray's tick and the
forwarder: they kept three copies of it.

The check accepts once the timer REACHES this value (>=), and the timer
advances one 250 ms tick at a time (on macOS, the real time between ticks), so
500 means 500 ms of focus after the change is seen, 500 to 750 ms after the
real switch. Until 2026-10-22 the check was `>` and the value 1000, which made
1250 ms. The delay keeps a window that is only passed over
(Alt+Tab, a click through) from starting a switch. It was 1000 ms from before
the overlay MRU cache, when every switch re-sent all images; the maintainer
lowered it to 500 ms on 2026-10-22, when the field logs showed it to be the
largest part of a switch (a switch's own work: 9 ms median before the send,
35 ms median for the send).
"""

NEW_WINDOW_ACCEPT_TIME_MSEC = 500
