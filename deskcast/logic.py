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
    "addendum",
    "schedule",
    "appendix",
    "exhibit",
    "obligation",
    "obligations",
    "contractor",
    "client",
    "covenant",
    "breach",
    "remedies",
    "consideration",
    "precedence",
    "continuance",
    "continuity",
    "intellectual property",
    "confidential",
    "representation",
    "warranty",
    "severability",
    "assignment",
    "notice",
    "effective date",
    "board authorization",
    "special project",
    "invoice",
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
    "shall not",
    "may not",
    "risk",
    "failure",
    "illegal",
    "breach",
    "default",
    "penalty",
    "indemnif",
    "liability",
    "terminate for cause",
    "material breach",
    "without limitation",
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
    if re.search(r"addendum|agreement|contract|msa|sow|continuity|indemnif", title.lower()):
        scores["contract"] += 6
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

    # Bullet / numbered lists (including 0.1 / 1.2 style contract subsections)
    bulletish = sum(
        1
        for ln in lines
        if re.match(r"^(\-|\*|\u2022|\d+[\).]|[a-z][\).]|\d+\.\d+)\s+", ln, re.I)
    )
    if bulletish >= 3 or (bulletish >= 2 and len(lines) <= 14):
        return "list"

    # Contract risk / restriction language
    if _score(t, _WARN) >= 2 or re.search(
        r"\b(shall not|must not|may not|liable for|indemnif|material breach|terminate)\b", t
    ):
        if _score(t, _WARN) >= 1 or "shall not" in t or "must not" in t:
            return "warning"

    # Definitions / interpretations
    if re.search(
        r"\b(means|for purposes of|as used herein|defined terms?|interpretation)\b", t
    ) and (len(text.split()) < 160 or "means" in t):
        return "definition"

    if _score(t, _PROC) >= 2 or re.search(r"step\s+\d+", t):
        return "procedure"
    if re.search(r"\bfor example\b|\be\.g\.\b|\bsuch as\b", t) and len(text.split()) < 120:
        return "example"
    if _score(t, _DEF) >= 1 and len(text.split()) < 100:
        return "definition"
    if re.search(r"\b(summary|in conclusion|key takeaway|remember|recitals)\b", t):
        return "summary"
    # Operative shall/must without warning → treat as procedure/obligation path
    if re.search(r"\b(shall|must|is required to|agrees to)\b", t) and len(text.split()) < 220:
        return "procedure"
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
            "Skip NDA/header noise; voice operative clauses only",
            "Flag obligations (shall/must) and restrictions (shall not)",
            "Color highlights risk, liability, precedence, and ambiguity",
            "Name each Article/Section title so the walkthrough is a full sheet, not a skim",
            "Surface schedules/appendices and money/IP/authority terms",
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
    # boost hard obligation / restriction language
    if re.search(r"(?i)\b(shall not|must not|material breach|indemnif|order of precedence)\b", text):
        base = min(10, base + 2)
    elif re.search(r"(?i)\b(shall|must|agrees to)\b", text):
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
    desk_style: str = "sports",
) -> str:
    """Play-by-play line with position-aware transitions (smoother desk flow)."""
    # Self-contained: longer blurb so the audio carries the clause, not just a pointer
    blurb_n = 70 if doc_kind == "contract" else 42
    blurb = _clip(ch.text, blurb_n)
    title = _clean_title(ch.title)
    kind = ch.kind or "narrative"
    bridge = _bridge_in(i, total, prev, ch, doc_kind, desk_style=desk_style)
    core = _pbp_core(kind, title, blurb, doc_kind, i, total, desk_style=desk_style)
    # Light handoff cue only mid-pack — not every line
    if i < total - 1 and kind in ("definition", "list", "procedure") and i % 2 == 0:
        if desk_style == "clear_channel":
            return f"{bridge}{core} Dale — take the road read."
        if desk_style == "night_watch":
            return f"{bridge}{core} Dana — hold the light on this one."
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
    desk_style: str = "sports",
) -> str:
    """Color line that answers the lead host, then optionally tees the next package."""
    key_n = 3 if doc_kind == "contract" else 2
    key = _key_sentences(ch.text, key_n)
    kind = ch.kind or "narrative"
    tags = [t for t in (ch.tags or []) if t not in (kind,) and not t.startswith("n:")][:2]
    tag_bit = f" Keep an eye on {', '.join(tags)}." if tags else ""

    body = _color_core(kind, key, doc_kind, tag_bit, ch, desk_style=desk_style)
    # Soft transition out → next title (smoother than hard package cuts)
    if nxt is not None and i < total - 1 and doc_kind != "contract":
        nt = _clean_title(nxt.title)
        nk = nxt.kind or "narrative"
        if (ch.priority or 0) >= 8:
            body += f" Hold that — next we slide into {nt}."
        elif nk == "warning":
            if desk_style == "clear_channel":
                body += f" And Bo, next up we've got a yellow on {nt}."
            else:
                body += f" And Mike, coming up we've got a caution flag on {nt}."
        elif i % 3 == 1:
            body += f" From here, we ease into {nt}."
    elif nxt is not None and i < total - 1 and doc_kind == "contract" and i % 4 == 0:
        # Sparse next-title cues only — keep airtime on the clause itself
        if desk_style == "clear_channel":
            body += f" Down the road a piece: {_clean_title(nxt.title)}."
        else:
            body += f" Next package: {_clean_title(nxt.title)}."
    return body


