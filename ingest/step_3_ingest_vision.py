"""
step_3_ingest_vision.py — Extract tables from PDF pages listed in filtered_pages.json.

Results are appended to ingest/output_vision.json.
Progress is tracked in ingest/step_3_checkpoint.jsonl for resume support.
After each PDF, the user is asked whether to continue to the next one.

Usage:
    uv run python ingest/step_3_ingest_vision.py
"""

import base64
import datetime
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import fitz
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from step_3_prompts import build_vision_messages

load_dotenv()

_ROOT           = Path(__file__).parent.parent
FILTERED_PAGES  = Path("ingest/filtered_pages.json")
OUT_JSON        = Path("ingest/output_vison.json")
CHECKPOINT_PATH = Path("ingest/step_3_checkpoint.jsonl")

VISION_MODEL      = "gemini-2.5-flash-lite"
VISION_ZOOM       = 2.0
VISION_MAX_TOKENS = 12000
VISION_WORKERS    = 32

_json_lock = threading.Lock()
_ckpt_lock = threading.Lock()


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


def _log(msg: str) -> None:
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _page_id(source: str, page: int) -> str:
    return f"{source}__p{page}"


# ── Checkpoint ────────────────────────────────────────────────────────────────

def load_checkpoint() -> set[str]:
    if not CHECKPOINT_PATH.exists():
        return set()
    done: set[str] = set()
    for line in CHECKPOINT_PATH.read_text().splitlines():
        try:
            row = json.loads(line)
            if row.get("status") == "success":
                done.add(row["id"])
        except (json.JSONDecodeError, KeyError):
            pass
    return done


def _record(source: str, page: int, status: str, n_tables: int = 0) -> None:
    row = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "id": _page_id(source, page),
        "source": source,
        "page": page,
        "status": status,
        "n_tables": n_tables,
    }
    with _ckpt_lock:
        with open(CHECKPOINT_PATH, "a") as f:
            f.write(json.dumps(row) + "\n")


