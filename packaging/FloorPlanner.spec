# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_root = Path(SPECPATH).parent
datas, binaries, hiddenimports = collect_all("pypdfium2")

analysis = Analysis(
    [str(project_root / "run_floor_planner.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Standard desktop libraries are supplied by the target Linux distribution.
# Keeping them out of the archive avoids shipping a snapshot of the CI runner's
# GTK/X11 stack and improves compatibility with newer supported distributions.
if sys.platform.startswith("linux"):
    analysis.exclude_system_libraries()

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="FloorPlanner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collected = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FloorPlanner",
)

if sys.platform == "darwin":
    app = BUNDLE(
        collected,
        name="FloorPlanner.app",
        icon=None,
        bundle_identifier="com.connor.floorplanner",
    )
