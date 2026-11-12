package org.polykybd.flasher

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GitHubTest {
    /** Answers by "METHOD path" (query included); records every request. */
    private class FakeHttp(val routes: Map<String, GitHub.Response>) : GitHub.Http {
        val calls = mutableListOf<Triple<String, String, String?>>()
        val headers = mutableListOf<Map<String, String>>()
        override fun request(method: String, url: String, headers: Map<String, String>, body: String?): GitHub.Response {
            val key = method + " " + url.removePrefix(GitHub.API)
            calls += Triple(method, key, body)
            this.headers += headers
            return routes[key] ?: GitHub.Response(404, """{"message":"Not Found"}""")
        }
    }

    private fun ok(body: String) = GitHub.Response(200, body)
    private val fw = GitHub.TARGETS.first { it.label == "Firmware" }

    // ---- device flow ----

    @Test fun deviceCodeRequestSendsOnlyTheClientId() {
        val http = FakeHttp(mapOf("POST https://github.com/login/device/code" to ok(
            """{"device_code":"dc","user_code":"WDJB-MJHT","verification_uri":"https://github.com/login/device","expires_in":900,"interval":5}""")))
        val code = GitHub(http, "Iv1.abc").requestDeviceCode()
        assertEquals("WDJB-MJHT", code.userCode)
        assertEquals(5, code.intervalSec)
        assertEquals("client_id=Iv1.abc", http.calls.single().third)
        assertFalse(http.calls.single().third!!.contains("secret"))
    }

    @Test fun deviceCodeRefusesWithoutAClientId() {
        val e = runCatching { GitHub(FakeHttp(emptyMap()), "").requestDeviceCode() }.exceptionOrNull()
        assertTrue(e?.message, e is GitHub.GitHubException && e.message!!.contains("not set up"))
    }

    @Test fun pollPendingSlowDownAndDone() {
        fun poll(body: String) = GitHub.parsePoll(ok(body), 5, 1_000)
        assertEquals(GitHub.Poll.Pending(5), poll("""{"error":"authorization_pending"}"""))
        assertEquals(GitHub.Poll.Pending(10), poll("""{"error":"slow_down","interval":10}"""))
        val done = poll("""{"access_token":"ghu_x","expires_in":28800,"refresh_token":"ghr_y","refresh_token_expires_in":15897600}""")
        done as GitHub.Poll.Done
        assertEquals("ghu_x", done.tokens.access)
        assertEquals(1_000 + 28_800_000L, done.tokens.accessExpiresAtMs)
        assertEquals("ghr_y", done.tokens.refresh)
    }

    @Test fun pollWithoutExpiryKeepsTheTokenForever() {
        val done = GitHub.parsePoll(ok("""{"access_token":"ghu_x","token_type":"bearer"}"""), 5, 1_000) as GitHub.Poll.Done
        assertEquals(0L, done.tokens.accessExpiresAtMs)
        assertNull(done.tokens.refresh)
    }

    @Test fun pollFailuresSayWhy() {
        fun msg(err: String) = (GitHub.parsePoll(ok("""{"error":"$err"}"""), 5, 0) as GitHub.Poll.Failed).message
        assertTrue(msg("expired_token").contains("expired"))
        assertTrue(msg("access_denied").contains("cancelled"))
        assertTrue(msg("device_flow_disabled").contains("Device flow"))
    }

    @Test fun refreshUsesTheRefreshTokenAndNoSecret() {
        val http = FakeHttp(mapOf("POST https://github.com/login/oauth/access_token" to ok(
            """{"access_token":"ghu_new","expires_in":28800,"refresh_token":"ghr_new"}""")))
        val t = GitHub(http, "Iv1.abc").refresh(GitHub.Tokens("ghu_old", 1, "ghr_old", 0), 0)
        assertEquals("ghu_new", t.access)
        val body = http.calls.single().third!!
        assertTrue(body, body.contains("grant_type=refresh_token") && body.contains("refresh_token=ghr_old"))
        assertFalse(body.contains("secret"))
    }

    @Test fun tokensRoundTripThroughJson() {
        val t = GitHub.Tokens("a", 5, null, 0)
        assertEquals(t, GitHub.Tokens.fromJson(t.toJson()))
    }

    // ---- prepared notes ----

    @Test fun newestPreparedSortsByVersionNotText() {
        val names = listOf("README.md", "PolyKybd-fw-v0.9.20.md", "PolyKybd-fw-v0.10.0.md", "v9.9.9.md",
            "PolyKybd-fw-v1.2.md", "PolyKybd-fw-v0.10.0.txt")
        assertEquals("PolyKybd-fw-v0.10.0", GitHub.newestPrepared(names, "PolyKybd-fw-v"))
    }

    @Test fun hostPrefixDoesNotMatchFirmwareNotes() {
        assertEquals("v1.22.6", GitHub.newestPrepared(listOf("PolyKybd-fw-v9.0.0.md", "v1.22.6.md", "v1.3.0.md"), "v"))
        assertNull(GitHub.newestPrepared(listOf("PolyKybd-fw-v9.0.0.md"), "v"))
    }

    @Test fun titleIsTheFirstLineWithoutTheHash() {
        assertEquals("PolyKybd v1.13.0 AI agent keys", GitHub.titleOf("# PolyKybd v1.13.0 AI agent keys\n\nbody"))
    }

    private fun statusRoutes(published: Int = 404) = mapOf(
        "GET /repos/thpoll83/qmk_firmware" to ok("""{"default_branch":"PolyKybd"}"""),
        "GET /repos/thpoll83/qmk_firmware/actions/workflows/publish-release.yml" to ok("{}"),
        "GET /repos/thpoll83/qmk_firmware/contents/?ref=release-notes" to ok(
            """[{"name":"PolyKybd-fw-v1.12.0.md"},{"name":"PolyKybd-fw-v1.13.0.md"}]"""),
        "GET /repos/thpoll83/qmk_firmware/contents/PolyKybd-fw-v1.13.0.md?ref=release-notes" to ok("# Title 13\nbody"),
        "GET /repos/thpoll83/qmk_firmware/releases/tags/PolyKybd-fw-v1.13.0" to GitHub.Response(published, "{}"),
        "GET /repos/thpoll83/qmk_firmware/releases/latest" to ok("""{"tag_name":"PolyKybd-fw-v1.12.0"}"""),
    )

    @Test fun statusReadsTheNewestPreparedRelease() {
        val http = FakeHttp(statusRoutes())
        val s = GitHub(http, "id").status("tok", fw)
        assertEquals("PolyKybd", s.defaultBranch)
        assertTrue(s.workflowPresent)
        assertEquals(GitHub.Prepared("PolyKybd-fw-v1.13.0", "Title 13"), s.prepared)
        assertFalse(s.preparedPublished)
        assertEquals("PolyKybd-fw-v1.12.0", s.latestTag)
        assertTrue(http.headers.all { it["Authorization"] == "Bearer tok" })
    }

    @Test fun statusWithoutWorkflowOrNotes() {
        val routes = statusRoutes().toMutableMap()
        routes.remove("GET /repos/thpoll83/qmk_firmware/actions/workflows/publish-release.yml")
        routes.remove("GET /repos/thpoll83/qmk_firmware/contents/?ref=release-notes")
        val s = GitHub(FakeHttp(routes), "id").status("tok", fw)
        assertFalse(s.workflowPresent)
        assertNull(s.prepared)
    }

    @Test fun unauthorizedIsReportedSoTheCallerCanRefresh() {
        val http = FakeHttp(mapOf("GET /user" to GitHub.Response(401, """{"message":"Bad credentials"}""")))
        assertTrue(runCatching { GitHub(http, "id").login("old") }.exceptionOrNull() is GitHub.Unauthorized)
    }

    // ---- dispatch ----

    private val ready = GitHub.RepoStatus(fw, "PolyKybd", true, GitHub.Prepared("PolyKybd-fw-v1.13.0", "T"), false, null)
    private val runJson = """{"id":77,"status":"queued","conclusion":null,"html_url":"https://github.com/r/77","created_at":"2026-11-12T10:00:05Z"}"""

    @Test fun dispatchPassesTheConfirmedTagAndDefaultBranch() {
        val http = FakeHttp(mapOf(
            "POST /repos/thpoll83/qmk_firmware/actions/workflows/publish-release.yml/dispatches" to
                ok("""{"workflow_run_id":77,"run_url":"x","html_url":"y"}"""),
            "GET /repos/thpoll83/qmk_firmware/actions/runs/77" to ok(runJson),
        ))
        val run = GitHub(http, "id").dispatch("tok", ready, dryRun = false, nowMs = 0)
        assertEquals(77L, run.id)
        assertFalse(run.finished)
        val body = JSONObject(http.calls.first().third!!)
        assertEquals("PolyKybd", body.getString("ref"))
        assertEquals("PolyKybd-fw-v1.13.0", body.getJSONObject("inputs").getString("tag"))
        assertEquals(false, body.getJSONObject("inputs").getBoolean("dry_run"))
    }

    @Test fun dispatchWithoutRunIdFindsTheNewRun() {
        val now = GitHub.parseIsoMs("2026-11-12T10:00:00Z")
        val http = FakeHttp(mapOf(
            "POST /repos/thpoll83/qmk_firmware/actions/workflows/publish-release.yml/dispatches" to GitHub.Response(204, ""),
            "GET /repos/thpoll83/qmk_firmware/actions/workflows/publish-release.yml/runs?event=workflow_dispatch&per_page=5" to
                ok("""{"runs":[$runJson]}"""),
        ))
        assertEquals(77L, GitHub(http, "id").dispatch("tok", ready, dryRun = true, nowMs = now).id)
    }

    @Test fun dispatchRefusalSaysWhy() {
        val http = FakeHttp(mapOf("POST /repos/thpoll83/qmk_firmware/actions/workflows/publish-release.yml/dispatches" to
            GitHub.Response(403, """{"message":"Resource not accessible by integration"}""")))
        val e = runCatching { GitHub(http, "id").dispatch("tok", ready, dryRun = false, nowMs = 0) }.exceptionOrNull()
        assertTrue(e?.message, e!!.message!!.contains("403") && e.message!!.contains("not accessible"))
    }

    @Test fun runStates() {
        val done = GitHub.parseRun(JSONObject("""{"id":1,"status":"completed","conclusion":"success","html_url":"u"}"""))
        assertTrue(done.finished && done.ok)
        val failed = GitHub.parseRun(JSONObject("""{"id":1,"status":"completed","conclusion":"failure","html_url":"u"}"""))
        assertTrue(failed.finished && !failed.ok)
        assertNull(GitHub.parseRun(JSONObject(runJson)).conclusion)
    }
}
