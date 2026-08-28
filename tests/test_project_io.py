import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from floor_planner.core import Calibration, Project
from floor_planner.project_io import (
    MAX_PROJECT_JSON_BYTES,
    PROJECT_JSON_NAME,
    PROJECT_PDF_NAME,
    ProjectFileError,
    load_project_bundle,
    save_project_bundle,
)


class ProjectBundleTests(unittest.TestCase):
    def test_bundle_keeps_project_and_pdf_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source plan.pdf"
            source_bytes = b"%PDF-1.4\n% test fixture\n"
            source.write_bytes(source_bytes)
            os.utime(source, (0, 0))
            destination = root / "family room.floorplan"
            project = Project(
                pdf_name=source.name,
                display_unit="ft",
                calibrations={0: Calibration(0, 0, 100, 0, 120)},
            )

            save_project_bundle(str(destination), project, str(source))
            loaded = load_project_bundle(str(destination))
            try:
                self.assertEqual(loaded.project.to_dict(), project.to_dict())
                self.assertEqual(Path(loaded.pdf_path).read_bytes(), source_bytes)
            finally:
                loaded.close()

    @unittest.skipIf(os.name == "nt", "POSIX permission behavior")
    def test_overwrite_preserves_existing_file_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            destination = root / "shared.floorplan"
            destination.write_bytes(b"old")
            destination.chmod(0o664)

            save_project_bundle(str(destination), Project(), str(source))

            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o664)

    def test_oversized_layout_member_is_rejected_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.floorplan"
            with zipfile.ZipFile(
                path, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.writestr(PROJECT_JSON_NAME, b" " * (MAX_PROJECT_JSON_BYTES + 1))
                archive.writestr(PROJECT_PDF_NAME, b"%PDF-1.4\n")
            with self.assertRaises(ProjectFileError):
                load_project_bundle(str(path))

    def test_pathological_json_number_uses_project_error_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad-number.floorplan"
            payload = b'{"schema_version":' + b"9" * 5000 + b"}"
            with zipfile.ZipFile(
                path, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.writestr(PROJECT_JSON_NAME, payload)
                archive.writestr(PROJECT_PDF_NAME, b"%PDF-1.4\n")
            with self.assertRaises(ProjectFileError):
                load_project_bundle(str(path))


if __name__ == "__main__":
    unittest.main()
