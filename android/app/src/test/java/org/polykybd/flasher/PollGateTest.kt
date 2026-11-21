package org.polykybd.flasher

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class PollGateTest {
    private fun now() = System.nanoTime() / 1_000_000

    @Test fun passedTimeReturnsAtOnce() {
        assertTrue(PollGate { 1_000 }.waitUntil(1_000))
    }

    @Test fun cancelBeforeTheWaitIsNotLost() {
        val gate = PollGate(::now)
        gate.cancel()
        val t0 = System.nanoTime()
        assertFalse(gate.waitUntil(now() + 60_000))
        assertTrue(System.nanoTime() - t0 < TimeUnit.SECONDS.toNanos(1))
    }

    @Test fun resetClearsAnEarlierCancel() {
        val gate = PollGate(::now)
        gate.cancel()
        gate.reset()
        assertTrue(gate.waitUntil(now() - 1))
    }

    @Test fun cancelEndsARunningWait() {
        val gate = PollGate(::now)
        val pool = Executors.newSingleThreadExecutor()
        try {
            val result = pool.submit<Boolean> { gate.waitUntil(now() + 60_000) }
            Thread.sleep(100)
            gate.cancel()
            assertFalse(result.get(2, TimeUnit.SECONDS))
        } finally {
            pool.shutdownNow()
        }
    }

    /** A wake-up that is not a cancel, like a spurious return of wait(), must not end the wait early. */
    @Test fun earlyWakeUpWaitsForTheRestOfTheInterval() {
        val lockField = PollGate::class.java.getDeclaredField("lock").apply { isAccessible = true }
        val gate = PollGate(::now)
        val lock = lockField.get(gate) as Object
        val start = now()
        val pool = Executors.newSingleThreadExecutor()
        try {
            val result = pool.submit<Long> {
                gate.waitUntil(start + 400)
                now() - start
            }
            Thread.sleep(50)
            synchronized(lock) { lock.notifyAll() }
            val waited = result.get(2, TimeUnit.SECONDS)
            assertTrue("returned after $waited ms", waited >= 400)
        } finally {
            pool.shutdownNow()
        }
    }
}
