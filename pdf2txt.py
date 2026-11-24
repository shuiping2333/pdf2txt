"""把扫描版 PDF 按页识别成文本。

渲染用 PyMuPDF，识别用 RapidOCR（中英，CPU）。按页顺序写入，不依赖 Poppler 或 Tesseract。
"""

import argparse
import logging
import re
import sys
import time
from pathlib import Path

import numpy as np
import pymupdf
from rapidocr import RapidOCR

logging.getLogger("RapidOCR").setLevel(logging.WARNING)


def parse_args():
    parser = argparse.ArgumentParser(description="扫描版 PDF 转文本（PyMuPDF + RapidOCR）")
    parser.add_argument("pdf", nargs="?", type=Path, help="PDF 文件路径")
    parser.add_argument("--first", action="store_true", help="转换当前目录里按文件名排序的第一个 PDF")
    parser.add_argument("-o", "--output", type=Path, help="输出路径，默认与 PDF 同名")
    parser.add_argument("--format", choices=("txt", "md"), help="输出格式。默认看 -o 的扩展名，否则为 txt")
    parser.add_argument("--start", type=int, default=1, help="起始页，从 1 开始")
    parser.add_argument("--end", type=int, default=None, help="结束页，包含该页；默认到最后一页")
    parser.add_argument("--dpi", type=int, default=200, help="渲染分辨率，默认 200")
    return parser.parse_args()


def page_to_image(page, dpi):
    zoom = dpi / 72
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    channels = pixmap.n
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, channels)
    if channels == 4:
        image = image[:, :, :3]
    return image.copy()


def text_from_result(result):
    if result is None:
        return ""
    texts = getattr(result, "txts", None)
    if texts:
        return "\n".join(text.strip() for text in texts if text and text.strip())
    # rapidocr 2.x 返回 [box, text, score] 列表
    if isinstance(result, (list, tuple)) and result and isinstance(result[0], (list, tuple)):
        lines = []
        for item in result:
            if len(item) >= 2 and item[1] and str(item[1]).strip():
                lines.append(str(item[1]).strip())
        return "\n".join(lines)
    return ""


def resolve_output(pdf_path, output_path, fmt):
    if output_path is not None:
        if fmt is None:
            fmt = "md" if output_path.suffix.lower() == ".md" else "txt"
        return output_path, fmt
    fmt = fmt or "txt"
    suffix = ".md" if fmt == "md" else ".txt"
    return pdf_path.with_suffix(suffix), fmt


# 页眉装饰，以及「024 人际关系疗法」「译丛序言003」「1 导言 007」这类页码行。
_NOISE_LINE = re.compile(r"^[>＞›»\s]+$|^[*＊]{1,3}$")
_RUNNING_HEADER = re.compile(
    r"^(?:"
    r"\d{2,4}\s*[\u4e00-\u9fffA-Za-z·]{2,16}"
    r"|[\u4e00-\u9fff]{2,12}\s*\d{2,4}"
    r"|\d{1,2}\s*[\u4e00-\u9fff]{2,8}\s*\d{2,4}"
    r")$"
)
_FOOTNOTE = re.compile(r"^[\[【［]\d+[\]】］](?=\s|$)")
_FOOTNOTE_AT_START = re.compile(r"^[\[【［]\d+[\]】］](?=\S)")
_HEADING_PUNCT = set("。！？，、；,.;：:（）()[]【】“”\"'")
_CLOSERS = "）)」”’》】"


def _is_heading(line):
    if len(line) < 4 or len(line) > 16:
        return False
    if any(char in _HEADING_PUNCT for char in line):
        return False
    return sum(1 for char in line if "\u4e00" <= char <= "\u9fff") >= 2


def _sentence_end(text):
    core = text.rstrip(_CLOSERS + " \t")
    if core.endswith(("et al.", "et al", "e.g.", "i.e.", "etc.")):
        return False
    return core.endswith(("。", "！", "？", "…", "."))


def _join_text(left, right):
    if not left:
        return right
    last, first = left[-1], right[0]
    if _FOOTNOTE.match(left):
        return left + " " + right
    if last == "-" and first.isascii():
        return left[:-1] + right
    if last.isascii() and first.isascii() and (last.isalnum() or last in ",&") and (first.isalnum() or first == "("):
        return left + " " + right
    return left + right


