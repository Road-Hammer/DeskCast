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

from .hosts import (
    DEFAULT_DESK_MODE,
    DeskMode,
    DeskModeId,
    apply_host_names_to_script,
    get_desk_mode,
)
from .logic import (
    cold_open_lines,
    close_lines,
    midshow_bridge,
    pick_color_line,
    pick_pbp_line,
    pick_readthrough_line,
)
from .models import Line, Outline, Script

# Canonical names used inside rule banks; remapped per desk mode at the end.
PBP_NAME = "Mike"
COLOR_NAME = "Dana"


def generate_script(
    outline: Outline,
    *,
    use_llm: bool = True,
    ollama_model: str = "llama3.2:1b",
    openai_base: str | None = None,
    openai_key: str | None = None,
    desk_mode: str | DeskModeId | DeskMode | None = None,
) -> Script:
    desk = desk_mode if isinstance(desk_mode, DeskMode) else get_desk_mode(desk_mode)
    # Always start from rule logic (structure + obligations). LLM polishes speech.
    base = apply_host_names_to_script(
        _logic_script(outline, desk_style=desk.id), desk
    )
    if not use_llm:
        return base

    # 1) Prefer polish of the logic script (reliable with tiny models)
    try:
        polished = _llm_polish_script(
            base, desk=desk, ollama_model=ollama_model,
            openai_base=openai_base, openai_key=openai_key,
        )
        if polished:
            return polished
    except Exception:
        pass

    # 2) Fall back to full LLM generation from outline
    try:
        raw = _llm_script(outline, ollama_model, openai_base, openai_key, desk=desk)
        if raw:
            raw = raw.model_copy(update={"doc_kind": outline.doc_kind or "general"})
            return apply_host_names_to_script(raw, desk)
    except Exception:
        pass
    return base


