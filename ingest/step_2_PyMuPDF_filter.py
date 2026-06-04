"""
PyMuPDF_filter.py - Scan PDF files and keep pages that contain tables or chart-like content with high numeric density.

Keep a page when any of these checks match:
  1. TABLE     : page.find_tables() finds at least one table
  2. IMAGE     : the page has raster images and page text numeric density > NUM_DENSITY_THRESHOLD
  3. DRAWING   : the page has vector drawings (line/fill paths exceed the threshold)
                 and numeric density > NUM_DENSITY_THRESHOLD

Numeric density = number of digit characters / total number of non-whitespace characters

Usage:
    uv run python ingest/PyMuPDF_filter.py                     # Scan all PDFs
    uv run python ingest/PyMuPDF_filter.py --pdf RIO_FY2024.pdf --pages 101-150
"""

import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import fitz  # pymupdf

OUT_JSON              = Path("ingest/filtered_pages.json")
NUM_DENSITY_THRESHOLD = 0.05   # Minimum ratio of digit characters to non-whitespace characters
MIN_DIGIT_COUNT       = 20     # Minimum digit count before a page is worth visual-model processing
MIN_DRAWING_PATHS     = 10     # Minimum vector drawing paths, excluding simple divider lines
MIN_TEXT_CHARS        = 100    # Minimum non-whitespace text chars, excluding image-only pages
NUM_WORKERS           = 15     # Number of parallel scan workers
SAVE_EVERY            = 50     # Save a checkpoint after every N scanned pages


def _get_reports_dir(cli_path: str | None) -> Path:
    if cli_path:
        d = Path(cli_path)
    else:
        raw = input("PDF reports directory (e.g. /Users/yourname/Downloads/annual_reports): ").strip()
        d = Path(raw)
    if not d.is_dir():
        print(f"Error: '{d}' is not a directory.", file=sys.stderr)
        sys.exit(1)
    return d


def numeric_density(text: str) -> float:
    non_ws = re.sub(r"\s", "", text)
    if not non_ws:
        return 0.0
    digits = sum(1 for c in non_ws if c.isdigit())
    return digits / len(non_ws)


def classify_page(page: fitz.Page) -> tuple[list[str], int, float]:
    """Return (matched reasons, digit count, page numeric density). Empty reasons means no match."""
    reasons = []

    # Absolute digit count shared by all checks.
    text        = page.get_text()
    text_chars  = len(re.sub(r"\s", "", text))
    digit_count = sum(1 for c in text if c.isdigit())
    density     = digit_count / text_chars if text_chars else 0.0
    has_digits  = digit_count >= MIN_DIGIT_COUNT
    dense_enough = density > NUM_DENSITY_THRESHOLD
    has_text    = text_chars  >= MIN_TEXT_CHARS
    passes      = has_digits and dense_enough and has_text

    # 1. Table detection
    try:
        tables = page.find_tables()
        if tables.tables:
            if passes:
                reasons.append("TABLE")
            else:
                # If the full-page checks fail, inspect each table region.
                page_area = page.rect.width * page.rect.height
                for tbl in tables.tables:
                    bbox = tbl.bbox
                    bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                    tbl_text   = page.get_text(clip=bbox)
                    tbl_nonws  = len(re.sub(r"\s", "", tbl_text))
                    tbl_digits = sum(1 for c in tbl_text if c.isdigit())
                    if bbox_area > 0.8 * page_area:
                        # Possible two-column layout false positive: use absolute counts instead.
                        if tbl_nonws >= MIN_TEXT_CHARS and tbl_digits >= MIN_DIGIT_COUNT:
                            reasons.append("TABLE")
                            break
                    else:
                        # Normal table: judge by local density.
                        local_density = tbl_digits / tbl_nonws if tbl_nonws else 0.0
                        if local_density > NUM_DENSITY_THRESHOLD:
                            reasons.append("TABLE")
                            break
    except Exception:
        pass

    # 2. Raster images
    if page.get_images() and passes:
        reasons.append("IMAGE")

    # 3. Vector drawings, since charts usually contain many paths.
    drawings = page.get_drawings()
    if len(drawings) >= MIN_DRAWING_PATHS and passes:
        reasons.append("DRAWING")

    return reasons, digit_count, density


