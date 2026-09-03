"""Quality checks for TogoQA document ingestion — 6 automated controls.

Each check returns a QualityResult with pass/fail status and details.
Documents failing critical checks are marked NEEDS_REVIEW or rejected.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

USEFUL_CHAR_THRESHOLD = 0.95
MIN_TEXT_LENGTH = 50

ALLOWED_DOMAINS = {
    "education.gouv.tg", "www.education.gouv.tg",
    "inseed.tg", "www.inseed.tg",
    "data.gouv.tg",
    "jo.gouv.tg",
    "legitogo.gouv.tg",
    "ens-superieur.gouv.tg",
    "ens-technique.gouv.tg",
    "action-sociale.gouv.tg",
    "planification.gouv.tg",
    "presidence.gouv.tg",
    "togo.gouv.tg",
    "service-public.gouv.tg",
    "uis.unesco.org",
    "planipolis.iiep.unesco.org",
    "www.unicef.org",
    "data.worldbank.org",
    "afdb.org", "www.afdb.org",
    "bceao.int", "www.bceao.int",
    "imf.org", "www.imf.org",
    "pasec.confemen.org",
    "globalpartnership.org", "www.globalpartnership.org",
    "atop.tg", "www.atop.tg",
    "editogo.tg", "www.editogo.tg",
    "togofirst.com", "www.togofirst.com",
    "republicoftogo.com", "www.republicoftogo.com",
    "icilome.com", "www.icilome.com",
    "liberte-togo.com", "www.liberte-togo.com",
    "lalternative.tg", "www.lalternative.tg",
    "fraternite-info.com", "www.fraternite-info.com",
}


@dataclass
class QualityResult:
    check: str
    passed: bool
    score: float = 1.0
    details: str = ""
    action: str = ""


@dataclass
class QualityReport:
    results: list[QualityResult] = field(default_factory=list)
    overall_passed: bool = True
    suggested_status: str = "parsed"

    def add(self, result: QualityResult):
        self.results.append(result)
        if not result.passed:
            self.overall_passed = False


def run_quality_checks(
    text: str,
    url: str = "",
    checksum: str = "",
    tables: list | None = None,
    existing_checksums: set[str] | None = None,
    school_year: str | None = None,
    reference_period: str | None = None,
) -> QualityReport:
    """Run all 6 quality checks on a parsed document."""
    report = QualityReport()

    report.add(check_readability(text))
    report.add(check_table_coherence(tables or []))
    report.add(check_period_known(text, school_year, reference_period))
    report.add(check_sums_plausible(text))
    report.add(check_duplication(checksum, existing_checksums or set()))
    report.add(check_source_allowlist(url))

    failed = [r for r in report.results if not r.passed]
    if any(r.action == "reject" for r in failed):
        report.suggested_status = "rejected"
    elif failed:
        report.suggested_status = "needs_review"
    else:
        report.suggested_status = "parsed"

    return report


def check_readability(text: str) -> QualityResult:
    """Check 1: Document is readable (>95% useful characters)."""
    if not text or len(text) < MIN_TEXT_LENGTH:
        return QualityResult(
            check="readability",
            passed=False,
            score=0.0,
            details=f"Text too short ({len(text)} chars)",
            action="needs_review",
        )

    useful = sum(1 for c in text if c.isalnum() or c.isspace() or c in ".,;:!?()-/''\"")
    ratio = useful / len(text)

    return QualityResult(
        check="readability",
        passed=ratio >= USEFUL_CHAR_THRESHOLD,
        score=ratio,
        details=f"Useful char ratio: {ratio:.2%}",
        action="" if ratio >= USEFUL_CHAR_THRESHOLD else "needs_review",
    )


def check_table_coherence(tables: list) -> QualityResult:
    """Check 2: Tables have detectable columns and consistent row lengths."""
    if not tables:
        return QualityResult(
            check="table_coherence",
            passed=True,
            score=1.0,
            details="No tables to check",
        )

    issues = []
    for i, table in enumerate(tables):
        headers = table.get("headers", []) if isinstance(table, dict) else getattr(table, "headers", [])
        rows = table.get("rows", []) if isinstance(table, dict) else getattr(table, "rows", [])

        if not headers:
            issues.append(f"Table {i + 1}: no headers detected")
            continue

        col_count = len(headers)
        bad_rows = sum(1 for row in rows if len(row) != col_count)
        if bad_rows > 0:
            issues.append(f"Table {i + 1}: {bad_rows}/{len(rows)} rows have inconsistent column count")

    if issues:
        return QualityResult(
            check="table_coherence",
            passed=False,
            score=0.5,
            details="; ".join(issues),
            action="needs_review",
        )

    return QualityResult(
        check="table_coherence",
        passed=True,
        score=1.0,
        details=f"{len(tables)} tables OK",
    )


SCHOOL_YEAR_RE = re.compile(r"20[012]\d\s*[-/]\s*20[012]\d")
YEAR_RE = re.compile(r"\b20[012]\d\b")


def check_period_known(
    text: str,
    school_year: str | None = None,
    reference_period: str | None = None,
) -> QualityResult:
    """Check 3: Document has a known reference period."""
    if school_year or reference_period:
        return QualityResult(
            check="period_known",
            passed=True,
            score=1.0,
            details=f"school_year={school_year}, reference_period={reference_period}",
        )

    if SCHOOL_YEAR_RE.search(text[:5000]):
        return QualityResult(
            check="period_known",
            passed=True,
            score=0.8,
            details="School year found in text",
        )

    if YEAR_RE.search(text[:5000]):
        return QualityResult(
            check="period_known",
            passed=True,
            score=0.6,
            details="Year found in text (no explicit school year)",
        )

    return QualityResult(
        check="period_known",
        passed=False,
        score=0.2,
        details="No date or school year detected",
        action="needs_review",
    )


TOTAL_PATTERN = re.compile(
    r"(?:total|ensemble|les deux sexes)\s*[:\s]\s*([\d\s.,]+)",
    re.IGNORECASE,
)
GIRLS_PATTERN = re.compile(
    r"(?:filles?|féminin)\s*[:\s]\s*([\d\s.,]+)",
    re.IGNORECASE,
)
BOYS_PATTERN = re.compile(
    r"(?:garçons?|masculin)\s*[:\s]\s*([\d\s.,]+)",
    re.IGNORECASE,
)


def check_sums_plausible(text: str) -> QualityResult:
    """Check 4: Girls + Boys ≈ Total when all three are present."""
    totals = TOTAL_PATTERN.findall(text[:10000])
    girls = GIRLS_PATTERN.findall(text[:10000])
    boys = BOYS_PATTERN.findall(text[:10000])

    if not (totals and girls and boys):
        return QualityResult(
            check="sums_plausible",
            passed=True,
            score=1.0,
            details="Not enough gendered data to verify",
        )

    def parse_num(s):
        s = s.strip().replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    t = parse_num(totals[0])
    g = parse_num(girls[0])
    b = parse_num(boys[0])

    if t is None or g is None or b is None or t == 0:
        return QualityResult(
            check="sums_plausible",
            passed=True,
            score=0.8,
            details="Could not parse all values",
        )

    ratio = abs((g + b) - t) / t
    passed = ratio < 0.05

    return QualityResult(
        check="sums_plausible",
        passed=passed,
        score=1.0 - ratio,
        details=f"F({g:.0f}) + M({b:.0f}) = {g + b:.0f} vs Total({t:.0f}), diff={ratio:.1%}",
        action="" if passed else "needs_review",
    )


def check_duplication(checksum: str, existing_checksums: set[str]) -> QualityResult:
    """Check 5: Document is not a duplicate (same SHA-256 checksum)."""
    if not checksum:
        return QualityResult(
            check="duplication",
            passed=True,
            score=1.0,
            details="No checksum provided",
        )

    is_dup = checksum in existing_checksums

    return QualityResult(
        check="duplication",
        passed=not is_dup,
        score=0.0 if is_dup else 1.0,
        details="Duplicate checksum found" if is_dup else "Unique document",
        action="reject" if is_dup else "",
    )


def check_source_allowlist(url: str) -> QualityResult:
    """Check 6: Document comes from an approved source domain."""
    if not url:
        return QualityResult(
            check="source_allowlist",
            passed=True,
            score=0.5,
            details="No URL to check",
        )

    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()

    if domain in ALLOWED_DOMAINS:
        return QualityResult(
            check="source_allowlist",
            passed=True,
            score=1.0,
            details=f"Domain '{domain}' is in allowlist",
        )

    if any(domain.endswith("." + d) for d in ALLOWED_DOMAINS):
        return QualityResult(
            check="source_allowlist",
            passed=True,
            score=0.9,
            details=f"Subdomain '{domain}' matches allowlist",
        )

    return QualityResult(
        check="source_allowlist",
        passed=False,
        score=0.0,
        details=f"Domain '{domain}' is NOT in allowlist",
        action="reject",
    )
