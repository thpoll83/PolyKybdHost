"""Self-update progress handling shared by the tray app and the forwarder.

``PolyHost`` and ``PolyForwarder`` both run :class:`~polyhost.services.updater.UpdateInstaller`
behind a ``QProgressDialog`` and both have to deal with the same three outcomes:
streaming progress, a Windows locked-file **relay** restart, and a failure. They
had two hand-written copies of that, and the copies had drifted:

* ``_on_update_progress`` was byte-identical — pure duplication.
* the **relay spawn** was not. The tray used
  ``spawn_detached([relaunch_executable(), relay_path])``; the forwarder used a
  bare ``subprocess.Popen([sys.executable, relay_path], close_fds=False, ...)``.
  Both divergences are the documented failure modes (CLAUDE.md, "Every relaunch
  in the update chain must be spawned DETACHED"): ``sys.executable`` is whatever
  interpreter this process happens to run under, so a forwarder started from a
  terminal relaunched itself through ``python.exe`` and owned a console window
  from then on; and a bare ``Popen`` skips ``CREATE_BREAKAWAY_FROM_JOB`` (a
  VS Code debug session's job object then takes the restarted app down with it)
  and the DEVNULL stdio a console-less child needs.

The controller drives a **duck-typed** dialog rather than constructing one, so
each app keeps its own dialog styling — the tray snaps its dialog to the tray
corner, the forwarder uses a plain one — while the logic lives here once. That
also keeps this module import-light and unit-testable without a Qt platform.
"""
from polyhost.services.updater import relaunch_executable, spawn_detached

#: Shown while the relay script takes over — the app is about to vanish.
RELAY_LABEL = "Restarting to complete update…"


class UpdateProgressController:
    """Owns the update progress dialog and the relay handoff.

    ``log`` needs ``info`` and ``error``. The dialog (attached with
    :meth:`attach`) needs the ``QProgressDialog`` subset used below; every method
    is a no-op when no dialog is attached, so a headless/failed-dialog path never
    has to guard at the call site.
    """

    def __init__(self, log):
        self.log = log
        self.dialog = None

    def attach(self, dialog):
        """Adopt a freshly-shown progress dialog."""
        self.dialog = dialog
        return dialog

    def on_progress(self, percent, message):
        """Render one progress callback.

        A negative percent means "indeterminate" (the installer does not always
        know a total), which Qt spells as a 0..0 range; the next real percent has
        to restore the 0..100 range or the bar stays a busy pulse forever."""
        if self.dialog is None:
            return
        self.dialog.setLabelText(message)
        if percent < 0:
            self.dialog.setRange(0, 0)          # indeterminate / busy pulse
        else:
            if self.dialog.maximum() == 0:
                self.dialog.setRange(0, 100)
            self.dialog.setValue(percent)

    def close(self):
        """Close and forget the dialog. Idempotent."""
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def stage_relay(self, relay_path):
        """Spawn the locked-file relay script so it outlives this process.

        Returns True if the relay was started. A failure here is the last step
        of an update, so it is reported rather than raised: silently failing to
        spawn is indistinguishable from "the app never came back", with the tree
        already rewritten and no evidence anywhere.
        """
        if self.dialog is not None:
            self.dialog.setLabelText(RELAY_LABEL)
            self.dialog.setValue(100)
        argv = [relaunch_executable(), str(relay_path)]
        try:
            spawn_detached(argv)
        except Exception as e:  # noqa: BLE001 — must not escape into a Qt slot
            self.log.error("Could not start the update relay %s: %s", relay_path, e)
            return False
        self.log.info("Update relay started: %s", relay_path)
        return True
