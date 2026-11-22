#!/usr/bin/env python3
"""
Generate a Bible EPUB (or embedded flash C++ data) optimized for the Ink Bible
firmware on CrossPoint Reader (Xteink X3/X4).

Supports multiple free/open Bible translations from eBible.org USFM archives,
with the NET Bible (New English Translation) as the default embedded firmware Bible:
- `net`: NET Bible (New English Translation) — default embedded in firmware
- `bsb`: Berean Standard Bible (Modern English, Public Domain / CC0, with full footnotes)
- `web`: World English Bible (Modern English, Public Domain, with translator notes)
- `kjv`: King James Version (Classic English, Public Domain)
- `asv`: American Standard Version (Classic English, Public Domain)

Each generated EPUB archive has:
- Each of the 1,189 canonical chapters as its own spine XHTML item
  (`B01_C001.xhtml` .. `B66_C022.xhtml`), matching the firmware's `BibleCanon`
  table (`chapterOffset + chapter - 1` -> `spineIndex 0 .. 1188`).
- Each verse beginning with `<b id="vM">M</b>` (recorded as a navigable anchor by
  the firmware parser for instant Book -> Chapter -> Verse lookup).
- USFM translator footnotes (`\\f ... \\f*`) emitted as linked EPUB footnotes
  (`<a href="#fnN">[N]</a>` + `<p id="fnN"><a href="#fnrefN"><b>[N]</b></a> ...</p>`)
  viewable via the firmware's Links & Footnotes feature.
"""

import argparse
import html
import io
import re
import sys
import urllib.request
import zipfile
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent if "__file__" in globals() else Path.cwd()
DEFAULT_OUTPUT = PROJECT_ROOT / "bible.epub"
DEFAULT_CPP_OUTPUT = PROJECT_ROOT / "lib" / "BibleCanon" / "NetBibleData.generated.cpp"
DEFAULT_HEADER_PATH = PROJECT_ROOT / "lib" / "BibleCanon" / "NetBibleData.h"
GROUP_SIZE = 16

BIBLE_VERSIONS = {
    "net": {
        "title": "NET Bible",
        "creator": "Biblical Studies Press",
        "rights": "NET Bible® copyright © 1996-2016 Biblical Studies Press, L.L.C.",
        "identifier": "ink-bible-net-v1",
        "url": "https://ebible.org/Scriptures/engnet_usfm.zip",
        "cache_name": "engnet_usfm.zip",
    },
    "bsb": {
        "title": "Berean Standard Bible (BSB)",
        "creator": "Berean Bible",
        "rights": "Public Domain (CC0 1.0 Universal)",
        "identifier": "ink-bible-bsb-v1",
        "url": "https://ebible.org/Scriptures/engbsb_usfm.zip",
        "cache_name": "engbsb_usfm.zip",
    },
    "web": {
        "title": "World English Bible (WEB)",
        "creator": "ebible.org",
        "rights": "Public Domain",
        "identifier": "ink-bible-web-v1",
        "url": "https://ebible.org/Scriptures/engwebp_usfm.zip",
        "cache_name": "engwebp_usfm.zip",
    },
    "kjv": {
        "title": "King James Version (KJV)",
        "creator": "Public Domain",
        "rights": "Public Domain",
        "identifier": "ink-bible-kjv-v1",
        "url": "https://ebible.org/Scriptures/eng-kjv2006_usfm.zip",
        "cache_name": "eng-kjv2006_usfm.zip",
    },
    "asv": {
        "title": "American Standard Version (ASV)",
        "creator": "Public Domain",
        "rights": "Public Domain",
        "identifier": "ink-bible-asv-v1",
        "url": "https://ebible.org/Scriptures/eng-asv_usfm.zip",
        "cache_name": "eng-asv_usfm.zip",
    },
}

# Standard 66-book Protestant canon USFM \id codes in canonical order (Genesis .. Revelation).
CANONICAL_USFM_IDS = [
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL",
    "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH",
    "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS",
    "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
]

