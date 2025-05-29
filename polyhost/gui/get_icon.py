import os
import pathlib

from PyQt5.QtGui import QIcon


def get_icon(name):
    return QIcon(os.path.join(pathlib.Path(__file__).parent.parent.resolve(), "res/icons/", name))
