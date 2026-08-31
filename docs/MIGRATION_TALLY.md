# Ink Bible Customization & Upstream Sync Guide

This document maintains the canonical record of all customizations, architectural adjustments, and brand migrations in this repository relative to upstream [`crosspoint-reader/crosspoint-reader`](https://github.com/crosspoint-reader/crosspoint-reader), as well as the step-by-step guide for pulling in new upstream releases (e.g. `1.6.0`).

---

## 1. Fork Baseline & Current Commit Structure

- **Upstream Base Tag**: [`v1.5.0`](https://github.com/crosspoint-reader/crosspoint-reader/releases/tag/v1.5.0) ([`e00f5958dfeea2a3e640c39eb78186fd20996f4b`](https://github.com/crosspoint-reader/crosspoint-reader/commit/e00f5958dfeea2a3e640c39eb78186fd20996f4b))
- **Custom Commits on Top**: Exactly 1 clean, unified atomic commit:
  1. `feat: initialize Ink Bible fork with rebrand, SD migration, CI/CD, and docs` *(All source rebranding, SD paths, Web UI, translations, logo, SD migration, workflows, documentation, AGENTS.md, and skills)*

---

## 2. The Clean Desired Net State

### A. Storage & Paths (`/.crosspoint` $\rightarrow$ `/.inkbible`)
| Component / File | Purpose / Change |
|---|---|
| `lib/Serialization/PersistableStore.h` & `.cpp` | Base directory `DEFAULT_PERSISTABLE_STORE_DIR` changed to `"/.inkbible/"` |
| `lib/KOReaderSync/KOReaderCredentialStore.h` & `.cpp` | Credentials stored at `/.inkbible/koreader_credentials.json` |
| `lib/KOReaderSync/KOReaderSyncClient.cpp` | Progress stored at `/.inkbible/koreader_progress.json` |
| `src/CrossPointSettings.h` | Settings file path: `/.inkbible/settings.json` |
| `src/CrossPointState.h` | State file path: `/.inkbible/state.json` |
| `src/OpdsServerStore.h` | OPDS servers path: `/.inkbible/opds_servers.json` |
| `src/WifiCredentialStore.h` | Wi-Fi credentials path: `/.inkbible/wifi_credentials.json` |
| `src/RecentBooksStore.h` & `.cpp` | Recent books list: `/.inkbible/recent_books.json` |
| `src/util/BookCacheUtils.cpp` | Book render caches: `/.inkbible/cache/` |
| `src/util/BookmarkFile.cpp` & `BookmarkUtil.cpp` | User bookmarks: `/.inkbible/bookmarks/` |
| `src/util/Dictionary.cpp` | Dictionary temp & index: `/.inkbible/dict.tmp` and `/.inkbible/dict_cache/` |
| `src/activities/boot_sleep/SleepActivity.cpp` | Custom sleep covers: `/.inkbible/sleep_covers/` |
| `src/activities/reader/ReaderActivity.cpp` | Cover caches: `/.inkbible/covers/` & `/.inkbible/sleep_covers/` |
| `src/activities/home/HomeActivity.cpp` | Cover cache: `/.inkbible/covers/` |
| `src/activities/settings/ClearCacheActivity.cpp` | Cache purge targeting `/.inkbible/cache/` |
| `src/main.cpp` | Automatic boot migration: migrates legacy `/.crosspoint` to `/.inkbible` if detected |
| `src/network/*` | Web server, downloaders, and OTA updaters targeting `/.inkbible/` |

> [!NOTE]
> Internal C++ class names (such as `CrossPointSettings`, `CrossPointState`, `CrossPointWebServer`) are intentionally preserved to ensure painless upstream mergeability.

### B. Logo & Visual Branding
| File | Change |
|---|---|
| `src/images/Logo120.h` | Ink Bible 120×120 bitmap (`logo120Data`) |
| `src/main.cpp` | Serial startup banner: `=== Ink Bible Startup ===` & `"Starting Ink Bible version "` |
| `src/network/WebDAVHandler.cpp` | Header `"Ink Bible WebDAV Server"` and XML owner `<D:owner><D:href>inkbible</D:href></D:owner>` |
| `src/network/html/*.html` | Web portal page titles, headers, and footer brand labels |

### C. Localization
In all 31 YAML files under `lib/I18n/translations/`:
- `STR_CROSSPOINT: "CrossPoint"` $\rightarrow$ `STR_CROSSPOINT: "Ink Bible"`

### D. CI/CD & Governance
- `.github/workflows/ci.yml`, `release.yml`, `release_candidate.yml`: Artifact naming (`inkbible-*.bin`) and build checks.
- `.github/ISSUE_TEMPLATE/*` & `PULL_REQUEST_TEMPLATE.md`: Ink Bible templates.
- `AGENTS.md` & `.skills/*`: Memory discipline (380KB RAM ceiling on ESP32-C3) and embedded architecture rules.

---

## 3. How to Sync When Upstream Cuts a New Release (e.g. `1.6.0`)

When upstream publishes a new official release tag (e.g. `1.6.0`), follow this workflow to replay your customizations on top of the new upstream baseline:

```bash
# 1. Ensure working directory is clean
git status

# 2. Fetch latest tags and commits from upstream
git fetch upstream --tags

# 3. Rebase Ink Bible commits onto the new release tag
# Format: git rebase --onto <NEW_UPSTREAM_TAG> <OLD_UPSTREAM_TAG> develop
git rebase --onto 1.6.0 v1.5.0 develop

# 4. If any file has a merge conflict (e.g. upstream modified a path or HTML string):
# - Check status: git status
# - Keep .inkbible paths where appropriate
# - Stage resolved file: git add <resolved_file>
# - Continue rebase: git rebase --continue

# 5. Build and verify the firmware
pio run

# 6. Align master and push cleanly to origin
git branch -f master develop
git push origin develop master --force
```

---

## 4. Disaster Recovery: One-Shot Fresh Fork Recipe

If you ever need to recreate the fork from scratch against upstream:

```bash
# 1. Clone fresh upstream and set remotes
git clone https://github.com/crosspoint-reader/crosspoint-reader.git ink-bible
cd ink-bible
git remote rename origin upstream
git remote add origin https://github.com/scheblein/ink-bible.git

# 2. Copy over non-code assets and configs from ink-bible:
# - src/images/Logo120.h
# - AGENTS.md, .skills/, and docs/
# - README.md, USER_GUIDE.md, and GOVERNANCE.md
# - .github/ workflows and issue templates

# 3. Apply path migrations:
find src lib -type f \( -name "*.cpp" -o -name "*.h" \) -exec sed -i '' 's/\/\.crosspoint/\/\.inkbible/g' {} +

# 4. Update translations:
find lib/I18n/translations -type f -name "*.yaml" -exec sed -i '' 's/STR_CROSSPOINT: "CrossPoint"/STR_CROSSPOINT: "Ink Bible"/g' {} +

# 5. Update Web HTML and WebDAV strings:
find src/network -type f \( -name "*.html" -o -name "*.cpp" \) -exec sed -i '' 's/CrossPoint/Ink Bible/g' {} +

# 6. Add boot migration check in src/main.cpp setup()
# 7. Commit in 2 atomic commits and push
```