CANONICAL_CHAPTER_COUNTS = [
    50, 40, 27, 36, 34, 24, 21, 4, 31, 24,
    22, 25, 29, 36, 10, 13, 10, 42, 150, 31,
    12, 8, 66, 52, 5, 48, 12, 14, 3, 9,
    1, 4, 7, 3, 3, 3, 2, 14, 4,
    28, 16, 24, 21, 28, 16, 16, 13, 6, 6,
    4, 4, 5, 3, 6, 4, 3, 1, 13, 5,
    5, 3, 5, 1, 1, 1, 22,
]

DEFAULT_CACHE_ZIP = PROJECT_ROOT / ".cache" / BIBLE_VERSIONS["net"]["cache_name"]

BIBLE_CSS = """\
body {
  line-height: 1.4;
  margin: 0;
  padding: 0;
}
h1 {
  font-size: 1.5em;
  text-align: center;
  margin-top: 0.6em;
  margin-bottom: 0.4em;
}
h2 {
  font-size: 1.25em;
  text-align: center;
  margin-top: 0.8em;
  margin-bottom: 0.4em;
}
h3 {
  font-size: 1.05em;
  text-align: left;
  margin-top: 0.7em;
  margin-bottom: 0.25em;
}
p {
  margin-top: 0;
  margin-bottom: 0.35em;
}
p.q {
  margin-left: 1.2em;
  margin-top: 0;
  margin-bottom: 0.15em;
  text-align: left;
}
p.pi {
  margin-left: 1.0em;
  margin-top: 0;
  margin-bottom: 0.35em;
}
p.d {
  font-style: italic;
  margin-top: 0.2em;
  margin-bottom: 0.4em;
}
span.sc {
  font-variant: small-caps;
}
"""


