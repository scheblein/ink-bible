# Ink Bible

**Ink Bible** is an all-in-one, dedicated handheld **NET Bible (New English Translation)** firmware for the **Xteink X3 and X4** e-paper readers (and other FreeInk-supported ESP32 devices).

The complete **66-book, 1,189-chapter, 31,102-verse NET Bible** is compiled directly into the firmware flash image (`firmware.bin`) — no `.epub` files need to be copied to the SD card. Power on the device and it opens straight into Scripture with a fast 3-stage **Book → Chapter → Verse** passage picker.

---

## Key Features

- **All-in-One Flash-Embedded NET Bible**: The entire 66-book Protestant canon (`lib/BibleCanon/NetBibleData.generated.cpp`, ~1.56 MB compressed in `.rodata`) streams directly from internal flash on demand. An SD card is used only for saving reading progress, layout caches, bookmarks, clippings, and custom fonts. *(If you ever place a custom `/bible.epub` on the SD card, it overrides the built-in flash text.)*
- **Direct-to-Scripture Startup & On-Device Guide**: First boot opens a run-once **Welcome** quick-start card before jumping straight to Genesis 1; subsequent boots resume your last reading position. Reopen the full **User Guide** anytime via **Reader Menu → User Guide** or **Settings → General → User Guide**. Holding **Back** during startup opens the SD Card File Browser at `/`.
- **3-Stage Passage Picker (`Book → Chapter → Verse`)**:
  - Press **Confirm** (short press) while reading — or select **Go to Passage** from the Reader Menu (hold **Confirm**) — to open the canonical picker:
    1. **Select Book** (Genesis – Revelation, with chapter counts)
    2. **Select Chapter** (`1 .. N`)
    3. **Select Verse** (`1 .. M`) — jumps directly to the exact page containing that verse.
  - Pressing **Back** inside the picker steps back (`Verse → Chapter → Book → Reading Page`).
- **Inline Translator & Study Footnotes**: USFM footnotes (`[1]`, `[2]`, ...) are linked in the text. On X3/X4, front **Left / Right** open inline footnote selection on the current page by default (configurable in **Settings → Controls → Front buttons → Left / Right buttons**, automatically falling back to page turns if side buttons are disabled); pressing **Back** returns to your verse. Also accessible via **Reader Menu → Links and Footnotes**.
- **Bookmarks, Highlights & Clippings**: Hold **Back** to toggle a bookmark on the current page, short-press **Back** to open your Bookmarks list and hop between passages, or select and save verse ranges as highlighted clippings (exported to `/My Clippings.txt` on the SD card).
- **Clean Typography & Layout**:
  - Poetry indentation, Psalm superscriptions, section headings, small-caps divine name (`LORD`), and italics.
  - Adjustable font family, point size, line spacing, margins, paragraph alignment, night mode (inverted display), and reading orientation.
  - Custom SD-card font support (`.cpfont` in `/fonts/`).
- **Hardware Controls & Accessories**:
  - Chapter skip via long-press on Next/Previous Page buttons.
  - Optional Tilt Page Turn for X3 / IMU devices (**Settings → Controls → Tilt Page Turn**).
  - Bluetooth page turner remote support (**Settings → Connectivity → Bluetooth Page Turner**).
