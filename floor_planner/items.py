from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsSceneContextMenuEvent,
    QMenu,
    QStyle,
    QStyleOptionGraphicsItem,
    QWidget,
)

from .core import Furniture, format_measurement


class FurnitureItem(QGraphicsObject):
    changed = Signal(object)
    edit_requested = Signal(object)
    duplicate_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(
        self,
        furniture: Furniture,
        points_per_inch: float,
        display_unit: str,
    ) -> None:
        super().__init__()
        self.furniture = furniture
        self._points_per_inch = points_per_inch
        self._display_unit = display_unit
        self._path = QPainterPath()
        self._mouse_start = QPointF()
        self.setZValue(10.0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setAcceptHoverEvents(True)
        self._update_movable()
        self._rebuild_path()
        self.setPos(furniture.x, furniture.y)
        self.setRotation(furniture.rotation)
        self.setTransformOriginPoint(0.0, 0.0)
        self.setToolTip(self._tooltip())

    def _rebuild_path(self) -> None:
        self.prepareGeometryChange()
        polygon = QPolygonF(
            [
                QPointF(x * self._points_per_inch, y * self._points_per_inch)
                for x, y in self.furniture.shape.polygon_inches()
            ]
        )
        self._path = QPainterPath()
        self._path.addPolygon(polygon)
        self._path.closeSubpath()
        self.update()

    def _tooltip(self) -> str:
        shape = self.furniture.shape
        state = " • locked" if self.furniture.locked else ""
        return (
            f"{self.furniture.name}\n"
            f"{format_measurement(shape.width_in, self._display_unit)} × "
            f"{format_measurement(shape.depth_in, self._display_unit)}{state}"
        )

    def set_scale(self, points_per_inch: float) -> None:
        self._points_per_inch = points_per_inch
        self._rebuild_path()

    def set_display_unit(self, display_unit: str) -> None:
        self._display_unit = display_unit
        self.setToolTip(self._tooltip())
        self.update()

    def refresh_from_model(self) -> None:
        self._update_movable()
        self._rebuild_path()
        self.setPos(self.furniture.x, self.furniture.y)
        self.setRotation(self.furniture.rotation)
        self.setToolTip(self._tooltip())

    def _update_movable(self) -> None:
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            not self.furniture.locked,
        )

    def boundingRect(self) -> QRectF:
        return self._path.boundingRect().adjusted(-5.0, -5.0, 5.0, 5.0)

    def shape(self) -> QPainterPath:
        return self._path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        base = QColor(self.furniture.color)
        fill = QColor(base)
        fill.setAlpha(150 if not self.furniture.locked else 105)
        pen = QPen(base.darker(135), 1.8)
        pen.setCosmetic(True)
        if option.state & QStyle.StateFlag.State_Selected:
            pen.setColor(QColor("#111827"))
            pen.setWidthF(2.5)
        painter.setPen(pen)
        painter.setBrush(fill)
        painter.drawPath(self._path)

        bounds = self._path.boundingRect()
        if bounds.width() >= 18 and bounds.height() >= 12:
            font = QFont()
            font.setPointSizeF(8.0)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(QColor("#102A43")))
            label = self.furniture.name
            painter.drawText(bounds.adjusted(3, 3, -3, -3), 0x84, label)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor("white"))
            painter.setPen(QPen(QColor("#111827"), 1.5))
            painter.drawEllipse(QPointF(0.0, bounds.top() - 3.5), 3.0, 3.0)

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._mouse_start = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().mouseReleaseEvent(event)
        if self.pos() != self._mouse_start:
            self.furniture.x = self.pos().x()
            self.furniture.y = self.pos().y()
            self.changed.emit(self)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.edit_requested.emit(self)
        event.accept()

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:
        menu = QMenu()
        edit = menu.addAction("Edit dimensions…")
        duplicate = menu.addAction("Duplicate")
        menu.addSeparator()
        rotate_left = menu.addAction("Rotate left 15°")
        rotate_right = menu.addAction("Rotate right 15°")
        rotate_90 = menu.addAction("Rotate 90°")
        lock = menu.addAction("Unlock" if self.furniture.locked else "Lock")
        menu.addSeparator()
        delete = menu.addAction("Delete")
        chosen = menu.exec(event.screenPos())
        if chosen is edit:
            self.edit_requested.emit(self)
        elif chosen is duplicate:
            self.duplicate_requested.emit(self)
        elif chosen is rotate_left:
            self.rotate_by(-15.0)
        elif chosen is rotate_right:
            self.rotate_by(15.0)
        elif chosen is rotate_90:
            self.rotate_by(90.0)
        elif chosen is lock:
            self.furniture.locked = not self.furniture.locked
            self._update_movable()
            self.setToolTip(self._tooltip())
            self.update()
            self.changed.emit(self)
        elif chosen is delete:
            self.delete_requested.emit(self)

    def rotate_by(self, degrees: float) -> None:
        self.furniture.rotation = (self.furniture.rotation + degrees) % 360.0
        self.setRotation(self.furniture.rotation)
        self.changed.emit(self)
