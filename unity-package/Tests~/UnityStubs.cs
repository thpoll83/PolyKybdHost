// SPDX-License-Identifier: GPL-3.0-or-later
//
// Compile-only stand-ins for the UnityEditor / UnityEngine members the package
// uses, so `run_tests.sh` can check that ContextReporter.cs and
// ReporterSettings.cs compile without a Unity install. The signatures follow
// UnityCsReference (Editor/Mono/EditorWindow.cs, EditorApplication.cs,
// AssemblyReloadEvents.cs, Settings/SettingsProvider.cs, EditorPrefs). They
// are NOT the real assemblies: a member Unity renamed or removed is not caught
// here. Nothing in this file is shipped to Unity (Tests~ is ignored by the
// asset database).

using System;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Event { }
    public enum LogType { Log }
    public static class Debug
    {
        public static void LogWarning(object message) { }
        public static void LogException(Exception exception) { }
    }
    public static class Mathf
    {
        public static int Clamp(int value, int min, int max) => value < min ? min : value > max ? max : value;
    }
    public class GUIContent
    {
        public GUIContent(string text, string tooltip) { }
    }
}

namespace UnityEditor
{
    [AttributeUsage(AttributeTargets.Class)]
    public class InitializeOnLoadAttribute : Attribute { }

    [AttributeUsage(AttributeTargets.Method)]
    public class SettingsProviderAttribute : Attribute { }

    public enum PlayModeStateChange { EnteredEditMode, ExitingEditMode, EnteredPlayMode, ExitingPlayMode }
    public enum SettingsScope { User, Project }
    public enum MessageType { None, Info, Warning, Error }

    public class ScriptableObject { }

    public class EditorWindow : ScriptableObject
    {
        public static EditorWindow focusedWindow => null;
        public static event Action windowFocusChanged { add { } remove { } }
    }

    public static class EditorApplication
    {
        public delegate void CallbackFunction();
        internal static CallbackFunction globalEventHandler;
        public static CallbackFunction update;
        public static event Action<PlayModeStateChange> playModeStateChanged { add { } remove { } }
        public static event Action quitting { add { } remove { } }
        public static bool isPlaying => false;
        public static double timeSinceStartup => 0;
    }

    public static class AssemblyReloadEvents
    {
        public delegate void AssemblyReloadCallback();
        public static event AssemblyReloadCallback beforeAssemblyReload { add { } remove { } }
    }

    public static class EditorPrefs
    {
        public static bool GetBool(string key, bool defaultValue) => defaultValue;
        public static void SetBool(string key, bool value) { }
        public static int GetInt(string key, int defaultValue) => defaultValue;
        public static void SetInt(string key, int value) { }
        public static string GetString(string key, string defaultValue) => defaultValue;
        public static void SetString(string key, string value) { }
    }

    public static class EditorGUILayout
    {
        public static void HelpBox(string message, MessageType type) { }
        public static bool Toggle(UnityEngine.GUIContent label, bool value) => value;
        public static int IntField(UnityEngine.GUIContent label, int value) => value;
        public static string PasswordField(UnityEngine.GUIContent label, string password) => password;
    }

    public class SettingsProvider
    {
        public SettingsProvider(string path, SettingsScope scope, IEnumerable<string> keywords = null) { }
        public string label { get; set; }
        public IEnumerable<string> keywords { get; set; }
        public Action<string> guiHandler { get; set; }
    }
}