- **Wireless File Transfer & OTA Updates**:
  - Built-in Wi-Fi Web UI (**Settings → Connectivity → File Transfer**, hotspot SSID `Ink-Bible` at `http://inkbible.local/` or station mode) for managing clippings, settings, and SD fonts.
  - Over-the-air (OTA) firmware updates from [GitHub Releases](https://github.com/scheblein/ink-bible/releases) or SD card `.bin` updates.

---

## Quick Controls Reference (Xteink X3 / X4)

| Action | Button / Gesture |
| --- | --- |
| **Next / Previous Page** | Down / Up side buttons (or Front Right / Left if set to Page turn) |
| **Select Footnotes on Page** | Front Left / Right (default; configurable in Controls) |
| **Next / Previous Chapter** | Long-press Next / Previous Page |
| **Go to Passage (`Book → Chapter → Verse`)** | Short-press **Confirm** (or Reader Menu → **Go to Passage**) |
| **Reader Menu** | Long-press **Confirm** |
| **Bookmarks (Hop Between Passages)** | Short-press **Back** (or Reader Menu → **Bookmarks**) |
| **Toggle Bookmark** | Long-press **Back** (or Reader Menu → **Toggle Bookmark**) |
| **Switch Bible (SD File Browser)** | Reader Menu → **Switch Bible** (or hold **Back** during power-on boot) |
| **Return from Footnote** | Short-press **Back** while viewing a footnote |
| **Sleep / Wake** | Long-press **Power** |

---

## Installing Ink Bible

### Option 1: Build & Flash via PlatformIO (Recommended for Developers)

1. Clone the repository with submodules:
   ```bash
   git clone --recursive https://github.com/scheblein/ink-bible.git
   cd ink-bible
   ```
2. Wake your X3/X4 so it is on the reading screen and connect it via USB-C.
3. Build and upload:
   ```bash
   pio run -e default -t upload
   ```
   *(During the build, `scripts/generate_net_bible_epub.py` automatically downloads and caches the official NET Bible USFM archive from eBible.org and generates the flash-embedded C++ chapter tables.)*

### Option 2: Flash a Prebuilt Release Binary (`esptool`)

1. Download `ink-bible-<version>-x3-x4.bin` from [GitHub Releases](https://github.com/scheblein/ink-bible/releases).
2. Wake your X3/X4 and connect it via USB-C.
3. Flash at offset `0x10000`:
   ```bash
   pip install esptool
   esptool.py --chip esp32c3 --baud 921600 write_flash 0x10000 ink-bible-<version>-x3-x4.bin
   ```

> **Note on USB-Locked Third-Party Xteink Devices:**
> Units purchased directly from `xteink.com` are unlocked. Some units purchased from third-party resellers (e.g. AliExpress) ship with USB flashing locked; see [CrossPoint's Unlocker Tool](https://crosspointreader.com/#unlock-tool) before flashing if your device does not appear as a USB serial port when awake.

---

## Generating a Standalone `bible.epub` (Optional)

Although the NET Bible is embedded directly in the firmware flash, you can also generate a standalone `bible.epub` archive at any time:

```bash
python3 scripts/generate_net_bible_epub.py -o bible.epub
```

---

## Development & Verification

### Prerequisites

- [pioarduino PlatformIO Core](https://github.com/pioarduino/platformio-core)
- Python 3.8+
- `clang-format`
- CMake & Ninja (for host unit tests)

### Running Checks & Tests

```bash
# Format C/C++ sources
./bin/clang-format-fix -g

# Static analysis
pio check --skip-packages -e default --fail-on-defect=medium --fail-on-defect=high

# Host unit tests
cmake -S test -B build/test -GNinja
cmake --build build/test
ctest --test-dir build/test --output-on-failure

# Build X3/X4 firmware binary
pio run -e default
```

---

## Documentation

- [User Guide](./USER_GUIDE.md)
- [Web Server Guide](./docs/webserver.md)
- [SD Card Fonts Guide](./docs/sd-card-fonts.md)
- [File Formats & Cache Structure](./docs/file-formats.md)

---

## License & Acknowledgments

- **Firmware Code**: MIT License (`LICENSE`). Built on [CrossPoint Reader](https://github.com/crosspoint-reader/crosspoint-reader) and the [FreeInk SDK](https://freeink.org).
- **Scripture Text**: NET Bible® copyright © 1996–2016 by Biblical Studies Press, L.L.C. (https://netbible.com). All rights reserved. Used in accordance with Biblical Studies Press's free ministry/non-commercial distribution terms.