def download_usfm_zip(cache_path: Path, url: str = BIBLE_VERSIONS["net"]["url"]) -> bytes:
    if cache_path.exists():
        print(f"Using cached USFM archive: {cache_path}")
        return cache_path.read_bytes()

    print(f"Downloading Bible USFM archive from {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (InkBible-Generator/1.0)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(data)
    print(f"Saved {len(data):,} bytes to {cache_path}")
    return data


def format_usfm_footnote(fn_inner: str) -> str:
    """Format the contents of a USFM \\f ... \\f* footnote into clean XHTML."""
    content = fn_inner.strip()
    if not content or "[[EMPTY]]" in content:
        return ""
    # Strip caller marker (+ or - or single char at start)
    content = re.sub(r"^[+-]\s*", "", content)

    # Extract optional reference \fr ...
    ref_text = ""
    m_fr = re.search(r"\\fr\s+([^\\]+)", content)
    if m_fr:
        ref_text = m_fr.group(1).strip().rstrip(":")
        content = content[: m_fr.start()] + content[m_fr.end() :]

    # Escape XML special characters before inserting HTML tags
    content = html.escape(content, quote=False)

    # Convert \fq / \fqa (footnote quote / alternate translation) to italics
    content = re.sub(r"\\\+?fq(?:a)?\s+([^\\]+)", lambda m: f"<i>{m.group(1).strip()}</i> ", content)
    # Convert \fl (footnote label, e.g., "Heb.", "tn") to bold
    content = re.sub(r"\\\+?fl\s+([^\\]+)", lambda m: f"<b>{m.group(1).strip()}</b> ", content)
    # Remove \ft / \fv / \fk markers while keeping their text
    content = re.sub(r"\\\+?(?:ft|fv|fk)\*?\s*", " ", content)
    # Strip word wrapper inside footnotes if any
    content = re.sub(r"\\\+?w\s+([^|\\]+?)(?:\|[^\\]*?)?\\\+?w\*", r"\1", content)
    # Strip any remaining USFM markers
    content = re.sub(r"\\\+?[a-zA-Z0-9]+\*?", " ", content)
    formatted = re.sub(r"\s+", " ", content).strip()
    if not formatted:
        return ""
    if ref_text:
        return f"<b>{html.escape(ref_text, quote=False)}</b>: {formatted}"
    return formatted


def clean_usfm_inline(text: str, footnotes_out: list = None) -> str:
    """Convert USFM inline markers to clean XHTML, extracting non-empty footnotes if footnotes_out is provided."""
    fn_placeholders = []

    def replace_fn(match):
        if footnotes_out is None:
            return ""
        fn_html = format_usfm_footnote(match.group(1))
        if not fn_html:
            return ""
        footnotes_out.append(fn_html)
        fn_idx = len(footnotes_out)
        token = f"__INKBIBLE_FN_{len(fn_placeholders)}__"
        fn_placeholders.append(
            f' <a id="fnref{fn_idx}" epub:type="noteref" href="#fn{fn_idx}">[{fn_idx}]</a>'
        )
        return token

    # Process footnotes \f ... \f*
    text = re.sub(r"\\f\b(.*?)\\f\*", replace_fn, text)
    # Remove cross-references \x ... \x* if any
    text = re.sub(r"\\x\b.*?\\x\*", "", text)
    # Strip word wrapper \w word|strong="..."\w* or \+w word|strong="..."\+w*
    text = re.sub(r"\\\+?w\s+([^|\\]+?)(?:\|[^\\]*?)?\\\+?w\*", r"\1", text)

    # Escape XML special characters before inserting HTML tags
    text = html.escape(text, quote=False)

    # Divine name \nd ... \nd* -> small caps
    text = re.sub(r"\\\+?nd\s+(.*?)\\\+?nd\*", r'<span class="sc">\1</span>', text)
    # Small caps \sc ... \sc*
    text = re.sub(r"\\\+?sc\s+(.*?)\\\+?sc\*", r'<span class="sc">\1</span>', text)
    # Italics \it ... \it* or \add ... \add*
    text = re.sub(r"\\\+?(?:it|add)\s+(.*?)\\\+?(?:it|add)\*", r"<i>\1</i>", text)
    # Bold \bd ... \bd*
    text = re.sub(r"\\\+?bd\s+(.*?)\\\+?bd\*", r"<b>\1</b>", text)
    # Words of Jesus \wj ... \wj*
    text = re.sub(r"\\\+?wj\s+(.*?)\\\+?wj\*", r"\1", text)
    # Quoted OT text \qt ... \qt* (sometimes ends with \qt**)
    text = re.sub(r"\\\+?qt\s+(.*?)\\\+?qt\*+", r"\1", text)

    # Strip any stray remaining backslash markers
    text = re.sub(r"\\\+?[a-zA-Z0-9]+\*?", "", text)
    # Restore footnote links
    for idx, link_html in enumerate(fn_placeholders):
        text = text.replace(f"__INKBIBLE_FN_{idx}__", link_html)
    # Normalize multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_usfm_book(usfm_text: str, book_index: int):
    """
    Parse a single book's USFM text into:
      (book_name, chapters_list)
    where chapters_list is a list of (chapter_num, max_verse, xhtml_string).
    """
    book_name = f"Book {book_index + 1}"
    h_match = re.search(r"^\\h\s+(.+)$", usfm_text, re.M)
    if h_match:
        book_name = h_match.group(1).strip()

    chapters = []
    current_chapter = 0
    max_verse_in_chapter = 0
    body_lines = []
    chapter_footnotes = []
    pending_pre_chapter_lines = []
    open_p_class = None  # None, "p", "q", "pi", "d"
    p_buffer = []

    def flush_p():
        nonlocal open_p_class, p_buffer
        if not p_buffer:
            open_p_class = None
            return
        content = " ".join(s for s in p_buffer if s).strip()
        if content:
            target = body_lines if current_chapter > 0 else pending_pre_chapter_lines
            if open_p_class in ("q", "pi", "d"):
                target.append(f'<p class="{open_p_class}">{content}</p>')
            else:
                target.append(f"<p>{content}</p>")
        p_buffer = []
        open_p_class = None

    def start_p(cls="p"):
        nonlocal open_p_class
        flush_p()
        open_p_class = cls

    def finish_chapter():
        nonlocal body_lines, chapter_footnotes, current_chapter, max_verse_in_chapter
        flush_p()
        if current_chapter <= 0:
            return
        if chapter_footnotes:
            body_lines.append("<hr/>")
            for fn_idx, fn_html in enumerate(chapter_footnotes, start=1):
                body_lines.append(
                    f'<p id="fn{fn_idx}"><a href="#fnref{fn_idx}"><b>[{fn_idx}]</b></a> {fn_html}</p>'
                )
        ch_title = f"{book_name} {current_chapter}"
        xhtml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en" lang="en">\n'
            "<head>\n"
            f"  <title>{html.escape(ch_title)}</title>\n"
            '  <link rel="stylesheet" type="text/css" href="style.css"/>\n'
            "</head>\n"
            "<body>\n"
            + "\n".join(body_lines)
            + "\n</body>\n</html>\n"
        )
        chapters.append((current_chapter, max_verse_in_chapter, xhtml))
        body_lines = []
        chapter_footnotes = []

    for raw_line in usfm_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Metadata headers and introductions handled at book level
        if line.startswith(("\\id ", "\\ide ", "\\h ", "\\toc1 ", "\\toc2 ", "\\toc3 ", "\\mt", "\\is", "\\ip", "\\im", "\\io", "\\ie", "\\rem ")):
            continue

        # Chapter marker
        m_c = re.match(r"^\\c\s+(\d+)\b", line)
        if m_c:
            finish_chapter()
            current_chapter = int(m_c.group(1))
            max_verse_in_chapter = 0
            if current_chapter == 1:
                body_lines.append(f"<h1>{html.escape(book_name)}</h1>")
            body_lines.append(f'<h2 id="c{current_chapter}">{html.escape(book_name)} {current_chapter}</h2>')
            if pending_pre_chapter_lines:
                body_lines.extend(pending_pre_chapter_lines)
                pending_pre_chapter_lines.clear()
            continue

        # Section headings
        m_s = re.match(r"^\\(?:s\d*|ms\d*|mr|sr|r|sp)\b\s*(.*)$", line)
        if m_s:
            flush_p()
            heading_text = clean_usfm_inline(m_s.group(1), chapter_footnotes if current_chapter > 0 else None)
            if heading_text:
                target = body_lines if current_chapter > 0 else pending_pre_chapter_lines
                target.append(f"<h3>{heading_text}</h3>")
            continue

        # Psalm descriptive title \d
        m_d = re.match(r"^\\d\b\s*(.*)$", line)
        if m_d:
            start_p("d")
            d_text = clean_usfm_inline(m_d.group(1), chapter_footnotes if current_chapter > 0 else None)
            if d_text:
                p_buffer.append(d_text)
            continue

        # Blank / stanza break
        if re.match(r"^\\(?:b|nb)\b\s*$", line):
            continue

        # Paragraph / poetry markers
        m_p = re.match(r"^\\(p|m|pmo|pm|pmc|pmr|pi\d*|pc|pr|cls|q\d*|qr|qc|qm\d*|li\d*)\b\s*(.*)$", line)
        if m_p:
            tag, rest = m_p.group(1), m_p.group(2)
            cls = "q" if tag.startswith(("q", "li")) else ("pi" if tag.startswith(("pi", "pm")) else "p")
            start_p(cls)
            if rest:
                line = rest
            else:
                continue

        # Verse marker (may appear at start of line or after paragraph marker)
        m_v = re.match(r"^\\v\s+(\d+)(?:-\d+)?\b\s*(.*)$", line)
        if m_v:
            v_num = int(m_v.group(1))
            if v_num > max_verse_in_chapter:
                max_verse_in_chapter = v_num
            v_text = clean_usfm_inline(m_v.group(2), chapter_footnotes if current_chapter > 0 else None)
            if open_p_class is None:
                open_p_class = "p"
            anchor_id = f"v{v_num}"
            verse_html = f'<b id="{anchor_id}">{v_num}</b>'
            if v_text:
                verse_html += f" {v_text}"
            p_buffer.append(verse_html)
            continue

        # Continuation text on its own line (only inside a chapter)
        if current_chapter > 0:
            cleaned = clean_usfm_inline(line, chapter_footnotes)
            if cleaned:
                if open_p_class is None:
                    open_p_class = "p"
                p_buffer.append(cleaned)

    finish_chapter()
    expected_chapters = CANONICAL_CHAPTER_COUNTS[book_index]
    if len(chapters) != expected_chapters:
        # Filter to canonical 1..expected_chapters if extra chapters exist
        chapters = [ch for ch in chapters if 1 <= ch[0] <= expected_chapters]
    return book_name, chapters


