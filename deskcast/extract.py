# Copyright 2026 Susquehanna Timberwolf Lines, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import re
from pathlib import Path


def extract_text(path: Path) -> str:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _from_pdf(path)
    if suffix in {".docx"}:
        return _from_docx(path)
    if suffix in {".txt", ".md", ".markdown", ".csv", ".log"}:
        return path.read_text(encoding="utf-8", errors="replace")
    # Fallback: try utf-8
    return path.read_text(encoding="utf-8", errors="replace")


def _from_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        if t.strip():
            parts.append(t)
    text = "\n\n".join(parts)
    if len(text.strip()) < 40:
        raise ValueError(
            "PDF text layer is nearly empty. Run OCR first, e.g.:\n"
            f'  python -m ocrmypdf -l eng "{path}" "{path.with_name(path.stem + "_ocr.pdf")}"'
        )
    return _normalize(text)


def _from_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    return _normalize("\n\n".join(parts))


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = _strip_boilerplate(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Repeated header/footer / form junk that drowns operative clauses in legal PDFs
_BOILER_LINE = re.compile(
    r"(?i)^("
    r"confidential(\s*[-–—|].*)?|"
    r"nda(\s+confidential.*)?|"
    r"non-disclosure.*|"
    r"proprietary\s*[-–—].*restricted|"
    r".*nda restrictions apply.*|"
    r".*page\s+\d+\s+of\s+\d+.*|"
    r"rc\d+(\.\d+)?\s*\|?\s*page.*"
    r")$"
)
_BOILER_CONTAINS = re.compile(
    r"(?i)("
    r"confidential\s*[-–—]\s*nda|"
    r"nda restrictions apply|"
    r"non-disclosure,\s*non-use|"
    r"limited-distribution\s+obligations\s+apply|"
    r"obligations\s+apply\s*$|"
    r"this document contains confidential|"
    r"click or tap here to (sign|enter)|"
    r"^signature\s*$|"
    r"^date\s*:?\s*$|"
    r"^printed name\s*/?\s*title\s*:?\s*$|"
    r"^_{5,}$|"
    r"^date click or tap"
    r")"
)


def _strip_boilerplate(text: str) -> str:
    """Drop repeating NDA banners, page footers, and empty signature shells."""
    kept: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            kept.append("")
            continue
        if _BOILER_LINE.match(line):
            continue
        if _BOILER_CONTAINS.search(line) and len(line.split()) <= 18:
            continue
        # Pure TOC leader junk
        if re.fullmatch(r"[\.\s\d]+", line):
            continue
        kept.append(line)
    # Collapse runs of blanks
    out: list[str] = []
    blank = 0
    for ln in kept:
        if not ln:
            blank += 1
            if blank <= 1:
                out.append("")
            continue
        blank = 0
        out.append(ln)
    return "\n".join(out).strip()
