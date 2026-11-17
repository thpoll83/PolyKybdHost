// SPDX-License-Identifier: GPL-3.0-or-later
//
// Unit tests for ReporterCore.cs, run without Unity (see run_tests.sh).
// A tiny runner: each test is a static method; a failed check throws.

using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using PolyKybd.ContextReporter;

static class CoreTests
{
    static void Eq<T>(T want, T got, string what)
    {
        if (!EqualityComparer<T>.Default.Equals(want, got))
            throw new Exception(what + ": want <" + want + "> got <" + got + ">");
    }

    static void True(bool cond, string what)
    {
        if (!cond)
            throw new Exception(what);
    }

    static string Json(byte[] b) => Encoding.UTF8.GetString(b);

    static void WindowTokens()
    {
        Eq("scene", ReporterCore.WindowToken(new[] { "SceneView" }), "scene");
        Eq("game", ReporterCore.WindowToken(new[] { "GameView", "PlayModeView" }), "game");
        // The Device Simulator is a PlayModeView: it takes the Game view's token.
        Eq("game", ReporterCore.WindowToken(new[] { "SimulatorWindow", "PlayModeView" }), "simulator");
        Eq("animation", ReporterCore.WindowToken(new[] { "AnimationWindow" }), "animation");
        Eq("animator", ReporterCore.WindowToken(new[] { "AnimatorControllerTool" }), "animator");
        Eq("hierarchy", ReporterCore.WindowToken(new[] { "SceneHierarchyWindow", "SearchableEditorWindow" }), "hierarchy");
        Eq("project", ReporterCore.WindowToken(new[] { "ProjectBrowser" }), "project");
        Eq("inspector", ReporterCore.WindowToken(new[] { "InspectorWindow", "PropertyEditor" }), "inspector");
        // A subclass of the Scene view (a package's custom view) is still a Scene view.
        Eq("scene", ReporterCore.WindowToken(new[] { "MySceneView", "SceneView", "SearchableEditorWindow" }), "subclass");
        Eq("other", ReporterCore.WindowToken(new[] { "SomePackageWindow" }), "unknown");
        Eq("none", ReporterCore.WindowToken(new string[0]), "no window");
        Eq("none", ReporterCore.WindowToken(null), "null");
    }

    static void ContextUrls()
    {
        Eq("unity://edit/scene", ReporterCore.ContextUrl(false, "scene"), "edit");
        Eq("unity://play/game", ReporterCore.ContextUrl(true, "game"), "play");
        Eq("unity://edit/none", ReporterCore.ContextUrl(false, null), "no token");
    }

    static void Payloads()
    {
        Eq("{\"app\": \"unity\", \"url\": \"unity://edit/scene\", \"focused\": true, \"pid\": 4242, \"input_age\": 0.4}",
           Json(ReporterCore.Payload("unity://edit/scene", "", 4242, 0.43)), "full");
        Eq("{\"app\": \"unity\", \"url\": null, \"focused\": false, \"pid\": 7}",
           Json(ReporterCore.Payload(null, "", 7, null, false)), "withdrawal");
        Eq("{\"app\": \"unity\", \"url\": \"unity://play/game\", \"focused\": true, \"token\": \"a\\\"b\\\\c\"}",
           Json(ReporterCore.Payload("unity://play/game", "a\"b\\c")), "token escaped");
        Eq("{\"app\": \"unity\", \"url\": \"unity://edit/scene\", \"focused\": true, \"input_age\": 0.0}",
           Json(ReporterCore.Payload("unity://edit/scene", null, null, -3)), "negative age clamps");
        // The decimal point is a dot whatever the editor's culture.
        var saved = Thread.CurrentThread.CurrentCulture;
        try
        {
            Thread.CurrentThread.CurrentCulture = new System.Globalization.CultureInfo("de-DE");
            True(Json(ReporterCore.Payload("u", "", 1, 2.5)).Contains("\"input_age\": 2.5"), "culture");
        }
        finally
        {
            Thread.CurrentThread.CurrentCulture = saved;
        }
    }

    static void Policy()
    {
        var p = new SendPolicy(3.0);
        True(p.Due("unity://edit/scene", 0), "first report");
        p.Sent("unity://edit/scene", 0);
        True(!p.Due("unity://edit/scene", 1), "no repeat inside the keep-alive");
        True(p.Due("unity://edit/game", 1), "a change is sent at once");
        True(p.Due("unity://edit/scene", 3), "keep-alive");
        True(!p.Due(null, 10), "nothing to send");
        p.Reset();
        True(p.Due("unity://edit/scene", 1), "after a reset");
    }

