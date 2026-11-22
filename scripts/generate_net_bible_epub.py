#!/usr/bin/env python3
"""
Generate a NET Bible (New English Translation) EPUB optimized for the Ink Bible
firmware on CrossPoint Reader (Xteink X3/X4).

Downloads the official public USFM package from eBible.org (or reads a local
engnet_usfm.zip cache) and compiles an EPUB 2/3 archive where:
- Each of the 1,189 canonical chapters is its own spine XHTML item
  (`B01_C001.xhtml` .. `B66_C022.xhtml`), matching the firmware's `BibleCanon`
  table (`chapterOffset + chapter - 1` -> `spineIndex 0 .. 1188`).
- Each chapter file is small (typically 2-8 KB, max ~24 KB for Psalm 119), so
  the ESP32-C3 lays out and renders any chapter in milliseconds with plenty of
  free RAM.
- Each verse begins with `<b id="vM">M</b>` (recorded as a navigable anchor by
  the firmware parser for instant Book -> Chapter -> Verse lookup).
- Poetry (`\\q1`), section headings (`\\s1`, `\\ms1`, `\\ms2`, `\\d`), indented prose
  (`\\pi1`), Divine Name (`\\nd`), small caps (`\\sc`), and italics (`\\it`) are
  preserved with clean semantic markup and minimal memory overhead.
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

USFM_URL = "https://ebible.org/Scriptures/engnet_usfm.zip"
PROJECT_ROOT = Path(__file__).parent.parent if "__file__" in globals() else Path.cwd()
DEFAULT_CACHE_ZIP = PROJECT_ROOT / ".cache" / "engnet_usfm.zip"
DEFAULT_OUTPUT = PROJECT_ROOT / "bible.epub"
DEFAULT_CPP_OUTPUT = PROJECT_ROOT / "lib" / "BibleCanon" / "NetBibleData.generated.cpp"
DEFAULT_HEADER_PATH = PROJECT_ROOT / "lib" / "BibleCanon" / "NetBibleData.h"
GROUP_SIZE = 16

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


def download_usfm_zip(cache_path: Path) -> bytes:
    if cache_path.exists():
        print(f"Using cached USFM archive: {cache_path}")
        return cache_path.read_bytes()

    print(f"Downloading NET Bible USFM archive from {USFM_URL} ...")
    req = urllib.request.Request(USFM_URL, headers={"User-Agent": "Mozilla/5.0 (InkBible-Generator/1.0)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(data)
    print(f"Saved {len(data):,} bytes to {cache_path}")
    return data


def clean_usfm_inline(text: str) -> str:
    """Convert USFM inline markers to clean XHTML and strip Strong's tags and footnotes."""
    # Remove footnotes \f ... \f*
    text = re.sub(r"\\f\b.*?\\f\*", "", text)
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
    # Italics \it ... \it*
    text = re.sub(r"\\\+?it\s+(.*?)\\\+?it\*", r"<i>\1</i>", text)
    # Bold \bd ... \bd*
    text = re.sub(r"\\\+?bd\s+(.*?)\\\+?bd\*", r"<b>\1</b>", text)
    # Quoted OT text \qt ... \qt* (sometimes ends with \qt**)
    text = re.sub(r"\\\+?qt\s+(.*?)\\\+?qt\*+", r"\1", text)

    # Strip any stray remaining backslash markers
    text = re.sub(r"\\\+?[a-zA-Z0-9]+\*?", "", text)
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
        nonlocal body_lines, current_chapter, max_verse_in_chapter
        flush_p()
        if current_chapter <= 0:
            return
        ch_title = f"{book_name} {current_chapter}"
        xhtml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">\n'
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

    for raw_line in usfm_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Metadata headers handled at book level
        if line.startswith(("\\id ", "\\h ", "\\toc1 ", "\\toc2 ", "\\mt1 ")):
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
        m_s = re.match(r"^\\(?:s1|ms1|ms2)\b\s*(.*)$", line)
        if m_s:
            flush_p()
            heading_text = clean_usfm_inline(m_s.group(1))
            if heading_text:
                target = body_lines if current_chapter > 0 else pending_pre_chapter_lines
                target.append(f"<h3>{heading_text}</h3>")
            continue

        # Psalm descriptive title \d
        m_d = re.match(r"^\\d\b\s*(.*)$", line)
        if m_d:
            start_p("d")
            d_text = clean_usfm_inline(m_d.group(1))
            if d_text:
                p_buffer.append(d_text)
            continue

        # Paragraph / poetry markers
        m_p = re.match(r"^\\(p|pi1|q1)\b\s*(.*)$", line)
        if m_p:
            tag, rest = m_p.group(1), m_p.group(2)
            cls = "q" if tag == "q1" else ("pi" if tag == "pi1" else "p")
            start_p(cls)
            if rest:
                line = rest
            else:
                continue

        # Verse marker (may appear at start of line or after paragraph marker)
        m_v = re.match(r"^\\v\s+(\d+)\b\s*(.*)$", line)
        if m_v:
            v_num = int(m_v.group(1))
            if v_num > max_verse_in_chapter:
                max_verse_in_chapter = v_num
            v_text = clean_usfm_inline(m_v.group(2))
            if open_p_class is None:
                open_p_class = "p"
            anchor_id = f"v{v_num}"
            verse_html = f'<b id="{anchor_id}">{v_num}</b>'
            if v_text:
                verse_html += f" {v_text}"
            p_buffer.append(verse_html)
            continue

        # Continuation text on its own line
        cleaned = clean_usfm_inline(line)
        if cleaned:
            if open_p_class is None:
                open_p_class = "p"
            p_buffer.append(cleaned)

    finish_chapter()
    return book_name, chapters


