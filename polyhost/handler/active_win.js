for (const window of workspace.windowList()) {
    if(workspace.activeWindow === window) {
        var info;
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
        print(info);
    }
}