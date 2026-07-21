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
"""Lightweight content logic for DeskCast — no GPU, pure rules."""
from __future__ import annotations

import re
from collections import Counter
from typing import Literal

from .models import Chunk, Outline

DocKind = Literal["study_guide", "contract", "ops_brief", "report", "general"]
ChunkKind = Literal[
    "definition",
    "list",
    "warning",
    "procedure",
    "qa",
    "example",
    "summary",
    "narrative",
]


# Keyword banks (lowercase)
_STUDY = {
    "exam",
    "quiz",
    "chapter",
    "study",
    "guide",
    "certification",
    "comptia",
    "ccna",
    "objective",
    "review",
    "flashcard",
    "test",
    "practice",
}
_CONTRACT = {
    "agreement",
    "hereby",
    "party",
    "parties",
    "shall",
    "warranty",
    "indemnif",
    "liability",
    "clause",
    "whereas",
    "termination",
    "governing law",
}
_OPS = {
    "t-minus",
    "timeline",
    "checklist",
    "staging",
    "gate",
    "detention",
    "loadout",
    "radio",
    "all-call",
    "runbook",
    "sop",
}
_WARN = {
    "warning",
    "caution",
    "danger",
    "critical",
    "never",
    "do not",
    "must not",
    "risk",
    "failure",
    "illegal",
}
_PROC = {
    "step",
    "first",
    "then",
    "next",
    "finally",
    "install",
    "configure",
    "procedure",
    "how to",
}
_DEF = {
    "means",
    "defined as",
    "is a",
    "refers to",
    "definition",
    "also known as",
    "aka",
}


def detect_doc_kind(title: str, text: str) -> DocKind:
    blob = f"{title}\n{text[:8000]}".lower()
    scores = {
        "study_guide": _score(blob, _STUDY),
        "contract": _score(blob, _CONTRACT),
        "ops_brief": _score(blob, _OPS),
        "report": _score(blob, {"report", "findings", "analysis", "conclusion", "executive summary"}),
    }
    # study guide strong signals in filename/title
    if re.search(r"study\s*guide|exam|cert|comptia|ccna|network\+|a\+", title.lower()):
        scores["study_guide"] += 5
    best = max(scores, key=scores.get)
    if scores[best] < 2:
        return "general"
    return best  # type: ignore[return-value]


def classify_chunk(text: str, title: str = "") -> ChunkKind:
    t = f"{title}\n{text}".lower()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Q&A
    if re.search(r"^\s*(q|question)\s*[:.)]", text, re.I | re.M) or (
        "?" in text and re.search(r"^\s*(a|answer)\s*[:.)]", text, re.I | re.M)
    ):
        return "qa"

    # Bullet / numbered lists
    bulletish = sum(1 for ln in lines if re.match(r"^(\-|\*|\u2022|\d+[\).])\s+", ln))
    if bulletish >= 3 or (bulletish >= 2 and len(lines) <= 12):
        return "list"

    if _score(t, _WARN) >= 2:
        return "warning"
    if _score(t, _PROC) >= 2 or re.search(r"step\s+\d+", t):
        return "procedure"
    if re.search(r"\bfor example\b|\be\.g\.\b|\bsuch as\b", t) and len(text.split()) < 120:
        return "example"
    if _score(t, _DEF) >= 1 and len(text.split()) < 100:
        return "definition"
    if re.search(r"\b(summary|in conclusion|key takeaway|remember)\b", t):
        return "summary"
    return "narrative"


def enrich_outline(outline: Outline, full_text: str) -> Outline:
    """Attach doc_kind + per-chunk kinds/priority for script + UI logic."""
    doc_kind = detect_doc_kind(outline.title, full_text)
    enriched: list[Chunk] = []
    for ch in outline.chunks:
        kind = classify_chunk(ch.text, ch.title)
        priority = _priority(kind, ch.text)
        tags = _tags(ch.text, kind)
        enriched.append(
            ch.model_copy(
                update={
                    "kind": kind,
                    "priority": priority,
                    "tags": tags,
                }
            )
        )
    # Re-order: warnings / procedures first-ish within same flow? Keep order but flag.
    return outline.model_copy(update={"doc_kind": doc_kind, "chunks": enriched})


def logic_summary(outline: Outline) -> dict:
    kinds = Counter(c.kind or "narrative" for c in outline.chunks)
    return {
        "doc_kind": outline.doc_kind or "general",
        "chunk_kinds": dict(kinds),
        "high_priority": [
            {"index": c.index, "title": c.title, "kind": c.kind, "priority": c.priority}
            for c in outline.chunks
            if (c.priority or 0) >= 7
        ],
        "rules_applied": _rules_for_doc(outline.doc_kind or "general"),
    }


