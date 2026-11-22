#pragma once

#include "activities/Activity.h"

// Paginated on-device quick-start and controls guide.
// In welcomeMode, opens on a one-page Quick Start card before the full guide;
// dismissing persists APP_STATE.welcomeShown and finishes back to goHome().
class UserGuideActivity final : public Activity {
 public:
  explicit UserGuideActivity(GfxRenderer& renderer, MappedInputManager& mappedInput, bool welcomeMode = false,
                             bool cleanInitialRefresh = false);

  void onEnter() override;
  void loop() override;
  void render(RenderLock&& lock) override;
  bool handleHomeGesture() override;

 private:
  void dismiss();
  int pageCount() const;
  void drawBody(int x, int y, int maxWidth, int maxY, const char* text) const;

  const bool welcomeMode;
  bool cleanInitialRefresh;
  int currentPage = 0;
};