def load_canonical_usfm_books(usfm_zip_bytes: bytes):
    """Return a list of 66 (book_index, raw_usfm_text) tuples in canonical order (GEN..REV)."""
    zf_in = zipfile.ZipFile(io.BytesIO(usfm_zip_bytes))
    usfm_files = [n for n in zf_in.namelist() if n.lower().endswith((".usfm", ".sfm"))]
    books_by_id = {}
    for name in usfm_files:
        raw_text = zf_in.read(name).decode("utf-8-sig", errors="replace")
        m_id = re.search(r"^\\id\s+([A-Z0-9]{3})\b", raw_text, re.M)
        if m_id:
            code = m_id.group(1).upper()
            if code in CANONICAL_USFM_IDS and code not in books_by_id:
                books_by_id[code] = raw_text

    if len(books_by_id) != 66:
        missing = [c for c in CANONICAL_USFM_IDS if c not in books_by_id]
        raise RuntimeError(f"Expected 66 canonical USFM books, found {len(books_by_id)} (missing: {missing})")

    return [(idx, books_by_id[code]) for idx, code in enumerate(CANONICAL_USFM_IDS)]


def parse_all_usfm_chapters(usfm_zip_bytes: bytes):
    canonical_books = load_canonical_usfm_books(usfm_zip_bytes)

    all_chapters = []
    for idx, raw_text in canonical_books:
        book_name, chapters = parse_usfm_book(raw_text, idx)
        for ch_num, v_count, xhtml in chapters:
            all_chapters.append((idx, book_name, ch_num, v_count, xhtml))
    if len(all_chapters) != 1189:
        raise RuntimeError(f"Expected 1189 chapters, found {len(all_chapters)}")
    return all_chapters


