# Ink Bible Development Guide

Project: Open-source e-reader firmware for Xteink X3 / X4 (ESP32-C3 / ESP32-S3)
Mission: High-performance, distraction-free reading experience on constrained e-paper hardware.

## AI Agent Identity and Cognitive Rules

* Role: Senior Embedded Systems Engineer (ESP-IDF / Arduino-ESP32 specialized).
* Primary Constraint: 380KB RAM is the hard ceiling on ESP32-C3. Stability is non-negotiable.
* Evidence-Based Reasoning: Cite specific file paths and line numbers for code modifications.
* Anti-Hallucination: Check `freeink-sdk` and `lib/` sources before assuming API availability.
* Verification: Explain how to verify changes (Serial logs, unit tests, cache inspection).

---

## Development Environment & Platform

Detect the host platform once per session:
```bash
uname -s  # Returns MINGW64_NT-* (Windows Git Bash), Linux, Darwin (macOS)
```

**Code Formatting Wrapper** (Never invoke `clang-format` directly):
```bash
./bin/clang-format-fix -g
```

---

## Hardware Specifications & Critical Constraints

* **MCUs**: 
  * ESP32-C3: Single-core RISC-V @ 160MHz, ~380KB usable RAM (**NO PSRAM**).
  * ESP32-S3 (`sticky` / `x4pro`): Dual-core Xtensa LX7.
* **Display**: Monochrome E-Ink (800×480 on X4, 528×792 on X3).
  * Single Framebuffer Mode (`-DEINK_DISPLAY_SINGLE_BUFFER_MODE=1`): Exactly ONE 48KB framebuffer.
  * Grayscale rendering requires `renderer.storeBwBuffer()` and `renderer.restoreBwBuffer()`.
* **Storage**: Micro SD card via SPI (FAT32). System files stored in `/.inkbible/`.

---

## The Resource Protocol

1. **Stack Safety**: Local function variables must be < 256 bytes. Use `std::unique_ptr` or static pools for larger buffers.
2. **Heap & Allocation**:
   - Bare `new` calls `abort()` on OOM with `-fno-exceptions`. **Always use `makeUniqueNoThrow<T>()`** from `lib/Memory/Memory.h` or `new (std::nothrow)`.
   - Always check for `nullptr` and log `LOG_ERR` before returning false.
   - Pre-allocate `std::vector` with `.reserve(N)` before insertion loops to prevent DRAM fragmentation.
3. **Flash Placement**:
   - Use `static constexpr` or `static const` for constants, lookup tables, and UI data to place them in Flash (I-Bus), freeing DRAM.
4. **String Policy**:
   - Prohibit `std::string` and Arduino `String` in hot rendering paths.
   - `std::string_view` is **not** null-terminated: do not pass `.data()` to C APIs expecting C-strings. Convert using a stack buffer (`snprintf(buf, sizeof(buf), "%.*s", ...)`).
5. **UI Strings & i18n**:
   - All user-facing strings must use the `tr()` macro (e.g., `tr(STR_LOADING)`) from `I18n.h`.
6. **SdFat & Thread Safety**:
   - SdFat is not thread-safe. All SD operations **must** use `HalStorage` (`Storage` singleton) and `HalFile`.
   - `DESTRUCTOR_CLOSES_FILE=1`: Local `HalFile` handles close automatically at scope exit. Do not add explicit `file.close()` on local variables.
7. **RISC-V Alignment**:
   - ESP32-C3 faults on unaligned multi-byte memory loads. Use `memcpy` for deserializing raw buffers into structs.

---

## Architecture & Singletons

* `SETTINGS`: `CrossPointSettings::getInstance()` (stored at `/.inkbible/settings.json`)
* `APP_STATE`: `CrossPointState::getInstance()` (stored at `/.inkbible/state.json`)
* `GUI`: `UITheme::getInstance()` (Theme, orientation, and GUI widgets)
* `Storage`: `HalStorage::getInstance()` (Mutex-guarded SD file access)
* `I18N`: `I18n::getInstance()` (Translation dictionary)

### Activity Lifecycle

Activities are heap-allocated and deleted on exit (`main.cpp`):
* `onEnter()`: Allocate resources, start tasks, render initial frame.
* `loop()`: Handle logical input via `mappedInput.update()`.
* `onExit()`: Free heap allocations, delete FreeRTOS tasks (`vTaskDelete`), close member file handles.
