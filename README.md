# Floor Planner

Floor Planner is a simple Windows app for placing correctly sized furniture on a PDF floor plan. It works offline and does not upload your floor plan anywhere.

## Download on Windows

**You do not need Python, Node.js, Git, or a terminal.**

1. Open the [latest Floor Planner release](https://github.com/connoraking/floor_plan/releases/latest).
2. Find the **Assets** section.
3. Download **`Floor-Planner-Setup-2.3.0.exe`**.
4. Double-click the downloaded file. Floor Planner will install and add a shortcut.

Do not download the files named **Source code**. Those are for developers and will not install the app.

If you do not want to install anything, download **`Floor-Planner-Portable-2.3.0.exe`** instead. Keep that file anywhere and double-click it whenever you want to use Floor Planner.

### If Windows shows a warning

The app is free and is not code-signed yet, so Windows may show **Windows protected your PC** the first time.

Only when the file came from this repository, click **More info**, then **Run anyway**.

## How to use it

1. Click **Open PDF** and choose your floor plan.
2. Select a page and click **Calibrate**.
3. Click both ends of a measurement printed on the plan, then enter its real length.
4. Click **Rectangle** or **L-shape** and enter the furniture dimensions.
5. Drag the furniture into place.

When furniture is selected, use its blue handles:

- Drag the right handle to change its width.
- Drag the bottom handle to change its depth.
- Drag the corner handle to change both.

Use the controls on the right to enter exact dimensions, rotate the furniture, change its color, duplicate it, lock it, or delete it.

## Save or share your plan

- **Save editable** creates a `.floorplan` file that you can open later and continue editing.
- **Export PDF** creates a normal PDF with the furniture included. Send this PDF to anyone you want.

Removing a page inside Floor Planner does not change your original PDF.

## Other computers

The release page also provides a macOS `.dmg` and a Linux `.AppImage`. Windows users should choose one of the `.exe` files described above.

<details>
<summary><strong>Developer information — not needed to download or use the app</strong></summary>

The app is built with Electron, JavaScript, and PDF.js. Python is not used.

Node.js 24 is only needed if you want to change the source code or build the app yourself:

```bash
npm ci
npm run dev
```

Run the automated tests and production build with:

```bash
npm test
npm run build
```

Create desktop packages with `npm run dist:win`, `npm run dist:mac`, or `npm run dist:linux` on the matching operating system.

</details>

<details>
<summary><strong>Repository owner — publishing version 2.3.0</strong></summary>

The `v2.3.0` tag already exists locally. Do not create it again. Push the code and the existing tag with:

```bash
git push origin main
git push origin v2.3.0
```

The second command must say `v2.3.0`, with one zero at the end. After the tag is pushed, GitHub Actions tests the app and creates the Windows, macOS, and Linux downloads. The Release can take several minutes to appear.

</details>

## Current limitations

Furniture uses rectangles and L-shapes so its dimensions stay exact. The PDF is a visual background; the app does not automatically detect walls or prevent furniture from overlapping them.

## License

Floor Planner is MIT licensed. See `THIRD_PARTY_NOTICES.md` for information about the main components included in the desktop app.
