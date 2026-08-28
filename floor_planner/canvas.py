from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsView


class FloorPlanView(QGraphicsView):
    calibration_drawn = Signal(QPointF, QPointF)
    delete_pressed = Signal()
    duplicate_pressed = Signal()
    rotate_requested = Signal(float)
    nudge_requested = Signal(float, float)
    files_dropped = Signal(list)
    zoom_changed = Signal(int)
    mode_changed = Signal(str)

    def __init__(self, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self._mode = "select"
        self._calibration_start: QPointF | None = None
        self._temporary_line: QGraphicsLineItem | None = None
        self._panning = False
        self._pan_last = QPoint()
        self._space_down = False
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setBackgroundBrush(QColor("#CDD5DF"))
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in {"select", "pan", "calibrate"}:
            return
        self.cancel_calibration()
        self._mode = mode
        if mode == "pan":
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        elif mode == "calibrate":
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.mode_changed.emit(mode)

    def cancel_calibration(self) -> None:
        self._calibration_start = None
        if self._temporary_line is not None and self.scene() is not None:
            self.scene().removeItem(self._temporary_line)
        self._temporary_line = None

    def fit_page(self) -> None:
        if self.scene() is None or self.scene().sceneRect().isEmpty():
            return
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._emit_zoom()

    def zoom_by(self, factor: float) -> None:
        current = self.transform().m11()
        target = current * factor
        if 0.08 <= target <= 20.0:
            self.scale(factor, factor)
            self._emit_zoom()

    def _emit_zoom(self) -> None:
        self.zoom_changed.emit(round(self.transform().m11() * 100))

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.zoom_by(1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self._space_down
        ):
            self._panning = True
            self._pan_last = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if self._mode == "calibrate" and event.button() == Qt.MouseButton.LeftButton:
            self._calibration_start = self.mapToScene(event.position().toPoint())
            self._temporary_line = QGraphicsLineItem()
            pen = QPen(QColor("#D97706"), 2.0, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._temporary_line.setPen(pen)
            self._temporary_line.setZValue(1000.0)
            self.scene().addItem(self._temporary_line)
            self._temporary_line.setLine(
                self._calibration_start.x(),
                self._calibration_start.y(),
                self._calibration_start.x(),
                self._calibration_start.y(),
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def _constrained_point(
        self, point: QPointF, modifiers: Qt.KeyboardModifier
    ) -> QPointF:
        if self._calibration_start is None or not (
            modifiers & Qt.KeyboardModifier.ShiftModifier
        ):
            return point
        dx = point.x() - self._calibration_start.x()
        dy = point.y() - self._calibration_start.y()
        distance = math.hypot(dx, dy)
        if distance == 0:
            return point
        angle = math.atan2(dy, dx)
        snapped = round(angle / (math.pi / 4.0)) * (math.pi / 4.0)
        return QPointF(
            self._calibration_start.x() + math.cos(snapped) * distance,
            self._calibration_start.y() + math.sin(snapped) * distance,
        )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            current = event.position().toPoint()
            delta = current - self._pan_last
            self._pan_last = current
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
            return
        if (
            self._mode == "calibrate"
            and self._calibration_start
            and self._temporary_line
        ):
            end = self._constrained_point(
                self.mapToScene(event.position().toPoint()), event.modifiers()
            )
            self._temporary_line.setLine(
                self._calibration_start.x(),
                self._calibration_start.y(),
                end.x(),
                end.y(),
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            self._panning = False
            self.viewport().setCursor(
                Qt.CursorShape.OpenHandCursor
                if self._mode == "pan"
                else Qt.CursorShape.ArrowCursor
            )
            event.accept()
            return
        if (
            self._mode == "calibrate"
            and event.button() == Qt.MouseButton.LeftButton
            and self._calibration_start is not None
        ):
            start = self._calibration_start
            end = self._constrained_point(
                self.mapToScene(event.position().toPoint()), event.modifiers()
            )
            self.cancel_calibration()
            if math.hypot(end.x() - start.x(), end.y() - start.y()) > 1e-3:
                self.calibration_drawn.emit(start, end)
            self.set_mode("select")
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._space_down = True
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if key in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
            self.delete_pressed.emit()
            return
        if key == Qt.Key.Key_Escape:
            self.cancel_calibration()
            self.set_mode("select")
            if self.scene() is not None:
                self.scene().clearSelection()
            return
        if key in {Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down}:
            step = 6.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
            dx = (
                -step
                if key == Qt.Key.Key_Left
                else step
                if key == Qt.Key.Key_Right
                else 0.0
            )
            dy = (
                -step
                if key == Qt.Key.Key_Up
                else step
                if key == Qt.Key.Key_Down
                else 0.0
            )
            self.nudge_requested.emit(dx, dy)
            return
        if key == Qt.Key.Key_BracketLeft:
            self.rotate_requested.emit(-15.0)
            return
        if key == Qt.Key.Key_BracketRight:
            self.rotate_requested.emit(15.0)
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space_down = False
            self.viewport().setCursor(
                Qt.CursorShape.OpenHandCursor
                if self._mode == "pan"
                else Qt.CursorShape.ArrowCursor
            )
            event.accept()
            return
        super().keyReleaseEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        if any(path.lower().endswith((".pdf", ".floorplan")) for path in paths):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        supported = [
            path for path in paths if path.lower().endswith((".pdf", ".floorplan"))
        ]
        if supported:
            self.files_dropped.emit(supported)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
