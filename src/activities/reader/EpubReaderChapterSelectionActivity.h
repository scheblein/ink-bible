#pragma once
#include <Epub.h>

#include <memory>
#include <string>

#include "activities/UiListActivity.h"

class EpubReaderChapterSelectionActivity final : public UiListActivity {
  enum class BibleStage : uint8_t { Book, Chapter, Verse };

  std::shared_ptr<Epub> epub;
  int currentTocIndex = 0;
  bool bibleMode = false;
  BibleStage bibleStage = BibleStage::Book;
  int selectedBookIndex = 0;
  int selectedChapterNumber = 1;
  int initialChapterNumber = 1;

  // Scratch buffers for rowProvider in Bible mode (only one row is formatted at a time).
  char rowLabelBuf[32]{};
  char rowValueBuf[16]{};
  static void provideBibleRow(void* ctx, uint16_t index, freeink::ui::ListItem& item);

  // Windowed row buffers: TOC entries are SD-backed (BookMetadataCache LUT
  // reads), so only the rows around the viewport are materialized. A
  // several-hundred-entry TOC (547 in a large collection) built up front cost
  // ~60KB of labels + ListItems — starving the CJK glyph arena into
  // SD-per-repaint — for rows that were never drawn. The window follows
  // nav.top via itemsWindowFirst (see fui::ListProps); refreshing it also
  // batch-prewarms the window's fallback glyphs, so each page of the list
  // pays one bounded SD pass and repaints stay RAM-only.
  static constexpr int TOC_WINDOW = 24;
  std::string windowLabels[TOC_WINDOW];
  freeink::ui::ListItem windowItems[TOC_WINDOW];
  int windowStart = -1;
  int windowCount = 0;
  void refreshTocWindow(int start);

  // Total items count for the active stage / TOC
  int listCount() const override;
  void buildScreen(UiScreen& screen) override;
  void activateIndex(int index) override;
  // Back cancels with a result (or steps back a stage in Bible mode) and
  // Confirm activates on RELEASE here, and a missing epub swallows everything past Back.
  bool handleButtons() override;
  // Header is drawn inside the safe area (not full-width like the base).
  void drawChrome() override;

 public:
  explicit EpubReaderChapterSelectionActivity(GfxRenderer& renderer, MappedInputManager& mappedInput,
                                              const std::shared_ptr<Epub>& epub, int currentTocIndex);
  void onEnter() override;
};
