#include "NetBibleData.h"

#include <InflateStream.h>
#include <Logging.h>

#include <algorithm>
#include <cstdlib>
#include <cstring>

#include "BibleCanon.h"

namespace NetBibleData {

int parseChapterSpineIndex(std::string_view href) {
  const size_t slash = href.rfind('/');
  if (slash != std::string_view::npos) {
    href.remove_prefix(slash + 1);
  }
  // Expected format: "B01_C001.xhtml" (14 chars)
  if (href.size() != 14 || href[0] != 'B' || href[3] != '_' || href[4] != 'C' ||
      href.substr(8) != ".xhtml") {
    return -1;
  }
  const auto isDigit = [](const char c) { return c >= '0' && c <= '9'; };
  if (!isDigit(href[1]) || !isDigit(href[2]) || !isDigit(href[5]) || !isDigit(href[6]) || !isDigit(href[7])) {
    return -1;
  }
  const int bookNum = (href[1] - '0') * 10 + (href[2] - '0');
  const int chapNum = (href[5] - '0') * 100 + (href[6] - '0') * 10 + (href[7] - '0');
  if (bookNum < 1 || bookNum > BibleCanon::BOOK_COUNT) return -1;
  const int bookIdx = bookNum - 1;
  if (chapNum < 1 || chapNum > BibleCanon::BOOKS[bookIdx].chapterCount) return -1;
  return BibleCanon::getSpineIndex(bookIdx, chapNum);
}

bool getEmbeddedItemSize(std::string_view href, size_t* outSize) {
  if (href == "OEBPS/style.css" || href == "style.css") {
    if (outSize) *outSize = STYLE_CSS_LEN;
    return true;
  }
  const int spineIndex = parseChapterSpineIndex(href);
  if (spineIndex < 0 || spineIndex >= TOTAL_CHAPTERS) return false;
  if (outSize) *outSize = CHAPTER_UNCOMPRESSED_SIZES[spineIndex];
  return true;
}

bool streamEmbeddedItem(std::string_view href, Print& out) {
  if (href == "OEBPS/style.css" || href == "style.css") {
    return out.write(reinterpret_cast<const uint8_t*>(STYLE_CSS), STYLE_CSS_LEN) == STYLE_CSS_LEN;
  }

  const int spineIndex = parseChapterSpineIndex(href);
  if (spineIndex < 0 || spineIndex >= TOTAL_CHAPTERS) {
    LOG_ERR("BIBLE", "Unknown embedded chapter href: %.*s", static_cast<int>(href.size()), href.data());
    return false;
  }

  const int groupIndex = spineIndex / GROUP_SIZE;
  const int firstSpineInGroup = groupIndex * GROUP_SIZE;
  size_t skipBytes = 0;
  for (int i = firstSpineInGroup; i < spineIndex; ++i) {
    skipBytes += CHAPTER_UNCOMPRESSED_SIZES[i];
  }
  const size_t targetBytes = CHAPTER_UNCOMPRESSED_SIZES[spineIndex];
  const uint32_t compStart = GROUP_COMPRESSED_OFFSETS[groupIndex];
  const uint32_t compEnd = GROUP_COMPRESSED_OFFSETS[groupIndex + 1];

  InflateStream inflate;
  if (!inflate.init(/*streaming=*/true)) {
    LOG_ERR("BIBLE", "Failed to init InflateStream for chapter %d", spineIndex);
    return false;
  }
  inflate.setSource(COMPRESSED_CHAPTERS_BLOB + compStart, compEnd - compStart);

  constexpr size_t CHUNK_SIZE = 2048;
  auto* chunkBuf = static_cast<uint8_t*>(malloc(CHUNK_SIZE));
  if (!chunkBuf) {
    LOG_ERR("BIBLE", "OOM: chapter inflate chunk buffer");
    return false;
  }

  size_t remainingSkip = skipBytes;
  while (remainingSkip > 0) {
    size_t produced = 0;
    const size_t ask = std::min(remainingSkip, CHUNK_SIZE);
    const auto status = inflate.readAtMost(chunkBuf, ask, &produced);
    if (status == InflateStream::Status::Error || produced == 0) {
      LOG_ERR("BIBLE", "Inflate skip failed at chapter %d", spineIndex);
      free(chunkBuf);
      return false;
    }
    remainingSkip -= produced;
  }

  size_t remainingWrite = targetBytes;
  while (remainingWrite > 0) {
    size_t produced = 0;
    const size_t ask = std::min(remainingWrite, CHUNK_SIZE);
    const auto status = inflate.readAtMost(chunkBuf, ask, &produced);
    if (status == InflateStream::Status::Error || produced == 0) {
      LOG_ERR("BIBLE", "Inflate read failed at chapter %d", spineIndex);
      free(chunkBuf);
      return false;
    }
    if (out.write(chunkBuf, produced) != produced) {
      LOG_ERR("BIBLE", "Failed writing inflated chapter %d to stream", spineIndex);
      free(chunkBuf);
      return false;
    }
    remainingWrite -= produced;
  }

  free(chunkBuf);
  return true;
}

}  // namespace NetBibleData
