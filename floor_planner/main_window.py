from __future__ import annotations

import copy
import math
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any
from uuid import uuid4

import pypdfium2 as pdfium
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QColor,
    QFont,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .canvas import FloorPlanView
from .core import (
    UNIT_LABELS,
    Calibration,
    Furniture,
    Project,
    ValidationError,
    format_measurement,
    to_inches,
)
from .dialogs import CalibrationDialog, FurnitureDialog
from .items import FurnitureItem
from .project_io import (
    LoadedProject,
    ProjectFileError,
    load_project_bundle,
    save_project_bundle,
)

PDF_RENDER_SCALE = 2.0
MAX_PDF_RENDER_EDGE = 5_000
MAX_PDF_RENDER_PIXELS = 12_000_000
MAX_PDF_PAGE_POINTS = 1_000_000
MAX_EXPORT_EDGE = 8_000
MAX_EXPORT_PIXELS = 16_000_000


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Floor Planner")
        self.resize(1280, 820)
        self.setMinimumSize(760, 500)

        self.project = Project()
        self.pdf_document: Any | None = None
        self.pdf_path: str | None = None
        self.project_path: str | None = None
        self.loaded_bundle: LoadedProject | None = None
        self.last_directory = str(Path.home())
        self.background_item: QGraphicsPixmapItem | None = None
        self.calibration_line_item: QGraphicsLineItem | None = None
        self.calibration_label_item: QGraphicsSimpleTextItem | None = None
        self.furniture_items: list[FurnitureItem] = []
        self._changing_page = False

        self._history_current: dict[str, Any] = {}
        self._history_past: list[dict[str, Any]] = []
        self._history_future: list[dict[str, Any]] = []
        self._saved_snapshot: dict[str, Any] = {}
        self._saved_current_page = 0

        self.scene = QGraphicsScene(self)
        self.view = FloorPlanView(self)
        self.view.setScene(self.scene)
        self.scene.selectionChanged.connect(self._update_inspector)
        self.view.calibration_drawn.connect(self._finish_calibration)
        self.view.delete_pressed.connect(self.delete_selected)
        self.view.duplicate_pressed.connect(self.duplicate_selected)
        self.view.rotate_requested.connect(self.rotate_selected)
        self.view.nudge_requested.connect(self.nudge_selected)
        self.view.files_dropped.connect(self._open_dropped_files)
        self.view.zoom_changed.connect(self._update_zoom_label)
        self.view.mode_changed.connect(self._sync_mode_actions)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_central_widget()
        self._create_inspector()
        self._create_status_bar()
        self._reset_history()
        self._update_ui_state()

    # ----- UI construction -------------------------------------------------

    def _create_actions(self) -> None:
        self.open_pdf_action = QAction("Open PDF…", self)
        self.open_pdf_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_pdf_action.triggered.connect(self.open_pdf)

        self.open_project_action = QAction("Open Project…", self)
        self.open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_project_action.triggered.connect(self.open_project)

        self.save_action = QAction("Save Project", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.save_project)

        self.save_as_action = QAction("Save Project As…", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(lambda: self.save_project(save_as=True))

        self.export_action = QAction("Export Current Page as PNG…", self)
        self.export_action.setShortcut(QKeySequence("Ctrl+E"))
        self.export_action.triggered.connect(self.export_png)

        self.quit_action = QAction("Quit", self)
        self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.undo)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcuts(
            [QKeySequence.StandardKey.Redo, QKeySequence("Ctrl+Shift+Z")]
        )
        self.redo_action.triggered.connect(self.redo)

        self.duplicate_action = QAction("Duplicate", self)
        self.duplicate_action.setShortcut(QKeySequence("Ctrl+D"))
        self.duplicate_action.triggered.connect(self.duplicate_selected)

        self.delete_action = QAction("Delete", self)
        self.delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_action.triggered.connect(self.delete_selected)

        self.select_action = QAction("Select", self)
        self.select_action.setCheckable(True)
        self.select_action.setChecked(True)
        self.select_action.setShortcut(QKeySequence("V"))
        self.select_action.triggered.connect(lambda: self.view.set_mode("select"))

        self.pan_action = QAction("Pan", self)
        self.pan_action.setCheckable(True)
        self.pan_action.setShortcut(QKeySequence("H"))
        self.pan_action.triggered.connect(lambda: self.view.set_mode("pan"))

        self.mode_group = QActionGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addAction(self.select_action)
        self.mode_group.addAction(self.pan_action)

        self.calibrate_action = QAction("Calibrate Scale", self)
        self.calibrate_action.setShortcut(QKeySequence("K"))
        self.calibrate_action.triggered.connect(self.begin_calibration)

        self.add_rectangle_action = QAction("Add Rectangle", self)
        self.add_rectangle_action.setShortcut(QKeySequence("R"))
        self.add_rectangle_action.triggered.connect(
            lambda: self.add_furniture("rectangle")
        )

        self.add_l_shape_action = QAction("Add L-Shape", self)
        self.add_l_shape_action.setShortcut(QKeySequence("L"))
        self.add_l_shape_action.triggered.connect(lambda: self.add_furniture("l_shape"))

        self.rotate_left_action = QAction("Rotate Left 15°", self)
        self.rotate_left_action.setShortcut(QKeySequence("["))
        self.rotate_left_action.triggered.connect(lambda: self.rotate_selected(-15.0))

        self.rotate_right_action = QAction("Rotate Right 15°", self)
        self.rotate_right_action.setShortcut(QKeySequence("]"))
        self.rotate_right_action.triggered.connect(lambda: self.rotate_selected(15.0))

        self.fit_action = QAction("Fit Page", self)
        self.fit_action.setShortcut(QKeySequence("Ctrl+0"))
        self.fit_action.triggered.connect(self.view.fit_page)

        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.zoom_in_action.triggered.connect(lambda: self.view.zoom_by(1.2))

        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.zoom_out_action.triggered.connect(lambda: self.view.zoom_by(1.0 / 1.2))

        self.shortcuts_action = QAction("Keyboard Shortcuts", self)
        self.shortcuts_action.setShortcut(QKeySequence("?"))
        self.shortcuts_action.triggered.connect(self.show_shortcuts)

        self.about_action = QAction("About Floor Planner", self)
        self.about_action.triggered.connect(self.show_about)

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.open_pdf_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.duplicate_action)
        edit_menu.addAction(self.delete_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.rotate_left_action)
        edit_menu.addAction(self.rotate_right_action)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.select_action)
        view_menu.addAction(self.pan_action)
        view_menu.addSeparator()
        view_menu.addAction(self.fit_action)
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.shortcuts_action)
        help_menu.addAction(self.about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main toolbar", self)
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        toolbar.addAction(self.open_pdf_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.select_action)
        toolbar.addAction(self.pan_action)
        toolbar.addAction(self.calibrate_action)
        toolbar.addSeparator()
        toolbar.addAction(self.add_rectangle_action)
        toolbar.addAction(self.add_l_shape_action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        toolbar.addWidget(QLabel("Page "))
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 1)
        self.page_spin.setFixedWidth(62)
        self.page_spin.valueChanged.connect(self._page_spin_changed)
        toolbar.addWidget(self.page_spin)
        self.page_count_label = QLabel(" / 0  ")
        toolbar.addWidget(self.page_count_label)

        toolbar.addWidget(QLabel("Units "))
        self.unit_combo = QComboBox()
        for key, label in UNIT_LABELS.items():
            self.unit_combo.addItem(label, key)
        self.unit_combo.setCurrentIndex(
            self.unit_combo.findData(self.project.display_unit)
        )
        self.unit_combo.currentIndexChanged.connect(self._display_unit_changed)
        toolbar.addWidget(self.unit_combo)

    def _create_central_widget(self) -> None:
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setContentsMargins(14, 10, 14, 10)

        self.start_panel = QWidget()
        self.start_panel.setObjectName("startPanel")
        start_layout = QHBoxLayout(self.start_panel)
        start_layout.setContentsMargins(18, 14, 18, 14)
        start_message = QLabel(
            "Start by choosing the PDF floor plan on this computer. You can also drag it onto the gray area below."
        )
        start_message.setWordWrap(True)
        self.choose_pdf_button = QPushButton("Choose a PDF…")
        self.choose_pdf_button.setObjectName("primaryButton")
        self.choose_pdf_button.clicked.connect(self.open_pdf)
        self.choose_project_button = QPushButton("Open a saved project…")
        self.choose_project_button.clicked.connect(self.open_project)
        start_layout.addWidget(start_message, 1)
        start_layout.addWidget(self.choose_pdf_button)
        start_layout.addWidget(self.choose_project_button)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.banner)
        layout.addWidget(self.start_panel)
        layout.addWidget(self.view, 1)
        self.setCentralWidget(central)

    def _create_inspector(self) -> None:
        dock = QDockWidget("Furniture", self)
        dock.setObjectName("inspectorDock")
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)

        self.inspector_name = QLabel("Nothing selected")
        self.inspector_name.setWordWrap(True)
        self.inspector_name.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.inspector_details = QLabel(
            "Open a PDF, calibrate the scale, then add a rectangle or L-shape."
        )
        self.inspector_details.setWordWrap(True)
        self.inspector_details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.edit_button = QPushButton("Edit name and dimensions…")
        self.edit_button.clicked.connect(self.edit_selected)

        rotate_row = QHBoxLayout()
        self.rotate_left_button = QPushButton("↶ 15°")
        self.rotate_left_button.clicked.connect(lambda: self.rotate_selected(-15.0))
        self.rotate_right_button = QPushButton("↷ 15°")
        self.rotate_right_button.clicked.connect(lambda: self.rotate_selected(15.0))
        self.rotate_90_button = QPushButton("↷ 90°")
        self.rotate_90_button.clicked.connect(lambda: self.rotate_selected(90.0))
        rotate_row.addWidget(self.rotate_left_button)
        rotate_row.addWidget(self.rotate_right_button)
        rotate_row.addWidget(self.rotate_90_button)

        action_row = QHBoxLayout()
        self.duplicate_button = QPushButton("Duplicate")
        self.duplicate_button.clicked.connect(self.duplicate_selected)
        self.lock_button = QPushButton("Lock")
        self.lock_button.clicked.connect(self.toggle_selected_lock)
        action_row.addWidget(self.duplicate_button)
        action_row.addWidget(self.lock_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("deleteButton")
        self.delete_button.clicked.connect(self.delete_selected)

        layout.addWidget(self.inspector_name)
        layout.addWidget(self.inspector_details)
        layout.addSpacing(12)
        layout.addWidget(self.edit_button)
        layout.addLayout(rotate_row)
        layout.addLayout(action_row)
        layout.addWidget(self.delete_button)
        layout.addStretch(1)
        dock.setWidget(panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        self._inspector_controls = [
            self.edit_button,
            self.rotate_left_button,
            self.rotate_right_button,
            self.rotate_90_button,
            self.duplicate_button,
            self.lock_button,
            self.delete_button,
        ]

    def _create_status_bar(self) -> None:
        status = QStatusBar(self)
        self.setStatusBar(status)
        self.scale_label = QLabel("Scale: not set")
        self.zoom_label = QLabel("Zoom: 100%")
        status.addPermanentWidget(self.scale_label)
        status.addPermanentWidget(self.zoom_label)
        status.showMessage("Drop a PDF onto the window or choose Open PDF.")

    # ----- PDF and project lifecycle --------------------------------------

    def open_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open a floor plan",
            self.last_directory,
            "PDF floor plans (*.pdf *.PDF);;All files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.last_directory = str(Path(path).parent)
            self._load_pdf_path(path)

    def _load_pdf_path(self, path: str) -> None:
        if not self._maybe_save_changes():
            return
        project = Project(
            pdf_name=Path(path).name, display_unit=self.project.display_unit
        )
        self.statusBar().showMessage(f"Opening {Path(path).name}…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            document, rendered = self._prepare_document(path, 0)
        except Exception as exc:  # noqa: BLE001 - PDFium exposes backend-specific errors.
            QApplication.restoreOverrideCursor()
            self._show_error("Could not open PDF", self._friendly_pdf_error(exc))
            self.statusBar().showMessage("The PDF could not be opened.", 7000)
            return
        QApplication.restoreOverrideCursor()
        self._replace_document(document, path, project, rendered, None, None)
        self.statusBar().showMessage(
            "PDF opened. Draw a line to calibrate its scale.", 7000
        )

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open a Floor Planner project",
            self.last_directory,
            "Floor Planner projects (*.floorplan)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.last_directory = str(Path(path).parent)
            self._load_project_path(path)

    def _load_project_path(self, path: str) -> None:
        if not self._maybe_save_changes():
            return
        loaded: LoadedProject | None = None
        document: Any | None = None
        try:
            loaded = load_project_bundle(path)
            document, rendered = self._prepare_document(
                loaded.pdf_path, loaded.project.current_page
            )
            page_count = len(document)
            pages = set(loaded.project.calibrations)
            pages.update(item.page for item in loaded.project.furniture)
            if any(page >= page_count for page in pages):
                raise ProjectFileError(
                    "The project refers to a PDF page that does not exist."
                )
        except Exception as exc:  # noqa: BLE001 - validates both ZIP and PDF backends.
            if document is not None:
                document.close()
            if loaded is not None:
                loaded.close()
            self._show_error("Could not open project", str(exc))
            return
        self._replace_document(
            document,
            loaded.pdf_path,
            loaded.project,
            rendered,
            path,
            loaded,
        )
        self.statusBar().showMessage("Project opened.", 5000)

    def _open_dropped_files(self, paths: list[str]) -> None:
        if not paths:
            return
        path = paths[0]
        if path.lower().endswith(".floorplan"):
            self._load_project_path(path)
        else:
            self._load_pdf_path(path)

    def _prepare_document(
        self, path: str, page_index: int
    ) -> tuple[Any, tuple[QImage, float, float]]:
        document = pdfium.PdfDocument(path)
        try:
            if len(document) == 0:
                raise RuntimeError("The PDF does not contain any pages.")
            if page_index < 0 or page_index >= len(document):
                raise RuntimeError("The saved page does not exist in this PDF.")
            rendered = self._render_page_data(document, page_index)
            return document, rendered
        except Exception:
            document.close()
            raise

    def _render_page_data(
        self, document: Any, page_index: int
    ) -> tuple[QImage, float, float]:
        page = document[page_index]
        bitmap = None
        try:
            page_width, page_height = page.get_size()
            if (
                not math.isfinite(page_width)
                or not math.isfinite(page_height)
                or page_width <= 0
                or page_height <= 0
                or max(page_width, page_height) > MAX_PDF_PAGE_POINTS
            ):
                raise RuntimeError(
                    "The PDF page dimensions are outside the supported range."
                )
            render_scale = min(
                PDF_RENDER_SCALE,
                MAX_PDF_RENDER_EDGE / max(page_width, page_height),
                math.sqrt(MAX_PDF_RENDER_PIXELS / (page_width * page_height)),
            )
            bitmap = page.render(scale=render_scale)
            pil_image = bitmap.to_pil().convert("RGBA")
            width, height = pil_image.size
            raw = pil_image.tobytes("raw", "RGBA")
            image = QImage(
                raw, width, height, width * 4, QImage.Format.Format_RGBA8888
            ).copy()
            if image.isNull():
                raise RuntimeError("The PDF page could not be rendered.")
            return image, float(page_width), float(page_height)
        finally:
            if bitmap is not None:
                close_bitmap = getattr(bitmap, "close", None)
                if callable(close_bitmap):
                    close_bitmap()
            close_page = getattr(page, "close", None)
            if callable(close_page):
                close_page()

    def _replace_document(
        self,
        document: Any,
        pdf_path: str,
        project: Project,
        rendered: tuple[QImage, float, float],
        project_path: str | None,
        loaded_bundle: LoadedProject | None,
    ) -> None:
        self.view.set_mode("select")
        self._close_document_resources()
        self.scene.clear()
        self.background_item = None
        self.calibration_line_item = None
        self.calibration_label_item = None
        self.furniture_items = []

        self.pdf_document = document
        self.pdf_path = pdf_path
        self.project = project
        self.project_path = project_path
        self.loaded_bundle = loaded_bundle

        self._changing_page = True
        self.page_spin.setRange(1, len(document))
        self.page_spin.setValue(project.current_page + 1)
        self.page_count_label.setText(f" / {len(document)}  ")
        self._changing_page = False
        self.unit_combo.blockSignals(True)
        self.unit_combo.setCurrentIndex(self.unit_combo.findData(project.display_unit))
        self.unit_combo.blockSignals(False)

        self._show_rendered_page(rendered)
        self._rebuild_furniture_items()
        self._draw_calibration_reference()
        self.view.fit_page()
        self._reset_history()
        self._update_ui_state()
        self._update_inspector()

    def _close_document_resources(self) -> None:
        if self.pdf_document is not None:
            try:
                self.pdf_document.close()
            except Exception:  # noqa: BLE001,S110 - best-effort native handle cleanup.
                pass
        self.pdf_document = None
        if self.loaded_bundle is not None:
            self.loaded_bundle.close()
        self.loaded_bundle = None

    def _show_rendered_page(self, rendered: tuple[QImage, float, float]) -> None:
        image, page_width, page_height = rendered
        pixmap = QPixmap.fromImage(image)
        if self.background_item is None:
            self.background_item = QGraphicsPixmapItem()
            self.background_item.setZValue(-100.0)
            self.scene.addItem(self.background_item)
        self.background_item.setPixmap(pixmap)
        self.background_item.setPos(0.0, 0.0)
        self.background_item.setTransform(
            QTransform.fromScale(
                page_width / pixmap.width(), page_height / pixmap.height()
            )
        )
        self.scene.setSceneRect(QRectF(0.0, 0.0, page_width, page_height))

    def _page_spin_changed(self, value: int) -> None:
        if self._changing_page or self.pdf_document is None:
            return
        new_page = value - 1
        old_page = self.project.current_page
        if new_page == old_page:
            return
        try:
            rendered = self._render_page_data(self.pdf_document, new_page)
        except Exception as exc:  # noqa: BLE001 - PDFium exposes backend-specific errors.
            self._show_error("Could not show page", self._friendly_pdf_error(exc))
            self._changing_page = True
            self.page_spin.setValue(old_page + 1)
            self._changing_page = False
            return
        self.project.current_page = new_page
        self.scene.clearSelection()
        self._show_rendered_page(rendered)
        self._update_page_item_visibility()
        self._draw_calibration_reference()
        self.view.fit_page()
        self._update_ui_state()
        self._update_window_title()

    # ----- Scale calibration ---------------------------------------------

    def begin_calibration(self) -> None:
        if self.pdf_document is None:
            QMessageBox.information(
                self,
                "Open a PDF first",
                "Choose a PDF floor plan before setting its scale.",
            )
            return
        self.view.set_mode("calibrate")
        self.banner.setText(
            "Click and drag between the endpoints of a known measurement. Hold Shift to keep the line straight."
        )
        self.banner.setStyleSheet(
            "background: #FFF3CD; color: #7A4D00; font-weight: 600;"
        )
        self.statusBar().showMessage(
            "Draw a calibration line on a known wall or printed dimension."
        )

    def _finish_calibration(self, start: QPointF, end: QPointF) -> None:
        dialog = CalibrationDialog(self.project.display_unit, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._update_ui_state()
            return
        try:
            calibration = Calibration(
                start.x(), start.y(), end.x(), end.y(), dialog.real_inches()
            )
            calibration.validate()
        except ValidationError as exc:
            self._show_error("Could not set scale", str(exc))
            return
        self.project.calibrations[self.project.current_page] = calibration
        self._rebuild_furniture_items()
        self._draw_calibration_reference()
        self._commit_history()
        self._update_ui_state()
        self.statusBar().showMessage(
            "Scale calibrated. Furniture will now be drawn true to size.", 7000
        )

    def _draw_calibration_reference(self) -> None:
        for item in (self.calibration_line_item, self.calibration_label_item):
            if item is not None and item.scene() is self.scene:
                self.scene.removeItem(item)
        self.calibration_line_item = None
        self.calibration_label_item = None

        calibration = self.project.calibrations.get(self.project.current_page)
        if calibration is None:
            return
        line = QGraphicsLineItem(
            calibration.start_x,
            calibration.start_y,
            calibration.end_x,
            calibration.end_y,
        )
        pen = QPen(QColor("#00897B"), 2.0, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        line.setPen(pen)
        line.setZValue(5.0)
        line.setToolTip("Scale calibration reference")
        self.scene.addItem(line)
        self.calibration_line_item = line

        label = QGraphicsSimpleTextItem(
            format_measurement(calibration.real_inches, self.project.display_unit)
        )
        font = QFont()
        font.setPointSizeF(8.0)
        font.setBold(True)
        label.setFont(font)
        label.setBrush(QColor("#00695C"))
        midpoint = QPointF(
            (calibration.start_x + calibration.end_x) / 2.0,
            (calibration.start_y + calibration.end_y) / 2.0,
        )
        label.setPos(midpoint + QPointF(4.0, 4.0))
        label.setZValue(5.0)
        self.scene.addItem(label)
        self.calibration_label_item = label

    # ----- Furniture operations -----------------------------------------

    def add_furniture(self, kind: str) -> None:
        if self.pdf_document is None:
            QMessageBox.information(
                self,
                "Open a PDF first",
                "Choose a PDF floor plan before adding furniture.",
            )
            return
        calibration = self.project.calibrations.get(self.project.current_page)
        if calibration is None:
            QMessageBox.information(
                self,
                "Set the scale first",
                "Calibrate a known distance so the furniture is drawn at the correct size.",
            )
            self.begin_calibration()
            return
        dialog = FurnitureDialog(kind, self.project.display_unit, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, shape, color = dialog.values()
        center = self.view.mapToScene(self.view.viewport().rect().center())
        page_rect = self.scene.sceneRect()
        if not page_rect.contains(center):
            center = page_rect.center()
        furniture = Furniture(
            name=name,
            shape=shape,
            page=self.project.current_page,
            x=center.x(),
            y=center.y(),
            color=color,
        )
        self.project.furniture.append(furniture)
        item = self._add_furniture_item(furniture)
        self.scene.clearSelection()
        item.setSelected(True)
        self._commit_history()
        self._update_ui_state()
        self.statusBar().showMessage(
            "Furniture added. Drag it into place; use [ and ] to rotate.", 6000
        )

    def _add_furniture_item(self, furniture: Furniture) -> FurnitureItem:
        calibration = self.project.calibrations.get(furniture.page)
        points_per_inch = (
            calibration.points_per_inch if calibration is not None else 1.0
        )
        item = FurnitureItem(furniture, points_per_inch, self.project.display_unit)
        item.setVisible(furniture.page == self.project.current_page)
        item.changed.connect(self._item_changed)
        item.edit_requested.connect(lambda selected: self.edit_item(selected))
        item.duplicate_requested.connect(lambda selected: self.duplicate_item(selected))
        item.delete_requested.connect(lambda selected: self.delete_item(selected))
        self.scene.addItem(item)
        self.furniture_items.append(item)
        return item

    def _rebuild_furniture_items(self) -> None:
        for item in self.furniture_items:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
        self.furniture_items = []
        for furniture in self.project.furniture:
            self._add_furniture_item(furniture)
        self._update_inspector()

    def _update_page_item_visibility(self) -> None:
        for item in self.furniture_items:
            item.setVisible(item.furniture.page == self.project.current_page)

    def _selected_items(self) -> list[FurnitureItem]:
        return [
            item
            for item in self.scene.selectedItems()
            if isinstance(item, FurnitureItem)
        ]

    def _selected_item(self) -> FurnitureItem | None:
        items = self._selected_items()
        return items[0] if len(items) == 1 else None

    def _item_changed(self, item: FurnitureItem) -> None:
        # QGraphicsScene moves every selected item during a group drag, but only
        # the item under the mouse receives mouseReleaseEvent. Synchronize the
        # entire graphics layer so every moved piece is persisted and undoable.
        for graphics_item in self.furniture_items:
            graphics_item.furniture.x = graphics_item.pos().x()
            graphics_item.furniture.y = graphics_item.pos().y()
            graphics_item.furniture.rotation = graphics_item.rotation() % 360.0
        self._commit_history()
        self._update_inspector()

    def edit_selected(self) -> None:
        item = self._selected_item()
        if item is not None:
            self.edit_item(item)

    def edit_item(self, item: FurnitureItem) -> None:
        furniture = item.furniture
        dialog = FurnitureDialog(
            furniture.shape.kind,
            self.project.display_unit,
            existing=furniture,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, shape, color = dialog.values()
        furniture.name = name
        furniture.shape = shape
        furniture.color = color
        item.refresh_from_model()
        self._commit_history()
        self._update_inspector()

    def duplicate_selected(self) -> None:
        selected = self._selected_items()
        if not selected:
            return
        new_items: list[FurnitureItem] = []
        for item in selected:
            new_items.append(self.duplicate_item(item, commit=False))
        self.scene.clearSelection()
        for item in new_items:
            item.setSelected(True)
        self._commit_history()

    def duplicate_item(self, item: FurnitureItem, commit: bool = True) -> FurnitureItem:
        source = item.furniture
        calibration = self.project.calibrations[source.page]
        offset = calibration.points_per_inch * 6.0
        duplicate = Furniture.from_dict(source.to_dict())
        duplicate.item_id = str(uuid4())
        duplicate.name = f"{source.name} copy"
        duplicate.x += offset
        duplicate.y += offset
        duplicate.locked = False
        self.project.furniture.append(duplicate)
        new_item = self._add_furniture_item(duplicate)
        if commit:
            self.scene.clearSelection()
            new_item.setSelected(True)
            self._commit_history()
        return new_item

    def delete_selected(self) -> None:
        selected = self._selected_items()
        if not selected:
            return
        ids = {item.furniture.item_id for item in selected}
        self.project.furniture = [
            furniture
            for furniture in self.project.furniture
            if furniture.item_id not in ids
        ]
        for item in selected:
            if item in self.furniture_items:
                self.furniture_items.remove(item)
            self.scene.removeItem(item)
        self._commit_history()
        self._update_inspector()
        self.statusBar().showMessage(
            "Furniture deleted. Use Undo to bring it back.", 5000
        )

    def delete_item(self, item: FurnitureItem) -> None:
        self.scene.clearSelection()
        item.setSelected(True)
        self.delete_selected()

    def rotate_selected(self, degrees: float) -> None:
        selected = self._selected_items()
        if not selected:
            return
        for item in selected:
            item.furniture.rotation = (item.furniture.rotation + degrees) % 360.0
            item.setRotation(item.furniture.rotation)
        self._commit_history()
        self._update_inspector()

    def nudge_selected(self, dx: float, dy: float) -> None:
        selected = [
            item for item in self._selected_items() if not item.furniture.locked
        ]
        if not selected:
            return
        calibration = self.project.calibrations.get(self.project.current_page)
        if calibration is None:
            return
        magnitude = max(abs(dx), abs(dy))
        if self.project.display_unit in {"cm", "m"}:
            real_inches = to_inches(10.0 if magnitude > 1.0 else 1.0, "cm")
        else:
            real_inches = 6.0 if magnitude > 1.0 else 1.0
        page_step = real_inches * calibration.points_per_inch
        x_direction = 0.0 if dx == 0 else math.copysign(1.0, dx)
        y_direction = 0.0 if dy == 0 else math.copysign(1.0, dy)
        for item in selected:
            item.moveBy(x_direction * page_step, y_direction * page_step)
            item.furniture.x = item.pos().x()
            item.furniture.y = item.pos().y()
        self._commit_history()

    def toggle_selected_lock(self) -> None:
        selected = self._selected_items()
        if not selected:
            return
        lock = not all(item.furniture.locked for item in selected)
        for item in selected:
            item.furniture.locked = lock
            item.refresh_from_model()
        self._commit_history()
        self._update_inspector()

    # ----- History --------------------------------------------------------

    def _snapshot(self) -> dict[str, Any]:
        return {
            "display_unit": self.project.display_unit,
            "calibrations": {
                str(page): calibration.to_dict()
                for page, calibration in sorted(self.project.calibrations.items())
            },
            "furniture": [item.to_dict() for item in self.project.furniture],
        }

    def _reset_history(self) -> None:
        self._history_current = copy.deepcopy(self._snapshot())
        self._history_past = []
        self._history_future = []
        self._saved_snapshot = copy.deepcopy(self._history_current)
        self._saved_current_page = self.project.current_page
        self._update_history_actions()

    def _commit_history(self) -> None:
        new_snapshot = self._snapshot()
        if new_snapshot == self._history_current:
            return
        self._history_past.append(copy.deepcopy(self._history_current))
        if len(self._history_past) > 100:
            self._history_past.pop(0)
        self._history_current = copy.deepcopy(new_snapshot)
        self._history_future = []
        self._update_history_actions()

    def undo(self) -> None:
        if not self._history_past:
            return
        target = self._history_past.pop()
        self._history_future.append(copy.deepcopy(self._history_current))
        self._history_current = copy.deepcopy(target)
        self._apply_snapshot(target)
        self._update_history_actions()

    def redo(self) -> None:
        if not self._history_future:
            return
        target = self._history_future.pop()
        self._history_past.append(copy.deepcopy(self._history_current))
        self._history_current = copy.deepcopy(target)
        self._apply_snapshot(target)
        self._update_history_actions()

    def _apply_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.project.display_unit = str(snapshot["display_unit"])
        self.project.calibrations = {
            int(page): Calibration.from_dict(value)
            for page, value in snapshot["calibrations"].items()
        }
        self.project.furniture = [
            Furniture.from_dict(value) for value in snapshot["furniture"]
        ]
        self.unit_combo.blockSignals(True)
        self.unit_combo.setCurrentIndex(
            self.unit_combo.findData(self.project.display_unit)
        )
        self.unit_combo.blockSignals(False)
        self.scene.clearSelection()
        self._rebuild_furniture_items()
        self._draw_calibration_reference()
        self._update_ui_state()

    def _update_history_actions(self) -> None:
        self.undo_action.setEnabled(bool(self._history_past))
        self.redo_action.setEnabled(bool(self._history_future))
        self._update_window_title()

    @property
    def is_dirty(self) -> bool:
        return (
            self._history_current != self._saved_snapshot
            or self.project.current_page != self._saved_current_page
        )

    # ----- Save and export ------------------------------------------------

    def save_project(self, save_as: bool = False) -> bool:
        if self.pdf_document is None or self.pdf_path is None:
            QMessageBox.information(
                self, "Nothing to save", "Open a PDF floor plan first."
            )
            return False
        path = None if save_as else self.project_path
        if not path:
            suggested = str(
                Path(self.project_path)
                if self.project_path
                else Path(self.pdf_path).with_suffix(".floorplan")
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Floor Planner project",
                suggested,
                "Floor Planner projects (*.floorplan)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if not path:
                return False
            if not path.lower().endswith(".floorplan"):
                path += ".floorplan"
        self.project.current_page = self.page_spin.value() - 1
        try:
            save_project_bundle(path, self.project, self.pdf_path)
        except (ProjectFileError, ValidationError, OSError) as exc:
            self._show_error("Could not save project", str(exc))
            return False
        self.project_path = path
        self._saved_snapshot = copy.deepcopy(self._history_current)
        self._saved_current_page = self.project.current_page
        self._update_window_title()
        self.statusBar().showMessage(f"Saved {Path(path).name}", 5000)
        return True

    def export_png(self) -> None:
        if self.pdf_document is None:
            QMessageBox.information(
                self, "Nothing to export", "Open a PDF floor plan first."
            )
            return
        output_directory = (
            Path(self.project_path).parent
            if self.project_path
            else Path(self.pdf_path).parent
        )
        suggested = str(
            output_directory
            / f"{Path(self.project.pdf_name).stem}-layout-page-{self.project.current_page + 1}.png"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export furniture layout",
            suggested,
            "PNG images (*.png)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"

        rect = self.scene.sceneRect()
        scale = min(
            PDF_RENDER_SCALE,
            MAX_EXPORT_EDGE / max(rect.width(), rect.height()),
            math.sqrt(MAX_EXPORT_PIXELS / (rect.width() * rect.height())),
        )
        width = max(1, math.ceil(rect.width() * scale))
        height = max(1, math.ceil(rect.height() * scale))
        output = QImage(QSize(width, height), QImage.Format.Format_ARGB32)
        output.fill(QColor("white"))

        selected = self._selected_items()
        self.scene.clearSelection()
        calibration_visibility = []
        for item in (self.calibration_line_item, self.calibration_label_item):
            if item is not None:
                calibration_visibility.append((item, item.isVisible()))
                item.setVisible(False)
        painter = QPainter(output)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.scene.render(painter, QRectF(0.0, 0.0, width, height), rect)
        painter.end()
        for item, was_visible in calibration_visibility:
            item.setVisible(was_visible)
        for item in selected:
            item.setSelected(True)

        if not output.save(path, "PNG"):
            self._show_error(
                "Could not export image", "The PNG file could not be written."
            )
            return
        self.statusBar().showMessage(f"Exported {Path(path).name}", 6000)

    def _maybe_save_changes(self) -> bool:
        if not self.is_dirty:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Save your changes?")
        box.setText("This floor plan has unsaved changes.")
        box.setInformativeText(
            "Save them before opening another file or closing the app?"
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        result = box.exec()
        if result == QMessageBox.StandardButton.Save:
            return self.save_project()
        return result == QMessageBox.StandardButton.Discard

    # ----- UI state and helpers ------------------------------------------

    def _display_unit_changed(self) -> None:
        unit = self.unit_combo.currentData()
        if unit is None or unit == self.project.display_unit:
            return
        self.project.display_unit = str(unit)
        if self.pdf_document is None:
            # There is no saveable project yet, so this preference must not
            # create an unsavable dirty state.
            self._reset_history()
            return
        for item in self.furniture_items:
            item.set_display_unit(self.project.display_unit)
        self._draw_calibration_reference()
        self._commit_history()
        self._update_inspector()
        self._update_ui_state()

    def _update_ui_state(self) -> None:
        has_document = self.pdf_document is not None
        has_scale = self.project.current_page in self.project.calibrations
        self.start_panel.setVisible(not has_document)
        self.page_spin.setEnabled(
            has_document and len(self.pdf_document) > 1 if has_document else False
        )
        self.unit_combo.setEnabled(has_document)
        self.save_action.setEnabled(has_document)
        self.save_as_action.setEnabled(has_document)
        self.export_action.setEnabled(has_document)
        # Keep the main workflow buttons clickable at startup. Their handlers
        # explain the missing prerequisite instead of appearing broken.
        self.calibrate_action.setEnabled(True)
        self.add_rectangle_action.setEnabled(True)
        self.add_l_shape_action.setEnabled(True)
        self.fit_action.setEnabled(has_document)

        if not has_document:
            self.banner.setText(
                "Step 1 of 3 — Open or drop a PDF floor plan here. Everything stays on this computer."
            )
            self.banner.setStyleSheet(
                "background: #E8F1FF; color: #174EA6; font-weight: 600;"
            )
            self.scale_label.setText("Scale: not set")
        elif not has_scale:
            self.banner.setText(
                "Step 2 of 3 — Calibrate the scale: draw over a known wall length or printed measurement."
            )
            self.banner.setStyleSheet(
                "background: #FFF3CD; color: #7A4D00; font-weight: 600;"
            )
            self.scale_label.setText("Scale: not calibrated on this page")
        else:
            calibration = self.project.calibrations[self.project.current_page]
            self.banner.setText(
                "Step 3 of 3 — Add furniture, then drag it into place. Double-click a piece to edit it."
            )
            self.banner.setStyleSheet(
                "background: #DFF6E7; color: #176B37; font-weight: 600;"
            )
            self.scale_label.setText(
                f"Scale: {format_measurement(calibration.real_inches, self.project.display_unit)} reference"
            )
        self._update_history_actions()
        self._update_inspector()

    def _update_inspector(self) -> None:
        selected = self._selected_items()
        enabled = bool(selected)
        for control in self._inspector_controls:
            control.setEnabled(enabled)
        self.duplicate_action.setEnabled(enabled)
        self.delete_action.setEnabled(enabled)
        self.rotate_left_action.setEnabled(enabled)
        self.rotate_right_action.setEnabled(enabled)
        if not selected:
            if self.pdf_document is None:
                self.inspector_name.setText("Get started")
                self.inspector_details.setText(
                    "Choose a PDF floor plan, then calibrate one known distance before adding furniture."
                )
            elif self.project.current_page not in self.project.calibrations:
                self.inspector_name.setText("Set the scale")
                self.inspector_details.setText(
                    "Click Calibrate Scale and draw over a known wall length or printed dimension."
                )
            else:
                self.inspector_name.setText("Nothing selected")
                self.inspector_details.setText(
                    "Click a furniture piece to see its size and editing controls. "
                    "Double-click a piece to change its exact dimensions."
                )
            self.lock_button.setText("Lock")
            return
        if len(selected) > 1:
            self.inspector_name.setText(f"{len(selected)} pieces selected")
            self.inspector_details.setText(
                "Move, rotate, duplicate, lock, or delete them together."
            )
            self.edit_button.setEnabled(False)
            self.lock_button.setText(
                "Unlock" if all(item.furniture.locked for item in selected) else "Lock"
            )
            return
        item = selected[0]
        furniture = item.furniture
        shape = furniture.shape
        shape_name = "L-shape" if shape.kind == "l_shape" else "Rectangle"
        locked = "\nLocked" if furniture.locked else ""
        self.inspector_name.setText(furniture.name)
        self.inspector_details.setText(
            f"{shape_name}\n"
            f"{format_measurement(shape.width_in, self.project.display_unit)} × "
            f"{format_measurement(shape.depth_in, self.project.display_unit)}\n"
            f"Rotation: {furniture.rotation:g}°{locked}"
        )
        self.edit_button.setEnabled(True)
        self.lock_button.setText("Unlock" if furniture.locked else "Lock")

    def _sync_mode_actions(self, mode: str) -> None:
        self.select_action.setChecked(mode == "select")
        self.pan_action.setChecked(mode == "pan")

    def _update_zoom_label(self, percent: int) -> None:
        self.zoom_label.setText(f"Zoom: {percent}%")

    def _update_window_title(self) -> None:
        name = (
            Path(self.project_path).name if self.project_path else self.project.pdf_name
        )
        if self.pdf_document is None:
            name = "Untitled"
        marker = " *" if self.is_dirty else ""
        self.setWindowTitle(f"{name}{marker} — Floor Planner")

    def _friendly_pdf_error(self, exc: Exception) -> str:
        message = str(exc).strip()
        if not message:
            message = exc.__class__.__name__
        return (
            f"{message}\n\nThe file may be damaged, password-protected, or use a PDF feature "
            "that could not be rendered."
        )

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def show_shortcuts(self) -> None:
        QMessageBox.information(
            self,
            "Keyboard shortcuts",
            "Open PDF: Ctrl+O\n"
            "Save project: Ctrl+S\n"
            "Export PNG: Ctrl+E\n\n"
            "Select: V    Pan: H    Calibrate: K\n"
            "Rectangle: R    L-shape: L\n"
            "Rotate: [ and ]    Duplicate: Ctrl+D\n"
            "Delete: Delete/Backspace\n"
            "Nudge: Arrow keys (hold Shift for a larger step)\n"
            "Fit page: Ctrl+0    Cancel: Esc\n\n"
            "Mouse wheel zooms. Middle-drag or Space-drag pans.",
        )

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Floor Planner",
            "<h3>Floor Planner 0.1</h3>"
            "<p>Place true-to-size furniture over a PDF floor plan.</p>"
            "<p>Your PDFs and projects remain local on your computer.</p>"
            "<p>Built with the open-source Qt/PySide6, PDFium, and Pillow libraries. "
            "Release packages include their license notices and corresponding-source information.</p>",
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._maybe_save_changes():
            self._close_document_resources()
            event.accept()
        else:
            event.ignore()


APP_STYLESHEET = """
QMainWindow, QDialog { background: #F7F8FA; }
QToolBar { background: #FFFFFF; border-bottom: 1px solid #D0D5DD; spacing: 5px; padding: 5px; }
QToolButton { padding: 6px 8px; border-radius: 5px; }
QToolButton:hover { background: #EEF2F6; }
QToolButton:checked { background: #DCE9FF; color: #174EA6; }
QPushButton { padding: 7px 10px; border: 1px solid #B8C1CC; border-radius: 5px; background: white; }
QPushButton:hover { background: #F0F4F8; }
QPushButton:disabled { color: #98A2B3; background: #F2F4F7; }
QWidget#startPanel { background: #FFFFFF; border-bottom: 1px solid #D0D5DD; }
QPushButton#primaryButton { background: #1769E0; color: white; border-color: #1769E0; font-weight: 600; }
QPushButton#primaryButton:hover { background: #1257BC; }
QPushButton#deleteButton { color: #B42318; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox { padding: 5px; border: 1px solid #B8C1CC; border-radius: 4px; background: white; }
QDockWidget { font-weight: 600; }
QStatusBar { background: #FFFFFF; border-top: 1px solid #D0D5DD; }
"""


def run() -> int:
    smoke_test = "--smoke-test" in sys.argv
    qt_arguments = [argument for argument in sys.argv if argument != "--smoke-test"]
    app = QApplication.instance() or QApplication(qt_arguments)
    app.setApplicationName("Floor Planner")
    app.setOrganizationName("Floor Planner")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    def show_unhandled_error(exc_type, exc_value, exc_traceback) -> None:  # type: ignore[no-untyped-def]
        details = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        if sys.__stderr__ is not None:
            sys.__stderr__.write(details)
        QMessageBox.critical(
            None,
            "Floor Planner encountered an error",
            f"{exc_type.__name__}: {exc_value}\n\n"
            "Please copy this message when reporting the problem. The app will remain open.",
        )

    sys.excepthook = show_unhandled_error
    window = MainWindow()
    window.show()
    if smoke_test:

        def run_smoke_test() -> None:
            try:
                from PIL import Image

                if not window.choose_pdf_button.isEnabled():
                    raise RuntimeError("The start-screen PDF button is disabled.")
                with tempfile.TemporaryDirectory() as directory:
                    pdf_path = Path(directory) / "smoke-test.pdf"
                    Image.new("RGB", (320, 240), "white").save(
                        pdf_path, "PDF", resolution=72.0
                    )
                    document, rendered = window._prepare_document(str(pdf_path), 0)
                    window._replace_document(
                        document,
                        str(pdf_path),
                        Project(pdf_name=pdf_path.name),
                        rendered,
                        None,
                        None,
                    )
                    if (
                        window.pdf_document is None
                        or not window.calibrate_action.isEnabled()
                    ):
                        raise RuntimeError(
                            "A PDF loaded but the workflow did not activate."
                        )
                    window._close_document_resources()
            except Exception:  # noqa: BLE001 - smoke test must convert every failure to an exit code.
                if sys.__stderr__ is not None:
                    traceback.print_exc(file=sys.__stderr__)
                app.exit(1)
                return
            app.exit(0)

        QTimer.singleShot(0, run_smoke_test)
    return app.exec()
