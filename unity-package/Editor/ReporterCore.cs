// SPDX-License-Identifier: GPL-3.0-or-later
//
// The Unity-free half of the PolyKybd Context Reporter. Everything here builds
// and runs without UnityEngine/UnityEditor: the window token, the pseudo-URL,
// the JSON payload, the send policy and the sender thread. ContextReporter.cs is
// the thin Unity glue around it. Tests~/ compiles this file alone with Mono.
//
// What is sent, and nothing else:
//
//     POST http://127.0.0.1:<port>/report      Content-Type: application/json
//     {"app": "unity", "url": "unity://edit/scene", "focused": true,
//      "pid": 4242, "input_age": 0.4, "token": "<only if one is configured>"}
//
// The URL names the play state (edit or play) and the TYPE of the focused editor
// window. No scene, asset, project or window title is ever sent.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;

namespace PolyKybd.ContextReporter
{
    public static class ReporterCore
    {
        public const string App = "unity";
        public const int DefaultPort = 50164;          // PolyKybdHost `browser_report_port`
        // The host drops a report older than 8 s (browser_url.py DEFAULT_MAX_AGE_S),
        // so the context is re-sent well inside that window.
        public const double KeepAliveSeconds = 3.0;
        public const double PollSeconds = 0.2;          // how often the editor tick looks for a change
        public const int HttpTimeoutMs = 500;           // on the SENDER thread; the editor never waits

        // Editor window class name -> URL token. Checked from the most derived
        // class up, so a subclass of a listed window (the Device Simulator is a
        // PlayModeView, like the Game view) takes its base's token.
        static readonly Dictionary<string, string> WindowTokens = new Dictionary<string, string>
        {
            { "SceneView", "scene" },
            { "GameView", "game" },
            { "PlayModeView", "game" },
            { "AnimationWindow", "animation" },
            { "AnimatorControllerTool", "animator" },
            { "SceneHierarchyWindow", "hierarchy" },
            { "ProjectBrowser", "project" },
            { "InspectorWindow", "inspector" },
            { "PropertyEditor", "inspector" },
            { "ConsoleWindow", "console" },
            { "ProfilerWindow", "profiler" },
            { "TimelineWindow", "timeline" },
            { "AudioMixerWindow", "audiomixer" },
            { "LightingWindow", "lighting" },
            { "SearchWindow", "search" },
            { "CurveEditorWindow", "curves" },
        };

        /// <summary>The URL token for a focused window, given its class name and
        /// its base class names (most derived first). "none" when no editor window
        /// has focus, "other" for a window this list does not name.</summary>
        public static string WindowToken(IEnumerable<string> typeChain)
        {
            if (typeChain == null)
                return "none";
            bool any = false;
            foreach (var name in typeChain)
            {
                any = true;
                string token;
                if (name != null && WindowTokens.TryGetValue(name, out token))
                    return token;
            }
            return any ? "other" : "none";
        }

        /// <summary>unity://edit/&lt;window&gt; or unity://play/&lt;window&gt;.</summary>
        public static string ContextUrl(bool playing, string windowToken)
        {
            var w = string.IsNullOrEmpty(windowToken) ? "none" : windowToken;
            return "unity://" + (playing ? "play" : "edit") + "/" + w;
        }

        /// <summary>One report as UTF-8 JSON. url == null with focused == false
        /// withdraws this instance's context (reporting turned off, Unity quits).</summary>
        public static byte[] Payload(string url, string token = "", int? pid = null,
                                     double? inputAge = null, bool focused = true)
        {
            var sb = new StringBuilder();
            sb.Append("{\"app\": ").Append(JsonString(App));
            sb.Append(", \"url\": ").Append(url == null ? "null" : JsonString(url));
            sb.Append(", \"focused\": ").Append(focused ? "true" : "false");
            if (pid.HasValue)
                sb.Append(", \"pid\": ").Append(pid.Value.ToString(CultureInfo.InvariantCulture));
            if (inputAge.HasValue)
            {
                var age = Math.Round(Math.Max(0.0, inputAge.Value), 1);
                sb.Append(", \"input_age\": ").Append(age.ToString("0.0", CultureInfo.InvariantCulture));
            }
            if (!string.IsNullOrEmpty(token))
                sb.Append(", \"token\": ").Append(JsonString(token));
            sb.Append('}');
            return Encoding.UTF8.GetBytes(sb.ToString());
        }

