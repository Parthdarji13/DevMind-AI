"""
Unit tests for citation validation against source chunk metadata (Step 22).
Ref: PRD Section 6 (FR-07, FR-08, FR-09), Section 7; Step 22 of execution guide.
Verifies:
- Valid citations map back to exact physical source lines and snippets.
- Invented/hallucinated file paths are strictly rejected.
- Out-of-bounds line numbers are rejected.
- Multiple citation syntaxes ([File: p, Lines: s-e], [p:s-e], `p:s-e`) are recognized.
- Inverted line ranges are normalized.
- Empty or citation-free text is handled safely.
"""
import pytest

from backend.app.models.chat import Citation
from backend.app.models.chunk import CodeChunk
from backend.app.services.llm.citation_validator import (
    CitationStatus,
    CitationValidator,
)


def _make_chunk(
    chunk_id: str,
    file_path: str,
    start_line: int,
    end_line: int,
    content: str,
) -> CodeChunk:
    lines = content.splitlines() or [""]
    return CodeChunk(
        chunk_id=chunk_id,
        repo_id="test_repo",
        file_path=file_path,
        language="python",
        start_line=start_line,
        end_line=end_line,
        content=content,
        chunk_index=0,
        char_count=len(content),
        line_count=len(lines),
    )


def test_valid_citation_fixture_maps_to_exact_source_lines():
    """Verify citation fixture maps back to exact source lines and extracts correct snippet."""
    source_content = (
        "def compute_tax(subtotal: float, rate: float) -> float:\n"
        "    tax = subtotal * rate\n"
        "    return round(tax, 2)\n"
        "def format_currency(amount: float) -> str:\n"
        "    return f'${amount:.2f}'"
    )
    chunk = _make_chunk(
        chunk_id="chk_tax",
        file_path="billing/tax_calculator.py",
        start_line=20,
        end_line=24,
        content=source_content,
    )

    validator = CitationValidator()
    text = (
        "Tax is calculated using compute_tax in "
        "[File: billing/tax_calculator.py, Lines: 20-22]."
    )

    report = validator.process_text_citations(text, [chunk])

    assert report.total_extracted == 1
    assert len(report.valid_citations) == 1
    assert len(report.invalid_citations) == 0

    cit = report.valid_citations[0]
    assert cit.file_path == "billing/tax_calculator.py"
    assert cit.start_line == 20
    assert cit.end_line == 22
    assert cit.chunk_id == "chk_tax"
    assert cit.snippet is not None

    expected_snippet = (
        "def compute_tax(subtotal: float, rate: float) -> float:\n"
        "    tax = subtotal * rate\n"
        "    return round(tax, 2)"
    )
    assert cit.snippet == expected_snippet


def test_rejection_of_hallucinated_file():
    """Verify invented files not in retrieved chunks are rejected."""
    chunk = _make_chunk(
        chunk_id="chk_auth",
        file_path="services/auth.py",
        start_line=1,
        end_line=10,
        content="def login(): pass",
    )

    validator = CitationValidator()
    # Hallucinated file: billing/stripe_webhook.py
    text = (
        "Webhooks are handled in [File: billing/stripe_webhook.py, Lines: 1-10]."
    )

    report = validator.process_text_citations(text, [chunk])

    assert report.total_extracted == 1
    assert len(report.valid_citations) == 0
    assert len(report.invalid_citations) == 1
    assert report.invalid_citations[0].status == CitationStatus.UNKNOWN_FILE
    assert "does not exist in retrieved evidence" in report.invalid_citations[0].reason


def test_rejection_of_out_of_bounds_lines():
    """Verify line numbers falling outside chunk boundaries are rejected."""
    chunk = _make_chunk(
        chunk_id="chk_auth",
        file_path="services/auth.py",
        start_line=10,
        end_line=25,
        content="def login():\n    return True",
    )

    validator = CitationValidator()
    # Chunk only covers lines 10-25; citation claims lines 500-520!
    text = (
        "Sessions are terminated in [File: services/auth.py, Lines: 500-520]."
    )

    report = validator.process_text_citations(text, [chunk])

    assert report.total_extracted == 1
    assert len(report.valid_citations) == 0
    assert len(report.invalid_citations) == 1
    assert report.invalid_citations[0].status == CitationStatus.OUT_OF_BOUNDS
    assert "fall outside the line boundaries" in report.invalid_citations[0].reason


def test_multiple_citation_syntax_formats():
    """Verify all supported citation format syntaxes are parsed and validated."""
    c1 = _make_chunk("chk_1", "src/models.py", 5, 15, "class User:\n    id: int")
    c2 = _make_chunk("chk_2", "src/api.py", 1, 20, "@app.get('/users')\ndef list_users(): pass")

    validator = CitationValidator()
    text = (
        "Users are defined in [src/models.py:5-10] and "
        "listed via the endpoint in `src/api.py:1-5`."
    )

    report = validator.process_text_citations(text, [c1, c2])

    assert report.total_extracted == 2
    assert len(report.valid_citations) == 2
    assert report.valid_citations[0].file_path == "src/models.py"
    assert report.valid_citations[1].file_path == "src/api.py"


def test_inverted_range_normalization():
    """Verify citations with inverted start/end lines are normalized correctly."""
    chunk = _make_chunk("chk_1", "app/utils.py", 1, 30, "def helper(): pass")

    validator = CitationValidator()
    # Inverted: 20-10
    text = "Helper function is at [File: app/utils.py, Lines: 20-10]."

    report = validator.process_text_citations(text, [chunk])

    assert len(report.valid_citations) == 1
    assert report.valid_citations[0].start_line == 10
    assert report.valid_citations[0].end_line == 20


def test_citation_free_text_handling():
    """Verify responses without citations are handled cleanly without error."""
    chunk = _make_chunk("chk_1", "app/main.py", 1, 10, "app = FastAPI()")
    validator = CitationValidator()

    text = "This response contains no bracketed citations or file references."
    report = validator.process_text_citations(text, [chunk])

    assert report.total_extracted == 0
    assert len(report.valid_citations) == 0
    assert len(report.invalid_citations) == 0
