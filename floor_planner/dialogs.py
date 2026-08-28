from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .core import (
    MAX_FURNITURE_INCHES,
    UNIT_LABELS,
    Furniture,
    ShapeSpec,
    ValidationError,
    format_measurement,
    from_inches,
    to_inches,
)

COLOR_CHOICES = [
    ("Blue", "#2F80ED"),
    ("Teal", "#11998E"),
    ("Green", "#27AE60"),
    ("Orange", "#F2994A"),
    ("Red", "#EB5757"),
    ("Purple", "#9B51E0"),
    ("Gray", "#667085"),
]


class ShapePreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self._shape: ShapeSpec | None = None
        self._color = QColor("#2F80ED")

    def set_shape(self, shape: ShapeSpec | None, color: str) -> None:
        self._shape = shape
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#F7F8FA"))
        if self._shape is None:
            painter.setPen(QColor("#667085"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Enter valid dimensions"
            )
            return
        points = self._shape.polygon_inches()
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        margin = 24.0
        scale = min(
            max(1.0, self.width() - margin * 2) / span_x,
            max(1.0, self.height() - margin * 2) / span_y,
        )
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        path = QPainterPath()
        for index, (x, y) in enumerate(points):
            px = center_x + x * scale
            py = center_y + y * scale
            if index == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)
        path.closeSubpath()
        fill = QColor(self._color)
        fill.setAlpha(150)
        painter.setBrush(fill)
        painter.setPen(QPen(self._color.darker(120), 2.0))
        painter.drawPath(path)


