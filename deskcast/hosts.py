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
"""Desk host personas and desk-mode pairs.

Official pair: Mike + Dana (sports desk).

Unofficial *test* personas (Bo, Dale, Art) are STWL-owned *working names*
for internal product testing only. They are **not** endorsements, likenesses,
or licensed uses of any real broadcaster, trademark, or radio brand.
If testing goes well, STWL may pursue proper licenses; otherwise we redesign
original hosts with a similar *essence* (warm overnight lane, trucker clear-
channel grit, late-night open-lines curiosity) under fully original names.
See PERSONAS_UNOFFICIAL.md at the project root.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DeskModeId = Literal["sports", "clear_channel", "night_watch"]

DEFAULT_DESK_MODE: DeskModeId = "sports"


@dataclass(frozen=True)
class HostProfile:
    """Single on-air persona."""

    id: str
    name: str
    role_label: str  # lower-third role line
    voice: str  # edge-tts voice id
    portrait_stem: str  # assets/hosts/{stem}.png
    # Soft essence notes for future LLM style banks (not real-person claims)
    essence: str
    shirt: tuple[int, int, int]
    skin: tuple[int, int, int]
    hair: tuple[int, int, int]
    # edge-tts prosody — warmer overnight hosts run slower / slightly lower
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"


@dataclass(frozen=True)
class DeskMode:
    """Dual-host desk configuration."""

    id: DeskModeId
    label: str
    short_label: str
    pbp: HostProfile
    color: HostProfile
    official: bool
    # Broadcast bar tagline
    live_tag: str
    # Soft style hint for LLM / future phrase banks
    style_hint: str
    disclaimer: str | None = None


# --- Host registry -----------------------------------------------------------

MIKE = HostProfile(
    id="mike",
    name="Mike",
    role_label="PLAY-BY-PLAY",
    voice="en-US-GuyNeural",
    portrait_stem="mike_pbp",
    essence="Tempo, package framing, clean handoffs.",
    shirt=(200, 40, 40),
    skin=(230, 190, 160),
    hair=(40, 30, 25),
    rate="+5%",
    pitch="+0Hz",
)

DANA = HostProfile(
    id="dana",
    name="Dana",
    role_label="COLOR ANALYST",
    voice="en-US-JennyNeural",
    portrait_stem="dana_color",
    essence="Nuance, exam tips, risk and obligation callouts.",
    shirt=(30, 110, 190),
    skin=(210, 170, 140),
    hair=(90, 55, 35),
    rate="+0%",
    pitch="+0Hz",
)

# Unofficial test personas — STWL working names only (see PERSONAS_UNOFFICIAL.md)
# Bo: Guy is warmer/more natural than Davis for long-form overnight reads;
#     slowed rate + slight pitch drop = companion lane, less robotic.
BO = HostProfile(
    id="bo",
    name="Bo",
    role_label="OVERNIGHT HOST",
    voice="en-US-GuyNeural",
    portrait_stem="bo_overnight",
    essence=(
        "Warm clear-channel overnight lane: long-haul companion energy, "
        "steady pacing, friendly check-ins — original STWL test persona."
    ),
    shirt=(45, 85, 55),
    skin=(225, 185, 150),
    hair=(55, 40, 30),
    rate="-12%",
    pitch="-3Hz",
    volume="+0%",
)

DALE = HostProfile(
    id="dale",
    name="Dale",
    role_label="ROAD ANALYST",
    voice="en-US-EricNeural",
    portrait_stem="dale_road",
    essence=(
        "Gravel-road grit and practical color: plain talk on obligations, "
        "deadlines, and what bites on the road — original STWL test persona."
    ),
    shirt=(90, 70, 40),
    skin=(215, 175, 145),
    hair=(70, 55, 40),
    rate="-8%",
    pitch="-2Hz",
)

ART = HostProfile(
    id="art",
    name="Art",
    role_label="NIGHT WATCH",
    voice="en-US-ChristopherNeural",
    portrait_stem="art_nightwatch",
    essence=(
        "Late-night open-lines curiosity: atmospheric open, calm questions, "
        "lets the document mystery unfold — original STWL test persona."
    ),
    shirt=(40, 45, 90),
    skin=(220, 180, 155),
    hair=(50, 45, 50),
    rate="-10%",
    pitch="-1Hz",
)

HOSTS: dict[str, HostProfile] = {
    h.id: h for h in (MIKE, DANA, BO, DALE, ART)
}

# --- Desk modes --------------------------------------------------------------

DESK_MODES: dict[DeskModeId, DeskMode] = {
    "sports": DeskMode(
        id="sports",
        label="Sports desk — Mike & Dana (official)",
        short_label="Sports desk",
        pbp=MIKE,
        color=DANA,
        official=True,
        live_tag="LIVE DESK",
        style_hint="Sports-desk dual commentary: tempo + risk color.",
        disclaimer=None,
    ),
    "clear_channel": DeskMode(
        id="clear_channel",
        label="Clear channel overnight — Bo & Dale [UNOFFICIAL TEST]",
        short_label="Clear channel (unofficial)",
        pbp=BO,
        color=DALE,
        official=False,
        live_tag="CLEAR CHANNEL",
        style_hint=(
            "Overnight clear-channel dual: warm host pacing, practical road "
            "analyst color. Not affiliated with any real radio brand or DJ."
        ),
        disclaimer=(
            "UNOFFICIAL TEST PERSONAS (Bo & Dale). STWL working names only — "
            "not licensed likenesses. Internal product testing. May be replaced "
            "with fully original hosts or properly licensed personas later."
        ),
    ),
    "night_watch": DeskMode(
        id="night_watch",
        label="Night Watch — Art & Dana [UNOFFICIAL TEST]",
        short_label="Night Watch (unofficial)",
        pbp=ART,
        color=DANA,
        official=False,
        live_tag="NIGHT WATCH",
        style_hint=(
            "Late-night desk: atmospheric open, curious framing, grounded "
            "color/risk from Dana. Art is an STWL test persona, not a real DJ."
        ),
        disclaimer=(
            "UNOFFICIAL TEST PERSONA (Art). STWL working name only — not a "
            "licensed likeness. Paired with official Dana for color. Internal "
            "product testing. May be replaced with a fully original host later."
        ),
    ),
}


def normalize_desk_mode(value: str | None) -> DeskModeId:
    """Map user/CLI input to a valid desk mode id."""
    if not value:
        return DEFAULT_DESK_MODE
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "sports": "sports",
        "sport": "sports",
        "mike_dana": "sports",
        "default": "sports",
        "clear_channel": "clear_channel",
        "clearchannel": "clear_channel",
        "overnight": "clear_channel",
        "bo_dale": "clear_channel",
        "truck": "clear_channel",
        "night_watch": "night_watch",
        "nightwatch": "night_watch",
        "art": "night_watch",
        "late_night": "night_watch",
    }
    mid = aliases.get(key, key)
    if mid not in DESK_MODES:
        valid = ", ".join(DESK_MODES)
        raise ValueError(f"Unknown desk mode {value!r}. Choose one of: {valid}")
    return mid  # type: ignore[return-value]


def get_desk_mode(mode: str | DeskModeId | None = None) -> DeskMode:
    return DESK_MODES[normalize_desk_mode(mode if isinstance(mode, str) or mode is None else mode)]


def desk_mode_choices() -> list[str]:
    return list(DESK_MODES.keys())


def desk_mode_ui_labels() -> list[str]:
    """Human labels for combobox (order preserved)."""
    return [DESK_MODES[k].label for k in DESK_MODES]


def desk_mode_from_ui_label(label: str) -> DeskModeId:
    for mid, dm in DESK_MODES.items():
        if dm.label == label or dm.short_label == label or mid == label:
            return mid
    return normalize_desk_mode(label)


def apply_host_names_to_script(script, desk: DeskMode):
    """Rewrite speaker fields and in-dialogue Mike/Dana address names."""
    import re

    from .models import Line, Script

    pbp_n = desk.pbp.name
    color_n = desk.color.name

    def fix_line(ln: Line) -> Line:
        if ln.role == "pbp":
            speaker = pbp_n
        elif ln.role == "color":
            speaker = color_n
        else:
            speaker = ln.speaker
        text = ln.text
        # Canonical bank names → active desk hosts
        text = re.sub(r"\bMike\b", pbp_n, text)
        text = re.sub(r"\bDana\b", color_n, text)
        return ln.model_copy(update={"speaker": speaker, "text": text})

    return Script(
        title=script.title,
        doc_kind=script.doc_kind,
        cold_open=[fix_line(x) for x in script.cold_open],
        segments=[fix_line(x) for x in script.segments],
        close=[fix_line(x) for x in script.close],
    )


def unofficial_banner(desk: DeskMode) -> str | None:
    if desk.official:
        return None
    return desk.disclaimer