def refine_text(text):
    """去掉页眉和装饰符，并把排版换行接成段落。短标题在段首时标成 heading。"""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or _NOISE_LINE.match(line) or _RUNNING_HEADER.match(line):
            continue
        lines.append(line)

    blocks = []
    buffer = ""

    def flush():
        nonlocal buffer
        if buffer:
            blocks.append(("para", buffer))
            buffer = ""

    for index, line in enumerate(lines):
        line = _FOOTNOTE_AT_START.sub(lambda matched: matched.group(0) + " ", line, count=1)
        if _FOOTNOTE.match(line):
            flush()
            buffer = line
            continue
        coming = lines[index + 1] if index + 1 < len(lines) else ""
        at_break = (not buffer) or _sentence_end(buffer)
        if _is_heading(line) and at_break and (not coming or len(coming) >= len(line)):
            flush()
            blocks.append(("heading", line))
            continue
        buffer = _join_text(buffer, line)
    flush()
    return blocks


def format_page(number, text, fmt):
    blocks = refine_text(text)
    if fmt == "txt":
        parts = [f"--- 第 {number} 页 ---", ""]
        for _kind, content in blocks:
            parts.extend((content, ""))
        return "\n".join(parts).rstrip() + "\n\n"

    parts = [f"## 第 {number} 页", ""]
    for kind, content in blocks:
        parts.append(f"### {content}" if kind == "heading" else content)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n\n"


def reflow_markdown(text):
    """把已经按行切开的 Markdown 再用当前整理规则写一遍，不必重新 OCR。"""
    pieces = re.split(r"(?=^## 第 \d+ 页\s*$)", text, flags=re.M)
    pages = []
    for piece in pieces:
        matched = re.match(r"## 第 (\d+) 页\s*", piece)
        if not matched:
            continue
        pages.append(format_page(int(matched.group(1)), piece[matched.end():], "md"))
    return "".join(pages)


def extract(pdf_path, output_path, start, end, dpi, fmt):
    if not pdf_path.is_file():
        raise FileNotFoundError(f"找不到 PDF：{pdf_path}")
    if dpi < 72:
        raise ValueError("dpi 不能低于 72")

    document = pymupdf.open(pdf_path)
    page_count = document.page_count
    start = max(1, start)
    end = page_count if end is None else min(end, page_count)
    if start > end:
        document.close()
        raise ValueError(f"页码范围无效：{start}-{end}，这份 PDF 共 {page_count} 页")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    engine = RapidOCR()
    started = time.perf_counter()
    written = 0

    with output_path.open("w", encoding="utf-8") as handle:
        for number in range(start, end + 1):
            page_started = time.perf_counter()
            image = page_to_image(document[number - 1], dpi)
            result = engine(image)
            text = text_from_result(result)
            handle.write(format_page(number, text, fmt))
            handle.flush()
            written += 1
            elapsed = time.perf_counter() - page_started
            print(f"第 {number}/{page_count} 页完成，用时 {elapsed:.1f} 秒", file=sys.stderr)

    document.close()
    total = time.perf_counter() - started
    print(
        f"已写入 {written} 页到 {output_path}，共用时 {total:.1f} 秒",
        file=sys.stderr,
    )


def main():
    args = parse_args()
    if args.pdf is None:
        if not args.first:
            print("请提供 PDF 路径，或双击 pdf2md.bat。", file=sys.stderr)
            return 1
        pdfs = sorted((item for item in Path.cwd().glob("*.pdf") if item.is_file()), key=lambda item: item.name)
        if not pdfs:
            print("当前目录没有 PDF。", file=sys.stderr)
            return 1
        pdf_path = pdfs[0].resolve()
        print(f"转换：{pdf_path.name}", file=sys.stderr)
    else:
        pdf_path = args.pdf.expanduser().resolve()
    output_arg = args.output.expanduser().resolve() if args.output else None
    output_path, fmt = resolve_output(pdf_path, output_arg, args.format)
    try:
        extract(pdf_path, output_path, args.start, args.end, args.dpi, fmt)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