def pick_readthrough_line(
    ch: Chunk, doc_kind: str, *, desk_style: str = "sports"
) -> str | None:
    """
    Extra self-contained beat: read operative text on air so the cast
    stands alone without the PDF open.
    """
    if doc_kind != "contract":
        return None
    if (ch.priority or 0) < 7 and (ch.kind or "") not in ("warning", "procedure", "definition"):
        return None
    quote = _best_readthrough(ch.text, max_words=95)
    if not quote or len(quote.split()) < 12:
        return None
    title = _clean_title(ch.title)
    if desk_style == "clear_channel":
        leads = [
            f"Straight off the page, under {title}: {quote}",
            f"Here's the controlling language on {title}, no varnish: {quote}",
            f"Listen close — {title}: {quote}",
        ]
    elif desk_style == "night_watch":
        leads = [
            f"The instrument itself, under {title}: {quote}",
            f"In the quiet, the text says this — {title}: {quote}",
            f"Reading the operative line on {title}: {quote}",
        ]
    else:
        leads = [
            f"On the instrument, under {title}: {quote}",
            f"Reading the controlling language on {title}: {quote}",
            f"Plain text from the sheet — {title}: {quote}",
        ]
    return leads[ch.index % len(leads)]


def _bridge_in(
    i: int,
    total: int,
    prev: Chunk | None,
    ch: Chunk,
    doc_kind: str,
    *,
    desk_style: str = "sports",
) -> str:
    """Opening connector so packages don't all start the same way."""
    kind = ch.kind or "narrative"
    if desk_style == "clear_channel":
        if i == 0:
            openers = [
                "First marker on the map — ",
                "We roll out with ",
                "Lead stretch: ",
            ]
            return openers[i % len(openers)]
        if i == total - 1:
            return "Last stretch before we park it — "
        openers = [
            "Next mile marker — ",
            "Keep it in gear for ",
            "Along the board now: ",
            "Still rolling — ",
        ]
        return openers[i % len(openers)]
    if desk_style == "night_watch":
        if i == 0:
            return "We begin in the quiet with "
        if i == total - 1:
            return "Final package before we close the room — "
        openers = [
            "Another layer — ",
            "Stay with me for ",
            "Now the text shifts to ",
        ]
        return openers[i % len(openers)]
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


