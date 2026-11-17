// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * PolyKybd Mode Reporter, remote part: the debug tracker for a remote window.
 *
 * Packaged as its own small extension (remote/package.json,
 * `"extensionKind": ["workspace"]`), because an extension runs in exactly one
 * extension host. In a Remote SSH, WSL, Dev Container or Codespaces window it
 * runs in the remote extension host, where the debug adapters run and where
 * VS Code creates their trackers. It reads the same Debug Adapter Protocol
 * messages as the UI part (`SessionState` in core.ts) and passes "running" or
 * "stopped" per session to the UI part with
 * `commands.executeCommand(BRIDGE_STATE_COMMAND, msg)`. The UI part sends the
 * report to PolyKybdHost; this part opens no network connection.
 *
 * In a local window there is one extension host, `extension.extensionKind` is
 * `UI`, and the UI part's own tracker sees the adapters: this part then does
 * nothing.
 */
import * as vscode from "vscode";

import { BRIDGE_STATE_COMMAND, BRIDGE_SYNC_COMMAND, BridgeMessage, WorkspaceBridge } from "./core";

let output: vscode.OutputChannel | undefined;
let noted = false;

function deliver(msg: BridgeMessage): void {
  // Rejects while the UI part is not installed or not active yet. Its sync
  // call asks for every state again when it starts.
  Promise.resolve(vscode.commands.executeCommand(BRIDGE_STATE_COMMAND, msg)).catch((e: unknown) => {
    if (noted) return;
    noted = true;
    output?.appendLine(`State not passed to the UI part (is "PolyKybd Mode Reporter" installed on this computer?): ${String(e)}`);
  });
}

export function activate(context: vscode.ExtensionContext): void {
  if (context.extension.extensionKind !== vscode.ExtensionKind.Workspace) return;
  output = vscode.window.createOutputChannel("PolyKybd Mode Reporter (remote part)");
  context.subscriptions.push(output);
  const bridge = new WorkspaceBridge(deliver);

  context.subscriptions.push(
    vscode.debug.registerDebugAdapterTrackerFactory("*", {
      createDebugAdapterTracker(session: vscode.DebugSession) {
        const t = bridge.track(session.id);
        return {
          onWillReceiveMessage: (m: unknown) => t.toAdapter(m),
          onDidSendMessage: (m: unknown) => t.fromAdapter(m),
          onExit: () => t.exit(),
        };
      },
    }),
    vscode.debug.onDidTerminateDebugSession((s) => bridge.end(s.id)),
    vscode.commands.registerCommand(BRIDGE_SYNC_COMMAND, () => { noted = false; bridge.resync(); }),
  );
}

export function deactivate(): void {
  // Nothing to withdraw: the UI part clears a session's state when the
  // session terminates.
}
