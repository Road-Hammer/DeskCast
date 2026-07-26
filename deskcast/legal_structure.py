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
"""Parse contracts / legislation into a hierarchical legal structure."""
from __future__ import annotations

import re
from pathlib import Path

from .models import LegalDocument, LegalNode

# Heading patterns (order = priority when multiple match)
_HEADING_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    (
        "title",
        re.compile(
            r"(?i)^(title|part|division|subtitle|chapter|subchapter)\s+"
            r"([0-9ivxlcdm]+|[A-Z])\b[.\-:—\s]*(.*)$"
        ),
        1,
    ),
    (
        "article",
        re.compile(r"(?i)^article\s+([0-9ivxlcdm]+)\b[.\-:—\s]*(.*)$"),
        2,
    ),
    (
        "schedule",
        re.compile(
            r"(?i)^(schedule|appendix|exhibit|annex)\s+([A-Z0-9\-]+)\b[.\-:—\s]*(.*)$"
        ),
        2,
    ),
    (
        "section",
        re.compile(
            r"(?i)^(?:section|sec\.?|§)\s*(\d+(?:\.\d+)*)\b[.\-:—\s]*(.*)$"
        ),
        3,
    ),
    (
        "section",
        re.compile(r"^(\d+\.\d+(?:\.\d+)*)\s+([A-Z].{2,120})$"),
        3,
    ),
    (
        "subsection",
        re.compile(r"(?i)^(\([a-z0-9]+\))\s+(.{5,})$"),
        4,
    ),
]

_AMEND_HINT = re.compile(
    r"(?i)\b(is amended|amended to read|strike|insert after|delete the following|"
    r"as follows:|effective date|enacted by)\b"
)
_TOC_LINE = re.compile(r"\.{3,}|\s{2,}\d+\s*$")
_JUNK = re.compile(
    r"(?i)(nda restrictions|confidential\s*[-–]|click or tap|page\s+\d+\s+of\s+\d+|"
    r"obligations apply\s*$|signature\s*$)"
)


def parse_legal_structure(
    text: str,
    *,
    source: str | Path = "",
    title: str | None = None,
) -> LegalDocument:
    """
    Build a legal document tree from cleaned plain text.

    Leaves carry body text; heading-only nodes may accumulate body until the next peer/parent.
    """
    src = str(source)
    doc_title = title or (Path(src).stem if src else "Legal Document")
    doc_title = doc_title.replace("_", " ").replace("-", " ").strip()

    lines = _prep_lines(text)
    profile = _detect_profile(doc_title, text[:12000])

    # Flat list of (level, kind, label, heading_rest, body_lines)
    units: list[dict] = []
    cur: dict | None = None

    def flush():
        nonlocal cur
        if cur is None:
            return
        body = "\n".join(cur["body"]).strip()
        cur["body_text"] = body
        cur["word_count"] = len(body.split()) if body else 0
        units.append(cur)
        cur = None

    preamble: list[str] = []

    for ln in lines:
        h = _match_heading(ln)
        if h:
            flush()
            kind, level, label, rest = h
            title_line = f"{label}" + (f" — {rest}" if rest else "")
            cur = {
                "kind": kind,
                "level": level,
                "label": label,
                "title": _clean_title(title_line),
                "body": [ln],
                "is_amendment": bool(_AMEND_HINT.search(ln)),
            }
            continue
        if cur is None:
            if not _JUNK.search(ln) and not _TOC_LINE.search(ln):
                preamble.append(ln)
            continue
        if _TOC_LINE.search(ln) and len(ln) < 100:
            continue
        cur["body"].append(ln)
        if _AMEND_HINT.search(ln):
            cur["is_amendment"] = True

    flush()

    # Preamble node if substantial
    nodes: list[LegalNode] = []
    if preamble and len(" ".join(preamble).split()) >= 40:
        pre_text = "\n".join(preamble).strip()
        nodes.append(
            LegalNode(
                id="preamble",
                kind="preamble",
                label="Preamble",
                title="Preamble / front matter",
                text=pre_text,
                word_count=len(pre_text.split()),
                level=0,
            )
        )

    # Convert flat units to tree via stack
    root_children: list[LegalNode] = list(nodes)
    stack: list[LegalNode] = []
    node_i = 0

    for u in units:
        node_i += 1
        nid = f"{u['kind']}-{u['label']}-{node_i}".replace(" ", "")
        node = LegalNode(
            id=nid,
            kind=u["kind"],
            label=str(u["label"]),
            title=u["title"],
            text=u.get("body_text") or "",
            word_count=int(u.get("word_count") or 0),
            level=int(u["level"]),
            is_amendment=bool(u.get("is_amendment")),
            children=[],
        )
        while stack and stack[-1].level >= node.level:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            root_children.append(node)
        stack.append(node)

    # If nothing matched, single body node
    if not root_children:
        body = text.strip()
        root_children = [
            LegalNode(
                id="body-1",
                kind="section",
                label="1",
                title=doc_title,
                text=body,
                word_count=len(body.split()),
                level=1,
            )
        ]

    leaves = list(iter_leaves(root_children))
    total_words = sum(n.word_count for n in leaves) or sum(
        n.word_count for n in root_children
    )

    return LegalDocument(
        source=src,
        title=doc_title,
        profile=profile,  # type: ignore[arg-type]
        nodes=root_children,
        total_words=total_words,
        section_count=len(leaves),
    )


