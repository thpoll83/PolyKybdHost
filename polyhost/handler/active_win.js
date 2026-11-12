// Prints one line for polyhost/handler/kde_win_reporter.py to read back from the
// journal: "polykybd-window:<class>;<caption>;<pid>", or "polykybd-window:none"
// when no window is active. A read that finds neither is a failed read, not
// "no window".
var info = "none";
for (const window of workspace.windowList()) {
    if(workspace.activeWindow === window) {
        if (window.resourceClass) {
            info = window.resourceClass + ";";
        } else if (window.resourceName) {
            info = window.resourceName + ";";
        } else {
            info = ";";
        }
        if (window.caption) {
            info += window.caption + ";";
        } else {
            info += ";";
        }
        if (window.pid) {
            info += window.pid;
        }
    }
}
// A line break in a caption would split the reply, or forge a second one.
print("polykybd-window:" + info.replace(/[\r\n]/g, " "));
