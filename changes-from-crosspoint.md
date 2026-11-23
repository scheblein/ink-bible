# Changes from CrossPoint 2.0.0 to Ink Bible 1.0.0

This document compares upstream **CrossPoint Reader `2.0.0`** (`42d58daa`) to **Ink Bible `1.0.0`** on `develop`.

---

## 1. Menu Items & Navigation

### Boot & Top-Level Flow

| Area | CrossPoint 2.0.0 | Ink Bible 1.0.0 |
| --- | --- | --- |
| First boot | Boots to **Home** screen (`HomeActivity`) | Boots to **Welcome to Ink Bible** (`UserGuideActivity` in welcome mode) |
| Normal boot / `goHome()` | Opens **Home** screen (Library, Files, OPDS, File Transfer, Settings) | Opens the current Bible directly in the reader (or the built-in NET Bible if none is open) |
| Back held at boot / crash recovery | Boots to **Home** screen | Escape hatch to **File Browser** (`/`) |
| Library / OPDS / Plugins routes | `LibraryListActivity`, `OpdsBookBrowserActivity`, `PluginCatalogActivity` | Unlinked; fallback routes redirect to **File Browser** (`/`) |

---

### Reader Menu (`EpubReaderMenuActivity`)

| Item | CrossPoint 2.0.0 | Ink Bible 1.0.0 |
| --- | --- | --- |
| Passage / Chapter navigation | **Select Chapter** | Renamed to **Go to Passage** (opens 3-stage `Book → Chapter → Verse` picker for canonical Bibles) |
| **Footnotes** | Shown when page has footnotes | Kept |
| **Toggle Bookmark** / **Bookmarks** | Kept | Kept |
| **Create Clipping** / **View Clippings** | Kept | Kept |
| **Night Mode** | Kept | Kept |
| **Bluetooth Page Turner** | Shown when paired | Kept |
| **Orientation** | Kept | Kept |
| **Text Settings** | Kept | Kept |
| **Switch Bible** | — | **Added** (opens File Browser to pick another EPUB Bible) |
| **Settings** | — | **Added** (opens `SettingsListActivity` directly from the reader) |
| **User Guide** | — | **Added** (opens on-device 4-page `UserGuideActivity`) |
| **Lookup (Dictionary)** | Shown when a dictionary is selected | **Removed** |
| **Auto Page Turn** | Present | **Removed** |
| **Go to Percent** | Present | **Removed** |
| **Screenshot** | Present | **Removed** |
| **Display QR** | Present | **Removed** |
| **Go Home** | Present | **Removed** (no Home screen) |
| **Sync Progress (KOReader / Plugins)** | Shown when configured | **Removed** |
| **Delete Cache** | Present | **Removed** (still available in Settings → Reader → Clear Reading Cache) |

---

### Chapter / Passage Picker (`EpubReaderChapterSelectionActivity`)

| CrossPoint 2.0.0 | Ink Bible 1.0.0 |
| --- | --- |
| Flat EPUB table of contents list (**Select Chapter**) | Detects 1,189-chapter canonical Bibles (`BibleCanon::TOTAL_CHAPTER_COUNT`) and switches to a 3-stage picker: **Select Book** (66 books with chapter counts) → **Chapter** → **Verse** |

---

### Settings Top-Level Sections (`SettingsListActivity`)

| CrossPoint 2.0.0 (6 sections) | Ink Bible 1.0.0 (5 sections) |
| --- | --- |
| General | General |
| Display | Display |
| Reader | Reader |
| Controls | Controls |
| **Library** | **Removed** |
| Network / Connectivity | Network / Connectivity |

---

### Settings Sub-Menu Items (`SettingsActivity` & `SettingsList`)

#### General
- **Added:** **User Guide** (`SettingAction::UserGuide`)
- **Removed:** **Language** (`LanguageSelectActivity` — firmware is English-only, `custom_i18n_builtin_langs = en`)
- **Hidden (device & web):** **Show Hidden Files**
- **Kept:** Keyboard Layouts, Clock (RTC boards), Check for Updates, SD Firmware Update, About

#### Display
- **Trimmed Sleep Screen options:** Removed cover-based modes (`Cover`, `Cover + Custom`, `Cover + Transparent`); kept `Dark`, `Light`, `Custom`, `None`, `Quick Resume`, `Transparent`.
- **Hidden (device & web):** **Sleep Cover Mode**, **Sleep Cover Filter**, **UI Theme**
- **Hidden on X4 Pro / X4 Classic (device & web):** **Sunlight Fading Fix** (previously only hidden on device)
- **Kept:** Sleep Timeout, Quick Resume Timeout, Refresh Frequency, Restore Light on Wake (frontlight boards)

#### Reader
- **Hidden (device & web):** **Images** (`imageRendering`)
- **Removed:** **Dictionary** selector
- **Kept:** Text Settings, Manage Fonts, Reader Menu Style, Customise Status Bar, Clear Reading Cache

#### Status Bar (`StatusBarSettingsActivity`)
- **Removed (device & web):** **XTC Status Bar** (`xtcStatusBarMode`)
- **Kept:** Chapter Page Count, Progress Bar, Progress Bar Thickness, Title, Battery, Clock (RTC boards)

