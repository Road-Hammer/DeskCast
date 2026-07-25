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

from .models import Chunk, Outline

# Prefer hard section breaks for contracts / addenda
_SECTION_HEAD = re.compile(
    r"(?im)^("
    r"article\s+[0-9ivxlcdm]+|"
    r"section\s+\d+(\.\d+)*|"
    r"schedule\s+[a-z0-9\-]+|"
    r"appendix\s+[a-z0-9\-]+|"
    r"exhibit\s+[a-z0-9\-]+|"
    r"\d+\.\d+(\.\d+)*\s+[A-Z]"
    r").*"
)


def build_outline(
    text: str,
    source: Path,
    title: str | None = None,
    max_chunks: int = 12,
    target_words: int = 180,
) -> Outline:
    """
    Build packages covering the **entire** document (no silent truncation).

    When the source is long, text is distributed evenly across up to
    ``max_chunks`` packages so every operative section can be voiced.
    """
    title = title or source.stem.replace("_", " ").replace("-", " ").title()
    paragraphs = _paragraphs(text)
    if not paragraphs:
        paragraphs = [text.strip() or "Empty document."]

    total_words = sum(len(p.split()) for p in paragraphs)
    # Aim to use the full budget of packages for long docs
    if total_words > target_words * max_chunks:
        # Slightly denser packs so we still fit in max_chunks without dropping tail
        target_words = max(90, (total_words + max_chunks - 1) // max_chunks)

    raw: list[tuple[str, str]] = []  # (title_hint, body)
    buf: list[str] = []
    words = 0
    pending_title: str | None = None

    def flush(force_title: str | None = None):
        nonlocal buf, words, pending_title
        if not buf:
            return
        body = "\n\n".join(buf).strip()
        if len(body.split()) < 8 and raw:
            # Glue tiny leftovers onto previous
            pt, pb = raw[-1]
            raw[-1] = (pt, (pb + "\n\n" + body).strip())
            buf = []
            words = 0
            pending_title = None
            return
        head = force_title or pending_title or body.split("\n", 1)[0][:100]
        raw.append((head, body))
        buf = []
        words = 0
        pending_title = None

    for p in paragraphs:
        is_head = bool(_SECTION_HEAD.match(p.strip()[:120]))
        pw = len(p.split())

        if is_head and buf and words >= max(40, target_words // 3):
            flush()
            pending_title = p.strip()[:100]

        if words + pw > target_words and buf:
            flush()
            if is_head:
                pending_title = p.strip()[:100]

        buf.append(p)
        words += pw
        if is_head and pending_title is None:
            pending_title = p.strip()[:100]
        if words >= target_words and not is_head:
            flush()

    flush()

    # Rebalance: cover full doc in at most max_chunks (merge, never drop)
    packs = _rebalance(raw, max_chunks)

    chunks: list[Chunk] = []
    for i, (head, body) in enumerate(packs):
        chunks.append(
            Chunk(
                index=i,
                title=_headline(head, i),
                text=body,
                word_count=len(body.split()),
            )
        )

    total = sum(c.word_count for c in chunks)
    return Outline(source=str(source), title=title, chunks=chunks, total_words=total)


def _paragraphs(text: str) -> list[str]:
    # Prefer blank-line paragraphs; also split on hard section heads mid-block
    blocks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: list[str] = []
    for b in blocks:
        lines = b.split("\n")
        if len(lines) == 1:
            out.append(b)
            continue
        buf: list[str] = []
        for ln in lines:
            if _SECTION_HEAD.match(ln.strip()) and buf:
                out.append("\n".join(buf).strip())
                buf = [ln]
            else:
                buf.append(ln)
        if buf:
            out.append("\n".join(buf).strip())
    return out or blocks


def _rebalance(raw: list[tuple[str, str]], max_chunks: int) -> list[tuple[str, str]]:
    if not raw:
        return [("Segment 1", "No extractable body text.")]
    if len(raw) <= max_chunks:
        return raw

    # Merge consecutive packs into max_chunks buckets by word weight
    weights = [max(1, len(body.split())) for _, body in raw]
    total = sum(weights)
    target = total / max_chunks
    packs: list[tuple[str, str]] = []
    i = 0
    for bucket in range(max_chunks):
        if i >= len(raw):
            break
        remaining_buckets = max_chunks - bucket
        remaining_items = len(raw) - i
        # Must leave at least one item per remaining bucket
        take_min = 1
        take_max = remaining_items - (remaining_buckets - 1)
        acc_w = 0
        take = 0
        title = raw[i][0]
        bodies: list[str] = []
        while i + take < len(raw) and take < take_max:
            if take >= take_min and acc_w >= target and bucket < max_chunks - 1:
                break
            bodies.append(raw[i + take][1])
            acc_w += weights[i + take]
            take += 1
            if acc_w >= target * 1.15 and take >= take_min and bucket < max_chunks - 1:
                break
        if take == 0:
            break
        packs.append((title, "\n\n".join(bodies)))
        i += take
    # Any leftover (float error) → last pack
    if i < len(raw):
        rest = "\n\n".join(b for _, b in raw[i:])
        if packs:
            t, b = packs[-1]
            packs[-1] = (t, b + "\n\n" + rest)
        else:
            packs.append((raw[i][0], rest))
    return packs


def _headline(line: str, idx: int) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    line = re.sub(r"\.{2,}", " ", line)
    if len(line) < 8:
        return f"Segment {idx + 1}"
    if len(line) > 72:
        line = line[:69].rstrip() + "…"
    return line
