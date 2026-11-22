#pragma once

#include <Print.h>

#include <cstddef>
#include <cstdint>
#include <string_view>

namespace NetBibleData {

inline constexpr int TOTAL_CHAPTERS = 1189;
inline constexpr int GROUP_SIZE = 16;
inline constexpr int GROUP_COUNT = (TOTAL_CHAPTERS + GROUP_SIZE - 1) / GROUP_SIZE;

extern const char STYLE_CSS[];
extern const size_t STYLE_CSS_LEN;
extern const uint16_t CHAPTER_UNCOMPRESSED_SIZES[TOTAL_CHAPTERS];
extern const uint32_t GROUP_COMPRESSED_OFFSETS[GROUP_COUNT + 1];
extern const uint8_t COMPRESSED_CHAPTERS_BLOB[];

// Parses a spine href of the form "OEBPS/B01_C001.xhtml" or "B01_C001.xhtml"
// into a 0..1188 spineIndex, or returns -1 if not a canonical chapter href.
int parseChapterSpineIndex(std::string_view href);

// Returns the uncompressed byte size of an embedded NET Bible item ("OEBPS/style.css" or chapter XHTML).
bool getEmbeddedItemSize(std::string_view href, size_t* outSize);

// Streams an embedded NET Bible item ("OEBPS/style.css" or chapter XHTML) from internal flash into `out`.
bool streamEmbeddedItem(std::string_view href, Print& out);

}  // namespace NetBibleData
