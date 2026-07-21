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


def build_outline(
    text: str,
    source: Path,
    title: str | None = None,
    max_chunks: int = 12,
    target_words: int = 180,
) -> Outline:
    title = title or source.stem.replace("_", " ").replace("-", " ").title()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[Chunk] = []
    buf: list[str] = []
    words = 0
    idx = 0

    def flush():
        nonlocal buf, words, idx
        if not buf:
            return
        body = "\n\n".join(buf).strip()
        wc = len(body.split())
        head = body.split("\n", 1)[0][:80]
        chunks.append(
            Chunk(
                index=idx,
                title=_headline(head, idx),
                text=body,
                word_count=wc,
            )
        )
        idx += 1
        buf = []
        words = 0

    for p in paragraphs:
        pw = len(p.split())
        if words + pw > target_words and buf:
            flush()
            if len(chunks) >= max_chunks:
                break
        buf.append(p)
        words += pw
        if words >= target_words:
            flush()
            if len(chunks) >= max_chunks:
                break
    if len(chunks) < max_chunks:
        flush()

    # If still over max (edge), merge tail into last
    if len(chunks) > max_chunks:
        keep = chunks[: max_chunks - 1]
        rest = chunks[max_chunks - 1 :]
        merged = "\n\n".join(c.text for c in rest)
        keep.append(
            Chunk(
                index=max_chunks - 1,
                title="Closing stretch",
                text=merged,
                word_count=len(merged.split()),
            )
        )
        chunks = keep

    total = sum(c.word_count for c in chunks)
    return Outline(source=str(source), title=title, chunks=chunks, total_words=total)


def _headline(line: str, idx: int) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    if len(line) < 8:
        return f"Segment {idx + 1}"
    if len(line) > 72:
        line = line[:69].rstrip() + "…"
    return line
