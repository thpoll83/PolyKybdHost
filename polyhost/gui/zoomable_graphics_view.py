from PyQt5.QtWidgets import QGraphicsView

# share of the viewport the scene fills at relative zoom 1, so the fitted board
# keeps a margin and no scroll bar appears at exactly the fit
FIT_MARGIN = 0.96


class ZoomableGraphicsView(QGraphicsView):
    """
    QGraphicsView that supports wheel zoom.
    `zoom_callback(delta)` is called with +1 / -1 steps when wheel triggers zoom.

    With `fit_scene=True` the zoom is RELATIVE to the window: `relative_zoom`
    1.0 shows the whole of `fit_rect` (the scene rect when unset), and every
    resize re-applies fit x relative_zoom, so a fully visible scene stays fully
    visible (shrinking with the window) and a zoomed-in one keeps its size
    relative to it. Give scenes that show the same thing differently the same
    `fit_rect` extent, and they show it at the same size.
    """
    def __init__(self, *args, zoom_callback=None, fit_scene=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.zoom_callback = zoom_callback
        self.fit_scene = fit_scene
        self.relative_zoom = 1.0
        self.fit_rect = None            # QRectF in scene coordinates, or None
        # anchor so zoom focuses under the mouse pointer
        # noinspection PyTypeChecker
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def _fit_rect(self):
        return self.fit_rect if self.fit_rect is not None else self.sceneRect()

    def fit_scale(self) -> float:
        """The scale at which the fit rect just fits the viewport."""
        r = self._fit_rect()
        vp = self.viewport().size()
        if r.width() <= 0 or r.height() <= 0 or vp.width() <= 0 or vp.height() <= 0:
            return 1.0
        return FIT_MARGIN * min(vp.width() / r.width(), vp.height() / r.height())

    def apply_zoom(self, center=None) -> None:
        """Scale to fit x relative_zoom, centred on `center` (scene point) or
        on whatever the viewport showed in its middle."""
        if center is None:
            center = self.mapToScene(self.viewport().rect().center())
        s = self.fit_scale() * self.relative_zoom
        self.resetTransform()
        self.scale(s, s)
        self.centerOn(center)

    def refit(self) -> None:
        """Back to the scene's middle at the current relative zoom: after the
        scene rect changes (another mode lays the board out differently)."""
        if self.fit_scene:
            self.apply_zoom(self._fit_rect().center())
        else:
            self.centerOn(self.sceneRect().center())

    def zoom_by(self, factor: float) -> None:
        """Change the relative zoom by `factor`, anchored under the mouse."""
        self.relative_zoom *= factor
        self.scale(factor, factor)

    def resizeEvent(self, event):
        # the middle of what was on screen stays in the middle; while the
        # whole board is visible, that is the board's own middle
        center = self.mapToScene(self.viewport().rect().center())
        super().resizeEvent(event)
        if self.fit_scene:
            self.apply_zoom(self._fit_rect().center() if self.relative_zoom <= 1.0 else center)

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
