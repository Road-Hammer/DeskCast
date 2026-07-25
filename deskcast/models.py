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

from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["pbp", "color", "both"]
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


class Line(BaseModel):
    role: Role
    speaker: str
    text: str
    # optional UI / logic metadata
    chunk_index: int | None = None
    chunk_kind: ChunkKind | None = None


class Script(BaseModel):
    title: str
    doc_kind: DocKind = "general"
    cold_open: list[Line] = Field(default_factory=list)
    segments: list[Line] = Field(default_factory=list)
    close: list[Line] = Field(default_factory=list)

    def all_lines(self) -> list[Line]:
        return [*self.cold_open, *self.segments, *self.close]


class Chunk(BaseModel):
    index: int
    title: str
    text: str
    word_count: int
    kind: ChunkKind | None = None
    priority: int | None = None
    tags: list[str] = Field(default_factory=list)


class Outline(BaseModel):
    source: str
    title: str
    chunks: list[Chunk]
    total_words: int
    doc_kind: DocKind | None = None


# --- Legal structure / multi-episode planning ---

LegalKind = Literal[
    "preamble",
    "title",
    "article",
    "chapter",
    "section",
    "subsection",
    "schedule",
    "appendix",
    "exhibit",
    "other",
]
LegalProfile = Literal["contract", "legislation", "general"]


class LegalNode(BaseModel):
    id: str
    kind: str
    label: str
    title: str
    text: str = ""
    word_count: int = 0
    level: int = 0
    is_amendment: bool = False
    children: list["LegalNode"] = Field(default_factory=list)


class LegalDocument(BaseModel):
    source: str
    title: str
    profile: LegalProfile = "general"
    nodes: list[LegalNode] = Field(default_factory=list)
    total_words: int = 0
    section_count: int = 0


class EpisodeSpec(BaseModel):
    index: int
    id: str
    title: str
    section_titles: list[str] = Field(default_factory=list)
    word_count: int = 0
    estimated_minutes: float = 0.0
    pack_start: int = 0
    pack_end: int = 0  # exclusive index into flat packs
    priority_focus: list[str] = Field(default_factory=list)


class EpisodePlan(BaseModel):
    source: str
    title: str
    profile: LegalProfile = "general"
    target_minutes: float = 20.0
    words_per_minute: int = 140
    total_words: int = 0
    total_episodes: int = 0
    episodes: list[EpisodeSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


LegalNode.model_rebuild()
