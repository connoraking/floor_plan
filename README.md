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

## Download on macOS

1. Open the [latest Floor Planner release](https://github.com/connoraking/floor_plan/releases/latest) and expand **Assets**.
2. Download **`Floor-Planner-2.3.4-universal.dmg`**. This works on both Intel and Apple silicon Macs.
3. Open the downloaded file and drag **Floor Planner** into **Applications**.
4. Open **Applications** in Finder and double-click **Floor Planner**.

### If Apple blocks the app

The current Mac release lacks Developer ID signing and Apple notarization. You may see a message saying Apple could not verify Floor Planner is free of malware, with a **Move to Trash** button. That message alone does not mean Apple detected malware, but it does mean Apple has not verified this app.

Only continue if you downloaded it from this repository's release page and trust it:

1. Keep Floor Planner in **Applications**; do not move it to Trash.
2. After trying to open it, go to **Apple menu → System Settings → Privacy & Security**.
3. Scroll down to **Security**, find the message about Floor Planner, and click **Open Anyway**.
4. Confirm with your Mac password or Touch ID if asked, then click **Open**.

This saves an exception for this copy of the app. No terminal commands or disabling your Mac's security protections are needed. **Control-click → Open is no longer the bypass on recent macOS versions.** See [Apple's opening instructions](https://support.apple.com/en-us/102445).

If **Open Anyway** is missing, try opening Floor Planner from Applications once more, then check those settings again. A work- or school-managed Mac may require its administrator's help. If the warning instead says the app **will damage your computer** or **is damaged**, stop and report that exact message; these instructions are not for those warnings.

## Download on Linux

Download `Floor-Planner-2.3.4-x86_64.AppImage` from the [latest release](https://github.com/connoraking/floor_plan/releases/latest), allow the file to run as a program in its Properties, then double-click it.

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

The current macOS job builds an unsigned, unnotarized app. Removing the Mac security warning requires a Developer ID signing certificate through the Apple Developer Program and signing/notarization configured in that job. A successful build or a new version tag alone does not remove the warning. See [Apple's distribution guidance](https://developer.apple.com/news/?id=saqachfa).

</details>

## Current limitations

Furniture uses rectangles and L-shapes so its dimensions stay exact. The PDF is a visual background; the app does not automatically detect walls or prevent furniture from overlapping them.

## License

Floor Planner is MIT licensed. See `THIRD_PARTY_NOTICES.md` for information about the main components included in the desktop app.