def build_embedded_cpp(usfm_zip_bytes: bytes, cpp_path: Path, force: bool = False):
    script_mtime = Path(__file__).stat().st_mtime if "__file__" in globals() else 0
    if not force and cpp_path.exists() and cpp_path.stat().st_size > 1_000_000 and cpp_path.stat().st_mtime >= script_mtime:
        return

    all_chapters = parse_all_usfm_chapters(usfm_zip_bytes)
    chapter_bytes = [xhtml.encode("utf-8") for (_, _, _, _, xhtml) in all_chapters]
    uncompressed_lengths = [len(b) for b in chapter_bytes]
    if max(uncompressed_lengths) > 0xFFFF:
        raise RuntimeError(f"Chapter exceeds uint16_t max size (65535 B): {max(uncompressed_lengths)} B")

    compressed_chunks = []
    group_offsets = [0]
    for i in range(0, len(chapter_bytes), GROUP_SIZE):
        group_raw = b"".join(chapter_bytes[i : i + GROUP_SIZE])
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        deflated = comp.compress(group_raw) + comp.flush()
        compressed_chunks.append(deflated)
        group_offsets.append(group_offsets[-1] + len(deflated))

    blob = b"".join(compressed_chunks)
    num_groups = len(compressed_chunks)

    cpp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cpp_path, "w", encoding="utf-8") as f:
        f.write("// THIS FILE IS AUTO-GENERATED BY scripts/generate_net_bible_epub.py. DO NOT EDIT.\n")
        f.write("// clang-format off\n")
        f.write('#include "NetBibleData.h"\n\n')
        f.write("namespace NetBibleData {\n\n")
        f.write(f"const char STYLE_CSS[] = R\"CSS({BIBLE_CSS})CSS\";\n")
        f.write(f"const size_t STYLE_CSS_LEN = sizeof(STYLE_CSS) - 1;\n\n")

        f.write(f"const uint16_t CHAPTER_UNCOMPRESSED_SIZES[{len(uncompressed_lengths)}] = {{\n")
        for i in range(0, len(uncompressed_lengths), 16):
            row = ", ".join(str(x) for x in uncompressed_lengths[i : i + 16])
            f.write(f"    {row},\n")
        f.write("};\n\n")

        f.write(f"const uint32_t GROUP_COMPRESSED_OFFSETS[{num_groups + 1}] = {{\n")
        for i in range(0, len(group_offsets), 12):
            row = ", ".join(f"{x}u" for x in group_offsets[i : i + 12])
            f.write(f"    {row},\n")
        f.write("};\n\n")

        f.write(f"const uint8_t COMPRESSED_CHAPTERS_BLOB[{len(blob)}] = {{\n")
        for i in range(0, len(blob), 24):
            row = ",".join(f"0x{b:02x}" for b in blob[i : i + 24])
            f.write(f"    {row},\n")
        f.write("};\n\n")
        f.write("}  // namespace NetBibleData\n")

    print(
        f"Generated embedded NET Bible C++ data: {cpp_path} "
        f"({len(blob):,} B compressed across {num_groups} groups, "
        f"{sum(uncompressed_lengths):,} B raw)"
    )


