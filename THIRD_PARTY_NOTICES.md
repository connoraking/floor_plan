# Third-party software notices

Floor Planner itself is licensed under the MIT License. Release packages also contain the open-source components below. Exact versions for a particular package are recorded in `BUNDLED_VERSIONS.txt`, and their license texts are included in the `third_party_licenses` folder beside the application.

## Qt, PySide6, and Shiboken6

Floor Planner uses the Qt Community Edition through PySide6 and Shiboken6. These components are Copyright © The Qt Company Ltd. and other contributors and are available under the GNU Lesser General Public License version 3 (LGPLv3), or under alternative license terms offered by their copyright holders.

The application uses the shared Qt libraries dynamically and does not modify them. You may study, modify, reverse engineer for debugging, and replace those libraries as permitted by the LGPLv3. After extracting the release archive, the shared libraries are in the application support directory (`_internal/PySide6/Qt` on Windows/Linux, or inside `FloorPlanner.app/Contents/Frameworks` on macOS). An ABI-compatible replacement may be placed in the corresponding location.

Windows and Linux packages are not code-signed. PyInstaller applies an ad-hoc signature to the macOS app bundle. After replacing a library on macOS, re-sign the modified bundle from Terminal with `codesign --force --deep --sign - FloorPlanner.app`; this creates a new ad-hoc signature and allows the modified libraries to load.

The full GPLv3 and LGPLv3 terms are included. For tagged GitHub releases, the repository's Release page carries exact-version source archives for Qt Base, Qt SVG, Qt Wayland, and Qt for Python under the distributor's control. Their direct links are recorded in `BUNDLED_VERSIONS.txt`. Upstream information is also available from:

- https://doc.qt.io/qtforpython-6/
- https://code.qt.io/cgit/pyside/pyside-setup.git/
- https://code.qt.io/cgit/qt/qtbase.git/

The Qt wheel also contains ICU and Unicode data. Their complete binary-distribution notices are included as `ICU-LICENSE.txt` and `UNICODE-LICENSE.txt`.

## PDFium and pypdfium2

PDF rendering is provided by pypdfium2 and PDFium. They are distributed under BSD-3-Clause, Apache-2.0, and component-specific licenses. The complete license set shipped by the installed pypdfium2 wheel is copied into `third_party_licenses/pypdfium2-*` for each release.

Source: https://github.com/pypdfium2-team/pypdfium2

## Pillow

Image conversion and export use Pillow, licensed under the MIT-CMU license. Its license is copied into `third_party_licenses/Pillow-*`.

Source: https://github.com/python-pillow/Pillow

## Python

The packaged application includes the CPython runtime, licensed under the Python Software Foundation License Version 2 and the additional historical terms in `third_party_licenses/PYTHON-LICENSE.txt`.

Source: https://github.com/python/cpython

## PyInstaller bootloader

Release executables are created with the PyInstaller bootloader. PyInstaller is GPL-2.0-or-later with a Bootloader Exception permitting the bootloader to be embedded in and distributed with applications. Its complete licensing terms are copied into `third_party_licenses/PyInstaller-*`.

Source: https://github.com/pyinstaller/pyinstaller

This notice is informational and is not legal advice. Each upstream license text controls the corresponding component.