def _pbp_core(
    kind: str,
    title: str,
    blurb: str,
    doc_kind: str,
    i: int,
    total: int,
    *,
    desk_style: str = "sports",
) -> str:
    # Only stamp package numbers occasionally (first, last, every 3rd) for less robot cadence
    stamp = (i == 0) or (i == total - 1) or (i % 3 == 0)
    if desk_style == "clear_channel":
        num = f"package {i + 1} of {total}, " if stamp else ""
    elif desk_style == "night_watch":
        num = f"layer {i + 1} of {total}. " if stamp else ""
    else:
        num = f"(pack {i + 1} of {total}) " if stamp else ""

    if desk_style == "clear_channel" and doc_kind == "contract":
        by_kind = {
            "warning": f"{num}watch this fence line — {title}. {blurb}",
            "procedure": f"{num}who owes what on {title}: {blurb}",
            "definition": f"{num}words that steer the whole sheet — {title}. {blurb}",
            "list": f"{num}stack of hooks under {title}: {blurb}",
            "summary": f"{num}pull it together on {title}. {blurb}",
            "narrative": f"{num}{title}. On the sheet: {blurb}",
        }
        return by_kind.get(kind, by_kind["narrative"])

    if desk_style == "night_watch" and doc_kind == "contract":
        by_kind = {
            "warning": f"{num}this one has teeth — {title}. {blurb}",
            "procedure": f"{num}duty under {title}: {blurb}",
            "definition": f"{num}defined carefully — {title}. {blurb}",
            "list": f"{num}several strands under {title}: {blurb}",
            "summary": f"{num}{title}. {blurb}",
            "narrative": f"{num}{title}. The text says: {blurb}",
        }
        return by_kind.get(kind, by_kind["narrative"])

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
        by_kind = {
            "warning": f"{num}restriction / risk — {title}. Listen close: {blurb}",
            "procedure": f"{num}operative duty — {title}. Who must do what: {blurb}",
            "definition": f"{num}defined terms — {title}. Precision matters: {blurb}",
            "list": f"{num}clause stack — {title}. Points on the page: {blurb}",
            "summary": f"{num}controlling summary — {title}. {blurb}",
            "narrative": f"{num}{title}. On the sheet: {blurb}",
        }
        return by_kind.get(kind, by_kind["narrative"])

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


def _color_core(
    kind: str,
    key: str,
    doc_kind: str,
    tag_bit: str,
    ch: Chunk,
    *,
    desk_style: str = "sports",
) -> str:
    # Rotate phrase starters so every color line doesn't sound identical
    if desk_style == "clear_channel":
        soft = [
            "Plain talk — ",
            "Here's the practical bite: ",
            "What bites on the road: ",
            "Don't miss this one — ",
            "From the cab side: ",
        ]
    elif desk_style == "night_watch":
        soft = [
            "Steady now — ",
            "Listen to the edge of it: ",
            "What I'd keep in the dark: ",
            "Ground it here: ",
            "The risk under that: ",
        ]
    else:
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
        shall = _obligation_pull(ch.text)
        core = shall or key
        if desk_style == "clear_channel":
            by_kind = {
                "warning": f"{lead}if you ignore this, the deal goes sideways — {core}{tag_bit}",
                "procedure": f"{lead}someone has to own this: {core} Fuzzy deadline? Get it in writing.{tag_bit}",
                "definition": f"{lead}these words steer everything after them — {core}{tag_bit}",
                "list": f"{lead}walk each hook one at a time: {core}{tag_bit}",
                "summary": f"{lead}one control to keep in the pocket: {core}{tag_bit}",
                "narrative": f"{lead}{core} Fuzzy language is where the argument starts.{tag_bit}",
            }
            return by_kind.get(kind, by_kind["narrative"])
        by_kind = {
            "warning": f"{lead}this is where a deal goes sideways if ignored — {core}{tag_bit}",
            "procedure": f"{lead}duty language: {core} If the actor or deadline is fuzzy, fix it in writing.{tag_bit}",
            "definition": f"{lead}definitions control the rest of the instrument — {core}{tag_bit}",
            "list": f"{lead}walk the list; each item is a separate hook: {core}{tag_bit}",
            "summary": f"{lead}if you remember one control from this pack: {core}{tag_bit}",
            "narrative": f"{lead}{core} Ambiguity is where disputes start.{tag_bit}",
        }
        return by_kind.get(kind, by_kind["narrative"])

    if doc_kind == "ops_brief":
        if kind == "warning":
            return f"{lead}escalate early. {key}{tag_bit}"
        return f"{lead}{key} Verify before you move.{tag_bit}"

    if kind == "warning":
        return f"{lead}raise the urgency. {key}{tag_bit}"
    return f"{lead}{key} That's why this beat matters.{tag_bit}"