def build_bible_epub(usfm_zip_bytes: bytes, output_path: Path, version_key: str = "net"):
    version_meta = BIBLE_VERSIONS.get(version_key, BIBLE_VERSIONS["net"])
    canonical_books = load_canonical_usfm_books(usfm_zip_bytes)

    manifest_items = ['<item id="style" href="style.css" media-type="text/css"/>']
    spine_items = []
    nav_points = []
    play_order = 1
    total_chapters = 0
    total_verses = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as epub:
        # 1. mimetype must be first and uncompressed
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        # 2. META-INF/container.xml
        epub.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
            "  <rootfiles>\n"
            '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
            "  </rootfiles>\n"
            "</container>\n",
        )

        # 3. Stylesheet
        epub.writestr("OEBPS/style.css", BIBLE_CSS)

        # 4. Parse and write each of the 66 books (1,189 chapter XHTML files)
        for idx, raw_text in canonical_books:
            book_name, chapters = parse_usfm_book(raw_text, idx)

            for ch_num, v_count, xhtml in chapters:
                total_chapters += 1
                total_verses += v_count
                item_id = f"B{idx + 1:02d}_C{ch_num:03d}"
                href = f"{item_id}.xhtml"
                ch_label = f"{book_name} {ch_num}"

                epub.writestr(f"OEBPS/{href}", xhtml.encode("utf-8"))
                manifest_items.append(
                    f'<item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>'
                )
                spine_items.append(f'<itemref idref="{item_id}"/>')
                nav_points.append(
                    f'    <navPoint id="np-{play_order}" playOrder="{play_order}">\n'
                    f"      <navLabel><text>{html.escape(ch_label)}</text></navLabel>\n"
                    f'      <content src="{href}"/>\n'
                    f"    </navPoint>"
                )
                play_order += 1

        # 5. OEBPS/content.opf
        manifest_xml = "\n    ".join(manifest_items)
        spine_xml = "\n    ".join(spine_items)
        title_esc = html.escape(version_meta["title"])
        creator_esc = html.escape(version_meta["creator"])
        ident_esc = html.escape(version_meta["identifier"])
        rights_esc = html.escape(version_meta["rights"])
        content_opf = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<package version="2.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId">\n'
            '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            f"    <dc:title>{title_esc}</dc:title>\n"
            f"    <dc:creator>{creator_esc}</dc:creator>\n"
            "    <dc:language>en</dc:language>\n"
            f'    <dc:identifier id="BookId">{ident_esc}</dc:identifier>\n'
            f"    <dc:rights>{rights_esc}</dc:rights>\n"
            "  </metadata>\n"
            "  <manifest>\n"
            f"    {manifest_xml}\n"
            '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>\n'
            "  </manifest>\n"
            '  <spine toc="ncx">\n'
            f"    {spine_xml}\n"
            "  </spine>\n"
            "</package>\n"
        )
        epub.writestr("OEBPS/content.opf", content_opf.encode("utf-8"))

        # 6. OEBPS/toc.ncx
        nav_xml = "\n".join(nav_points)
        toc_ncx = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
            "  <head>\n"
            f'    <meta name="dtb:uid" content="{ident_esc}"/>\n'
            '    <meta name="dtb:depth" content="1"/>\n'
            '    <meta name="dtb:totalPageCount" content="0"/>\n'
            '    <meta name="dtb:maxPageNumber" content="0"/>\n'
            "  </head>\n"
            f"  <docTitle><text>{title_esc}</text></docTitle>\n"
            "  <navMap>\n"
            f"{nav_xml}\n"
            "  </navMap>\n"
            "</ncx>\n"
        )
        epub.writestr("OEBPS/toc.ncx", toc_ncx.encode("utf-8"))

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(
        f"Generated {output_path} [{version_meta['title']}] ({size_mb:.2f} MB): "
        f"66 books, {total_chapters} chapters, {total_verses} verses."
    )


