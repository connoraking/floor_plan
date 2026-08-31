from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
import sysconfig
from importlib import metadata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_LICENSES = (
    "GPL-3.0.txt",
    "ICU-LICENSE.txt",
    "LGPL-3.0.txt",
    "UNICODE-LICENSE.txt",
)
LICENSE_DISTRIBUTIONS = ("pypdfium2", "Pillow", "PyInstaller")


def _safe_component(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in ".-_" else "_"
        for character in value
    )


def _license_relative_path(entry: Path) -> Path | None:
    parts = entry.parts
    lowered = [part.lower() for part in parts]
    if "licenses" in lowered:
        index = lowered.index("licenses")
        remainder = parts[index + 1 :]
        return Path(*remainder) if remainder else None
    name = entry.name.lower()
    if name.startswith(("license", "copying", "notice")):
        return Path(entry.name)
    return None


def _copy_distribution_licenses(distribution_name: str, destination: Path) -> str:
    package = metadata.distribution(distribution_name)
    version = package.version
    package_destination = destination / (
        f"{_safe_component(distribution_name)}-{_safe_component(version)}"
    )
    copied = 0
    for entry in package.files or ():
        relative = _license_relative_path(Path(str(entry)))
        if relative is None:
            continue
        source = Path(package.locate_file(entry))
        if not source.is_file():
            continue
        target = package_destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    if copied == 0:
        raise RuntimeError(
            f"No license files were found in the installed {distribution_name} {version} package."
        )
    return version


def _copy_python_license(destination: Path) -> None:
    candidates = (
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
        PROJECT_ROOT / "third_party_licenses" / "PYTHON-LICENSE.txt",
    )
    source = next((candidate for candidate in candidates if candidate.is_file()), None)
    if source is None:
        raise RuntimeError("The CPython license text could not be found.")
    shutil.copy2(source, destination / "PYTHON-LICENSE.txt")


def _bundled_versions(distribution_versions: dict[str, str]) -> str:
    python_version = platform.python_version()
    pyside_version = metadata.version("PySide6-Essentials")
    shiboken_version = metadata.version("shiboken6")
    pdfium_version = distribution_versions["pypdfium2"]
    pillow_version = distribution_versions["Pillow"]
    pyinstaller_version = distribution_versions["PyInstaller"]
    repository = os.environ.get("GITHUB_REPOSITORY")
    release_tag = os.environ.get("GITHUB_REF_NAME", "")
    repository_url = (
        f"https://github.com/{repository}"
        if repository
        else "the source repository accompanying this package"
    )
    if repository and release_tag.startswith("v"):
        qt_source_base = (
            f"https://github.com/{repository}/releases/download/{release_tag}"
        )
        qt_sources = {
            component: f"{qt_source_base}/{component}-v{pyside_version}-source.tar.gz"
            for component in ("qtbase", "qtsvg", "qtwayland", "pyside-setup")
        }
    else:
        qt_sources = {
            "qtbase": f"https://github.com/qt/qtbase/tree/v{pyside_version}",
            "qtsvg": f"https://github.com/qt/qtsvg/tree/v{pyside_version}",
            "qtwayland": f"https://github.com/qt/qtwayland/tree/v{pyside_version}",
            "pyside-setup": f"https://github.com/pyside/pyside-setup/tree/v{pyside_version}",
        }
    return f"""Bundled component versions and corresponding source
=================================================

Floor Planner: 0.1.0
Source: {repository_url}

Qt / PySide6 Essentials: {pyside_version}
Shiboken6: {shiboken_version}
Qt Base complete source: {qt_sources["qtbase"]}
Qt SVG complete source: {qt_sources["qtsvg"]}
Qt Wayland complete source: {qt_sources["qtwayland"]}
Qt for Python complete source: {qt_sources["pyside-setup"]}

pypdfium2 / PDFium package: {pdfium_version}
Source: https://github.com/pypdfium2-team/pypdfium2/tree/{pdfium_version}

Pillow: {pillow_version}
Source: https://github.com/python-pillow/Pillow/tree/{pillow_version}

CPython: {python_version}
Source: https://github.com/python/cpython/tree/v{python_version}

PyInstaller bootloader: {pyinstaller_version}
Source: https://github.com/pyinstaller/pyinstaller/tree/v{pyinstaller_version}

The Qt/PySide libraries are unmodified. The source links above identify the
corresponding upstream source, build files, and exact release tags used by this
binary package. Network access is required to retrieve those source trees.
"""


def collect_release_licenses(output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    license_directory = output_directory / "third_party_licenses"
    license_directory.mkdir(parents=True, exist_ok=True)

    shutil.copy2(PROJECT_ROOT / "LICENSE", output_directory / "LICENSE.txt")
    shutil.copy2(
        PROJECT_ROOT / "THIRD_PARTY_NOTICES.md",
        output_directory / "THIRD_PARTY_NOTICES.md",
    )
    for filename in STATIC_LICENSES:
        shutil.copy2(
            PROJECT_ROOT / "third_party_licenses" / filename,
            license_directory / filename,
        )
    _copy_python_license(license_directory)

    versions = {
        name: _copy_distribution_licenses(name, license_directory)
        for name in LICENSE_DISTRIBUTIONS
    }
    (output_directory / "BUNDLED_VERSIONS.txt").write_text(
        _bundled_versions(versions), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add application and third-party license notices to a release folder."
    )
    parser.add_argument("output_directory", type=Path)
    arguments = parser.parse_args()
    collect_release_licenses(arguments.output_directory.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
