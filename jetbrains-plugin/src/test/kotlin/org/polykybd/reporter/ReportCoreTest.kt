// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.reporter

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class ReportCoreTest {
    @Test
    fun editorWinsOverAStaleToolWindowId() {
        assertEquals("editor", ReportCore.windowToken(true, "Project"))
        assertEquals("editor", ReportCore.windowToken(true, null))
    }

    @Test
    fun knownToolWindowsGetTheirToken() {
        assertEquals("project", ReportCore.windowToken(false, "Project"))
        assertEquals("terminal", ReportCore.windowToken(false, "Terminal"))
        assertEquals("debug", ReportCore.windowToken(false, "Debug"))
        assertEquals("run", ReportCore.windowToken(false, "Run"))
        assertEquals("git", ReportCore.windowToken(false, "Version Control"))
        assertEquals("commit", ReportCore.windowToken(false, "Commit"))
    }

    @Test
    fun unknownToolWindowIdIsNeverSent() {
        assertEquals("other", ReportCore.windowToken(false, "Some Plugin/../secret"))
        assertEquals("other", ReportCore.windowToken(false, null))
    }

    @Test
    fun urlCarriesTheDebugState() {
        assertEquals("jetbrains://editor", ReportCore.contextUrl("editor", ReportCore.Debug.NONE))
        assertEquals("jetbrains://editor/paused", ReportCore.contextUrl("editor", ReportCore.Debug.PAUSED))
        assertEquals("jetbrains://terminal/running", ReportCore.contextUrl("terminal", ReportCore.Debug.RUNNING))
    }

    @Test
    fun debugState() {
        assertEquals(ReportCore.Debug.NONE, ReportCore.debugState(false, false, false))
        assertEquals(ReportCore.Debug.NONE, ReportCore.debugState(true, true, true))
        assertEquals(ReportCore.Debug.PAUSED, ReportCore.debugState(true, false, true))
        assertEquals(ReportCore.Debug.RUNNING, ReportCore.debugState(true, false, false))
    }

    @Test
    fun activationCountsAsInput() {
        assertEquals(12.3, ReportCore.inputAgeSeconds(12_345, null), 1e-9)
        assertEquals(0.5, ReportCore.inputAgeSeconds(60_000, 500), 1e-9)
        assertEquals(0.0, ReportCore.inputAgeSeconds(-5, null), 1e-9)
        assertTrue(ReportCore.inputAgeSeconds(Long.MAX_VALUE, null) < 1e7)
    }

    @Test
    fun payloadHasExactlyTheContractFields() {
        assertEquals(
            "{\"app\": \"jetbrains\", \"url\": \"jetbrains://editor/paused\", \"focused\": true, " +
                "\"pid\": 4242, \"input_age\": 0.4}",
            ReportCore.payload("jetbrains://editor/paused", true, 4242, 0.4, ""))
    }

    @Test
    fun withdrawalAndTokenEscaping() {
        assertEquals(
            "{\"app\": \"jetbrains\", \"url\": null, \"focused\": false, \"token\": \"a\\\"b\\\\c\\u000a\"}",
            ReportCore.payload(null, false, null, null, "a\"b\\c\n"))
    }

    @Test
    fun sendPolicyChangeAndKeepAlive() {
        val p = ReportCore.SendPolicy(3_000)
        assertFalse(p.due(null, 0))
        assertTrue(p.due("a", 0))
        p.sent("a", 0)
        assertFalse(p.due("a", 2_999))
        assertTrue(p.due("a", 3_000))
        assertTrue(p.due("b", 1))
        p.reset()
        assertTrue(p.due("a", 1))
    }

    @Test
    fun senderDeliversTheLatestAndSurvivesErrors() {
        val got = CopyOnWriteArrayList<String>()
        val logged = CopyOnWriteArrayList<String>()
        val done = CountDownLatch(1)
        val sender = Sender(post = { _, body ->
            if (body == "boom") throw java.io.IOException("refused")
            got.add(body)
            if (body == "last") done.countDown()
        }, log = { logged.add(it) })
        sender.submit(50164, "boom")
        sender.submit(50164, "boom")
        Thread.sleep(100)
        sender.submit(50164, "last")
        assertTrue(done.await(2, TimeUnit.SECONDS))
        sender.stop()
        sender.join(1_000)
        assertEquals(listOf("last"), got)
        assertEquals(1, logged.size)
    }
}
