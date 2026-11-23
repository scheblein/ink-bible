#pragma once

#include <I18n.h>

#include <cstring>

#include "CrossPointSettings.h"

namespace home_button {
struct ActionOption {
  StrId label;
  HomeButtonAction action;
};

inline constexpr ActionOption ACTION_OPTIONS[] = {
    {StrId::STR_HOME_SHORTCUT, HomeButtonAction::Home},
    {StrId::STR_IGNORE, HomeButtonAction::Ignore},
    {StrId::STR_PAGE_TURN, HomeButtonAction::NextPage},
    {StrId::STR_FORCE_REFRESH, HomeButtonAction::Refresh},
    {StrId::STR_FOOTNOTES, HomeButtonAction::Footnotes},
    {StrId::STR_CONFIRM, HomeButtonAction::Confirm},
    {StrId::STR_BOOKMARK_OPTION, HomeButtonAction::Bookmark},
    {StrId::STR_READER_MENU, HomeButtonAction::ReaderMenu},
    {StrId::STR_TOGGLE_FRONTLIGHT, HomeButtonAction::ToggleFrontlight},
    {StrId::STR_SAVE_CLIPPING, HomeButtonAction::CreateClipping},
};
inline constexpr size_t ACTION_OPTION_COUNT = sizeof(ACTION_OPTIONS) / sizeof(ACTION_OPTIONS[0]);

inline constexpr StrId ACTION_LABELS[ACTION_OPTION_COUNT] = {
    StrId::STR_HOME_SHORTCUT,     StrId::STR_IGNORE,        StrId::STR_PAGE_TURN,       StrId::STR_FORCE_REFRESH,
    StrId::STR_FOOTNOTES,         StrId::STR_CONFIRM,       StrId::STR_BOOKMARK_OPTION, StrId::STR_READER_MENU,
    StrId::STR_TOGGLE_FRONTLIGHT, StrId::STR_SAVE_CLIPPING,
};

constexpr bool labelsMatchOptions() {
  for (size_t i = 0; i < ACTION_OPTION_COUNT; ++i) {
    if (ACTION_LABELS[i] != ACTION_OPTIONS[i].label) return false;
  }
  return true;
}
static_assert(labelsMatchOptions());

inline int displayIndexForAction(const uint8_t rawAction) {
  for (size_t i = 0; i < ACTION_OPTION_COUNT; ++i) {
    if (static_cast<uint8_t>(ACTION_OPTIONS[i].action) == rawAction) return static_cast<int>(i);
  }
  return 0;  // Home
}

inline uint8_t actionForDisplayIndex(const int displayIndex) {
  if (displayIndex < 0 || static_cast<size_t>(displayIndex) >= ACTION_OPTION_COUNT) {
    return static_cast<uint8_t>(HomeButtonAction::Home);
  }
  return static_cast<uint8_t>(ACTION_OPTIONS[displayIndex].action);
}

inline constexpr StrId GESTURE_LABELS[] = {StrId::STR_HOME_BUTTON_TAP, StrId::STR_HOME_BUTTON_DOUBLE_TAP,
                                           StrId::STR_HOME_BUTTON_LONG_PRESS};
inline constexpr uint8_t CrossPointSettings::* FIELDS[] = {&CrossPointSettings::homeButtonTapAction,
                                                           &CrossPointSettings::homeButtonDoubleTapAction,
                                                           &CrossPointSettings::homeButtonLongPressAction};
inline constexpr const char* KEYS[] = {"homeButtonTapAction", "homeButtonDoubleTapAction", "homeButtonLongPressAction"};
inline bool isSetting(uint8_t CrossPointSettings::* field) {
  return field == FIELDS[0] || field == FIELDS[1] || field == FIELDS[2];
}
inline bool isSettingKey(const char* key) {
  if (!key) return false;
  for (const char* k : KEYS) {
    if (std::strcmp(key, k) == 0) return true;
  }
  return false;
}
}  // namespace home_button