class CalibrationDialog(QDialog):
    def __init__(self, display_unit: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set the plan scale")
        self.setModal(True)

        intro = QLabel(
            "Enter the real-world length of the line you just drew. "
            "Use a printed dimension or a wall length you know."
        )
        intro.setWordWrap(True)

        self.distance = QDoubleSpinBox()
        self.distance.setDecimals(3)
        self.distance.setRange(0.001, 1_000_000.0)
        self.distance.setValue(
            {"ft": 10.0, "in": 120.0, "cm": 300.0, "m": 3.0}[display_unit]
        )
        self.distance.selectAll()

        self.unit = QComboBox()
        for key, label in UNIT_LABELS.items():
            self.unit.addItem(label, key)
        self.unit.setCurrentIndex(self.unit.findData(display_unit))

        row = QHBoxLayout()
        row.addWidget(self.distance, 1)
        row.addWidget(self.unit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(row)
        layout.addWidget(buttons)
        self.resize(430, self.sizeHint().height())

    def real_inches(self) -> float:
        return to_inches(self.distance.value(), str(self.unit.currentData()))


class FurnitureDialog(QDialog):
    def __init__(
        self,
        kind: str,
        display_unit: str,
        existing: Furniture | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.display_unit = display_unit
        self.existing = existing
        title = "L-shaped furniture" if kind == "l_shape" else "Rectangle furniture"
        self.setWindowTitle(f"Edit {title}" if existing else f"Add {title}")
        self.setModal(True)
        self._color = existing.color if existing else "#2F80ED"

        self.name = QLineEdit(
            existing.name
            if existing
            else ("L-shaped couch" if kind == "l_shape" else "Sofa")
        )
        self.name.setPlaceholderText("Example: Living room sofa")

        self.preset = QComboBox()
        self.preset.addItem("Custom size", None)
        if kind == "rectangle" and existing is None:
            self.preset.addItem("3-seat sofa (84 × 36 in)", ("Sofa", 84.0, 36.0))
            self.preset.addItem("Queen bed (60 × 80 in)", ("Queen bed", 60.0, 80.0))
            self.preset.addItem(
                "Dining table (72 × 36 in)", ("Dining table", 72.0, 36.0)
            )
            self.preset.addItem("Desk (48 × 24 in)", ("Desk", 48.0, 24.0))
            self.preset.addItem("Armchair (36 × 36 in)", ("Armchair", 36.0, 36.0))
            self.preset.currentIndexChanged.connect(self._apply_preset)

        self.width = self._dimension_spin()
        self.depth = self._dimension_spin()
        self.section_depth = self._dimension_spin()
        self.chaise_width = self._dimension_spin()
        self.side = QComboBox()
        self.side.addItem("Chaise on the right", "right")
        self.side.addItem("Chaise on the left", "left")

        if existing:
            self.width.setValue(from_inches(existing.shape.width_in, display_unit))
            self.depth.setValue(from_inches(existing.shape.depth_in, display_unit))
            if existing.shape.section_depth_in is not None:
                self.section_depth.setValue(
                    from_inches(existing.shape.section_depth_in, display_unit)
                )
            if existing.shape.chaise_width_in is not None:
                self.chaise_width.setValue(
                    from_inches(existing.shape.chaise_width_in, display_unit)
                )
            self.side.setCurrentIndex(self.side.findData(existing.shape.chaise_side))
        else:
            defaults = {
                "ft": (7.0, 3.0, 3.0, 3.0),
                "in": (84.0, 36.0, 36.0, 36.0),
                "cm": (215.0, 90.0, 90.0, 90.0),
                "m": (2.15, 0.9, 0.9, 0.9),
            }[display_unit]
            self.width.setValue(
                defaults[0] if kind == "rectangle" else defaults[0] + defaults[3]
            )
            self.depth.setValue(
                defaults[1] if kind == "rectangle" else defaults[1] * 2.0
            )
            self.section_depth.setValue(defaults[2])
            self.chaise_width.setValue(defaults[3])

        self.color_button = QPushButton()
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button()

        unit_label = UNIT_LABELS[display_unit].lower()
        form = QFormLayout()
        form.addRow("Name", self.name)
        if kind == "rectangle" and existing is None:
            form.addRow("Quick size", self.preset)
        form.addRow(f"Width ({unit_label})", self.width)
        form.addRow(f"Depth ({unit_label})", self.depth)
        if kind == "l_shape":
            form.addRow(f"Main section depth ({unit_label})", self.section_depth)
            form.addRow(f"Chaise width ({unit_label})", self.chaise_width)
            form.addRow("Layout", self.side)
        form.addRow("Color", self.color_button)

        self.preview = ShapePreview()
        preview_frame = QFrame()
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_title = QLabel("Top-down preview")
        preview_title.setStyleSheet("font-weight: 600;")
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self.preview)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #667085;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(preview_frame)
        layout.addWidget(self.hint)
        layout.addWidget(buttons)

        for widget in (self.width, self.depth, self.section_depth, self.chaise_width):
            widget.valueChanged.connect(self._refresh_preview)
        self.side.currentIndexChanged.connect(self._refresh_preview)
        self._refresh_preview()
        self.resize(520, self.sizeHint().height())

    def _dimension_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(3)
        spin.setRange(0.001, from_inches(MAX_FURNITURE_INCHES, self.display_unit))
        spin.setSingleStep(
            {"ft": 0.25, "in": 1.0, "cm": 1.0, "m": 0.05}[self.display_unit]
        )
        return spin

    def _apply_preset(self) -> None:
        preset = self.preset.currentData()
        if not preset:
            return
        name, width_in, depth_in = preset
        self.name.setText(name)
        self.width.setValue(from_inches(width_in, self.display_unit))
        self.depth.setValue(from_inches(depth_in, self.display_unit))

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._color), self, "Choose furniture color"
        )
        if color.isValid():
            self._color = color.name()
            self._update_color_button()
            self._refresh_preview()

    def _update_color_button(self) -> None:
        self.color_button.setText(self._color.upper())
        self.color_button.setStyleSheet(
            f"QPushButton {{ background: {self._color}; color: white; font-weight: 600; padding: 6px; }}"
        )

    def shape_spec(self) -> ShapeSpec:
        shape = ShapeSpec(
            kind=self.kind,
            width_in=to_inches(self.width.value(), self.display_unit),
            depth_in=to_inches(self.depth.value(), self.display_unit),
            section_depth_in=(
                to_inches(self.section_depth.value(), self.display_unit)
                if self.kind == "l_shape"
                else None
            ),
            chaise_width_in=(
                to_inches(self.chaise_width.value(), self.display_unit)
                if self.kind == "l_shape"
                else None
            ),
            chaise_side=str(self.side.currentData()),
        )
        shape.validate()
        return shape

    def _refresh_preview(self) -> None:
        try:
            shape = self.shape_spec()
        except ValidationError as exc:
            self.preview.set_shape(None, self._color)
            self.hint.setText(str(exc))
            return
        self.preview.set_shape(shape, self._color)
        self.hint.setText(
            f"Overall size: {format_measurement(shape.width_in, self.display_unit)} × "
            f"{format_measurement(shape.depth_in, self.display_unit)}"
        )

    def accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(
                self, "Name needed", "Give this furniture piece a short name."
            )
            self.name.setFocus()
            return
        try:
            self.shape_spec()
        except ValidationError as exc:
            QMessageBox.warning(self, "Check the dimensions", str(exc))
            return
        super().accept()

    def values(self) -> tuple[str, ShapeSpec, str]:
        return self.name.text().strip(), self.shape_spec(), self._color