def _write_tables(tables: list[dict]) -> None:
    with _json_lock:
        existing = json.loads(OUT_JSON.read_text(encoding="utf-8")) if OUT_JSON.exists() else []
        OUT_JSON.write_text(json.dumps(existing + tables, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Targets ───────────────────────────────────────────────────────────────────

def load_targets() -> dict[str, list[int]]:
    entries = json.loads(FILTERED_PAGES.read_text(encoding="utf-8"))
    targets: dict[str, list[int]] = {}
    for e in entries:
        targets.setdefault(e["source"], []).append(e["page"])
    return targets


# ── Vision API ────────────────────────────────────────────────────────────────

def _make_client() -> OpenAI:
    key = os.getenv("GOOGLE_API_KEY")
    if key:
        return OpenAI(api_key=key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/", max_retries=0)
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"), max_retries=0)


def _extract_json(text: str) -> list:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        r = json.loads(text)
        return r if isinstance(r, list) else [r]
    except json.JSONDecodeError:
        pass
    merged, i = [], 0
    while i < len(text):
        if text[i] != '[':
            i += 1
            continue
        depth = in_str = escape_next = False
        depth = 0
        for j in range(i, len(text)):
            ch = text[j]
            if escape_next:        escape_next = False
            elif ch == '\\' and in_str: escape_next = True
            elif ch == '"':        in_str = not in_str
            elif not in_str:
                if ch == '[':   depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        try: merged.extend(json.loads(text[i:j+1]))
                        except json.JSONDecodeError: pass
                        i = j + 1
                        break
        else:
            break
    if merged:
        return merged
    raise json.JSONDecodeError("No valid JSON array found", text, 0)


def call_vision(img_bytes: bytes, source: str, page_num: int, client: OpenAI) -> list[dict] | None:
    """Return list of tables on success (empty list = no tables), None on failure."""
    messages = build_vision_messages(base64.b64encode(img_bytes).decode(), source, page_num)
    raw_text = ""
    for attempt in range(3):
        try:
            resp     = client.chat.completions.create(model=VISION_MODEL, max_tokens=VISION_MAX_TOKENS, messages=messages)
            raw_text = (resp.choices[0].message.content or "").strip()
            tables   = _extract_json(raw_text)
            return [
                {"source": source, "page": page_num, "table_index": i,
                 "title": t.get("title", ""), "header_rows": len(t.get("headers", [])) or 1,
                 "headers": t.get("headers", []), "rows": t.get("rows", [])}
                for i, t in enumerate(tables)
            ]
        except RateLimitError:
            if attempt < 2:
                _log(f"  p{page_num}: [rate limit] waiting 65s before retry ({attempt+1}/3)...")
                time.sleep(65)
            else:
                _log(f"  p{page_num}: [FAILED] rate limit — gave up after 3 retries")
                return None
        except json.JSONDecodeError as e:
            _log(f"  p{page_num}: [FAILED] JSON parse error: {e}")
            _log(f"  p{page_num}: raw model output ({len(raw_text)} chars): {raw_text[:500]}")
            return None
        except Exception as e:
            _log(f"  p{page_num}: [FAILED] {type(e).__name__}: {e}")
            return None
    return None


# ── Per-PDF processing ────────────────────────────────────────────────────────

def process_pdf(source: str, pages: list[int], client: OpenAI, done_ids: set[str], reports_dir: Path) -> int:
    pdf_path = reports_dir / source
    if not pdf_path.exists():
        _log(f"  {source} not found, skipping.")
        return 0

    # Pass 1 (serial): render pages to PNG bytes — fitz is not thread-safe
    doc        = fitz.open(str(pdf_path))
    to_process = []
    skipped    = 0
    for page_num in pages:
        if _page_id(source, page_num) in done_ids:
            skipped += 1
            continue
        if page_num - 1 >= len(doc):
            _log(f"  p{page_num}: out of range, skipping")
            continue
        img_bytes = doc[page_num - 1].get_pixmap(matrix=fitz.Matrix(VISION_ZOOM, VISION_ZOOM)).tobytes("png")
        to_process.append((page_num, img_bytes))
    doc.close()

    if skipped:
        _log(f"  Skipped {skipped} already-processed page(s).")
    if not to_process:
        return 0

    # Pass 2 (concurrent): call Vision API for all pending pages
    results: dict[int, int] = {}   # page_num → n_tables (-1 = failed)

    def _call_page(page_num: int, img_bytes: bytes) -> None:
        _log(f"  p{page_num}: calling vision model...")
        tables = call_vision(img_bytes, source, page_num, client)
        if tables is None:
            _record(source, page_num, "failed")
            _log(f"  p{page_num}: recorded as failed, will retry next run")
            results[page_num] = -1
            return
        if tables:
            _write_tables(tables)
            for t in tables:
                _log(f"    → table [{t['table_index']}]: {t['title'] or '(no title)'}")
        _record(source, page_num, "success", len(tables))
        done_ids.add(_page_id(source, page_num))
        results[page_num] = len(tables)
        _log(f"  p{page_num}: done — {len(tables)} table(s)")

    with ThreadPoolExecutor(max_workers=VISION_WORKERS) as executor:
        futures = {executor.submit(_call_page, pn, ib): pn for pn, ib in to_process}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                pn = futures[future]
                _log(f"  p{pn}: [FAILED] unexpected worker error: {e}")
                results[pn] = -1

    return sum(v for v in results.values() if v > 0)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Extract tables from PDF pages using vision model.")
    parser.add_argument("--reports-dir", help="Path to folder containing PDF files (e.g. /Users/yourname/Downloads/annual_reports)")
    args = parser.parse_args()

    if not FILTERED_PAGES.exists():
        print(f"Error: {FILTERED_PAGES} not found. Run step_2_PyMuPDF_filter.py first.", file=sys.stderr)
        sys.exit(1)
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")):
        print("Error: GOOGLE_API_KEY or OPENAI_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    reports_dir = _get_reports_dir(args.reports_dir)
    targets     = load_targets()
    done_ids    = load_checkpoint()
    client      = _make_client()
    provider    = "Gemini" if os.getenv("GOOGLE_API_KEY") else "OpenAI"

    total_pages = sum(len(v) for v in targets.values())
    pending     = sum(1 for src, pages in targets.items() for p in pages if _page_id(src, p) not in done_ids)
    _log(f"{total_pages} pages across {len(targets)} PDFs  |  pending: {pending}  |  {VISION_MODEL} via {provider}")

    sources      = list(targets.items())
    total_tables = 0
    for source, pages in sources:
        pending_pages = [p for p in pages if _page_id(source, p) not in done_ids]
        if not pending_pages:
            _log(f"[skip] {source}")
            continue

        _log(f"[start] {source}  ({len(pending_pages)} page(s))")
        n = process_pdf(source, pages, client, done_ids, reports_dir)
        total_tables += n
        _log(f"[done]  {source}  → {n} new table(s)")

    _log(f"Finished. {total_tables} new table(s) this run.")
    if OUT_JSON.exists():
        _log(f"{OUT_JSON.name} total: {len(json.loads(OUT_JSON.read_text(encoding='utf-8')))} table(s)")


if __name__ == "__main__":
    main()