        public static string JsonString(string s)
        {
            var sb = new StringBuilder("\"");
            foreach (var c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20)
                            sb.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        else
                            sb.Append(c);
                        break;
                }
            }
            return sb.Append('"').ToString();
        }
    }

    /// <summary>Send on change, plus a keep-alive while nothing changes.</summary>
    public sealed class SendPolicy
    {
        readonly double keepAlive;
        public string LastUrl { get; private set; }
        double? lastSent;

        public SendPolicy(double keepAliveSeconds = ReporterCore.KeepAliveSeconds)
        {
            keepAlive = keepAliveSeconds;
        }

        public bool Due(string url, double now)
        {
            if (url == null)
                return false;
            if (url != LastUrl || !lastSent.HasValue)
                return true;
            return now - lastSent.Value >= keepAlive;
        }

        public void Sent(string url, double now)
        {
            LastUrl = url;
            lastSent = now;
        }

        public void Reset()
        {
            LastUrl = null;
            lastSent = null;
        }
    }

    /// <summary>One background thread POSTing the LATEST report; an older pending
    /// one is dropped. Submit() only stores and signals, so the editor's main
    /// thread never touches the network. Failures are silent apart from one log
    /// line per distinct error; the next change or keep-alive retries.</summary>
    public sealed class Sender
    {
        readonly Action<int, byte[]> post;
        readonly Action<string> log;
        readonly object gate = new object();
        readonly AutoResetEvent wake = new AutoResetEvent(false);
        readonly HashSet<string> seen = new HashSet<string>();
        readonly Thread thread;
        KeyValuePair<int, byte[]>? pending;
        volatile bool stopping;

        public Sender(Action<int, byte[]> post = null, Action<string> log = null)
        {
            this.post = post ?? HttpPost;
            this.log = log ?? (_ => { });
            thread = new Thread(Run) { IsBackground = true, Name = "polykybd-reporter" };
            thread.Start();
        }

        public void Submit(int port, string url, string token = "", int? pid = null,
                           double? inputAge = null, bool focused = true)
        {
            var body = ReporterCore.Payload(url, token, pid, inputAge, focused);
            lock (gate)
                pending = new KeyValuePair<int, byte[]>(port, body);
            wake.Set();
        }

        /// <summary>Deliver the report still pending, if any, then end the thread.
        /// Waits at most timeoutMs. Called before a domain reload (Unity waits for
        /// managed threads) and when the editor quits.</summary>
        public bool Stop(int timeoutMs)
        {
            stopping = true;
            wake.Set();
            return thread.Join(timeoutMs);
        }

        void Run()
        {
            while (true)
            {
                if (!stopping)
                    wake.WaitOne();
                KeyValuePair<int, byte[]>? job;
                lock (gate)
                {
                    job = pending;
                    pending = null;
                }
                if (job == null)
                {
                    if (stopping)
                        return;
                    continue;
                }
                try
                {
                    post(job.Value.Key, job.Value.Value);
                }
                catch (Exception e)
                {
                    var key = e.GetType().Name + ": " + e.Message;
                    bool first;
                    lock (gate)
                        first = seen.Add(key);
                    if (first)
                        log("PolyKybd Context Reporter: report not delivered: " + key);
                }
            }
        }

        static void HttpPost(int port, byte[] body)
        {
            var req = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" +
                port.ToString(CultureInfo.InvariantCulture) + "/report");
            req.Method = "POST";
            req.ContentType = "application/json";
            req.Proxy = null;   // a loopback report must never go through a proxy
            req.Timeout = ReporterCore.HttpTimeoutMs;
            req.ReadWriteTimeout = ReporterCore.HttpTimeoutMs;
            req.KeepAlive = false;
            // HttpWebRequest sends "Expect: 100-continue" on a POST by default
            // and waits for an answer the host's HTTP/1.0 receiver never sends
            // before it sends the body. Send the body at once instead.
            req.ServicePoint.Expect100Continue = false;
            req.ContentLength = body.Length;
            using (var s = req.GetRequestStream())
                s.Write(body, 0, body.Length);
            using (var resp = (HttpWebResponse)req.GetResponse())
            using (var r = new StreamReader(resp.GetResponseStream()))
                r.ReadToEnd();
        }
    }
}