def cold_open_lines(
    outline: Outline,
    *,
    desk_style: str = "sports",
) -> tuple[str, str]:
    dk = outline.doc_kind or "general"
    n = len(outline.chunks)
    w = outline.total_words
    highs = [c for c in outline.chunks if (c.priority or 0) >= 7 and _is_substantive_title(c.title)]
    if not highs:
        highs = [c for c in outline.chunks if _is_substantive_title(c.title)][:4]
    high_n = len([c for c in outline.chunks if (c.priority or 0) >= 7])
    # Tease 1–2 real titles for a smoother runway into package 1
    teases = [_clean_title(c.title) for c in highs[:2]]
    tease = ""
    if teases:
        tease = " We'll lean hard on " + (" and ".join(teases)) + "."

    # Overnight clear-channel lane (Bo/Dale unofficial test)
    if desk_style == "clear_channel":
        if dk == "contract":
            pbp = (
                f"Good evening out there — wherever you're rolling. "
                f"We've got '{outline.title}' on the board tonight: a self-contained walk, "
                f"so you can follow along without the PDF on the seat beside you. "
                f"{n} stretches of the instrument, real shall and shall-not language, "
                f"no NDA wallpaper on the mic."
            )
            color = (
                f"About {w} words of body text, {n} packages.{tease} "
                f"I'll call the practical bites — fees that keep running, notices that have to land, "
                f"what actually holds if someone tests the fence. You keep us steady, Bo."
            )
        else:
            pbp = (
                f"Night stretch is open. '{outline.title}' is our cargo for the next little while — "
                f"{n} packages, easy pace, nothing rushed."
            )
            color = (
                f"Roughly {w} words on the board.{tease} "
                f"I'll flag the hard edges; you keep the lane warm."
            )
        return pbp, color

    # Late-night watch lane (Art unofficial test)
    if desk_style == "night_watch":
        if dk == "contract":
            pbp = (
                f"It's late, the board is quiet, and the document has teeth. "
                f"Tonight: '{outline.title}'. We read the operative language out loud — "
                f"{n} packages — so nothing hides in the fine print while the room is still."
            )
            color = (
                f"{w} words of body, {n} packs.{tease} "
                f"I'll ground the risk: liability, precedence, what fails closed. "
                f"You open the door, Art; I'll keep the flashlight steady."
            )
        else:
            pbp = (
                f"Night Watch is open. '{outline.title}' — {n} packages, "
                f"slow enough to hear what the text is really saying."
            )
            color = f"About {w} words.{tease} Nuance and risk flags are mine."
        return pbp, color

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
            f"Welcome in — contract desk is live. This cast is self-contained: "
            f"we read the operative language on air so you can follow '{outline.title}' "
            f"without the PDF open. Full sheet walk — duties, restrictions, money, "
            f"authority, IP, schedules. NDA page banners stay off the mic."
        )
        color = (
            f"{n} packages, about {w} words of body text on the board.{tease} "
            f"I'll pull shall/must, shall-not, precedence, and liability out loud — "
            f"not as a skim, as a working read."
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


def close_lines(outline: Outline, *, desk_style: str = "sports") -> tuple[str, str]:
    dk = outline.doc_kind or "general"
    highs = [c for c in outline.chunks if (c.priority or 0) >= 7]
    recap = ""
    if highs:
        names = ", ".join(_clean_title(c.title) for c in highs[:3])
        recap = f" High-yield recap: {names}."

    if desk_style == "clear_channel":
        if dk == "contract":
            color = (
                f"Last word from the road side:{recap} Put a name on every shall and shall-not. "
                f"If it's fuzzy, it fails on the worst night — fix it before you sign."
            )
            pbp = (
                f"We're parking it on '{outline.title}'. Full-sheet walk, not a skim. "
                f"Keep the exceptions written down. Safe miles — we'll catch you on the next stretch."
            )
        else:
            color = f"Winding down:{recap} Keep the hard edges marked."
            pbp = f"Clear channel out on '{outline.title}'. Appreciate you riding along."
        return pbp, color

    if desk_style == "night_watch":
        if dk == "contract":
            color = (
                f"Before we kill the lights:{recap} Map every obligation to an owner. "
                f"Ambiguity is where the bad night starts."
            )
            pbp = (
                f"Night Watch closes on '{outline.title}'. The text is still there when you come back. "
                f"Read it again in the daylight."
            )
        else:
            color = f"Closing the room:{recap}"
            pbp = f"That's Night Watch on '{outline.title}'. Stay curious — stay careful."
        return pbp, color

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
            f"Closing thought:{recap} Map every shall and shall-not to an owner. "
            f"If a clause is unclear, it fails on the worst day — clarify before execution."
        )
        pbp = (
            f"Desk is clear on '{outline.title}'. Full-sheet walk, not a skim. "
            f"Document exceptions; don't assume them. See you on the next review."
        )
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
    # Prefer obligation / restriction sentences, then mid-length informative
    def score(s: str) -> float:
        sl = s.lower()
        boost = 0.0
        if re.search(r"\b(shall not|must not|may not)\b", sl):
            boost -= 8
        elif re.search(r"\b(shall|must|agrees to|is required)\b", sl):
            boost -= 5
        if re.search(r"\b(liability|indemnif|terminate|breach|precedence)\b", sl):
            boost -= 3
        # Prefer ~12–28 words
        return abs(len(s.split()) - 18) + boost

    scored = sorted(parts, key=score)
    picked: list[str] = []
    for s in scored:
        if any(s[:40] == p[:40] for p in picked):
            continue
        # Skip pure confidentiality banner leftovers
        if re.search(r"(?i)nda restrictions|confidential\s*-\s*nda", s):
            continue
        picked.append(s)
        if len(picked) >= n:
            break
    return " ".join(picked) if picked else _clip(text, 40)


