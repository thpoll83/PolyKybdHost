from PyQt5.QtWidgets import (QWidget, QToolButton, QButtonGroup)

from polyhost.gui.flow_layout import FlowLayout


class ButtonArray(QWidget):
    """An exclusive row of checkable buttons (the layout editor's layer bar).

    The buttons are plain checkable QToolButtons, the same as the keycap-mode
    switch beside them, so the active one gets the platform's own checked look.
    ⚠️ No stylesheet: the old one painted the checked button green and BOLD, and
    bold text is wider than the width the flow layout reserved for it from the
    regular font, so the active layer's label was cut off ("0 Qwerty" read as
    ") Qwerty").
    """

    def __init__(self, options):
        super().__init__()

        # spacing 0: one segmented strip, like the keycap-mode switch
        self.layout = FlowLayout(self, spacing=0)
        self.layout.setContentsMargins(2, 2, 2, 2)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)  # only one is active

        for index, text in enumerate(options):
            btn = QToolButton()
            btn.setText(text)
            btn.setCheckable(True)
            if index == 0:
                btn.setChecked(True)

            self.group.addButton(btn, index)
            self.layout.addWidget(btn)

    def connect(self, slot):
        self.group.buttonClicked.connect(slot)

    def set_active(self, idx: int):
        btn = self.group.button(idx)
        if btn is not None:
            btn.setChecked(True)
