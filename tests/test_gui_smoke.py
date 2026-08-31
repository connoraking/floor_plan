import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import pypdfium2  # noqa: F401
    from PIL import Image
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

    GUI_DEPENDENCIES_AVAILABLE = True
except ImportError:
    GUI_DEPENDENCIES_AVAILABLE = False

if GUI_DEPENDENCIES_AVAILABLE:
    # Keep application imports outside the dependency probe. A broken internal
    # import must fail CI instead of being mistaken for an optional-dependency skip.
    from floor_planner.core import Calibration, Furniture, Project, ShapeSpec
    from floor_planner.main_window import MainWindow
    from floor_planner.project_io import save_project_bundle


@unittest.skipUnless(
    GUI_DEPENDENCIES_AVAILABLE, "Qt/PDF dependencies are not installed"
)
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_start_screen_buttons_open_a_pdf_and_never_look_inert(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "clickable plan.pdf"
            Image.new("RGB", (640, 480), "white").save(pdf_path, "PDF", resolution=72.0)

            window = MainWindow()
            window.show()
            self.app.processEvents()
            self.assertTrue(window.start_panel.isVisible())
            self.assertTrue(window.open_pdf_action.isEnabled())
            self.assertTrue(window.calibrate_action.isEnabled())
            self.assertTrue(window.add_rectangle_action.isEnabled())
            self.assertTrue(window.add_l_shape_action.isEnabled())

            with patch(
                "floor_planner.main_window.QFileDialog.getOpenFileName",
                return_value=(str(pdf_path), "PDF floor plans (*.pdf)"),
            ) as picker:
                QTest.mouseClick(window.choose_pdf_button, Qt.MouseButton.LeftButton)
                self.app.processEvents()

            self.assertEqual(window.pdf_path, str(pdf_path))
            self.assertFalse(window.start_panel.isVisible())
            self.assertTrue(window.calibrate_action.isEnabled())
            self.assertTrue(window.add_rectangle_action.isEnabled())
            window.calibrate_action.trigger()
            self.assertEqual(window.view.mode, "calibrate")
            window.view.set_mode("select")

            window.project.calibrations[0] = Calibration(20, 20, 220, 20, 120)
            window._update_ui_state()
            with patch("floor_planner.main_window.FurnitureDialog") as dialog_type:
                dialog = dialog_type.return_value
                dialog.exec.return_value = QDialog.DialogCode.Accepted
                dialog.values.return_value = (
                    "Test sofa",
                    ShapeSpec("rectangle", 84, 36),
                    "#2F80ED",
                )
                window.add_rectangle_action.trigger()
            self.assertEqual(len(window.project.furniture), 1)
            self.assertEqual(window.project.furniture[0].name, "Test sofa")
            self.assertEqual(
                picker.call_args.kwargs["options"],
                QFileDialog.Option.DontUseNativeDialog,
            )

            window._close_document_resources()
            window.deleteLater()

    def test_startup_workflow_actions_explain_their_prerequisites(self) -> None:
        window = MainWindow()
        with patch("floor_planner.main_window.QMessageBox.information") as message:
            window.calibrate_action.trigger()
            window.add_rectangle_action.trigger()
            window.add_l_shape_action.trigger()
        self.assertEqual(message.call_count, 3)
        self.assertTrue(
            all(call.args[1] == "Open a PDF first" for call in message.call_args_list)
        )
        window.deleteLater()

    def test_pdf_coordinates_and_furniture_scale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "known size.pdf"
            Image.new("RGB", (800, 600), "white").save(pdf_path, "PDF", resolution=72.0)

            window = MainWindow()
            window.show()
            self.app.processEvents()
            self.assertFalse(window.unit_combo.isEnabled())
            window.unit_combo.setCurrentIndex(window.unit_combo.findData("cm"))
            self.assertFalse(window.is_dirty)
            document, rendered = window._prepare_document(str(pdf_path), 0)
            project = Project(
                pdf_name=pdf_path.name,
                calibrations={0: Calibration(100, 100, 500, 100, 120)},
                furniture=[
                    Furniture(
                        "84-inch sofa",
                        ShapeSpec("rectangle", 84, 36),
                        page=0,
                        x=300,
                        y=250,
                    ),
                    Furniture(
                        "Side table",
                        ShapeSpec("rectangle", 24, 24),
                        page=0,
                        x=500,
                        y=250,
                    ),
                ],
            )
            window._replace_document(
                document, str(pdf_path), project, rendered, None, None
            )

            self.assertAlmostEqual(window.scene.sceneRect().width(), 800.0)
            # 400 PDF points calibrated to 120 inches = 3.333 points/inch.
            # An 84-inch sofa must therefore occupy exactly 280 PDF points.
            self.assertAlmostEqual(
                window.furniture_items[0].shape().boundingRect().width(), 280.0
            )

            # A group drag is delivered to one graphics item by Qt. The handler
            # must still synchronize and persist every selected item's new position.
            first, second = window.furniture_items
            first.setPos(310, 260)
            second.setPos(515, 265)
            window._item_changed(first)
            self.assertEqual(
                (project.furniture[0].x, project.furniture[0].y), (310, 260)
            )
            self.assertEqual(
                (project.furniture[1].x, project.furniture[1].y), (515, 265)
            )
            window.undo()
            self.assertEqual(
                (window.project.furniture[0].x, window.project.furniture[0].y),
                (300, 250),
            )
            self.assertEqual(
                (window.project.furniture[1].x, window.project.furniture[1].y),
                (500, 250),
            )

            export_path = Path(directory) / "layout.png"
            with patch(
                "floor_planner.main_window.QFileDialog.getSaveFileName",
                return_value=(str(export_path), "PNG images (*.png)"),
            ):
                window.export_png()
            self.assertTrue(export_path.is_file())
            with Image.open(export_path) as exported:
                self.assertEqual(exported.size, (1600, 1200))

            window._close_document_resources()
            window.deleteLater()

    def test_page_navigation_is_saved_and_document_open_resets_tool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "two pages.pdf"
            first = Image.new("RGB", (500, 400), "white")
            second = Image.new("RGB", (500, 400), "gray")
            first.save(
                pdf_path,
                "PDF",
                resolution=72.0,
                save_all=True,
                append_images=[second],
            )

            window = MainWindow()
            window.show()
            self.app.processEvents()
            document, rendered = window._prepare_document(str(pdf_path), 0)
            window._replace_document(
                document,
                str(pdf_path),
                Project(pdf_name=pdf_path.name),
                rendered,
                None,
                None,
            )
            self.assertFalse(window.is_dirty)
            window.page_spin.setValue(2)
            self.assertTrue(window.is_dirty)
            window.page_spin.setValue(1)
            self.assertFalse(window.is_dirty)

            window.view.set_mode("calibrate")
            replacement, replacement_render = window._prepare_document(str(pdf_path), 0)
            window._replace_document(
                replacement,
                str(pdf_path),
                Project(pdf_name=pdf_path.name),
                replacement_render,
                None,
                None,
            )
            self.assertEqual(window.view.mode, "select")

            window._close_document_resources()
            window.deleteLater()

    def test_oversized_pdf_page_is_rejected_before_rendering(self) -> None:
        class OversizedPage:
            render_called = False

            def get_size(self):  # type: ignore[no-untyped-def]
                return 2_000_000.0, 2_000_000.0

            def render(self, scale):  # type: ignore[no-untyped-def]
                del scale
                self.render_called = True
                raise AssertionError("render must not be called")

            def close(self) -> None:
                pass

        class FakeDocument:
            page = OversizedPage()

            def __getitem__(self, index):  # type: ignore[no-untyped-def]
                self.assert_index = index
                return self.page

        window = MainWindow()
        document = FakeDocument()
        with self.assertRaisesRegex(RuntimeError, "dimensions"):
            window._render_page_data(document, 0)
        self.assertFalse(document.page.render_called)
        window.deleteLater()

    def test_portable_project_opens_with_embedded_pdf_and_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_path = root / "family room.pdf"
            Image.new("RGB", (640, 480), "white").save(pdf_path, "PDF", resolution=72.0)
            project = Project(
                pdf_name=pdf_path.name,
                calibrations={0: Calibration(50, 50, 350, 50, 120)},
                furniture=[
                    Furniture(
                        "Couch",
                        ShapeSpec("rectangle", 84, 36),
                        page=0,
                        x=240,
                        y=200,
                    )
                ],
            )
            bundle_path = root / "family room.floorplan"
            save_project_bundle(str(bundle_path), project, str(pdf_path))

            window = MainWindow()
            window.show()
            self.app.processEvents()
            window._load_project_path(str(bundle_path))

            self.assertIsNotNone(window.pdf_document)
            self.assertEqual(window.project.furniture[0].name, "Couch")
            self.assertEqual(len(window.furniture_items), 1)
            extracted_pdf = Path(window.pdf_path)
            self.assertTrue(extracted_pdf.is_file())
            window._close_document_resources()
            self.assertFalse(extracted_pdf.exists())
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