def _obligation_pull(text: str) -> str | None:
    """Pull one sharp shall/must line for contract color."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    for p in parts:
        if len(p.split()) < 8 or len(p.split()) > 55:
            continue
        if re.search(r"(?i)\b(shall not|must not|may not|shall|must|agrees to)\b", p):
            if re.search(r"(?i)nda restrictions|confidential\s*-\s*nda", p):
                continue
            return p.strip()
    return None


def _best_readthrough(text: str, max_words: int = 95) -> str:
    """Best contiguous operative span for on-air read (self-contained cast)."""
    # Prefer multi-sentence block packed with obligations
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    parts = [p.strip() for p in parts if len(p.split()) >= 6]
    if not parts:
        return _clip(text, max_words)

    def oper_score(s: str) -> int:
        sl = s.lower()
        n = 0
        for k in (
            "shall not",
            "must not",
            "shall",
            "must",
            "agrees",
            "liable",
            "indemnif",
            "license",
            "ownership",
            "payment",
            "authority",
            "precedence",
            "terminate",
            "breach",
            "contractor",
            "organization",
        ):
            if k in sl:
                n += 2 if "shall" in k or "must" in k else 1
        if re.search(r"(?i)nda restrictions|confidential\s*-\s*nda|click or tap", s):
            n -= 10
        return n

    # Greedy window of 1–3 sentences with best score under max_words
    best = ""
    best_sc = -99
    for i in range(len(parts)):
        acc: list[str] = []
        for j in range(i, min(i + 3, len(parts))):
            acc.append(parts[j])
            blob = " ".join(acc)
            if len(blob.split()) > max_words:
                break
            sc = sum(oper_score(x) for x in acc) + min(3, len(acc))
            if sc > best_sc:
                best_sc = sc
                best = blob
    if not best:
        return _clip(text, max_words)
    # Clean whitespace / hyphenation from PDF extract
    best = re.sub(r"\s+", " ", best).strip()
    best = re.sub(r"(\w)-\s+(\w)", r"\1\2", best)
    return best


def _is_substantive_title(title: str) -> bool:
    t = title or ""
    if re.search(r"(?i)\b(article|schedule|appendix|exhibit|section)\b", t):
        return True
    if re.match(r"^\d+\.\d+", t.strip()):
        return True
    # Reject header fragments
    if re.search(r"(?i)obligations apply|nda|confidential|page \d+", t):
        return False
    return len(t.split()) >= 4