def _rules_for_doc(doc_kind: str) -> list[str]:
    base = [
        "PBP keeps tempo; package numbers only on first/last/every 3rd",
        "Bridges between packages (kind-to-kind transitions)",
        "Color answers Mike, then teases next title when useful",
        "Warnings / lists / defs get distinct language, not a template stamp",
        "Midpoint is a soft breath, not a hard commercial break",
        "Close recaps high-yield titles by name",
    ]
    extra = {
        "study_guide": [
            "Treat packages as study objectives",
            "Color adds exam-tip style asides",
            "Definitions get 'write this down' emphasis",
            "Open teases real high-yield titles",
        ],
        "contract": [
            "Flag obligations (shall/must)",
            "Color highlights risk and ambiguity",
        ],
        "ops_brief": [
            "Timeline language for procedures",
            "Call out critical path items",
        ],
        "report": [
            "Findings → implication structure",
        ],
        "general": [],
    }
    return base + extra.get(doc_kind, [])


def _score(blob: str, keys: set[str]) -> int:
    n = 0
    for k in keys:
        if k in blob:
            n += blob.count(k)
    return n


def _priority(kind: ChunkKind, text: str) -> int:
    base = {
        "warning": 9,
        "procedure": 8,
        "definition": 7,
        "qa": 7,
        "list": 6,
        "example": 5,
        "summary": 6,
        "narrative": 4,
    }[kind]
    # boost if dense numbers / ports / acronyms (tech study guides)
    if re.search(r"\b\d{1,5}\b", text) and re.search(r"\b[A-Z]{2,6}\b", text):
        base = min(10, base + 1)
    return base


def _tags(text: str, kind: ChunkKind) -> list[str]:
    tags = [kind]
    # Extract simple ALLCAPS / Camel tech tokens
    acros = re.findall(r"\b[A-Z]{2,6}\b", text)
    for a in acros[:6]:
        if a not in tags:
            tags.append(a)
    # Numbers that look like ports / years / counts
    nums = re.findall(r"\b\d{2,5}\b", text)
    for n in nums[:4]:
        tags.append(f"n:{n}")
    return tags[:12]


def pick_pbp_line(
    i: int,
    total: int,
    ch: Chunk,
    doc_kind: str,
    *,
    prev: Chunk | None = None,
    nxt: Chunk | None = None,
) -> str:
    """Play-by-play line with position-aware transitions (smoother desk flow)."""
    blurb = _clip(ch.text, 42)
    title = _clean_title(ch.title)
    kind = ch.kind or "narrative"
    bridge = _bridge_in(i, total, prev, ch, doc_kind)
    core = _pbp_core(kind, title, blurb, doc_kind, i, total)
    # Light handoff cue only mid-pack — not every line
    if i < total - 1 and kind in ("definition", "list", "procedure") and i % 2 == 0:
        return f"{bridge}{core} Dana — take the color."
    return f"{bridge}{core}"


def pick_color_line(
    ch: Chunk,
    doc_kind: str,
    *,
    i: int = 0,
    total: int = 1,
    nxt: Chunk | None = None,
    prev: Chunk | None = None,
) -> str:
    """Color line that answers Mike, then optionally tees the next package."""
    key = _key_sentences(ch.text, 2)
    kind = ch.kind or "narrative"
    tags = [t for t in (ch.tags or []) if t not in (kind,) and not t.startswith("n:")][:2]
    tag_bit = f" Keep an eye on {', '.join(tags)}." if tags else ""

    body = _color_core(kind, key, doc_kind, tag_bit, ch)
    # Soft transition out → next title (smoother than hard package cuts)
    if nxt is not None and i < total - 1:
        nt = _clean_title(nxt.title)
        nk = nxt.kind or "narrative"
        if (ch.priority or 0) >= 8:
            body += f" Hold that — next we slide into {nt}."
        elif nk == "warning":
            body += f" And Mike, coming up we've got a caution flag on {nt}."
        elif i % 3 == 1:
            body += f" From here, we ease into {nt}."
    return body


