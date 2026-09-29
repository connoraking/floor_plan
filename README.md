# Floor Planner

An easy, offline desktop app for checking whether furniture fits on a PDF floor plan. Open every page of the plan together, set the drawing scale with two clicks, and place true-to-size rectangles or L-shaped pieces.

## Download the app

**You do not need Python, Node, a terminal, or any technical setup.**

Go to the [latest Floor Planner release](https://github.com/connoraking/floor_plan/releases/latest), open **Assets**, and download the file for your computer:

| Computer | Download | What to do |
|---|---|---|
| Windows 10/11 | `Floor-Planner-Setup-...exe` | Recommended. Double-click once to install, then use the desktop shortcut. |
| Windows 10/11 | `Floor-Planner-Portable-...exe` | No installation. Keep the one file anywhere and double-click it. |
| macOS | `Floor-Planner-...dmg` | Open it and drag Floor Planner to Applications. |
| Linux | `Floor-Planner-...AppImage` | Make it executable, then double-click it. |

The downloads are currently community-built and unsigned. Windows may show a protection message the first time; choose **More info → Run anyway** only if the download came from this repository. On macOS, Control-click the app and choose **Open** the first time.

## Using Floor Planner

1. Click **Open PDF** and choose a floor plan. Every page appears in the middle of the window.
2. Click the page you want, then click **Calibrate this page**.
3. Click one end of a printed measurement and then its other end. Type the real distance. Check **Use this scale for every page** only when all pages use the same printed scale.
4. Click **Rectangle** for beds, tables, rugs, and regular sofas, or **L-shape** for sectionals and corner desks.
5. Enter the real dimensions in inches, then drag the colored piece into place. Click it again to reveal blue resize handles: drag the right handle for width, the bottom handle for depth, or the corner for both.

Use **Page layout → Two-page view** to put two pages side by side. Continuous view makes each complete page fill the workspace width in one scrollable column. In either layout, 100% zoom means fit-to-width; use the slider to make pages smaller or larger. The PDF scrollbars stay inside the middle workspace, so the furniture controls on the right always remain visible.

Every page has a **Remove** button. Removing a page hides it from the project and removes furniture placed on that page; the original PDF embedded in the project is not modified. Use the always-visible zoom slider for exact zoom, the +/− buttons for small steps, or hold Ctrl while scrolling over a page.

**Save editable** creates one portable `.floorplan` working file containing the PDF, scale, and furniture so you can keep editing later. **Export PDF** creates a normal, shareable PDF containing every visible floor-plan page with its furniture flattened on top.

Everything runs locally. Floor plans are not uploaded anywhere.

## Features

- Opens standard and multi-page PDF floor plans
- Loads long PDFs a few nearby pages at a time to keep the app responsive
- Shows all PDF pages, with continuous and two-page layouts
- Removes unwanted pages while preserving their original PDF page numbers
- Precise click-click calibration with zoom-independent endpoint markers and feet, inches, centimeters, or meters
- Optional one-click scale copy across every page
- Exact rectangles and guided L-shapes
- Sofa, queen-bed, and dining-table shortcuts
- Direct width/depth resize handles, dragging, keyboard nudging, rotation, duplication, locking, and deletion
- Portable project files with the source PDF embedded
- Shareable multi-page PDF export with furniture included
- High-contrast controls and visible keyboard focus
- Fully offline after download

## Development

The current app is Electron plus plain JavaScript and PDF.js. Python is not used by the app or its downloadable builds.

Install [Node.js 24](https://nodejs.org/), then run:

```bash
npm ci
npm run dev
```

Tests and a production renderer build:

```bash
npm test
npm run build
```

Create local packages:

```bash
npm run dist:win
npm run dist:mac
npm run dist:linux
```

`npm run dist:win` produces both the installer and portable EXE under `release/`.

## Publishing downloads to GitHub

Push a version tag to run the included GitHub Actions release workflow:

```bash
git tag v2.3.0
git push origin v2.3.0
```

The workflow tests the app, builds the Windows, macOS, and Linux downloads, and attaches them to a GitHub Release. It can also be run manually from the repository's **Actions** tab to create test artifacts without publishing a release.

## Current scope

The app uses guided rectangles and L-shapes so dimensions remain exact. The PDF is a visual background; Floor Planner does not automatically detect walls or prevent furniture from overlapping them.

## License

Floor Planner is MIT licensed. See `THIRD_PARTY_NOTICES.md` for the major components included in desktop builds.
