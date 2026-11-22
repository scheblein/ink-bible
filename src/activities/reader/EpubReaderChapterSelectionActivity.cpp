#include "EpubReaderChapterSelectionActivity.h"

#include <BibleCanon.h>
#include <FontCacheManager.h>
#include <GfxRenderer.h>
#include <I18n.h>

#include <cstdio>
#include <string>

#include "MappedInputManager.h"
#include "components/UIScale.h"
#include "components/UITheme.h"

namespace fui = freeink::ui;

EpubReaderChapterSelectionActivity::EpubReaderChapterSelectionActivity(GfxRenderer& renderer,
                                                                       MappedInputManager& mappedInput,
                                                                       const std::shared_ptr<Epub>& epub,
                                                                       const int currentTocIndex)
    : UiListActivity("EpubReaderChapterSelection", renderer, mappedInput),
      epub(epub),
      currentTocIndex(currentTocIndex),
      bibleMode(epub && epub->getSpineItemsCount() == BibleCanon::TOTAL_CHAPTER_COUNT) {}

void EpubReaderChapterSelectionActivity::onEnter() {
  UiListActivity::onEnter();

  // The reader underneath pins its page-render glyph arenas while this
  // overlay is up. clearCache() is heap-adaptive: below the retention floor
  // it frees them (the next page render's PrewarmScope rebuilds them at
  // normal page-turn cost), giving this list room to keep every row's
  // fallback glyphs resident — otherwise each repaint re-reads the visible
  // rows' glyphs from SD.
  if (auto* fcm = renderer.getFontCacheManager()) {
    fcm->clearCache();
  }

  if (!epub) {
    return;
  }

  if (bibleMode) {
    BibleCanon::resolveSpineIndex(currentTocIndex, selectedBookIndex, initialChapterNumber);
    selectedChapterNumber = initialChapterNumber;
    bibleStage = BibleStage::Book;
    nav.reset(selectedBookIndex);
    return;
  }

  // Start with the current chapter at the top of the viewport; the first
  // screen build pulls the viewport to it (ListNav follow-on-build) and
  // materializes the row window there (refreshTocWindow in buildScreen).
  nav.selected = currentTocIndex;
}

int EpubReaderChapterSelectionActivity::listCount() const {
  if (!epub) return 0;
  if (!bibleMode) return epub->getTocItemsCount();
  switch (bibleStage) {
    case BibleStage::Book:
      return BibleCanon::BOOK_COUNT;
    case BibleStage::Chapter:
      return (selectedBookIndex >= 0 && selectedBookIndex < BibleCanon::BOOK_COUNT)
                 ? BibleCanon::BOOKS[selectedBookIndex].chapterCount
                 : 0;
    case BibleStage::Verse:
      return BibleCanon::getVerseCount(selectedBookIndex, selectedChapterNumber);
  }
  return 0;
}

void EpubReaderChapterSelectionActivity::provideBibleRow(void* ctx, const uint16_t index, fui::ListItem& item) {
  auto* self = static_cast<EpubReaderChapterSelectionActivity*>(ctx);
  item.actionValue = static_cast<int16_t>(index);
  switch (self->bibleStage) {
    case BibleStage::Book: {
      if (index >= BibleCanon::BOOK_COUNT) return;
      const auto& book = BibleCanon::BOOKS[index];
      item.label = book.name;
      snprintf(self->rowValueBuf, sizeof(self->rowValueBuf), tr(STR_BIBLE_CHAPTER_COUNT_FORMAT),
               static_cast<unsigned>(book.chapterCount));
      item.value = self->rowValueBuf;
      return;
    }
    case BibleStage::Chapter:
      snprintf(self->rowLabelBuf, sizeof(self->rowLabelBuf), "%s %u", tr(STR_CHAPTER),
               static_cast<unsigned>(index + 1));
      item.label = self->rowLabelBuf;
      return;
    case BibleStage::Verse:
      snprintf(self->rowLabelBuf, sizeof(self->rowLabelBuf), "%s %u", tr(STR_VERSE), static_cast<unsigned>(index + 1));
      item.label = self->rowLabelBuf;
      return;
  }
}

// Materialize the ListItem/label window starting at `start` (clamped). TOC
// entries are SD LUT reads (getTocItem), so this runs only when the viewport
// leaves the current window. Finishes with a batch prewarm of the window's
// CJK fallback glyphs -- one bounded SD pass per list page; repaints inside
// the window stay RAM-only.
void EpubReaderChapterSelectionActivity::refreshTocWindow(const int start) {
  const int total = listCount();
  int clamped = start;
  if (clamped > total - TOC_WINDOW) clamped = total - TOC_WINDOW;
  if (clamped < 0) clamped = 0;
  if (clamped == windowStart) return;

  windowCount = total - clamped < TOC_WINDOW ? total - clamped : TOC_WINDOW;
  for (int i = 0; i < windowCount; i++) {
    const auto tocItem = epub->getTocItem(clamped + i);
    std::string indent(tocItem.level > 0 ? (tocItem.level - 1) * 2 : 0, ' ');
    windowLabels[i] = indent + tocItem.title;
    fui::ListItem item;
    item.label = windowLabels[i].c_str();
    item.actionValue = static_cast<int16_t>(clamped + i);
    windowItems[i] = item;
  }
  windowStart = clamped;

  struct PrewarmCtx {
    const std::string* labels;
    int count;
  } prewarmCtx{windowLabels, windowCount};
  renderer.prewarmFallbackText(
      uiScaleSpec().bodyFontId,
      [](const void* ctx, uint32_t i) -> const char* {
        const auto* c = static_cast<const PrewarmCtx*>(ctx);
        return i < static_cast<uint32_t>(c->count) ? c->labels[i].c_str() : nullptr;
      },
      &prewarmCtx, static_cast<uint32_t>(windowCount));
}

