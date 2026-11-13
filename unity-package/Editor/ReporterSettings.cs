// SPDX-License-Identifier: GPL-3.0-or-later
//
// Preferences > PolyKybd Context Reporter. Stored in EditorPrefs, so the
// settings are per user and apply to every project that has the package.

using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace PolyKybd.ContextReporter
{
    static class ReporterSettings
    {
        const string Prefix = "PolyKybd.ContextReporter.";

        public static bool Enabled
        {
            get => EditorPrefs.GetBool(Prefix + "Enabled", true);
            set => EditorPrefs.SetBool(Prefix + "Enabled", value);
        }

        public static int Port
        {
            get => EditorPrefs.GetInt(Prefix + "Port", ReporterCore.DefaultPort);
            set => EditorPrefs.SetInt(Prefix + "Port", Mathf.Clamp(value, 1, 65535));
        }

        public static string Token
        {
            get => EditorPrefs.GetString(Prefix + "Token", "");
            set => EditorPrefs.SetString(Prefix + "Token", value ?? "");
        }

        [SettingsProvider]
        static SettingsProvider Create()
        {
            return new SettingsProvider("Preferences/PolyKybd Context Reporter", SettingsScope.User)
            {
                label = "PolyKybd Context Reporter",
                keywords = new HashSet<string>(new[] { "PolyKybd", "keyboard", "overlay", "report" }),
                guiHandler = _ =>
                {
                    EditorGUILayout.HelpBox(
                        "Sends the play state and the type of the focused editor window " +
                        "(for example unity://edit/scene) to PolyKybdHost on 127.0.0.1. " +
                        "Nothing else is sent.", MessageType.None);
                    var enabled = EditorGUILayout.Toggle(
                        new GUIContent("Report context", "Switch the reporting off without removing the package"),
                        Enabled);
                    if (enabled != Enabled)
                    {
                        Enabled = enabled;
                        if (!enabled)
                            ContextReporter.Withdraw();
                    }
                    Port = EditorGUILayout.IntField(
                        new GUIContent("Port", "PolyKybdHost's browser_report_port (default 50164)"), Port);
                    Token = EditorGUILayout.PasswordField(
                        new GUIContent("Token", "Only if PolyKybdHost has browser_report_token set: the same value"),
                        Token);
                },
            };
        }
    }
}