    static void SenderKeepsOnlyTheLatest()
    {
        var got = new List<string>();
        var gate = new ManualResetEvent(false);
        var started = new ManualResetEvent(false);
        var s = new Sender((port, body) =>
        {
            started.Set();
            gate.WaitOne();
            lock (got) got.Add(port + " " + Json(body));
        });
        s.Submit(1, "unity://edit/a");
        started.WaitOne(2000);            // the first is being posted, blocked
        s.Submit(2, "unity://edit/b");    // dropped: replaced by the next one
        s.Submit(3, "unity://edit/c");
        gate.Set();
        True(s.Stop(2000), "thread ends");
        Eq(2, got.Count, "posted");
        True(got[0].StartsWith("1 ") && got[1].StartsWith("3 "), string.Join(" | ", got));
    }

    static void SenderLogsEachErrorOnce()
    {
        var logs = new List<string>();
        var s = new Sender((port, body) => { throw new InvalidOperationException("down"); },
                           msg => { lock (logs) logs.Add(msg); });
        for (int i = 0; i < 3; i++)
        {
            s.Submit(1, "unity://edit/scene");
            Thread.Sleep(50);
        }
        s.Stop(2000);
        Eq(1, logs.Count, "one line per distinct error");
    }

    static void SenderPostsJsonToLoopback()
    {
        // A one-shot HTTP server on a free loopback port reads what the real
        // HttpWebRequest path sends.
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        int port = ((IPEndPoint)listener.LocalEndpoint).Port;
        string request = null;
        var server = new Thread(() =>
        {
            using (var c = listener.AcceptTcpClient())
            using (var st = c.GetStream())
            {
                var buf = new byte[8192];
                var sb = new StringBuilder();
                while (true)
                {
                    int n = st.Read(buf, 0, buf.Length);
                    if (n <= 0) break;
                    sb.Append(Encoding.UTF8.GetString(buf, 0, n));
                    var text = sb.ToString();
                    int head = text.IndexOf("\r\n\r\n", StringComparison.Ordinal);
                    if (head >= 0 && text.EndsWith("}", StringComparison.Ordinal)) break;
                }
                request = sb.ToString();
                var ok = Encoding.ASCII.GetBytes(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}");
                st.Write(ok, 0, ok.Length);
            }
        });
        server.Start();
        var errors = new List<string>();
        var s = new Sender(log: m => errors.Add(m));
        s.Submit(port, "unity://play/game", "", 99, 1.0);
        True(server.Join(3000), "server got a request");
        s.Stop(2000);
        listener.Stop();
        True(request.StartsWith("POST /report HTTP/1.1", StringComparison.Ordinal), request);
        True(request.IndexOf("Content-Type: application/json", StringComparison.OrdinalIgnoreCase) >= 0, request);
        True(request.EndsWith("{\"app\": \"unity\", \"url\": \"unity://play/game\", \"focused\": true, \"pid\": 99, \"input_age\": 1.0}",
                              StringComparison.Ordinal), request);
        Eq(0, errors.Count, "no delivery error: " + string.Join(" ", errors));
    }

    static int Main(string[] args)
    {
        // `core_tests.exe post <port> <url|-> <token|->`: send one report through
        // the real Sender and exit; the host suite uses it against its server
        // (tests/unity_package/unity_package_test.py).
        if (args.Length == 4 && args[0] == "post")
        {
            var errors = new List<string>();
            var s = new Sender(log: m => { lock (errors) errors.Add(m); });
            string url = args[2] == "-" ? null : args[2];
            s.Submit(int.Parse(args[1]), url, args[3] == "-" ? "" : args[3], 4242, 0.5, url != null);
            s.Stop(3000);
            foreach (var e in errors)
                Console.WriteLine(e);
            return errors.Count == 0 ? 0 : 2;
        }
        var tests = new Dictionary<string, Action>
        {
            { "WindowTokens", WindowTokens },
            { "ContextUrls", ContextUrls },
            { "Payloads", Payloads },
            { "Policy", Policy },
            { "SenderKeepsOnlyTheLatest", SenderKeepsOnlyTheLatest },
            { "SenderLogsEachErrorOnce", SenderLogsEachErrorOnce },
            { "SenderPostsJsonToLoopback", SenderPostsJsonToLoopback },
        };
        int failed = 0;
        foreach (var t in tests)
        {
            try
            {
                t.Value();
                Console.WriteLine("ok   " + t.Key);
            }
            catch (Exception e)
            {
                failed++;
                Console.WriteLine("FAIL " + t.Key + ": " + e.Message);
            }
        }
        Console.WriteLine("Ran " + tests.Count + " tests, " + failed + " failed");
        return failed == 0 ? 0 : 1;
    }
}
