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
"""Plan multi-episode desk casts for long contracts / legislation."""
from __future__ import annotations

import re
from pathlib import Path

from .legal_structure import structure_to_outline_chunks
from .models import EpisodePlan, EpisodeSpec, LegalDocument


def plan_episodes(
    doc: LegalDocument,
    *,
    target_minutes: float = 20.0,
    words_per_minute: int = 140,
    max_episodes: int = 24,
    min_episodes: int = 1,
    packs: list[tuple[str, str]] | None = None,
) -> EpisodePlan:
    """
    Split flattened legal packs into episodes by spoken-word budget.

    ``words_per_minute`` is *source* words mapped to rough airtime
    (desk cast is denser than raw read; 130–150 is a practical range).
    """
    packs = packs if packs is not None else structure_to_outline_chunks(doc)
    if not packs:
        packs = [("Empty", "No extractable legal body text.")]

    weights = [max(1, len(body.split())) for _, body in packs]
    total_words = sum(weights)
    budget = max(200, int(target_minutes * words_per_minute))

    # How many episodes needed by budget
    n = max(min_episodes, (total_words + budget - 1) // budget)
    n = min(n, max_episodes, len(packs))

    episodes: list[EpisodeSpec] = []
    i = 0
    for ep_i in range(n):
        remaining_eps = n - ep_i
        remaining_packs = len(packs) - i
        # leave at least one pack per remaining episode
        take_max = remaining_packs - (remaining_eps - 1)
        take_max = max(1, take_max)
        acc = 0
        take = 0
        titles: list[str] = []
        focus: list[str] = []
        while take < take_max and i + take < len(packs):
            if take >= 1 and acc >= budget and ep_i < n - 1:
                break
            titles.append(packs[i + take][0])
            acc += weights[i + take]
            if _is_focus(packs[i + take][0], packs[i + take][1]):
                focus.append(packs[i + take][0][:80])
            take += 1
            # soft overflow stop
            if acc >= budget * 1.25 and take >= 1 and ep_i < n - 1:
                break
        if take == 0:
            break
        start = i
        end = i + take
        est_min = round(acc / float(words_per_minute), 1)
        ep_title = _episode_title(doc, ep_i, n, titles)
        episodes.append(
            EpisodeSpec(
                index=ep_i,
                id=f"ep{ep_i + 1:02d}",
                title=ep_title,
                section_titles=titles,
                word_count=acc,
                estimated_minutes=est_min,
                pack_start=start,
                pack_end=end,
                priority_focus=focus[:6],
            )
        )
        i = end

    # Leftover packs → last episode
    if i < len(packs) and episodes:
        rest_w = sum(weights[i:])
        episodes[-1].pack_end = len(packs)
        episodes[-1].section_titles.extend(t for t, _ in packs[i:])
        episodes[-1].word_count += rest_w
        episodes[-1].estimated_minutes = round(
            episodes[-1].word_count / float(words_per_minute), 1
        )

    notes = [
        f"Profile: {doc.profile}",
        f"Leaf sections: {doc.section_count}",
        f"Target ~{target_minutes} min/episode at ~{words_per_minute} source words/min",
        "No section is dropped; leftover packs attach to the final episode.",
        "Briefing aid only — not legal advice; not an official publication of law.",
    ]
    if doc.profile == "legislation":
        notes.append("Legislation mode: prefer amendment language and duty statements in VO.")
    if doc.profile == "contract":
        notes.append("Contract mode: prioritize shall/shall-not, money, IP, authority, schedules.")

    return EpisodePlan(
        source=doc.source,
        title=doc.title,
        profile=doc.profile,
        target_minutes=target_minutes,
        words_per_minute=words_per_minute,
        total_words=total_words,
        total_episodes=len(episodes),
        episodes=episodes,
        notes=notes,
    )


def plan_markdown(plan: EpisodePlan) -> str:
    lines = [
        f"# Episode plan — {plan.title}",
        "",
        f"- **Profile:** `{plan.profile}`",
        f"- **Episodes:** {plan.total_episodes}",
        f"- **Total words:** {plan.total_words}",
        f"- **Target:** ~{plan.target_minutes} min/episode",
        "",
        "## Notes",
        "",
    ]
    for n in plan.notes:
        lines.append(f"- {n}")
    lines.append("")
    lines.append("## Episodes")
    lines.append("")
    for ep in plan.episodes:
        lines.append(f"### {ep.id}: {ep.title}")
        lines.append("")
        lines.append(
            f"- **Packs:** {ep.pack_start + 1}–{ep.pack_end} "
            f"({ep.pack_end - ep.pack_start} packages)"
        )
        lines.append(f"- **Words:** {ep.word_count}")
        lines.append(f"- **Est. minutes:** ~{ep.estimated_minutes}")
        if ep.priority_focus:
            lines.append("- **Focus:** " + "; ".join(ep.priority_focus[:5]))
        lines.append("- **Sections:**")
        for t in ep.section_titles[:40]:
            lines.append(f"  - {t}")
        if len(ep.section_titles) > 40:
            lines.append(f"  - … +{len(ep.section_titles) - 40} more")
        lines.append("")
    return "\n".join(lines)


def packs_for_episode(
    packs: list[tuple[str, str]], ep: EpisodeSpec
) -> list[tuple[str, str]]:
    return packs[ep.pack_start : ep.pack_end]


def _episode_title(doc: LegalDocument, i: int, n: int, titles: list[str]) -> str:
    if not titles:
        return f"Episode {i + 1} of {n}"
    first = titles[0]
    last = titles[-1]
    # Shorten
    def short(s: str) -> str:
        s = re.sub(r"\s+", " ", s).strip()
        return s[:48] + ("…" if len(s) > 48 else "")

    if i == 0 and n == 1:
        return f"{doc.title} — full walk"
    if first == last:
        return f"Episode {i + 1}: {short(first)}"
    return f"Episode {i + 1}: {short(first)} → {short(last)}"


def _is_focus(title: str, body: str) -> bool:
    blob = f"{title}\n{body[:500]}".lower()
    keys = (
        "shall not",
        "must not",
        "indemnif",
        "liability",
        "termination",
        "payment",
        "precedence",
        "intellectual property",
        "license",
        "amended",
        "effective",
        "authority",
        "breach",
        "criminal",
        "penalty",
    )
    return any(k in blob for k in keys)
