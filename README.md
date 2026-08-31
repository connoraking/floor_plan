# Floor Planner

A simple, offline desktop app for testing whether real furniture will fit on a PDF floor plan.

Open a PDF, calibrate one known measurement, and add true-to-size rectangles or L-shaped furniture. Pieces can be dragged, rotated, duplicated, locked, edited, and saved in a portable project file.

## What it does

- Opens PDF floor plans, including multi-page PDFs
- Calibrates each page by drawing over a known wall length or printed dimension
- Supports feet, inches, centimeters, and meters
- Adds exact-size rectangles and guided L-shapes for sectionals or corner desks
- Includes common furniture size presets
- Supports zoom, pan, multi-select, keyboard nudging, rotation, locking, and undo/redo
- Saves a portable `.floorplan` file containing both the PDF and furniture layout
- Exports a clean, flattened PNG to share or print
- Keeps everything local—nothing is uploaded

## Easiest way to run it

If the repository has a published version, the simplest option is the **Releases** page: download the archive matching the computer, extract the whole archive, and launch Floor Planner. Those builds do not require Python. See [Downloadable desktop builds](#downloadable-desktop-builds).

To run directly from a downloaded copy of the repository instead:

### Windows

1. Install [Python 3.10 or newer](https://www.python.org/downloads/) if it is not already installed. During setup, check **Add Python to PATH**.
2. Download this repository with **Code → Download ZIP**, then unzip it.
3. Double-click `start_windows.bat`.

The first launch creates a private Python environment and downloads the app's dependencies, so it needs internet and may take a few minutes. Later launches reuse that setup.

### macOS or Linux

Install Python 3.10 or newer, then open Terminal in the downloaded folder and run:

```bash
./start_mac_linux.sh
```

If macOS downloaded the file without execute permission, run `chmod +x start_mac_linux.sh` once.

### From a terminal

Windows Command Prompt or PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m floor_planner
```

macOS or Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m floor_planner
```

## Using the app

1. Click **Open PDF** or drag a PDF onto the window.
2. Click **Calibrate Scale**, then drag between the endpoints of a known measurement. Enter its real length.
3. Click **Add Rectangle** or **Add L-Shape**, enter the furniture dimensions, and drag the new piece into position.
4. Double-click a piece to edit it. Use the right panel to rotate, duplicate, lock, or delete it.
5. Choose **File → Save Project** to create a portable `.floorplan` file, or export the current page as a PNG.

Useful controls:

| Action | Control |
|---|---|
| Zoom | Mouse wheel |
| Pan | Middle-drag, Space-drag, or Pan mode |
| Select several pieces | Drag a selection box |
| Rotate selected piece | `[` / `]` or the right panel |
| Move precisely | Arrow keys; hold Shift for a larger step |
| Duplicate | `Ctrl+D` / `Cmd+D` |
| Undo / redo | `Ctrl+Z` / `Ctrl+Y` (`Cmd+Z` / `Cmd+Shift+Z` on macOS) |
| Fit the whole page | `Ctrl+0` / `Cmd+0` |

Scale is stored independently for every PDF page. Furniture positions use stable PDF coordinates, so zooming or using a high-DPI screen will not change the layout.

## Downloadable desktop builds

Versioned packages appear on the repository's **Releases** page:

| Computer | Release archive | What to open after extracting |
|---|---|---|
| Windows 10/11, Intel or AMD 64-bit | `FloorPlanner-Windows-x64.zip` | `FloorPlanner/FloorPlanner.exe` |
| Mac with Apple silicon, macOS 13+ | `FloorPlanner-macOS-arm64.zip` | `FloorPlanner/FloorPlanner.app` |
| Mac with an Intel processor, macOS 13+ | `FloorPlanner-macOS-x64.zip` | `FloorPlanner/FloorPlanner.app` |
| Ubuntu 22.04+ or compatible Linux, x64 | `FloorPlanner-Linux-x64.tar.gz` | `FloorPlanner/FloorPlanner` |

Extract the entire archive; the executable needs the support files beside it. No Python setup is required.

For the repository owner: pushing a version tag such as `v0.1.0` runs the included GitHub Actions workflow and publishes all four archives as a GitHub Release. Exact Qt/PySide corresponding-source archives are attached to the same release. The workflow can also be run manually from the Actions tab to create temporary test artifacts.

These community builds are unsigned. For a build you trust, Windows may require **More info → Run anyway**. On macOS, Control-click the app and choose **Open**, or approve it under **System Settings → Privacy & Security**. Code signing can remove these warnings later.

## Development

The interface uses PySide6, and PDFs are rendered with pypdfium2. The geometry and project format are independent of the UI and covered by standard-library tests.

```bash
python -m unittest discover -s tests -v
```

Project layout:

```text
floor_planner/core.py        units, scale, geometry, and project model
floor_planner/project_io.py  portable .floorplan bundle format
floor_planner/canvas.py      zoomable and pannable PDF canvas
floor_planner/items.py       interactive furniture graphics
floor_planner/dialogs.py     calibration and shape editors
floor_planner/main_window.py application workflow
```

## Current scope

The first version intentionally uses guided rectangle and L-shape editors instead of arbitrary polygons. That keeps measurements exact and makes sectionals easy to create. The PDF is a visual background; the app does not automatically detect walls or prevent overlap.

## License

Floor Planner is MIT licensed. Downloadable builds also include `THIRD_PARTY_NOTICES.md` and the license texts for Qt/PySide6, PDFium, Pillow, Python, and the PyInstaller bootloader.