def iter_leaves(nodes: list[LegalNode]) -> list[LegalNode]:
    """Yield nodes that should become packages (prefer leaves with text)."""
    out: list[LegalNode] = []

    def walk(n: LegalNode):
        if n.children:
            # Parent with only a heading line and kids → skip empty parent text packaging
            for c in n.children:
                walk(c)
            # If parent has substantial own text beyond heading, also include
            if n.word_count >= 80 and _body_beyond_title(n):
                out.append(n)
        else:
            if n.word_count >= 12:
                out.append(n)
            elif n.text.strip():
                out.append(n)

    for n in nodes:
        walk(n)
    return out


def structure_to_outline_chunks(
    doc: LegalDocument,
    *,
    max_chunks: int | None = None,
) -> list[tuple[str, str]]:
    """
    Flatten structure to (title, body) packs for Outline, preserving order.
    Merges tiny leaves forward so packages stay speakable.
    """
    leaves = iter_leaves(doc.nodes)
    packs: list[tuple[str, str]] = []
    buf_title = ""
    buf_body: list[str] = []
    buf_words = 0

    def flush():
        nonlocal buf_title, buf_body, buf_words
        if not buf_body:
            return
        packs.append((buf_title or f"Segment {len(packs)+1}", "\n\n".join(buf_body)))
        buf_title = ""
        buf_body = []
        buf_words = 0

    for n in leaves:
        title = n.title
        body = n.text.strip()
        wc = n.word_count or len(body.split())
        if not body:
            continue
        if not buf_body:
            buf_title = title
            buf_body = [body]
            buf_words = wc
            continue
        # Merge tiny fragments
        if wc < 40 or buf_words < 60:
            buf_body.append(body)
            buf_words += wc
            continue
        flush()
        buf_title = title
        buf_body = [body]
        buf_words = wc
    flush()

    if max_chunks and len(packs) > max_chunks:
        packs = _merge_to_n(packs, max_chunks)
    return packs


def structure_markdown(doc: LegalDocument) -> str:
    lines = [
        f"# Legal structure — {doc.title}",
        "",
        f"- **Profile:** `{doc.profile}`",
        f"- **Sections (leaf packages):** {doc.section_count}",
        f"- **Words (approx):** {doc.total_words}",
        f"- **Source:** `{doc.source}`",
        "",
        "## Tree",
        "",
    ]

    def walk(n: LegalNode, depth: int = 0):
        pad = "  " * depth
        flag = " *(amendment language)*" if n.is_amendment else ""
        lines.append(
            f"{pad}- **{n.kind}** `{n.label}` — {n.title} "
            f"({n.word_count}w){flag}"
        )
        for c in n.children:
            walk(c, depth + 1)

    for n in doc.nodes:
        walk(n)
    lines.append("")
    lines.append("## Leaf order (render packages)")
    lines.append("")
    for i, n in enumerate(iter_leaves(doc.nodes), 1):
        lines.append(f"{i}. {n.title} — {n.word_count} words")
    lines.append("")
    return "\n".join(lines)


