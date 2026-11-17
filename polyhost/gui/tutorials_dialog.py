"""The Tutorials dialog and the step panel a running tutorial shows.

The dialog lists the scripts by category, like the Settings dialog. Start asks the
core to run one; from then on the core's "tutorial" event drives the step panel, a
small window that stays on top with Back, Next and Stop.

Both work in client mode: every core call goes through ``run_async(fn, done)``,
which the tray passes in (``host._core_click``), so a slow daemon never blocks the
GUI thread. docs/tutorials-plan.md.
"""
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
                             QPushButton, QScrollArea, QVBoxLayout,
                             QWidget)

from polyhost.gui import section_colors, section_style
from polyhost.gui.ui_kit import CARD_STYLE, WrapLabel, card, muted
from polyhost.i18n import _, _f, _nf, current_language
from polyhost.services.tutorials.loader import CATEGORIES, pick_text

_NAV_STYLE = """
QListWidget#tutorialsNav { background: transparent; border: none; outline: none; }
QLabel#tutorialTitle { font-weight: 600; }
QLabel#tutorialOled {
    background: black; color: white; border-radius: 4px; padding: 6px 10px;
}
"""


def category_label(category):
    labels = {
        "layers": _("Layers"),
        "languages": _("Languages and accents"),
        "light": _("Light and displays"),
        "emoji": _("Emoji"),
        "editor": _("Layout editor"),
        "other": _("Other"),
    }
    return labels.get(category, category)


def _text(texts):
    return pick_text(texts or {}, current_language())