def parse_all_usfm_chapters(usfm_zip_bytes: bytes):
    zf_in = zipfile.ZipFile(io.BytesIO(usfm_zip_bytes))
    usfm_files = sorted(n for n in zf_in.namelist() if n.endswith(".usfm"))
    if len(usfm_files) != 66:
        raise RuntimeError(f"Expected 66 USFM books, found {len(usfm_files)}")

    all_chapters = []
    for idx, usfm_name in enumerate(usfm_files):
        raw_text = zf_in.read(usfm_name).decode("utf-8", errors="replace")
        book_name, chapters = parse_usfm_book(raw_text, idx)
        for ch_num, v_count, xhtml in chapters:
            all_chapters.append((idx, book_name, ch_num, v_count, xhtml))
    if len(all_chapters) != 1189:
        raise RuntimeError(f"Expected 1189 chapters, found {len(all_chapters)}")
    return all_chapters


def build_embedded_cpp(usfm_zip_bytes: bytes, cpp_path: Path, force: bool = False):
    if not force and cpp_path.exists() and cpp_path.stat().st_size > 1_000_000:
        return

    all_chapters = parse_all_usfm_chapters(usfm_zip_bytes)
    chapter_bytes = [xhtml.encode("utf-8") for (_, _, _, _, xhtml) in all_chapters]
    uncompressed_lengths = [len(b) for b in chapter_bytes]

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


def build_bible_epub(usfm_zip_bytes: bytes, output_path: Path):
    zf_in = zipfile.ZipFile(io.BytesIO(usfm_zip_bytes))
    usfm_files = sorted(n for n in zf_in.namelist() if n.endswith(".usfm"))
    if len(usfm_files) != 66:
        raise RuntimeError(f"Expected 66 USFM books, found {len(usfm_files)}")

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
        for idx, usfm_name in enumerate(usfm_files):
            raw_text = zf_in.read(usfm_name).decode("utf-8", errors="replace")
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
        content_opf = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<package version="2.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId">\n'
            '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            "    <dc:title>NET Bible</dc:title>\n"
            "    <dc:creator>Biblical Studies Press</dc:creator>\n"
            "    <dc:language>en</dc:language>\n"
            '    <dc:identifier id="BookId">ink-bible-net-v1</dc:identifier>\n'
            "    <dc:rights>NET Bible® copyright © 1996-2016 Biblical Studies Press, L.L.C.</dc:rights>\n"
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
            '    <meta name="dtb:uid" content="ink-bible-net-v1"/>\n'
            '    <meta name="dtb:depth" content="1"/>\n'
            '    <meta name="dtb:totalPageCount" content="0"/>\n'
            '    <meta name="dtb:maxPageNumber" content="0"/>\n'
            "  </head>\n"
            "  <docTitle><text>NET Bible</text></docTitle>\n"
            "  <navMap>\n"
            f"{nav_xml}\n"
            "  </navMap>\n"
            "</ncx>\n"
        )
        epub.writestr("OEBPS/toc.ncx", toc_ncx.encode("utf-8"))

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(
        f"Generated {output_path} ({size_mb:.2f} MB): "
        f"66 books, {total_chapters} chapters, {total_verses} verses."
    )


def main():
    parser = argparse.ArgumentParser(description="Generate NET Bible EPUB for Ink Bible firmware.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output EPUB file path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--cache-zip",
        type=Path,
        default=DEFAULT_CACHE_ZIP,
        help=f"Local cache path for engnet_usfm.zip (default: {DEFAULT_CACHE_ZIP})",
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
        help="Skip generating bible.epub when --cpp-out is used",
    )
    args = parser.parse_args()

    usfm_bytes = download_usfm_zip(args.cache_zip)
    if args.cpp_out:
        build_embedded_cpp(usfm_bytes, args.cpp_out, force=True)
    if not args.no_epub:
        build_bible_epub(usfm_bytes, args.output)


if __name__ == "__main__":
    sys.exit(main())
else:
    if "Import" in globals():
        Import("env")
        usfm_bytes = download_usfm_zip(DEFAULT_CACHE_ZIP)
        build_embedded_cpp(usfm_bytes, DEFAULT_CPP_OUTPUT, force=False)
