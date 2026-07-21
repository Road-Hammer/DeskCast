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

import json
import re
from typing import Any

import httpx

from .logic import (
    cold_open_lines,
    close_lines,
    midshow_bridge,
    pick_color_line,
    pick_pbp_line,
)
from .models import Line, Outline, Script

PBP_NAME = "Mike"
COLOR_NAME = "Dana"


def generate_script(
    outline: Outline,
    *,
    use_llm: bool = True,
    ollama_model: str = "llama3.2:1b",
    openai_base: str | None = None,
    openai_key: str | None = None,
) -> Script:
    if use_llm:
        try:
            raw = _llm_script(outline, ollama_model, openai_base, openai_key)
            if raw:
                raw.doc_kind = outline.doc_kind or "general"
                return raw
        except Exception:
            pass
    return _logic_script(outline)


def _logic_script(outline: Outline) -> Script:
    """Rule-based dual-host script with smoother transitions and fewer hard cuts."""
    dk = outline.doc_kind or "general"
    pbp_open, color_open = cold_open_lines(outline)
    pbp_close, color_close = close_lines(outline)

    cold = [
        Line(role="pbp", speaker=PBP_NAME, text=pbp_open),
        Line(role="color", speaker=COLOR_NAME, text=color_open),
    ]

    segments: list[Line] = []
    chunks = outline.chunks
    total = len(chunks)

    for i, ch in enumerate(chunks):
        prev = chunks[i - 1] if i > 0 else None
        nxt = chunks[i + 1] if i + 1 < total else None

        # Soft midpoint bridge *before* the package (feels like a desk reset, not a commercial)
        mid = midshow_bridge(outline, i)
        if mid:
            segments.append(Line(role="pbp", speaker=PBP_NAME, text=mid))

        segments.append(
            Line(
                role="pbp",
                speaker=PBP_NAME,
                text=pick_pbp_line(i, total, ch, dk, prev=prev, nxt=nxt),
                chunk_index=ch.index,
                chunk_kind=ch.kind,
            )
        )
        segments.append(
            Line(
                role="color",
                speaker=COLOR_NAME,
                text=pick_color_line(ch, dk, i=i, total=total, nxt=nxt, prev=prev),
                chunk_index=ch.index,
                chunk_kind=ch.kind,
            )
        )
        # Fold "must-not-miss" into color already via priority; no extra choppy beat

    close = [
        Line(role="color", speaker=COLOR_NAME, text=color_close),
        Line(role="pbp", speaker=PBP_NAME, text=pbp_close),
    ]
    return Script(
        title=outline.title,
        doc_kind=dk,  # type: ignore[arg-type]
        cold_open=cold,
        segments=segments,
        close=close,
    )


def _llm_script(
    outline: Outline,
    ollama_model: str,
    openai_base: str | None,
    openai_key: str | None,
) -> Script | None:
    payload_chunks = [
        {
            "index": c.index,
            "title": c.title,
            "kind": c.kind,
            "priority": c.priority,
            "tags": c.tags[:6],
            "text": _clip(c.text, 200),
        }
        for c in outline.chunks
    ]
    system = (
        "You write dual-host sports-desk style commentary for document breakdowns. "
        f"Hosts: {PBP_NAME} (play-by-play, tempo) and {COLOR_NAME} (color, nuance, exam/risk tips). "
        f"Document kind: {outline.doc_kind or 'general'}. "
        "Respect chunk kinds: definition/list/warning/procedure/qa/example/summary/narrative. "
        "Warnings get urgency; study_guide gets exam-tip color. "
        "Return ONLY valid JSON: cold_open, segments, close — lists of "
        "{role:'pbp'|'color', speaker, text, chunk_index?, chunk_kind?}."
    )
    user = json.dumps(
        {"title": outline.title, "doc_kind": outline.doc_kind, "chunks": payload_chunks},
        ensure_ascii=False,
    )
    content = None
    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "options": {"temperature": 0.7, "num_predict": 2000},
                },
            )
            if r.status_code == 200:
                content = r.json()["message"]["content"]
    except Exception:
        content = None

    if not content and openai_base:
        headers = {"Authorization": f"Bearer {openai_key or 'sk-local'}"}
        with httpx.Client(timeout=120.0, base_url=openai_base.rstrip("/")) as client:
            r = client.post(
                "/v1/chat/completions",
                headers=headers,
                json={
                    "model": ollama_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.7,
                },
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]

    if not content:
        return None
    data = _parse_json_obj(content)
    return _script_from_dict(outline.title, data, outline.doc_kind or "general")


def _script_from_dict(title: str, data: dict[str, Any], doc_kind: str) -> Script:
    def lines(key: str) -> list[Line]:
        out: list[Line] = []
        for item in data.get(key) or []:
            role = item.get("role") or "pbp"
            if role not in ("pbp", "color", "both"):
                role = "pbp"
            speaker = item.get("speaker") or (PBP_NAME if role == "pbp" else COLOR_NAME)
            text = (item.get("text") or "").strip()
            if text:
                out.append(
                    Line(
                        role=role,
                        speaker=speaker,
                        text=text,
                        chunk_index=item.get("chunk_index"),
                        chunk_kind=item.get("chunk_kind"),
                    )
                )
        return out

    return Script(
        title=title,
        doc_kind=doc_kind,  # type: ignore[arg-type]
        cold_open=lines("cold_open"),
        segments=lines("segments"),
        close=lines("close"),
    )


def _parse_json_obj(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _clip(text: str, words: int) -> str:
    toks = text.split()
    if len(toks) <= words:
        return text.replace("\n", " ")
    return " ".join(toks[:words]).replace("\n", " ") + "…"