def scan_pdf(pdf_path: Path, page_start: int = 1, page_end: int | None = None, show_progress: bool = False) -> list[dict]:
    doc = fitz.open(str(pdf_path))
    end = min(page_end or len(doc), len(doc))
    total = end - (page_start - 1)
    results = []

    if show_progress:
        print(f"  {pdf_path.name}  [{total} pages]")

    for i, page_idx in enumerate(range(page_start - 1, end)):
        page                    = doc[page_idx]
        page_num                = page_idx + 1
        reasons, digits, density = classify_page(page)
        if reasons:
            results.append({
                "source":          pdf_path.name,
                "page":            page_num,
                "reasons":         reasons,
                "numeric_density": round(density, 3),
            })

        if show_progress:
            done    = i + 1
            bar_len = 30
            filled  = int(bar_len * done / total)
            bar     = "█" * filled + "░" * (bar_len - filled)
            print(f"\r  [{bar}] {done}/{total}", end="", flush=True)

    if show_progress:
        print(f"  → {len(results)} matched")
        print()

    doc.close()
    return results


def scan_all(reports_dir: Path) -> list[dict]:
    pdf_files = sorted(reports_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"Error: no PDFs found in {reports_dir}", file=sys.stderr)
        sys.exit(1)

    all_results: list[dict] = []
    lock              = threading.Lock()
    pages_scanned     = [0]
    last_checkpoint   = [0]
    print_lock        = threading.Lock()

    def log(msg: str) -> None:
        with print_lock:
            print(msg, flush=True)

    def save_checkpoint(snapshot: list[dict], total_scanned: int) -> None:
        sorted_snap = sorted(snapshot, key=lambda r: (r["source"], r["page"]))
        OUT_JSON.write_text(json.dumps(sorted_snap, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"  [checkpoint] {total_scanned} pages scanned, {len(snapshot)} matched → saved")

    def worker(pdf_path: Path) -> None:
        doc     = fitz.open(str(pdf_path))
        total   = len(doc)
        matched = 0
        log(f"  ▶ {pdf_path.name}  [{total} pages]")

        for page_idx in range(total):
            page                     = doc[page_idx]
            page_num                 = page_idx + 1
            reasons, digits, density = classify_page(page)

            with lock:
                pages_scanned[0] += 1
                if reasons:
                    all_results.append({
                        "source":          pdf_path.name,
                        "page":            page_num,
                        "reasons":         reasons,
                        "numeric_density": round(density, 3),
                    })
                    matched += 1
                cur_checkpoint = pages_scanned[0] // SAVE_EVERY
                should_save    = cur_checkpoint > last_checkpoint[0]
                if should_save:
                    last_checkpoint[0] = cur_checkpoint
                    snapshot           = list(all_results)
                    cur_scanned        = pages_scanned[0]

            if should_save:
                save_checkpoint(snapshot, cur_scanned)

        doc.close()
        log(f"  ✓ {pdf_path.name}: {matched}/{total} matched")

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [executor.submit(worker, p) for p in pdf_files]
        for f in as_completed(futures):
            f.result()  # Re-raise worker exceptions.

    return all_results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", help="Path to folder containing PDF files (e.g. /Users/yourname/Downloads/annual_reports)")
    parser.add_argument("--pdf",         help="Scan only the specified PDF filename, e.g. RIO_FY2024.pdf")
    parser.add_argument("--pages",       help="Page range, e.g. 101-150")
    args = parser.parse_args()

    reports_dir = _get_reports_dir(args.reports_dir)

    if args.pdf:
        pdf_path = reports_dir / args.pdf
        if not pdf_path.exists():
            print(f"Error: {pdf_path} not found", file=sys.stderr)
            sys.exit(1)
        page_start, page_end = 1, None
        if args.pages:
            parts      = args.pages.split("-")
            page_start = int(parts[0])
            page_end   = int(parts[1]) if len(parts) > 1 else page_start
        results = scan_pdf(pdf_path, page_start, page_end)
        print(f"{args.pdf} p{page_start}-{page_end or 'end'}: {len(results)} pages matched")
        for r in results:
            print(f"  p{r['page']:>4}  density={r['numeric_density']:.3f}  {'+'.join(r['reasons'])}")
    else:
        print(f"Scanning all PDFs in {reports_dir} with {NUM_WORKERS} workers ...")
        results = scan_all(reports_dir)
        results.sort(key=lambda r: (r["source"], r["page"]))
        OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nTotal: {len(results)} pages across all PDFs")
        print(f"Saved → {OUT_JSON}")


if __name__ == "__main__":
    main()
