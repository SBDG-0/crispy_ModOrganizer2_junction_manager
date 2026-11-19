# Junction Manager

## Description

A small Windows plugin for Mod Organizer 2. Store a mod in a location
and link its folder into MO2 using a directory junction. Changes through either
path affect the same files, without copying or syncing.

## Install

- Extract the archive into your MO2 installation. The result should be
`plugins/JunctionManager/__init__.py`. 
- Restart MO2 and open **Tools → Junction Manager**.

<img width="165"  alt="startfromtools" src="https://github.com/user-attachments/assets/f5cb7fbb-265f-4a16-87e3-7b5a8fbd973b" />
<img width="900"  alt="main" src="https://github.com/user-attachments/assets/5f895c15-32d4-42a7-9d7d-c7df4a98018e" />

Requires Windows 10/11 and MO2 2.5.2 with its bundled Python 3.12/PyQt6 plugin support.
No extra Python installation, administrator mode, or Developer Mode is required.
Windows PowerShell 5.1 creates junctions in a hidden process.

## Instances

Each discovered MO2 instance has a collapsible table. The active instance appears
first and is expanded automatically. Other instances start collapsed. The running
instance is identified by MO2's actual mods path, not by its display name.

Global instances are read from `%LOCALAPPDATA%/ModOrganizer/*/ModOrganizer.ini`.
The portable configuration next to this MO2 installation is also detected.
Custom base and mods paths are supported. The list updates automatically while
the manager is open. Instance creation, removal, and switching belong to MO2;
this plugin only reads its registered configurations. Instance configuration
files are never edited, and there is no separate instance registry to maintain.

Opening another section does not switch the running MO2 instance. Its buttons
operate on that section's mods folder. Changes to other instances are visible
when those instances next refresh; the active instance refreshes automatically.

## Use

- Expand the instance you want to manage. Add a folder or drop one or more mod
  folders into that section. The mod keeps its source folder's name.
- **Auto Link…** compares same-name ordinary mod folders against a selected source
  parent. Only identical copies are offered. Confirmation is required before
  conversion; contents are rechecked before each replacement.
- Failed creation restores the original duplicate. If cleanup cannot finish, a
  `.mfl-recovery-*` folder is retained and its location is reported.
- **Relink…** changes one existing link's source, retaining its mod name. Failure
  restores the original link, including a previously broken one.
- **Remove link** removes only the junction or directory symlink. Ordinary folders
  are protected. Source files stay where they are.
- Paths display their beginning. Double-click a path for a read-only scrolling
  and copying field. Header dividers autosize columns and rows on double-click.
- Tables use compact rows and fill the available space. Columns initially fit
  the window width. Drag a column divider to keep manual widths; right-click a
  column header and choose **Fit columns to window** to restore automatic sizing.
- Small transparent indicators identify linked folders in the active MO2 mod
  list. Disable them in MO2's plugin settings if desired, then restart MO2.
- The **?** button opens usage instructions, file-operation warnings, credits,
  and a language selector. **Follow MO2** reads the active instance's language;
  manual overrides affect only this plugin and are saved per MO2 instance.
  English, German, French, Arabic, Japanese, Simplified Chinese, and Russian are
  included. Arabic uses right-to-left text; filesystem paths remain left-to-right.
  Unsupported automatic languages fall back to English. Operating-system error
  messages may remain in the language supplied by Windows.
  Language changes are disabled while a filesystem operation is running.

Ctrl+T shows the instance's mods folder; Ctrl+S opens the selected original folder;
F5 refreshes the section; Delete removes selected links after confirmation.
The Refresh button inherits MO2's existing refresh icon, including theme changes;
there is no bundled copy of that icon. The ellipsis (`…`) on Add folder, Auto Link,
and Relink means a dialog opens before the operation, not that text is clipped.
The shortcut reminder appears once at the bottom of the manager. Shortcuts act
on the instance section containing keyboard focus.

Long operations run in a worker thread. Cancel stops between operations or while
hashing; already completed changes are kept. Closing a busy window requests
cancellation and waits for the current operation rather than abandoning it.

## Limits
<img width="900" alt="unavailable" src="https://github.com/user-attachments/assets/7474a027-94ca-4770-ada9-5072f59ea92f" />

This version handles local folders, not individual files or network-share sources.
It detects junctions and directory symbolic links, including broken links. Nested
links inside Auto Link candidates are skipped to avoid following cycles.

Close games and tools launched through MO2 before changing folder links. Editing
or deleting files **inside** a linked folder changes the original files too. Moving
source folders or changing drive letters can break links; use Relink to update them.

There are no queue modes, profiles, themes, account integration,
telemetry, external network requests, bundled runtimes, or file-copy background
services in this lightweight version. The interface uses MO2's existing Qt theme.
Translations are supplied with the plugin; it makes no online translation requests.
The help button references MO2's existing Help action icon and uses the same
`actionHelp` stylesheet identifier. It does not load its own copy or choose a
particular icon set. If MO2's Help icon is unavailable, Qt's standard help icon
is used. No third-party icon files are included or relicensed by this package.

## Sharing

The original source code, SVG artwork, and documentation in this package are
released under the **MIT License**. Copy, change, redistribute, sublicense, or use
them commercially while retaining the copyright and permission notices with
copies or substantial portions. See [LICENSE](LICENSE).

This implementation was written for the functional requirements of Junction Manager. It contains no files, assets, translations, or imports from Symbolic Link Manager .

MO2 and its existing dependencies retain their own licenses. They are not bundled
in this download. This license does not relicense dependencies or third-party
rights. The software is supplied without warranty.

---

made with ❤️ by SavageBulldogOG
