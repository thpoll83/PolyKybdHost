package org.polykybd.flasher

/**
 * Waits between device-flow polls. GitHub answers a poll sent before the interval has
 * passed with `slow_down` and adds 5 s to the interval, so nothing may end the wait
 * early except a cancel: not a spurious [Object.wait] return, not the screen coming back.
 * A cancel made before the wait starts is not lost, because the flag is read under the
 * same lock.
 *
 * [clock] must be one that a change of the phone's time does not move, or a clock set
 * back by an hour stops polling for that hour. The app passes
 * `SystemClock.elapsedRealtime`, which also counts deep sleep, so a code that expired
 * while the phone slept is seen as expired.
 */
class PollGate(private val clock: () -> Long) {
    private val lock = Object()
    private var cancelled = false

    /** Clears an earlier cancel. Call before a new sign-in. */
    fun reset() = synchronized(lock) { cancelled = false }

    /** Ends a running or the next [waitUntil] at once. */
    fun cancel() = synchronized(lock) {
        cancelled = true
        lock.notifyAll()
    }

    /** Returns true once [atMs] (from [clock]) has passed, false as soon as it is cancelled. */
    fun waitUntil(atMs: Long): Boolean = synchronized(lock) {
        while (!cancelled) {
            val left = atMs - clock()
            if (left <= 0) return true
            lock.wait(left)
        }
        false
    }
}
