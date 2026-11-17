# PolyKybd Mode Reporter (remote part)

The second part of [PolyKybd Mode Reporter](../README.md), for Remote SSH, WSL,
Dev Container and Codespaces windows of VS Code, Cursor and Windsurf.

In a remote window the debug adapters run in the remote extension host, and only
an extension there sees their messages. This part runs there
(`"extensionKind": ["workspace"]`), reads whether the program is running or
stopped, and passes that to PolyKybd Mode Reporter on your computer. It opens no
network connection; PolyKybd Mode Reporter sends the report to PolyKybdHost.

Install it in the remote: in a remote window, Extensions view, *PolyKybd Mode
Reporter (remote part)*, *Install in SSH: <host>* (or WSL, or Dev Container). In
a local window it does nothing.

The code is `src/remote.ts` and `src/core.ts` in the parent folder; `build.sh`
there packages both extensions.
