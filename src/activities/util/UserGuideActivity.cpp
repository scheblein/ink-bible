#include "UserGuideActivity.h"

#include <GfxRenderer.h>
#include <HalDisplay.h>
#include <I18n.h>

#include <cstdio>
#include <cstring>

#include "CrossPointState.h"
#include "MappedInputManager.h"
#include "components/UITheme.h"
#include "fontIds.h"

namespace {

struct GuidePage {
  StrId titleId;
  StrId bodyId;
};

constexpr GuidePage WELCOME_PAGE = {StrId::STR_WELCOME_TITLE, StrId::STR_GUIDE_WELCOME_BODY};

constexpr GuidePage GUIDE_PAGES[] = {
    {StrId::STR_GUIDE_PAGE_CONTROLS, StrId::STR_GUIDE_CONTROLS_BODY},
    {StrId::STR_GUIDE_PAGE_FOOTNOTES, StrId::STR_GUIDE_FOOTNOTES_BODY},
    {StrId::STR_GUIDE_PAGE_CLIPPINGS, StrId::STR_GUIDE_CLIPPINGS_BODY},
    {StrId::STR_GUIDE_PAGE_TIPS, StrId::STR_GUIDE_TIPS_BODY},
};

constexpr int GUIDE_PAGE_COUNT = static_cast<int>(sizeof(GUIDE_PAGES) / sizeof(GUIDE_PAGES[0]));

// Returns the length of a short leading "Label:" prefix on a paragraph, or 0.
size_t findBoldPrefixLen(const char* p, size_t len) {
  constexpr size_t MAX_PREFIX = 32;
  const size_t limit = len < MAX_PREFIX ? len : MAX_PREFIX;
  for (size_t i = 0; i < limit; ++i) {
    if (p[i] == ':') {
      return i + 1;
    }
  }
  return 0;
}

}  // namespace

UserGuideActivity::UserGuideActivity(GfxRenderer& renderer, MappedInputManager& mappedInput, const bool welcomeMode,
                                     const bool cleanInitialRefresh)
    : Activity("UserGuide", renderer, mappedInput),
      welcomeMode(welcomeMode),
      cleanInitialRefresh(cleanInitialRefresh) {}

void UserGuideActivity::onEnter() {
  Activity::onEnter();
  currentPage = 0;
  requestUpdate();
}

int UserGuideActivity::pageCount() const { return welcomeMode ? (GUIDE_PAGE_COUNT + 1) : GUIDE_PAGE_COUNT; }

void UserGuideActivity::dismiss() {
  if (welcomeMode) {
    APP_STATE.welcomeShown = true;
    APP_STATE.saveToFile();
  }
  finish();
}

bool UserGuideActivity::handleHomeGesture() {
  dismiss();
  return true;
}

void UserGuideActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    dismiss();
    return;
  }

  const int total = pageCount();

  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    if (welcomeMode || currentPage + 1 >= total) {
      dismiss();
    } else {
      currentPage++;
      requestUpdate();
    }
    return;
  }

  bool prev = mappedInput.wasReleased(MappedInputManager::Button::ScreenLeft) ||
              mappedInput.wasReleased(MappedInputManager::Button::ScreenUp);
  bool next = mappedInput.wasReleased(MappedInputManager::Button::ScreenRight) ||
              mappedInput.wasReleased(MappedInputManager::Button::ScreenDown);

  if (!prev && !next && mappedInput.hasTouch()) {
    const auto swipe = mappedInput.wasSwipe();
    if (swipe == MappedInputManager::SwipeDir::Right) {
      prev = true;
    } else if (swipe == MappedInputManager::SwipeDir::Left) {
      next = true;
    } else {
      int touchX = 0;
      int touchY = 0;
      if (mappedInput.wasScreenTapped(touchX, touchY)) {
        const auto& metrics = UITheme::getInstance().getMetrics();
        const Rect safeArea = UITheme::getInstance().getScreenSafeArea(renderer, true, false);
        const int headerBottom = safeArea.y + metrics.topPadding + metrics.headerHeight;
        if (touchY >= headerBottom) {
          if (touchX < renderer.getScreenWidth() / 3) {
            prev = true;
          } else {
            next = true;
          }
        }
      }
    }
  }

  if (prev && currentPage > 0) {
    currentPage--;
    requestUpdate();
  } else if (next && currentPage + 1 < total) {
    currentPage++;
    requestUpdate();
  }
}

