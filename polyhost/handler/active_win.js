for (const window of workspace.windowList()) {
    if(workspace.activeWindow === window) {
        var info;
        if (window.resourceName) {
            info = window.resourceName + ";";
        } else {
            info = ";";
        }
        if (window.caption) {
            info += window.caption;
        }
        print(info);
    }
}