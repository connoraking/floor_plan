from __future__ import annotations

import json
import os
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import Project, ValidationError

PROJECT_JSON_NAME = "project.json"
PROJECT_PDF_NAME = "source.pdf"
MAX_PROJECT_JSON_BYTES = 5 * 1024 * 1024
MAX_EMBEDDED_PDF_BYTES = 512 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024


class ProjectFileError(RuntimeError):
    """Raised when a portable project cannot be saved or opened."""


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON number: {value}")


@dataclass
class LoadedProject:
    project: Project
    pdf_path: str
    _temporary_directory: tempfile.TemporaryDirectory[str]

    def close(self) -> None:
        self._temporary_directory.cleanup()


def save_project_bundle(path: str, project: Project, source_pdf_path: str) -> None:
    """Atomically save JSON and the source PDF in one portable .floorplan ZIP."""
    project.validate()
    source = Path(source_pdf_path)
    destination = Path(path)
    temporary_path: str | None = None
    try:
        if not source.is_file():
            raise ProjectFileError("The source PDF could not be found.")
        if source.stat().st_size > MAX_EMBEDDED_PDF_BYTES:
            raise ProjectFileError("The source PDF is too large to embed in a project.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".floorplan.tmp", dir=destination.parent, delete=False
        ) as temporary_file:
            temporary_path = temporary_file.name
        with zipfile.ZipFile(
            temporary_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as archive:
            payload = json.dumps(
                project.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ).encode("utf-8")
            if len(payload) > MAX_PROJECT_JSON_BYTES:
                raise ProjectFileError("The project contains too much layout data.")
            archive.writestr(
                PROJECT_JSON_NAME, payload, compress_type=zipfile.ZIP_DEFLATED
            )

            # Stream the already-compressed PDF without copying its filesystem
            # timestamp. ZipInfo's safe 1980 epoch also supports very old files.
            pdf_info = zipfile.ZipInfo(PROJECT_PDF_NAME)
            pdf_info.compress_type = zipfile.ZIP_STORED
            with (
                source.open("rb") as pdf_source,
                archive.open(pdf_info, "w", force_zip64=True) as pdf_target,
            ):
                while chunk := pdf_source.read(COPY_CHUNK_BYTES):
                    pdf_target.write(chunk)

        if os.name != "nt":
            if destination.exists():
                output_mode = stat.S_IMODE(destination.stat().st_mode)
            else:
                current_umask = os.umask(0)
                os.umask(current_umask)
                output_mode = 0o666 & ~current_umask
            os.chmod(temporary_path, output_mode)
        os.replace(temporary_path, destination)
        temporary_path = None
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise ProjectFileError(f"Could not save the project: {exc}") from exc
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


def load_project_bundle(path: str) -> LoadedProject:
    """Load a .floorplan bundle and safely extract only its embedded PDF."""
    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            infos = archive.infolist()
            if len(infos) != 2 or {info.filename for info in infos} != {
                PROJECT_JSON_NAME,
                PROJECT_PDF_NAME,
            }:
                raise ProjectFileError(
                    "This file is not a complete Floor Planner project."
                )
            info_by_name = {info.filename: info for info in infos}
            json_info = info_by_name[PROJECT_JSON_NAME]
            pdf_info = info_by_name[PROJECT_PDF_NAME]
            if json_info.file_size > MAX_PROJECT_JSON_BYTES:
                raise ProjectFileError("The project layout data is too large.")
            if pdf_info.file_size > MAX_EMBEDDED_PDF_BYTES:
                raise ProjectFileError("The embedded PDF is too large.")
            if json_info.flag_bits & 0x1 or pdf_info.flag_bits & 0x1:
                raise ProjectFileError("Encrypted project bundles are not supported.")

            with archive.open(json_info, "r") as json_source:
                json_payload = json_source.read(MAX_PROJECT_JSON_BYTES + 1)
            if len(json_payload) > MAX_PROJECT_JSON_BYTES:
                raise ProjectFileError("The project layout data is too large.")
            raw_data: Any = json.loads(
                json_payload.decode("utf-8"),
                parse_constant=_reject_json_constant,
            )
            if not isinstance(raw_data, dict):
                raise ProjectFileError("The project data is malformed.")
            project = Project.from_dict(raw_data)
            temporary_directory = tempfile.TemporaryDirectory(prefix="floor-planner-")
            extracted_pdf = Path(temporary_directory.name) / PROJECT_PDF_NAME
            with (
                archive.open(pdf_info, "r") as source,
                extracted_pdf.open("wb") as target,
            ):
                total = 0
                while chunk := source.read(COPY_CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_EMBEDDED_PDF_BYTES:
                        raise ProjectFileError("The embedded PDF is too large.")
                    target.write(chunk)
        return LoadedProject(project, str(extracted_pdf), temporary_directory)
    except ProjectFileError:
        if temporary_directory is not None:
            temporary_directory.cleanup()
        raise
    except (
        OSError,
        KeyError,
        EOFError,
        NotImplementedError,
        RuntimeError,
        UnicodeError,
        ValueError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        ValidationError,
    ) as exc:
        if temporary_directory is not None:
            temporary_directory.cleanup()
        raise ProjectFileError(f"Could not open the project: {exc}") from exc