void UserGuideActivity::drawBody(const int x, int y, const int maxWidth, const int maxY, const char* text) const {
  if (!text || maxWidth <= 0) return;

  const int lineHeight = renderer.getLineHeight(UI_10_FONT_ID);
  const int lineStep = lineHeight + 4;
  const int paragraphGap = lineHeight / 2;
  const int spaceWidth = renderer.getSpaceWidth(UI_10_FONT_ID);

  // Share one 64-byte scratch buffer between prefix and word measurement to keep
  // total stack usage in this render frame under 256 bytes.
  char scratchBuf[64];
  char lineBuf[128];

  const char* p = text;
  while (*p != '\0' && y + lineHeight <= maxY) {
    const char* nl = std::strchr(p, '\n');
    const size_t paraLen = nl ? static_cast<size_t>(nl - p) : std::strlen(p);

    if (paraLen == 0) {
      y += paragraphGap;
      if (!nl) break;
      p = nl + 1;
      continue;
    }

    const char* cursor = p;
    const char* const paraEnd = p + paraLen;
    int curX = x;

    // Highlight short "Control:" prefixes in bold for scannability.
    const size_t prefixLen = findBoldPrefixLen(cursor, paraLen);
    if (prefixLen > 0 && prefixLen < sizeof(scratchBuf)) {
      std::memcpy(scratchBuf, cursor, prefixLen);
      scratchBuf[prefixLen] = '\0';
      const int prefixW = renderer.getTextWidth(UI_10_FONT_ID, scratchBuf, EpdFontFamily::BOLD);
      if (prefixW < maxWidth) {
        renderer.drawText(UI_10_FONT_ID, curX, y, scratchBuf, true, EpdFontFamily::BOLD);
        curX += prefixW;
        cursor += prefixLen;
        while (cursor < paraEnd && *cursor == ' ') {
          curX += spaceWidth;
          ++cursor;
        }
      }
    }

    size_t lineLen = 0;
    int lineWidth = 0;
    int lineStartX = curX;

    const auto flushLine = [&]() {
      if (lineLen > 0) {
        lineBuf[lineLen] = '\0';
        renderer.drawText(UI_10_FONT_ID, lineStartX, y, lineBuf, true, EpdFontFamily::REGULAR);
        lineLen = 0;
        lineWidth = 0;
      }
      y += lineStep;
      lineStartX = x;
    };

    while (cursor < paraEnd && y + lineHeight <= maxY) {
      while (cursor < paraEnd && *cursor == ' ') ++cursor;
      if (cursor >= paraEnd) break;

      const char* wordStart = cursor;
      while (cursor < paraEnd && *cursor != ' ') ++cursor;
      size_t wordLen = static_cast<size_t>(cursor - wordStart);
      if (wordLen >= sizeof(scratchBuf)) wordLen = sizeof(scratchBuf) - 1;

      std::memcpy(scratchBuf, wordStart, wordLen);
      scratchBuf[wordLen] = '\0';
      const int wordW = renderer.getTextWidth(UI_10_FONT_ID, scratchBuf, EpdFontFamily::REGULAR);
      const int availW = (x + maxWidth) - lineStartX;
      const int needW = (lineLen > 0 ? spaceWidth : 0) + wordW;

      if (lineLen > 0 && (lineWidth + needW > availW || lineLen + 1 + wordLen >= sizeof(lineBuf))) {
        flushLine();
        if (y + lineHeight > maxY) break;
      } else if (lineLen == 0 && lineStartX > x && wordW > availW) {
        // Bold prefix left too little room on the first line; start body on the next line.
        y += lineStep;
        lineStartX = x;
        if (y + lineHeight > maxY) break;
      }

      if (lineLen > 0) {
        lineBuf[lineLen++] = ' ';
        lineWidth += spaceWidth;
      }
      std::memcpy(lineBuf + lineLen, scratchBuf, wordLen);
      lineLen += wordLen;
      lineWidth += wordW;
    }

    if (y + lineHeight <= maxY) {
      flushLine();
    }

    if (!nl) break;
    p = nl + 1;
  }
}

void UserGuideActivity::render(RenderLock&&) {
  renderer.clearScreen();

  const int total = pageCount();
  const GuidePage& page = (welcomeMode && currentPage == 0)
                              ? WELCOME_PAGE
                              : GUIDE_PAGES[welcomeMode ? (currentPage - 1) : currentPage];

  const auto& metrics = UITheme::getInstance().getMetrics();
  const Rect headerRect = UITheme::getInstance().getHeaderRect(renderer, true, false);
  const Rect safeArea = UITheme::getInstance().getScreenSafeArea(renderer, true, false);

  char pageLabel[16];
  std::snprintf(pageLabel, sizeof(pageLabel), "%d / %d", currentPage + 1, total);
  GUI.drawHeader(renderer, headerRect, I18N.get(page.titleId), pageLabel);

  const int padX = metrics.contentSidePadding + 4;
  const int bodyX = safeArea.x + padX;
  const int bodyY = safeArea.y + metrics.topPadding + metrics.headerHeight + metrics.verticalSpacing + 4;
  const int bodyW = safeArea.width - padX * 2;
  const int bodyMaxY = safeArea.y + safeArea.height - 6;

  drawBody(bodyX, bodyY, bodyW, bodyMaxY, I18N.get(page.bodyId));

  const char* backLabel = welcomeMode ? tr(STR_GUIDE_READ) : tr(STR_BACK);
  const char* confirmLabel = welcomeMode ? tr(STR_GUIDE_READ)
                                         : (currentPage + 1 >= total ? tr(STR_GUIDE_DONE) : tr(STR_GUIDE_NEXT));
  const char* prevLabel = currentPage > 0 ? tr(STR_GUIDE_PREV) : "";
  const char* nextLabel = currentPage + 1 < total ? tr(STR_GUIDE_NEXT) : "";

  const auto labels =
      mappedInput.mapDirectionalLabels(backLabel, confirmLabel, prevLabel, nextLabel, prevLabel, nextLabel);
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);

  const auto refreshMode =
      cleanInitialRefresh ? HalDisplay::RefreshMode::HALF_REFRESH : HalDisplay::RefreshMode::FAST_REFRESH;
  cleanInitialRefresh = false;
  renderer.displayBuffer(refreshMode);
}