def _prep_lines(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    for raw in text.split("\n"):
        ln = re.sub(r"[ \t]+", " ", raw).strip()
        if not ln:
            continue
        # Markdown ATATX headings → plain legal headings
        ln = re.sub(r"^#{1,6}\s+", "", ln)
        # Markdown bold/italic noise on headings
        ln = re.sub(r"^\*{1,2}(.+?)\*{1,2}$", r"\1", ln)
        ln = re.sub(r"^_{1,2}(.+?)_{1,2}$", r"\1", ln)
        if _JUNK.search(ln) and len(ln.split()) <= 16:
            continue
        # Drop pure TOC leaders
        if _TOC_LINE.search(ln) and re.search(r"(?i)article|section|schedule|title", ln):
            # keep if it looks like a real heading without leader dots
            if "..." in ln or "…" in ln or re.search(r"\.\.\.", ln):
                continue
        out.append(ln)
    return out


def _match_heading(ln: str) -> tuple[str, int, str, str] | None:
    for kind, pat, level in _HEADING_PATTERNS:
        m = pat.match(ln.strip())
        if not m:
            continue
        groups = m.groups()
        if kind == "title":
            label = f"{groups[0]} {groups[1]}".strip()
            rest = (groups[2] or "").strip()
        elif kind == "schedule":
            label = f"{groups[0]} {groups[1]}".title()
            rest = (groups[2] or "").strip()
        elif kind == "article":
            label = f"Article {groups[0]}"
            rest = (groups[1] or "").strip()
        elif kind == "section":
            label = f"Section {groups[0]}" if not str(groups[0]).startswith("(") else str(groups[0])
            # second pattern: (num)(title)
            if len(groups) >= 2:
                rest = (groups[1] or "").strip()
            else:
                rest = ""
            if re.match(r"^\d+\.\d+", str(groups[0])):
                label = str(groups[0])
        else:
            label = str(groups[0])
            rest = (groups[1] if len(groups) > 1 else "") or ""
        # Reject TOC-like
        if "..." in ln or ln.count(".") > 8:
            continue
        return kind, level, label, rest
    return None


def _detect_profile(title: str, sample: str) -> str:
    blob = f"{title}\n{sample}".lower()
    leg = sum(
        1
        for k in (
            "be it enacted",
            "legislature",
            "statute",
            "public law",
            "bill no",
            "u.s.c",
            "code of",
            "is amended to read",
            "section is amended",
            "chapter ",
            "title  ",
        )
        if k in blob
    )
    con = sum(
        1
        for k in (
            "addendum",
            "agreement",
            "contractor",
            "whereas",
            "indemnif",
            "schedule ",
            "party",
            "shall ",
            "exhibit ",
        )
        if k in blob
    )
    if leg >= 2 and leg >= con:
        return "legislation"
    if con >= 2:
        return "contract"
    return "general"


def _clean_title(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip(" -–—|")
    t = re.sub(r"\.{2,}", " ", t)
    if len(t) > 100:
        t = t[:97].rstrip() + "…"
    return t or "Section"


def _body_beyond_title(n: LegalNode) -> bool:
    # crude: more than heading
    return n.word_count > len(n.title.split()) + 30


def _merge_to_n(packs: list[tuple[str, str]], n: int) -> list[tuple[str, str]]:
    if len(packs) <= n:
        return packs
    weights = [max(1, len(b.split())) for _, b in packs]
    total = sum(weights)
    target = total / n
    out: list[tuple[str, str]] = []
    i = 0
    for bi in range(n):
        if i >= len(packs):
            break
        rem_b = n - bi
        rem_i = len(packs) - i
        take_max = rem_i - (rem_b - 1)
        acc = 0
        take = 0
        title = packs[i][0]
        bodies: list[str] = []
        while take < take_max and i + take < len(packs):
            if take >= 1 and acc >= target and bi < n - 1:
                break
            bodies.append(packs[i + take][1])
            acc += weights[i + take]
            take += 1
        out.append((title, "\n\n".join(bodies)))
        i += take
    if i < len(packs) and out:
        t, b = out[-1]
        out[-1] = (t, b + "\n\n" + "\n\n".join(x[1] for x in packs[i:]))
    return out