void EpubReaderChapterSelectionActivity::activateIndex(const int index) {
  if (index < 0 || index >= listCount()) {
    return;
  }
  // The activated row leaves this screen or stage; a lingering flash would gray
  // an unrelated element on the next render.
  app.clearTapFlash();
  nav.selected = index;

  if (bibleMode) {
    switch (bibleStage) {
      case BibleStage::Book: {
        {
          RenderLock lock(*this);
          closeRouting();
          const bool sameBook = (index == selectedBookIndex);
          selectedBookIndex = index;
          selectedChapterNumber = sameBook ? initialChapterNumber : 1;
          bibleStage = BibleStage::Chapter;
          nav.reset(selectedChapterNumber - 1);
        }
        requestUpdate();
        return;
      }
      case BibleStage::Chapter: {
        RenderLock lock(*this);
        closeRouting();
        selectedChapterNumber = index + 1;
        bibleStage = BibleStage::Verse;
        nav.reset(0);
      }
        requestUpdate();
        return;
      case BibleStage::Verse: {
        const int verseNumber = index + 1;
        const int targetSpine = BibleCanon::getSpineIndex(selectedBookIndex, selectedChapterNumber);
        std::string anchor;
        if (verseNumber > 1) {
          char anchorBuf[16];
          snprintf(anchorBuf, sizeof(anchorBuf), "v%d", verseNumber);
          anchor = anchorBuf;
        }
        setResult(ChapterResult{targetSpine, std::move(anchor)});
        finish();
        return;
      }
    }
  }

  const auto tocItem = epub->getTocItem(index);
  if (tocItem.spineIndex == -1) {
    ActivityResult result;
    result.isCancelled = true;
    setResult(std::move(result));
    finish();
  } else {
    setResult(ChapterResult{tocItem.spineIndex, tocItem.anchor});
    finish();
  }
}

bool EpubReaderChapterSelectionActivity::handleButtons() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    if (bibleMode) {
      switch (bibleStage) {
        case BibleStage::Verse: {
          RenderLock lock(*this);
          closeRouting();
          bibleStage = BibleStage::Chapter;
          nav.reset(selectedChapterNumber - 1);
        }
          requestUpdate();
          return true;
        case BibleStage::Chapter: {
          RenderLock lock(*this);
          closeRouting();
          bibleStage = BibleStage::Book;
          nav.reset(selectedBookIndex);
        }
          requestUpdate();
          return true;
        case BibleStage::Book:
          break;
      }
    }
    ActivityResult result;
    result.isCancelled = true;
    setResult(std::move(result));
    finish();
    return true;
  }

  if (!epub) {
    return true;
  }

  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    activateIndex(nav.selected);
    return true;
  }

  return false;
}

void EpubReaderChapterSelectionActivity::buildScreen(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  const Rect safe = UITheme::getInstance().getScreenSafeArea(renderer, true, false);
  // Content: the safe area minus the header band drawChrome paints the title in.
  screen.setContentMarginFromScreen(fui::Insets{
      static_cast<int16_t>(safe.y + metrics.topPadding + metrics.headerHeight),
      static_cast<int16_t>(renderer.getScreenWidth() - (safe.x + safe.width)),
      static_cast<int16_t>(renderer.getScreenHeight() - (safe.y + safe.height)), static_cast<int16_t>(safe.x)});
  screen.spacer(static_cast<int16_t>(metrics.verticalSpacing));

  if (!epub) {
    return;
  }
  if (listCount() == 0) {
    screen.centeredText(tr(STR_NO_CHAPTERS), screen.theme().bodyText);
    return;
  }

  fui::ListProps props;
  props.count = static_cast<uint16_t>(listCount());
  props.action = ACTION_ROW;
  props.inputMask = fui::InputTouch;  // physical buttons stay in loop()
  if (bibleMode) {
    props.rowProvider = &EpubReaderChapterSelectionActivity::provideBibleRow;
    props.rowProviderCtx = this;
    props.valueInset = 8;
    syncListViewport(screen, props);
    screen.list(props);
    return;
  }
  syncListViewport(screen, props);
  // Materialize the row window for the final viewport (syncListViewport just
  // applied follow/clamping to nav.top) and hand list() the window with its
  // absolute base index.
  refreshTocWindow(nav.top);
  props.items = windowItems;
  props.itemsWindowFirst = static_cast<uint16_t>(windowStart);
  screen.list(props);
}

void EpubReaderChapterSelectionActivity::drawChrome() {
  const Rect headerRect = UITheme::getInstance().getHeaderRect(renderer, true, false);
  if (!bibleMode) {
    GUI.drawHeader(renderer, headerRect, tr(STR_SELECT_CHAPTER));
    return;
  }
  switch (bibleStage) {
    case BibleStage::Book:
      GUI.drawHeader(renderer, headerRect, tr(STR_SELECT_BOOK));
      return;
    case BibleStage::Chapter:
      GUI.drawHeader(renderer, headerRect, BibleCanon::BOOKS[selectedBookIndex].name);
      return;
    case BibleStage::Verse: {
      char headerBuf[48];
      snprintf(headerBuf, sizeof(headerBuf), "%s %d", BibleCanon::BOOKS[selectedBookIndex].name, selectedChapterNumber);
      GUI.drawHeader(renderer, headerRect, headerBuf);
      return;
    }
  }
}
