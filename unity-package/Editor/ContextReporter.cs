// SPDX-License-Identifier: GPL-3.0-or-later
//
// PolyKybd Context Reporter -- Unity Editor glue.
//
// Reports the play state and the TYPE of the focused editor window to the local
// PolyKybdHost (loopback only), so the keyboard shows the shortcuts of that
// window. ReporterCore.cs holds the logic that runs without Unity.
//
// Unity APIs used (all on the main thread):
//   EditorWindow.focusedWindow           the window with keyboard focus
//   EditorWindow.windowFocusChanged      focus change event (Unity 2023.2+); older
//                                        versions rely on the 0.2 s poll alone
//   EditorApplication.isPlaying          edit or play
//   EditorApplication.playModeStateChanged
//   EditorApplication.update             the poll and the 3 s keep-alive
//   EditorApplication.quitting           last report: url null, focused false
//   AssemblyReloadEvents.beforeAssemblyReload  stop the sender thread

using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEditor;
using UnityEngine;

namespace PolyKybd.ContextReporter
{
    [InitializeOnLoad]
    public static class ContextReporter
    {
        static Sender sender;
        static readonly SendPolicy policy = new SendPolicy();
        static double nextPoll;
        static double lastInput;
        static bool reported;
        static readonly int pid = System.Diagnostics.Process.GetCurrentProcess().Id;

        static ContextReporter()
        {
            sender = new Sender(log: msg => Debug.LogWarning(msg));
            lastInput = EditorApplication.timeSinceStartup;
            EditorApplication.update += Tick;
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
            EditorApplication.quitting += OnQuitting;
            AssemblyReloadEvents.beforeAssemblyReload += OnBeforeReload;
#if UNITY_2023_2_OR_NEWER
            EditorWindow.windowFocusChanged += OnFocusChanged;
#endif
            HookGlobalEvents();
        }

        /// <summary>Whether a report is sent at all (Preferences > PolyKybd).</summary>
        internal static bool Enabled => ReporterSettings.Enabled;

        static void OnFocusChanged()
        {
            lastInput = EditorApplication.timeSinceStartup;
            nextPoll = 0;   // report on the next tick, not after the poll interval
        }

        static void OnPlayModeChanged(PlayModeStateChange _)
        {
            OnFocusChanged();
        }

        static void OnInputEvent()
        {
            lastInput = EditorApplication.timeSinceStartup;
        }

        // `input_age` is the time since this editor last saw input, so that with
        // several Unity editors open the host follows the one being used.
        // EditorApplication.globalEventHandler (internal) sees every key event
        // the editor dispatches. Its type changed between versions (a
        // CallbackFunction with no argument, later Action<Event>), so it is
        // found by reflection; when that fails the age counts from the last
        // focus or play-mode change instead.
        static void HookGlobalEvents()
        {
            try
            {
                var f = typeof(EditorApplication).GetField("globalEventHandler",
                    BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
                if (f == null || !typeof(Delegate).IsAssignableFrom(f.FieldType))
                    return;
                var invoke = f.FieldType.GetMethod("Invoke");
                var n = invoke == null ? -1 : invoke.GetParameters().Length;
                string name = n == 0 ? nameof(OnGlobalEvent0) : n == 1 ? nameof(OnGlobalEvent1) : null;
                if (name == null)
                    return;
                var m = typeof(ContextReporter).GetMethod(name, BindingFlags.Static | BindingFlags.NonPublic);
                var handler = Delegate.CreateDelegate(f.FieldType, m, false);
                if (handler == null)
                    return;
                f.SetValue(null, Delegate.Combine((Delegate)f.GetValue(null), handler));
            }
            catch (Exception)
            {
                // Optional: without it input_age follows focus changes only.
            }
        }

        static void OnGlobalEvent0() { OnInputEvent(); }
        static void OnGlobalEvent1(Event _) { OnInputEvent(); }

        static IEnumerable<string> TypeChain(EditorWindow w)
        {
            if (w == null)
                yield break;
            for (var t = w.GetType(); t != null && t != typeof(EditorWindow); t = t.BaseType)
                yield return t.Name;
        }

        static string CurrentUrl()
        {
            var token = ReporterCore.WindowToken(TypeChain(EditorWindow.focusedWindow));
            return ReporterCore.ContextUrl(EditorApplication.isPlaying, token);
        }

        static void Tick()
        {
            var now = EditorApplication.timeSinceStartup;
            if (now < nextPoll)
                return;
            nextPoll = now + ReporterCore.PollSeconds;
            try
            {
                if (!Enabled)
                {
                    Withdraw();
                    return;
                }
                var url = CurrentUrl();
                if (!policy.Due(url, now))
                    return;
                sender.Submit(ReporterSettings.Port, url, ReporterSettings.Token, pid,
                              now - lastInput, true);
                policy.Sent(url, now);
                reported = true;
            }
            catch (Exception e)
            {
                // A report must never break the editor.
                Debug.LogException(e);
            }
        }

        /// <summary>Tell the host this editor stopped reporting, once, so the
        /// keyboard leaves the last window's overlay at once.</summary>
        internal static void Withdraw()
        {
            if (!reported || sender == null)
                return;
            sender.Submit(ReporterSettings.Port, null, ReporterSettings.Token, pid, null, false);
            reported = false;
            policy.Reset();
        }

        static void OnQuitting()
        {
            Withdraw();
            sender?.Stop(ReporterCore.HttpTimeoutMs + 200);
            sender = null;
        }

        static void OnBeforeReload()
        {
            // No withdrawal: the reloaded domain reports again within a tick.
            // Unity waits for managed threads before it unloads the domain, so
            // the sender thread must end here.
            EditorApplication.update -= Tick;
            sender?.Stop(ReporterCore.HttpTimeoutMs + 200);
            sender = null;
        }
    }
}
