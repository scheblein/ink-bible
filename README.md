# Ink Bible

**Ink Bible** is an open-source, distraction-free Bible e-reader firmware crafted specifically for the **Xteink X3** (and compatible ESP32-C3 e-paper devices).

Designed from the ground up for focused Scripture reading and personal study on monochrome E-Ink displays, Ink Bible delivers instant navigation, crisp typography, and weeks of battery life on ultra-low-power hardware.

---

## Key Features

- **Built for Scripture Reading**: Fast chapter and passage navigation, smooth page caching, and reading progress tracking.
- **Deep Study Tools**: Offline dictionary lookup (StarDict format) for quick cross-referencing and definitions.
- **Personal Annotations**: Bookmark verses and key passages with on-device management.
- **Custom Typography**: Embedded high-legibility fonts (Noto Serif, Noto Sans) plus support for custom fonts (`.cpfont`) loaded directly from the SD card.
- **Hardware-Tailored for Xteink X3**:
  - Crisp monochrome rendering tuned for the 528×792 e-paper display.
  - Gyroscope tilt-to-turn-page support and customizable button mappings.
  - Efficient power management with deep sleep and instant resume.
- **Effortless Transfers**:
  - **WiFi Web Manager**: Connect to the local web interface (`http://inkbible.local/`) over your home network or via the device's built-in Access Point to manage files wirelessly.
  - **USB Mass Storage**: Drag and drop texts directly over USB.

---

## SD Card Setup

Ink Bible uses a standard FAT32 micro SD card for books, dictionaries, fonts, and cached data:

```text
SD Card Root/
├── .inkbible/           # System directory (settings, state, bookmarks, caches)
│   ├── settings.json    # Device preferences
│   ├── state.json       # Resume position & runtime state
│   ├── recent.json      # Reading history
│   └── bookmarks/       # Saved bookmarks
├── books/               # Place your Bibles and reading materials here
├── dict/                # StarDict offline dictionary files (.dict.dz, .idx)
└── fonts/               # Custom .cpfont files organized by family folder
```

---

## Installation & Flashing

### 1. Web Flasher / Pre-built Binaries

1. Connect your **Xteink X3** to your computer via USB-C.
2. Download `firmware.bin` from the latest release.
3. Flash the binary to flash address `0x10000` using your preferred ESP32 web flasher or CLI tool.

### 2. Command Line (`esptool.py`)

Install `esptool`:

```bash
pip install esptool
```

Flash the firmware:

```bash
esptool.py --chip esp32c3 --port /dev/ttyACM0 --baud 921600 write_flash 0x10000 firmware.bin
```

*(Adjust `/dev/ttyACM0` or `COMx` to match your system's serial port.)*

---

## Development

### Prerequisites

- [PlatformIO CLI](https://platformio.org/) or VS Code with the PlatformIO extension
- Python 3.8+
- USB-C data cable

### Building from Source

Clone the repository:

```bash
git clone https://github.com/scheblein/ink-bible.git
cd ink-bible
```

Build the firmware:

```bash
pio run -e default
```

Build and flash directly to a connected device:

```bash
pio run -e default -t upload
```

Monitor serial output:

```bash
pio device monitor -b 115200
```

---

## License & Attribution

Ink Bible is open-source software released under the [MIT License](LICENSE).

Copyright (c) 2025 Dave Allie  
Copyright (c) 2026 Adam Scheblein

Ink Bible is forked from the [CrossPoint Reader](https://github.com/crosspoint-reader/crosspoint-reader) project under the MIT License.