def main():
    parser = argparse.ArgumentParser(description="Generate Bible EPUB or embedded C++ data for Ink Bible firmware.")
    parser.add_argument(
        "-v",
        "--version",
        choices=list(BIBLE_VERSIONS.keys()),
        default="net",
        help="Bible translation preset to generate (default: net)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=f"Output EPUB file path (default: {DEFAULT_OUTPUT} for net, or <version>.epub)",
    )
    parser.add_argument(
        "--cache-zip",
        type=Path,
        default=None,
        help="Local cache path for USFM zip archive",
    )
    parser.add_argument(
        "--cpp-out",
        type=Path,
        default=None,
        help="Optional path to generate embedded C++ source file (NetBibleData.generated.cpp)",
    )
    parser.add_argument(
        "--no-epub",
        action="store_true",
        help="Skip generating EPUB when --cpp-out is used",
    )
    args = parser.parse_args()

    version_meta = BIBLE_VERSIONS[args.version]
    cache_zip = args.cache_zip or (PROJECT_ROOT / ".cache" / version_meta["cache_name"])
    output_epub = args.output or (DEFAULT_OUTPUT if args.version == "net" else (PROJECT_ROOT / f"{args.version}.epub"))

    usfm_bytes = download_usfm_zip(cache_zip, version_meta["url"])
    if args.cpp_out:
        build_embedded_cpp(usfm_bytes, args.cpp_out, force=True)
    if not args.no_epub:
        build_bible_epub(usfm_bytes, output_epub, args.version)


if __name__ == "__main__":
    sys.exit(main())
else:
    if "Import" in globals():
        Import("env")
        usfm_bytes = download_usfm_zip(DEFAULT_CACHE_ZIP, BIBLE_VERSIONS["net"]["url"])
        build_embedded_cpp(usfm_bytes, DEFAULT_CPP_OUTPUT, force=False)
