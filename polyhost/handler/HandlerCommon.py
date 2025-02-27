from enum import Enum


class OverlayCommand(Enum):
    NONE = 0
    OFF_ON = 1
    DISABLE = 2
    ENABLE = 3
    
class Flags(Enum):
    HAS_OVERLAY = 0
    HAS_REMOTE = 1
    HAS_TITLE = 2
    HAS_TITLES_STARTS_W = 3
    HAS_TITLES_ENDS_W = 4
    HAS_TITLES_CONTAINS = 5
    