def _bridge_in(
    i: int,
    total: int,
    prev: Chunk | None,
    ch: Chunk,
    doc_kind: str,
) -> str:
    """Opening connector so packages don't all start the same way."""
    kind = ch.kind or "narrative"
    if i == 0:
        openers = [
            "We open the board with ",
            "First look — ",
            "Lead package: ",
        ]
        return openers[hash(ch.title) % len(openers)]
    if i == total - 1:
        return "Last package on the sheet — "
    if prev is not None:
        pk = prev.kind or "narrative"
        # Kind-to-kind transitions
        pairs = {
            ("definition", "procedure"): "With that definition locked, we go straight into process — ",
            ("definition", "list"): "Definition's down; now the board fills in — ",
            ("list", "warning"): "Coming off that checklist, here's the red flag — ",
            ("warning", "narrative"): "After that caution, we settle the context — ",
            ("procedure", "definition"): "Process leads to a term you need clean — ",
            ("narrative", "warning"): "Story sets up the risk — ",
            ("list", "procedure"): "List into sequence — ",
            ("qa", "definition"): "Question energy into a clean definition — ",
        }
        if (pk, kind) in pairs:
            return pairs[(pk, kind)]
        if (prev.priority or 0) >= 8:
            return "Building on that high-yield beat — "
        # Rotate generic bridges
        generics = [
            "Next up, ",
            "We keep rolling into ",
            "Stay with us for ",
            "From there we shift to ",
            "On the next card, ",
        ]
        return generics[i % len(generics)]
    return "Next, "


def _pbp_core(kind: str, title: str, blurb: str, doc_kind: str, i: int, total: int) -> str:
    # Only stamp package numbers occasionally (first, last, every 3rd) for less robot cadence
    stamp = (i == 0) or (i == total - 1) or (i % 3 == 0)
    num = f"(pack {i + 1} of {total}) " if stamp else ""

    if doc_kind == "study_guide":
        by_kind = {
            "definition": f"{num}definition drill — {title}. Write this: {blurb}",
            "list": f"{num}checklist — {title}. Tick it with me: {blurb}",
            "warning": f"{num}red-flag topic — {title}. Miss this and it costs you: {blurb}",
            "procedure": f"{num}step path — {title}. Here's the flow: {blurb}",
            "qa": f"{num}practice energy — {title}. Stem first: {blurb}",
            "example": f"{num}worked example — {title}. Pattern to watch: {blurb}",
            "summary": f"{num}takeaways — {title}. {blurb}",
            "narrative": f"{num}{title}. Core idea: {blurb}",
        }
        return by_kind.get(kind, by_kind["narrative"])

    if doc_kind == "contract":
        if kind == "warning":
            return f"{num}risk language in {title}. Listen close: {blurb}"
        return f"{num}{title}. On the page: {blurb}"

    if doc_kind == "ops_brief":
        if kind == "procedure":
            return f"{num}timeline — {title}. Sequence: {blurb}"
        if kind == "warning":
            return f"{num}critical risk — {title}. {blurb}"
        return f"{num}{title}. Situation: {blurb}"

    if kind == "warning":
        return f"{num}caution — {title}. {blurb}"
    if kind == "list":
        return f"{num}multi-point board — {title}. {blurb}"
    return f"{num}{title}. Here's the drive: {blurb}"


def _color_core(kind: str, key: str, doc_kind: str, tag_bit: str, ch: Chunk) -> str:
    # Rotate phrase starters so every color line doesn't sound identical
    soft = [
        "Yeah — ",
        "Exactly — ",
        "And the nuance is ",
        "Here's the color: ",
        "What I'd underline: ",
    ]
    lead = soft[ch.index % len(soft)]

    if doc_kind == "study_guide":
        by_kind = {
            "definition": f"{lead}if the exam asks what this *is*, anchor on {key}.{tag_bit}",
            "list": f"{lead}don't memorize blind — know why each item earns a seat. {key}{tag_bit}",
            "warning": f"{lead}this is trap-question fuel. {key}{tag_bit}",
            "procedure": f"{lead}order matters; flip the steps and the answer flips. {key}{tag_bit}",
            "qa": f"{lead}eliminate noise, then lock it. {key}{tag_bit}",
            "example": f"{lead}map the example back to the rule, not the story. {key}{tag_bit}",
            "summary": f"{lead}if you keep one card from this section: {key}{tag_bit}",
            "narrative": f"{lead}{key} That's the part casual readers skim past.{tag_bit}",
        }
        return by_kind.get(kind, by_kind["narrative"])

    if doc_kind == "contract":
        return f"{lead}obligation and risk live here — {key} Ambiguity is where disputes start.{tag_bit}"

    if doc_kind == "ops_brief":
        if kind == "warning":
            return f"{lead}escalate early. {key}{tag_bit}"
        return f"{lead}{key} Verify before you move.{tag_bit}"

    if kind == "warning":
        return f"{lead}raise the urgency. {key}{tag_bit}"
    return f"{lead}{key} That's why this beat matters.{tag_bit}"


