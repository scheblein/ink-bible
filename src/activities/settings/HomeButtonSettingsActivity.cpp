#include "HomeButtonSettingsActivity.h"

#include <utility>

#include "components/UITheme.h"

namespace fui = freeink::ui;

bool HomeButtonSettingsActivity::handleCustomInput() {
  return optionPopup.handleInput(mappedInput, [this] { requestUpdate(); });
}

void HomeButtonSettingsActivity::activateIndex(int index) {
  if (index < 0 || index >= listCount() || optionPopup.isActive()) return;
  mappedInput.resetHomeButtonInput();
  app.clearTapFlash();
  nav.selected = index;
  const auto field = home_button::FIELDS[index];
  const int current = home_button::displayIndexForAction(SETTINGS.*field);
  optionPopup.show(home_button::GESTURE_LABELS[index], home_button::ACTION_LABELS,
                   static_cast<int>(home_button::ACTION_OPTION_COUNT), current, [field](int selected) {
                     SETTINGS.*field = home_button::actionForDisplayIndex(selected);
                     SETTINGS.saveToFile();
                   });
  requestUpdate();
}

void HomeButtonSettingsActivity::render(RenderLock&& lock) {
  if (optionPopup.processRender(renderer, mappedInput)) return;
  UiListActivity::render(std::move(lock));
}

void HomeButtonSettingsActivity::buildScreen(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  screen.setContentMarginFromScreen(fui::Insets{static_cast<int16_t>(metrics.topPadding + metrics.headerHeight), 0,
                                                static_cast<int16_t>(metrics.buttonHintsHeight), 0});
  screen.spacer(static_cast<int16_t>(metrics.verticalSpacing));
  for (int i = 0; i < listCount(); ++i) {
    rows[i].label = I18N.get(home_button::GESTURE_LABELS[i]);
    rows[i].actionValue = static_cast<int16_t>(i);
    const int displayIndex = home_button::displayIndexForAction(SETTINGS.*home_button::FIELDS[i]);
    rows[i].value = I18N.get(home_button::ACTION_LABELS[displayIndex]);
  }
  fui::ListProps props;
  props.items = rows;
  props.count = listCount();
  props.action = ACTION_ROW;
  props.inputMask = fui::InputTouch;
  // Keep the gesture name and its current action at the same visual weight.
  props.labelText = screen.theme().smallText;
  // A default smallText style is treated as inherited by screen.list().
  props.labelText.maxLines = 2;
  syncListViewport(screen, props);
  screen.list(props);
}