def _llm_polish_script(
    script: Script,
    *,
    desk: DeskMode,
    ollama_model: str,
    openai_base: str | None,
    openai_key: str | None,
) -> Script | None:
    """Rewrite line text for natural overnight delivery while keeping structure."""
    lines = script.all_lines()
    if not lines:
        return None
    # Cap payload size for 1B models — polish first N + close
    payload = []
    for i, ln in enumerate(lines):
        payload.append(
            {
                "i": i,
                "role": ln.role,
                "speaker": ln.speaker,
                "text": ln.text[:500],
            }
        )
    system = (
        f"You polish dual-host overnight radio copy for spoken delivery. "
        f"Hosts: {desk.pbp.name} (lead) and {desk.color.name} (color). "
        f"Style: {desk.style_hint} "
        "Keep every speaker, role, and line index. Preserve shall/must/shall-not facts. "
        "Make lines warm, conversational, contractions OK, short sentences. "
        "Max ~40 words per line unless it is a direct read of operative contract text "
        "(those may stay longer). No sports jargon unless the style says sports desk. "
        "Return ONLY valid JSON: {\"lines\":[{\"i\":0,\"text\":\"...\"}, ...]} "
        "with one entry per input line index."
    )
    user = json.dumps({"lines": payload}, ensure_ascii=False)
    content = _chat_complete(
        system, user, ollama_model, openai_base, openai_key, num_predict=2500
    )
    if not content:
        return None
    data = _parse_json_obj(content)
    by_i: dict[int, str] = {}
    for item in data.get("lines") or []:
        try:
            idx = int(item.get("i"))
            text = (item.get("text") or "").strip()
            if text:
                by_i[idx] = text
        except Exception:
            continue
    if len(by_i) < max(2, len(lines) // 3):
        # Too few rewrites — treat as failure so we keep logic copy
        return None

    def polish_group(group: list[Line], offset: int) -> list[Line]:
        out: list[Line] = []
        for j, ln in enumerate(group):
            idx = offset + j
            text = by_i.get(idx, ln.text)
            out.append(ln.model_copy(update={"text": text}))
        return out

    n_cold = len(script.cold_open)
    n_seg = len(script.segments)
    return Script(
        title=script.title,
        doc_kind=script.doc_kind,
        cold_open=polish_group(script.cold_open, 0),
        segments=polish_group(script.segments, n_cold),
        close=polish_group(script.close, n_cold + n_seg),
    )


def _chat_complete(
    system: str,
    user: str,
    ollama_model: str,
    openai_base: str | None,
    openai_key: str | None,
    *,
    num_predict: int = 2000,
) -> str | None:
    content = None
    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "options": {"temperature": 0.55, "num_predict": num_predict},
                },
            )
            if r.status_code == 200:
                content = r.json()["message"]["content"]
    except Exception:
        content = None

    if not content and openai_base:
        headers = {"Authorization": f"Bearer {openai_key or 'sk-local'}"}
        with httpx.Client(timeout=180.0, base_url=openai_base.rstrip("/")) as client:
            r = client.post(
                "/v1/chat/completions",
                headers=headers,
                json={
                    "model": ollama_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.55,
                },
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
    return content


def _logic_script(outline: Outline, *, desk_style: str = "sports") -> Script:
    """Rule-based dual-host script with smoother transitions and fewer hard cuts."""
    dk = outline.doc_kind or "general"
    pbp_open, color_open = cold_open_lines(outline, desk_style=desk_style)
    pbp_close, color_close = close_lines(outline, desk_style=desk_style)

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
                text=pick_pbp_line(
                    i, total, ch, dk, prev=prev, nxt=nxt, desk_style=desk_style
                ),
                chunk_index=ch.index,
                chunk_kind=ch.kind,
            )
        )
        segments.append(
            Line(
                role="color",
                speaker=COLOR_NAME,
                text=pick_color_line(
                    ch,
                    dk,
                    i=i,
                    total=total,
                    nxt=nxt,
                    prev=prev,
                    desk_style=desk_style,
                ),
                chunk_index=ch.index,
                chunk_kind=ch.kind,
            )
        )
        # Self-contained read-through so high-yield contract packs stand alone on audio
        readthru = pick_readthrough_line(ch, dk, desk_style=desk_style)
        if readthru:
            segments.append(
                Line(
                    role="pbp" if i % 2 == 0 else "color",
                    speaker=PBP_NAME if i % 2 == 0 else COLOR_NAME,
                    text=readthru,
                    chunk_index=ch.index,
                    chunk_kind=ch.kind,
                )
            )

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
    *,
    desk: DeskMode | None = None,
) -> Script | None:
    desk = desk or get_desk_mode(DEFAULT_DESK_MODE)
    pbp_n, color_n = desk.pbp.name, desk.color.name
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
        f"You write dual-host desk commentary for document breakdowns. "
        f"Style: {desk.style_hint} "
        f"Hosts: {pbp_n} (play-by-play / lead, tempo) and {color_n} (color, nuance, exam/risk tips). "
        f"Use speaker names exactly: {pbp_n} and {color_n}. "
        f"Document kind: {outline.doc_kind or 'general'}. "
        "Write like real radio hosts talking to one listener — warm, spoken English, contractions, "
        "short sentences, natural handoffs. NOT checklist robot voice. NOT sports jargon unless sports desk. "
        "Each line 1–3 sentences, max ~45 words. Quote or paraphrase operative shall/must language. "
        "Respect chunk kinds: definition/list/warning/procedure/qa/example/summary/narrative. "
        "Warnings get urgency; study_guide gets exam-tip color. "
        "cold_open: 2 lines (pbp then color). segments: alternate pbp/color per chunk. "
        "close: 2 lines (color then pbp). "
        "Return ONLY valid JSON: cold_open, segments, close — lists of "
        "{role:'pbp'|'color', speaker, text, chunk_index?, chunk_kind?}."
    )
    user = json.dumps(
        {"title": outline.title, "doc_kind": outline.doc_kind, "chunks": payload_chunks},
        ensure_ascii=False,
    )
    content = _chat_complete(
        system, user, ollama_model, openai_base, openai_key, num_predict=2200
    )
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
            speaker = item.get("speaker") or (
                PBP_NAME if role == "pbp" else COLOR_NAME
            )
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
