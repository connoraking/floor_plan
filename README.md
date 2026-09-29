# Floor Planner

Floor Planner is a simple Windows app for placing correctly sized furniture on a PDF floor plan. It works offline and does not upload your floor plan anywhere.

## Download on Windows

**You do not need Python, Node.js, Git, or a terminal.**

1. Open the [latest Floor Planner release](https://github.com/connoraking/floor_plan/releases/latest).
2. Find the **Assets** section.
3. Download **`Floor-Planner-Setup-2.3.4.exe`**.
4. Double-click the downloaded file. Floor Planner will install and add a shortcut.

### Click this file

- **`Floor-Planner-Setup-2.3.4.exe`** is the Windows app installer. Double-click it, finish the short installation, and then open Floor Planner from its desktop or Start menu shortcut.

This is the only Windows program you need to download.

### What if the download is a ZIP file?

There are two very different ZIP files on GitHub:

#### `Source code (zip)` — do not download this to use the app

This contains developer files such as `src`, `electron`, and `package.json`. It does not contain an installed copy of Floor Planner. A normal user cannot click one of those files to start the app.

#### `Floor-Planner-Windows.zip` — a Windows build from the Actions page

This ZIP contains one usable Windows program:

- `Floor-Planner-Setup-2.3.4.exe`

To use it:

1. Right-click **`Floor-Planner-Windows.zip`** and choose **Extract All**.
2. Click **Extract**.
3. Open the new extracted folder.
4. Double-click **`Floor-Planner-Setup-2.3.4.exe`**.

Do not try to run the installer while it is still inside the ZIP. Extract it first.

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

## macOS and Linux

- **macOS:** Download `Floor-Planner-2.3.4-universal.dmg`, open it, and drag Floor Planner into Applications. If macOS blocks the unsigned app, Control-click it and choose **Open**.
- **Linux:** Download `Floor-Planner-2.3.4-x86_64.AppImage`, allow the file to run as a program in its Properties, then double-click it.

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

### Show the app version in a Starship prompt

Starship reads this project’s version from `package.json`. Open `~/.config/starship.toml` and make sure its package section is:

```toml
[package]
disabled = false
display_private = true
format = 'via [📦 $version]($style) '
```

Open a new terminal in this repository. The prompt will show the current app version, such as `v2.3.4`. `display_private = true` is required because this project is marked as a private npm package to prevent accidental publication to npm.

</details>

<details>
<summary><strong>Repository owner — publishing version 2.3.4</strong></summary>

The `v2.3.4` tag already exists locally. Do not create it again. Push the code and the existing tag with:

```bash
git push origin main
git push origin v2.3.4
```

After the tag is pushed, GitHub Actions creates one Release immediately after the tests pass. Independent Windows, macOS, and Linux jobs attach their own downloads as they finish, so one platform cannot prevent another platform from publishing.

</details>

## Current limitations

Furniture uses rectangles and L-shapes so its dimensions stay exact. The PDF is a visual background; the app does not automatically detect walls or prevent furniture from overlapping them.

## License

Floor Planner is MIT licensed. See `THIRD_PARTY_NOTICES.md` for information about the main components included in the desktop app.
