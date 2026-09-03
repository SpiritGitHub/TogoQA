"""Table extraction for TogoQA — PDF (Camelot) and HTML (pandas).

Extracts tabular data from documents, normalizes column names,
and produces structured records ready for the observations table.
"""

import io
import logging
import re
import tempfile
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    page_num: int | None
    headers: list[str]
    rows: list[list[str]]
    title: str = ""
    source: str = "html"
    accuracy: float | None = None


def extract_tables_html(html: str | bytes) -> list[ExtractedTable]:
    """Extract tables from HTML using pandas.read_html."""
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas not installed")
        return []

    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")

    try:
        dfs = pd.read_html(io.StringIO(html), flavor="bs4")
    except ValueError:
        return []
    except Exception as e:
        logger.warning("pandas.read_html failed: %s", e)
        return []

    tables = []
    for i, df in enumerate(dfs):
        if df.shape[0] < 1 or df.shape[1] < 2:
            continue
        headers = [str(c).strip() for c in df.columns]
        rows = []
        for _, row in df.iterrows():
            rows.append([str(v).strip() if not _is_nan(v) else "" for v in row])
        tables.append(ExtractedTable(
            page_num=None,
            headers=headers,
            rows=rows,
            title=f"Table {i + 1}",
            source="html",
        ))

    return tables


def extract_tables_pdf(raw: bytes, flavor: str = "lattice") -> list[ExtractedTable]:
    """Extract tables from a PDF using Camelot.

    flavor: 'lattice' (ruled tables) or 'stream' (whitespace-separated).
    Falls back to stream if lattice finds nothing.
    """
    try:
        import camelot
    except ImportError:
        logger.error("camelot-py not installed: pip install camelot-py[base]")
        return []

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        table_list = camelot.read_pdf(tmp_path, flavor=flavor, pages="all")

        if len(table_list) == 0 and flavor == "lattice":
            logger.debug("Lattice found no tables, trying stream mode")
            table_list = camelot.read_pdf(tmp_path, flavor="stream", pages="all")

        tables = []
        for t in table_list:
            df = t.df
            if df.shape[0] < 2 or df.shape[1] < 2:
                continue

            headers = [str(c).strip() for c in df.iloc[0]]
            rows = []
            for _, row in df.iloc[1:].iterrows():
                rows.append([str(v).strip() for v in row])

            tables.append(ExtractedTable(
                page_num=t.page,
                headers=headers,
                rows=rows,
                title=f"Table p.{t.page}",
                source="pdf_camelot",
                accuracy=t.accuracy if hasattr(t, "accuracy") else None,
            ))

        return tables

    except Exception as e:
        logger.warning("Camelot extraction failed: %s", e)
        return []
    finally:
        import os
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def normalize_headers(headers: list[str]) -> list[str]:
    """Normalize table column headers to lowercase snake_case."""
    normalized = []
    for h in headers:
        h = h.lower().strip()
        h = re.sub(r"[''`]", "", h)
        h = re.sub(r"[^a-zàâéèêëïîôùûüç0-9]+", "_", h)
        h = h.strip("_")
        normalized.append(h)
    return normalized


def table_to_records(table: ExtractedTable) -> list[dict]:
    """Convert an ExtractedTable to a list of dicts keyed by normalized headers."""
    norm = normalize_headers(table.headers)
    records = []
    for row in table.rows:
        record = {}
        for key, val in zip(norm, row):
            if key and val:
                record[key] = val
        if record:
            records.append(record)
    return records


def _is_nan(value) -> bool:
    try:
        import math
        return math.isnan(float(value))
    except (ValueError, TypeError):
        return str(value).lower() == "nan"