def cold_open_lines(outline: Outline) -> tuple[str, str]:
    dk = outline.doc_kind or "general"
    n = len(outline.chunks)
    w = outline.total_words
    highs = [c for c in outline.chunks if (c.priority or 0) >= 7]
    high_n = len(highs)
    # Tease 1–2 real titles for a smoother runway into package 1
    teases = [_clean_title(c.title) for c in highs[:2]]
    tease = ""
    if teases:
        tease = " We'll lean hard on " + (" and ".join(teases)) + "."

    if dk == "study_guide":
        pbp = (
            f"Welcome in — study desk is lit. Tonight we pressure-test "
            f"'{outline.title}'. Not a vibe check — a knowledge check. "
            f"We move through {n} packages without the robotic checklist feel."
        )
        color = (
            f"I've marked {high_n} high-yield spots across about {w} words of source.{tease} "
            f"You keep the tempo, Mike; I'll call exam traps as they show up."
        )
    elif dk == "contract":
        pbp = (
            f"Welcome in — legal-pad energy. We're walking '{outline.title}' "
            f"like a two-minute drill on the clauses that actually bite."
        )
        color = (
            f"{n} packages on the sheet.{tease} I'll flag obligation, liability, and anything fuzzy."
        )
    elif dk == "ops_brief":
        pbp = (
            f"Desk is hot — ops brief '{outline.title}'. Timeline, risks, "
            f"and the calls that keep the night clean."
        )
        color = f"About {w} words, {n} packages.{tease} Critical path and failure points are mine."
    else:
        pbp = (
            f"Welcome in — desk is hot, lights are up. Tonight we break down "
            f"'{outline.title}' with a smooth board, not a stop-start read."
        )
        color = (
            f"{n} packages, roughly {w} words.{tease} I'll dig nuance; you keep us rolling."
        )
    return pbp, color


def close_lines(outline: Outline) -> tuple[str, str]:
    dk = outline.doc_kind or "general"
    highs = [c for c in outline.chunks if (c.priority or 0) >= 7]
    recap = ""
    if highs:
        names = ", ".join(_clean_title(c.title) for c in highs[:3])
        recap = f" High-yield recap: {names}."

    if dk == "study_guide":
        color = (
            f"Wrapping the tape:{recap} Don't just re-read — re-teach those out loud. "
            f"If you can explain it clean, you own it."
        )
        pbp = (
            f"That's the desk on '{outline.title}'. Circle the soft spots, retest, and come back sharp. "
            f"Thanks for riding with us."
        )
    elif dk == "contract":
        color = (
            f"Closing thought:{recap} If a clause is unclear, it fails on the worst day. Clarify before you sign."
        )
        pbp = f"Desk is clear on '{outline.title}'. Document it — don't assume it. See you next review."
    elif dk == "ops_brief":
        color = f"Final color:{recap} Verify, then move. Hope is not a timeline."
        pbp = f"Ops desk out on '{outline.title}'. Stay clean out there."
    else:
        color = (
            f"Wrapping:{recap} Through-line over highlights — read the full source when you can."
        )
        pbp = f"That's the desk on '{outline.title}'. Appreciate you riding along — next breakdown soon."
    return pbp, color


def midshow_bridge(outline: Outline, i: int) -> str | None:
    """Occasional soft midpoint — not a hard commercial break every time."""
    total = len(outline.chunks)
    if total < 5 or i != total // 2:
        return None
    highs = [c for c in outline.chunks[i:] if (c.priority or 0) >= 7]
    dk = outline.doc_kind or "general"
    if dk == "study_guide":
        if highs:
            return (
                f"Quick breath — still ahead: {_clean_title(highs[0].title)}. "
                f"If your notes are thin on definitions or warnings, star those now."
            )
        return "Quick breath — second half of the board. Stay with the high-yield marks."
    if highs:
        return f"Halfway house — next pressure point is {_clean_title(highs[0].title)}. Stay with us."
    return "Halfway through the board — tempo stays clean."


def _clean_title(title: str) -> str:
    t = re.sub(r"\.{2,}", " ", title)  # TOC leader dots
    t = re.sub(r"\s+\d+\s*$", "", t)  # trailing page numbers
    t = re.sub(r"\s+", " ", t).strip(" -–—\u2026,;")
    # Drop near-empty TOC junk
    if len(t) < 4 or t.lower() in {"table of contents", "contents"}:
        return "this section"
    if len(t) > 48:
        t = t[:45].rstrip() + "…"
    return t or "this package"


def _clip(text: str, words: int) -> str:
    toks = text.split()
    if len(toks) <= words:
        return text.replace("\n", " ")
    return " ".join(toks[:words]).replace("\n", " ") + "…"


def _key_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    parts = [p.strip() for p in parts if len(p.split()) > 5]
    if not parts:
        return _clip(text, 40)
    # Prefer mid-length informative sentences; avoid near-duplicates
    scored = sorted(parts, key=lambda s: abs(len(s.split()) - 16))
    picked: list[str] = []
    for s in scored:
        if any(s[:40] == p[:40] for p in picked):
            continue
        picked.append(s)
        if len(picked) >= n:
            break
    return " ".join(picked)