#### Controls
- **Added (non-touch devices):** **Left / Right buttons** (`frontLeftRightBehavior`) — `Chapter / Book` (default: short press skips chapters, long press skips books), `Page turn`, or `Links and Footnotes`. Automatically falls back to page turns if side buttons are disabled.
- **Removed:** **Long-press Confirm function** (`longPressMenuFunction` removed from Settings UI; option list also drops `KOReader Sync` and `Dictionary`)
- **Hidden (device & web):** **Back short press to File Browser** (`backShortToFileBrowser`)
- **Trimmed Home Button actions (`HomeButtonSettingsActivity`):** Removed `KOReader Sync` and `Dictionary` from Tap / Double Tap / Long Press choices; relabeled `Home` to **Bible / Passage** (opens Passage Picker in the reader and returns to the Bible from other screens).
- **Trimmed Short Power Button actions:** Removed `KOReader Sync` on touch devices without a Home key.
- **Kept:** Front button follow orientation, Remap front buttons, Side button layout, Long-press behavior, Short power button, Power button footnote back, Double-click power frontlight (X4 Pro), Home button (boards with Home key), Touch controls (touch boards)

#### Library (removed section)
- **Hidden (device & web):** **Use Library Metadata**, **Remove Read Books from Recents**, **Move Finished Books to Read Folder**

#### Network / Connectivity
- **Added:** **File Transfer** (`SettingAction::FileTransfer` — moved here since the Home screen was removed)
- **Removed:** **KOReader Sync**, **OPDS Servers**, **Plugins** (removed from on-device Settings, Web Settings UI, and web server routes)
- **Kept:** Wi-Fi Networks, Bluetooth Page Turner

---

### File Transfer / Network Mode Menu (`NetworkModeSelectionActivity`)

| Item | CrossPoint 2.0.0 | Ink Bible 1.0.0 |
| --- | --- | --- |
| **Join Network** | Present | Kept |
| **Calibre Wireless** | Present | **Removed** |
| **Create Hotspot** | Present | Kept |
| **USB Drive** (when `FREEINK_CAP_USB_MSC`) | Present | Kept |

---

## 2. Reader Controls & Default Settings

| Control / Setting | CrossPoint 2.0.0 | Ink Bible 1.0.0 |
| --- | --- | --- |
| **Side Up / Down (hold)** (`longPressButtonBehavior`) | Default: `Off` | Default: **Chapter Skip** |
| **Front Left / Right** (`frontLeftRightBehavior`) | Always page turn | Default: **Chapter / Book** (short = chapter, hold = book; configurable to `Page turn` or `Links and Footnotes` in Settings → Controls) |
| **Confirm (short press)** | Opens Reader Menu | Opens **Passage Picker** (`Book → Chapter → Verse`) |
| **Confirm (long press)** | Configurable (`longPressMenuFunction`) | Opens **Reader Menu** |
| **Back (short press)** | Exits reader (Home / File Browser) | Opens **Bookmarks** list |
| **Back (long press)** | — | **Toggles Bookmark** on current page |

---

## 3. Built-in Bible & Reader Enhancements

- **Built-in NET Bible:** Generated at build time via `scripts/generate_net_bible_epub.py` and embedded in firmware (`lib/BibleCanon/BibleCanon.h`, `NetBibleData.cpp`).
- **Multi-version support:** Users can place additional EPUB Bibles on the SD card (or upload via File Transfer) and switch via **Reader Menu → Switch Bible**.
- **USFM footnotes & verse navigation:** Extended `ChapterHtmlSlimParser`, `BookMetadataCache`, and `Epub` to support Bible verse anchors and study-note footnotes cleanly.
- **On-device User Guide & Welcome screen:** New `UserGuideActivity` (`src/activities/util/UserGuideActivity.cpp`) shown on first boot (`APP_STATE.welcomeShown`) with tailored copy for button (X3/X4) and touch (X4 Pro) devices, accessible anytime from **Reader Menu → User Guide** or **Settings → General → User Guide**.
- **End-of-Book menu (`EndOfBookOptions`):** Replaced the trailing **Home** row with **Switch Bible** (opens File Browser).

---

## 4. Branding, Web UI, OTA & Build/CI

- **Branding:** Renamed UI strings, logo (`src/images/logo.svg`, `Logo120.h`), Web UI pages/titles/logs, and UDP discovery (`inkbible`) to **Ink Bible**.
- **Hotspot defaults:** AP SSID changed from `CrossPoint-Reader` to `Ink-Bible`; mDNS hostname changed from `crosspoint` to `inkbible`.
- **OTA updates:** `OtaUpdater.cpp` points to `scheblein/ink-bible` and looks for `ink-bible-<version>-<device>.bin`.
- **Version & languages:** `platformio.ini` sets `version = 1.0.0` and `custom_i18n_builtin_langs = en`.
- **CI & Releases:** Trimmed build matrix to Xteink targets (`x3-x4`, `x4pro`, `x4c`), removed unused CrossPoint workflows (`pr-firmware-links`, `pr-formatting-check`, `release-fonts`, `release_candidate`), and added auto-release on push to `master`.