class TutorialsDialog(QDialog):
    """Pick a tutorial. `run_async(fn, done)` runs `fn` off the GUI thread and
    calls `done(ok, value)` on it; `on_started(state)` opens the step panel."""

    def __init__(self, core, run_async, on_started, parent=None):
        super().__init__(parent)
        self.core = core
        self.run_async = run_async
        self.on_started = on_started
        self.info = {}
        self.setWindowTitle(_("PolyKybd Tutorials"))
        self.setStyleSheet(CARD_STYLE + _NAV_STYLE)
        self.resize(760, 480)

        main = QVBoxLayout(self)
        body = QHBoxLayout()
        self.nav = QListWidget()
        self.nav.setObjectName("tutorialsNav")
        self.nav.setFixedWidth(200)
        # Coloured entries and sections, as in Settings (gui/section_style.py).
        section_style.style_nav(self.nav)
        self.nav.currentRowChanged.connect(self._show_category)
        body.addWidget(self.nav)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        # Cards wrap their text to the width instead of scrolling sideways.
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body.addWidget(self.scroll, 1)
        main.addLayout(body, 1)

        self.status = WrapLabel(_("Reading the tutorials..."))
        muted(self.status)
        main.addWidget(self.status)
        buttons = QHBoxLayout()
        self.folder_button = QPushButton(_("Open tutorials folder"))
        self.folder_button.setToolTip(
            _("Put your own tutorial scripts (.yaml) in this folder."))
        self.folder_button.clicked.connect(self._open_folder)
        self.folder_button.setEnabled(False)
        buttons.addWidget(self.folder_button)
        buttons.addStretch(1)
        close = QPushButton(_("Close"))
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        main.addLayout(buttons)

    def load(self):
        """Read the list off the GUI thread; called after show()."""
        self.run_async(lambda: (True, self.core.tutorials_list()), self._loaded)

    # ---- list -------------------------------------------------------------------

    def _loaded(self, ok, info):
        if not ok or not isinstance(info, dict):
            self.status.setText(_f("Cannot read the tutorials: {error}", error=info))
            return
        self.info = info
        self.folder_button.setEnabled(bool(info.get("user_dir")))
        self._categories = [c for c in CATEGORIES
                            if any(t["category"] == c for t in info.get("tutorials", []))]
        self.nav.clear()
        dark = section_style.dialog_is_dark(self)
        self._colors = [section_colors.slot_color(i, dark) for i in range(len(self._categories))]
        for c, color in zip(self._categories, self._colors):
            section_style.add_nav_item(self.nav, category_label(c), color)
        errors = info.get("errors") or []
        if errors:
            lines = [f"{e['path']}: {e['error']}" for e in errors]
            self.status.setText(_nf("A tutorial script has an error:",
                                    "{n} tutorial scripts have errors:", len(errors))
                                + "\n" + "\n".join(lines))
        else:
            self.status.setText("")
        if self._categories:
            self.nav.setCurrentRow(0)

    def _show_category(self, row):
        if row < 0 or row >= len(getattr(self, "_categories", [])):
            return
        category = self._categories[row]
        protocol = self.info.get("protocol") or 0
        page = QWidget()
        outer = QVBoxLayout(page)
        section = section_style.ColorSection(category_label(category), self._colors[row])
        lay = section.body_layout
        for t in self.info.get("tutorials", []):
            if t["category"] == category:
                lay.addWidget(self._card(t, protocol))
        lay.addStretch(1)
        outer.addWidget(section, 1)
        self.scroll.setWidget(page)

    def _card(self, t, protocol):
        frame, lay = card()
        title = QLabel(_text(t["title"]))
        title.setObjectName("tutorialTitle")
        lay.addWidget(title)
        if t.get("summary"):
            lay.addWidget(WrapLabel(_text(t["summary"])))
        row = QHBoxLayout()
        note = _nf("{n} step", "{n} steps", t["steps"])
        if t.get("user"):
            note += " · " + _("your script")
        ready = protocol >= t["min_protocol"]
        if not ready:
            note += " · " + _f("needs firmware protocol {protocol}",
                               protocol=t["min_protocol"])
        info = WrapLabel(note)
        muted(info)
        row.addWidget(info, 1)
        start = QPushButton(_("Start"))
        start.setEnabled(ready)
        start.clicked.connect(lambda _checked=False, tid=t["id"]: self._start(tid))
        row.addWidget(start)
        lay.addLayout(row)
        return frame

    # ---- actions ------------------------------------------------------------------

    def _start(self, tid):
        self.status.setText(_("Starting..."))

        def done(ok, state):
            if not ok:
                self.status.setText(_f("Cannot start the tutorial: {error}", error=state))
                return
            self.on_started(state)
            self.accept()
        self.run_async(lambda: self.core.tutorial_start(tid), done)

    def _open_folder(self):
        import os
        path = self.info.get("user_dir")
        if not path:
            return
        os.makedirs(path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class TutorialPanel(QWidget):
    """The running tutorial's step: what the status display says, the longer text,
    and Back / Next / Stop. `update_state(state)` takes the core's event."""

    def __init__(self, core, run_async, parent=None):
        super().__init__(parent, Qt.Tool | Qt.WindowStaysOnTopHint)
        self.core = core
        self.run_async = run_async
        self.state = None
        self.setStyleSheet(_NAV_STYLE)
        self.setMinimumWidth(360)
        lay = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setObjectName("tutorialTitle")
        lay.addWidget(self.title)
        self.progress = QLabel()
        muted(self.progress)
        lay.addWidget(self.progress)
        self.oled = QLabel()
        self.oled.setObjectName("tutorialOled")
        self.oled.setFont(QFont("monospace"))
        self.oled.setToolTip(_("What the keyboard's status display will show"))
        lay.addWidget(self.oled)
        self.text = WrapLabel()
        lay.addWidget(self.text)
        self.note = WrapLabel()
        muted(self.note)
        lay.addWidget(self.note)
        buttons = QHBoxLayout()
        self.back_button = QPushButton(_("Back"))
        self.back_button.clicked.connect(lambda: self._action("back"))
        self.next_button = QPushButton(_("Next"))
        self.next_button.setDefault(True)
        self.next_button.clicked.connect(lambda: self._action("next"))
        self.stop_button = QPushButton(_("Stop"))
        self.stop_button.clicked.connect(lambda: self._action("stop"))
        buttons.addWidget(self.back_button)
        buttons.addStretch(1)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.next_button)
        lay.addLayout(buttons)

    def update_state(self, state):
        """Show `state`; a finished tutorial closes the panel."""
        if not state or state.get("finished"):
            self.state = None
            self.close()
            return
        self.state = state
        self.setWindowTitle(_text(state.get("title")))
        self.title.setText(_text(state.get("title")))
        step, steps = state["step"], state["steps"]
        self.progress.setText(_f("Step {step} of {steps}", step=step + 1, steps=steps))
        say = state.get("say") or []
        self.oled.setText("\n".join(say))
        self.oled.setVisible(bool(say))
        self.text.setText(_text(state.get("text")))
        notes = []
        if state.get("auto") and state.get("remaining_s") is not None:
            notes.append(_f("The next step starts in {seconds} s.",
                            seconds=round(state["remaining_s"])))
        if state.get("ring_error"):
            notes.append(_f("The keyboard cannot point at the key: {reason}",
                            reason=state["ring_error"]))
        self.note.setText("\n".join(notes))
        self.note.setVisible(bool(notes))
        self.back_button.setEnabled(step > 0)
        self.next_button.setText(_("Finish") if step + 1 >= steps else _("Next"))

    def _action(self, action):
        def done(ok, state):
            if ok:
                self.update_state(state)
        self.run_async(lambda: self.core.tutorial_action(action), done)

    def closeEvent(self, event):  # noqa: N802 - Qt name
        # Closing the window ends the tutorial, so the keyboard stops ringing.
        if self.state is not None:
            self.state = None
            self.run_async(lambda: self.core.tutorial_action("stop"), lambda ok, s: None)
        super().closeEvent(event)
