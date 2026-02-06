from PyQt5.QtWidgets import QGraphicsView

class ZoomableGraphicsView(QGraphicsView):
    """
    QGraphicsView that supports wheel zoom.
    `zoom_callback(delta)` is called with +1 / -1 steps when wheel triggers zoom.
    """
    def __init__(self, *args, zoom_callback=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.zoom_callback = zoom_callback
        # anchor so zoom focuses under the mouse pointer
        # noinspection PyTypeChecker
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle > 0:
            step = +1
        elif angle < 0:
            step = -1
        else:
            step = 0
        if step and self.zoom_callback:
            self.zoom_callback(step)
            return  # consume zoom event
        
        # otherwise default behavior (scroll/pan)
        super().wheelEvent(event)
