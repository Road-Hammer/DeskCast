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
import time
import uuid
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.panel import Panel

from .characters import ensure_default_hosts, project_assets_dir
from .episode_planner import packs_for_episode, plan_episodes, plan_markdown
from .extract import extract_text
from .hosts import DEFAULT_DESK_MODE, DeskMode, DeskModeId, get_desk_mode, unofficial_banner
from .legal_structure import (
    parse_legal_structure,
    structure_markdown,
    structure_to_outline_chunks,
)
from .logic import enrich_outline, logic_summary
from .models import Chunk, EpisodePlan, LegalDocument, Outline, Script
from .outline import build_outline
from .render import assemble_video
from .script import generate_script
from .slides import VisualMode, render_slides
from .tts import synthesize_script

console = Console()

ProgressCb = Callable[[str], None]


def run_pipeline(
    source: Path,
    *,
    out_root: Path | None = None,
    title: str | None = None,
    max_chunks: int = 10,
    use_llm: bool = True,
    ollama_model: str = "llama3.2:1b",
    voice_a: str | None = None,
    voice_b: str | None = None,
    offline_tts: bool = False,
    visuals: VisualMode = "characters",
    broll_dir: Path | None = None,
    assets_dir: Path | None = None,
    legal_mode: bool = True,
    episode_minutes: float = 20.0,
    multi_episode: bool = True,
    desk_mode: str | DeskModeId | None = DEFAULT_DESK_MODE,
    progress: ProgressCb | None = None,
) -> Path:
    """
    Build desk-cast video(s). Returns job directory path.

    When ``legal_mode`` is True (default), uses legal structure parse + episode planner
    for contracts/legislation-style documents.
    """
    def log(msg: str) -> None:
        console.print(msg)
        if progress:
            progress(msg)

    desk = get_desk_mode(desk_mode)
    # Default voices follow desk hosts unless caller overrides explicitly
    voice_a = voice_a or desk.pbp.voice
    voice_b = voice_b or desk.color.voice

    source = source.expanduser().resolve()
    out_root = (out_root or Path("out")).expanduser().resolve()
    job_id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    job = out_root / job_id
    job.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(f"[bold]DeskCast[/bold] job [cyan]{job_id}[/cyan]\n{source}", border_style="red"))
    log(f"Desk mode: [cyan]{desk.id}[/cyan] — {desk.pbp.name} / {desk.color.name}"
        + (" [yellow]UNOFFICIAL TEST[/yellow]" if not desk.official else ""))
    banner = unofficial_banner(desk)
    if banner:
        log(f"[yellow]{banner}[/yellow]")
        (job / "PERSONAS_UNOFFICIAL.txt").write_text(banner + "\n\nSee PERSONAS_UNOFFICIAL.md\n", encoding="utf-8")

    log("[bold]1/7 Extract[/bold]")
    text = extract_text(source)
    (job / "extracted.txt").write_text(text, encoding="utf-8")

    legal_doc: LegalDocument | None = None
    plan: EpisodePlan | None = None
    packs: list[tuple[str, str]] | None = None

    if legal_mode:
        log("[bold]2/7 Legal structure[/bold]")
        legal_doc = parse_legal_structure(text, source=source, title=title)
        (job / "structure.json").write_text(
            legal_doc.model_dump_json(indent=2), encoding="utf-8"
        )
        (job / "STRUCTURE.md").write_text(structure_markdown(legal_doc), encoding="utf-8")
        packs = structure_to_outline_chunks(legal_doc)
        log(
            f"  profile=[cyan]{legal_doc.profile}[/cyan] leaves={legal_doc.section_count} "
            f"packs={len(packs)} words≈{legal_doc.total_words}"
        )

        log("[bold]3/7 Episode plan[/bold]")
        plan = plan_episodes(
            legal_doc,
            target_minutes=episode_minutes,
            packs=packs,
        )
        if not multi_episode:
            # Force single episode spanning all packs
            plan = plan_episodes(
                legal_doc,
                target_minutes=max(episode_minutes, 999),
                max_episodes=1,
                packs=packs,
            )
        (job / "episode_plan.json").write_text(
            plan.model_dump_json(indent=2), encoding="utf-8"
        )
        (job / "EPISODE_PLAN.md").write_text(plan_markdown(plan), encoding="utf-8")
        log(f"  episodes={plan.total_episodes} target≈{episode_minutes}m each")
    else:
        log("[bold]2/7 Outline (generic)[/bold]")
        plan = None

    assets = assets_dir or project_assets_dir()
    ensure_default_hosts(assets, desk)
    broll = broll_dir or (assets / "broll")

    produced: list[Path] = []

    if plan and packs is not None and legal_doc is not None:
        ep_root = job / "episodes"
        ep_root.mkdir(exist_ok=True)
        for ep in plan.episodes:
            log(f"[bold]Episode {ep.id}[/bold] — {ep.title}")
            ep_dir = ep_root / ep.id
            ep_dir.mkdir(exist_ok=True)
            ep_packs = packs_for_episode(packs, ep)
            outline = _outline_from_packs(
                ep_packs,
                source=source,
                title=f"{plan.title} — {ep.title}",
                doc_hint=legal_doc.profile,
            )
            outline = enrich_outline(outline, "\n\n".join(b for _, b in ep_packs))
            # Contracts + legislation share obligation-oriented script bank
            if legal_doc.profile in ("contract", "legislation"):
                outline = outline.model_copy(update={"doc_kind": "contract"})
            # Cap package count per episode for laptop safety
            if len(outline.chunks) > max_chunks:
                outline = _rechunk_outline(outline, max_chunks)
                outline = enrich_outline(outline, "\n\n".join(c.text for c in outline.chunks))
                if legal_doc.profile in ("contract", "legislation"):
                    outline = outline.model_copy(update={"doc_kind": "contract"})

            mp4 = _render_one(
                outline,
                ep_dir,
                use_llm=use_llm,
                ollama_model=ollama_model,
                voice_a=voice_a,
                voice_b=voice_b,
                offline_tts=offline_tts,
                visuals=visuals,
                assets=assets,
                broll=broll,
                desk=desk,
                log=log,
                out_name="deskcast.mp4",
            )
            produced.append(mp4)
            _write_self_contained(ep_dir, outline, _load_script(ep_dir), source)
        _write_master_index(job, legal_doc, plan, produced)
        # Convenience: copy first / only episode to job root
        if produced:
            root_mp4 = job / "deskcast.mp4"
            root_mp4.write_bytes(produced[0].read_bytes())
            if len(produced) == 1:
                log(f"[green]Single episode[/green] → {root_mp4}")
            else:
                log(f"[green]{len(produced)} episodes[/green] → {ep_root} (ep01 also at job root)")
    else:
        log("[bold]3/7 Outline + logic[/bold]")
        outline = build_outline(text, source, title=title, max_chunks=max_chunks)
        outline = enrich_outline(outline, text)
        logic = logic_summary(outline)
        (job / "outline.json").write_text(outline.model_dump_json(indent=2), encoding="utf-8")
        (job / "logic.json").write_text(json.dumps(logic, indent=2), encoding="utf-8")
        log(
            f"  chunks={len(outline.chunks)} words≈{outline.total_words} "
            f"doc_kind=[cyan]{outline.doc_kind}[/cyan]"
        )
        mp4 = _render_one(
            outline,
            job,
            use_llm=use_llm,
            ollama_model=ollama_model,
            voice_a=voice_a,
            voice_b=voice_b,
            offline_tts=offline_tts,
            visuals=visuals,
            assets=assets,
            broll=broll,
            desk=desk,
            log=log,
            out_name="deskcast.mp4",
            start_step=4,
        )
        produced.append(mp4)
        script = _load_script(job)
        report = _report(source, outline, script, mp4, visuals=visuals, assets=assets, desk=desk)
        (job / "report.md").write_text(report, encoding="utf-8")
        _write_self_contained(job, outline, script, source)

    console.print(Panel.fit(f"[green]Done[/green]\n{job}", border_style="green"))
    return job


def plan_only(
    source: Path,
    *,
    title: str | None = None,
    out_dir: Path | None = None,
    episode_minutes: float = 20.0,
) -> tuple[LegalDocument, EpisodePlan, Path]:
    """Extract + structure + episode plan without rendering video."""
    source = source.expanduser().resolve()
    text = extract_text(source)
    doc = parse_legal_structure(text, source=source, title=title)
    packs = structure_to_outline_chunks(doc)
    plan = plan_episodes(doc, target_minutes=episode_minutes, packs=packs)
    out_dir = (out_dir or Path("out") / "plans").expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = out_dir / f"plan_{stamp}_{source.stem[:40]}"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "extracted.txt").write_text(text, encoding="utf-8")
    (dest / "structure.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    (dest / "STRUCTURE.md").write_text(structure_markdown(doc), encoding="utf-8")
    (dest / "episode_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    (dest / "EPISODE_PLAN.md").write_text(plan_markdown(plan), encoding="utf-8")
    return doc, plan, dest


def _outline_from_packs(
    packs: list[tuple[str, str]],
    *,
    source: Path,
    title: str,
    doc_hint: str,
) -> Outline:
    chunks: list[Chunk] = []
    for i, (head, body) in enumerate(packs):
        chunks.append(
            Chunk(
                index=i,
                title=head[:72],
                text=body,
                word_count=len(body.split()),
            )
        )
    total = sum(c.word_count for c in chunks)
    dk = "contract" if doc_hint == "contract" else "general"
    if doc_hint == "legislation":
        dk = "ops_brief"  # closest existing kind; enrich may re-detect
    return Outline(
        source=str(source),
        title=title,
        chunks=chunks,
        total_words=total,
        doc_kind=dk,  # type: ignore[arg-type]
    )


def _rechunk_outline(outline: Outline, max_chunks: int) -> Outline:
    if len(outline.chunks) <= max_chunks:
        return outline
    packs = [(c.title, c.text) for c in outline.chunks]
    # merge evenly
    n = max_chunks
    weights = [max(1, c.word_count) for c in outline.chunks]
    total = sum(weights)
    target = total / n
    new_chunks: list[Chunk] = []
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
        body = "\n\n".join(bodies)
        new_chunks.append(
            Chunk(index=bi, title=title[:72], text=body, word_count=len(body.split()))
        )
        i += take
    return outline.model_copy(
        update={
            "chunks": new_chunks,
            "total_words": sum(c.word_count for c in new_chunks),
        }
    )


def _render_one(
    outline: Outline,
    dest: Path,
    *,
    use_llm: bool,
    ollama_model: str,
    voice_a: str,
    voice_b: str,
    offline_tts: bool,
    visuals: VisualMode,
    assets: Path,
    broll: Path,
    log: ProgressCb,
    desk: DeskMode | None = None,
    out_name: str = "deskcast.mp4",
    start_step: int = 4,
) -> Path:
    desk = desk or get_desk_mode(DEFAULT_DESK_MODE)
    dest.mkdir(parents=True, exist_ok=True)
    logic = logic_summary(outline)
    (dest / "outline.json").write_text(outline.model_dump_json(indent=2), encoding="utf-8")
    (dest / "logic.json").write_text(json.dumps(logic, indent=2), encoding="utf-8")

    log(f"  [{start_step}/7] Script ({desk.pbp.name}/{desk.color.name})")
    script: Script = generate_script(
        outline, use_llm=use_llm, ollama_model=ollama_model, desk_mode=desk
    )
    (dest / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")
    log(f"    lines={len(script.all_lines())}")

    log(f"  [{start_step + 1}/7] TTS ({voice_a} / {voice_b})")
    clips = synthesize_script(
        script,
        dest / "audio",
        voice_a=voice_a,
        voice_b=voice_b,
        offline=offline_tts,
        prosody_a={
            "rate": desk.pbp.rate,
            "pitch": desk.pbp.pitch,
            "volume": desk.pbp.volume,
        },
        prosody_b={
            "rate": desk.color.rate,
            "pitch": desk.color.pitch,
            "volume": desk.color.volume,
        },
    )
    log(f"    clips={len(clips)}  prosody pbp={desk.pbp.rate}/{desk.pbp.pitch}")

    log(f"  [{start_step + 2}/7] Visuals ({visuals})")
    slides = render_slides(
        script,
        outline,
        dest / "slides",
        visuals=visuals,
        assets_dir=assets,
        broll_dir=broll,
        desk_mode=desk,
    )
    log(f"    frames={len(slides)}")

    log(f"  [{start_step + 3}/7] FFmpeg")
    mp4 = assemble_video(slides, clips, dest / out_name, work_dir=dest / "work")
    report = _report(
        Path(outline.source),
        outline,
        script,
        mp4,
        visuals=visuals,
        assets=assets,
        desk=desk,
    )
    (dest / "report.md").write_text(report, encoding="utf-8")
    return mp4


def _load_script(dest: Path) -> Script:
    raw = json.loads((dest / "script.json").read_text(encoding="utf-8"))
    return Script.model_validate(raw)


def _write_master_index(
    job: Path,
    doc: LegalDocument,
    plan: EpisodePlan,
    videos: list[Path],
) -> None:
    lines = [
        f"# DeskCast master index — {doc.title}",
        "",
        f"- **Profile:** `{doc.profile}`",
        f"- **Episodes:** {plan.total_episodes}",
        f"- **Sections:** {doc.section_count}",
        f"- **Words:** {doc.total_words}",
        f"- **Job:** `{job.name}`",
        "",
        "## Disclaimer",
        "",
        "Briefing aid only. Not legal advice. Not an official text of law or a substitute "
        "for the executed instrument.",
        "",
        "## Episodes",
        "",
    ]
    for ep, vid in zip(plan.episodes, videos):
        rel = vid.relative_to(job) if vid.is_relative_to(job) else vid
        lines.append(f"### {ep.id}: {ep.title}")
        lines.append("")
        lines.append(f"- **Video:** `{rel.as_posix()}`")
        lines.append(f"- **Est. minutes:** ~{ep.estimated_minutes}")
        lines.append(f"- **Words:** {ep.word_count}")
        lines.append(f"- **Packages:** {ep.pack_end - ep.pack_start}")
        lines.append("")
    lines.append("## Structure")
    lines.append("")
    lines.append("See `STRUCTURE.md` and `EPISODE_PLAN.md` in this folder.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("Copyright 2026 Susquehanna Timberwolf Lines, LLC")
    (job / "MASTER_INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    (job / "README_SELF_CONTAINED.md").write_text(
        f"""# Self-contained DeskCast job

**{doc.title}**

| File | Purpose |
|------|---------|
| `MASTER_INDEX.md` | Episode map |
| `STRUCTURE.md` | Full legal tree |
| `EPISODE_PLAN.md` | Planner output |
| `episodes/epXX/deskcast.mp4` | Per-episode videos |
| `deskcast.mp4` | Copy of episode 1 (convenience) |

Play videos offline. Transcripts live under each `episodes/epXX/` folder.

Copyright 2026 Susquehanna Timberwolf Lines, LLC
""",
        encoding="utf-8",
    )


def _write_self_contained(
    job: Path,
    outline: Outline,
    script: Script,
    source: Path,
) -> None:
    """Transcript + package cards so the job folder stands alone with the MP4."""
    lines = script.all_lines()
    transcript_parts = [
        f"# DeskCast transcript — {outline.title}",
        "",
        f"- **Source file:** `{Path(source).name if source else ''}`",
        f"- **Doc kind:** {outline.doc_kind or 'general'}",
        f"- **Packages:** {len(outline.chunks)}",
        f"- **Spoken lines:** {len(lines)}",
        f"- **Owner:** Susquehanna Timberwolf Lines, LLC",
        "",
        "Self-contained briefing transcript. Not legal advice.",
        "",
        "---",
        "",
        "## Spoken show",
        "",
    ]
    for i, ln in enumerate(lines, 1):
        who = ln.speaker or ln.role
        transcript_parts.append(f"**{i}. {who}:** {ln.text}")
        transcript_parts.append("")

    packages = [
        f"# Package cards — {outline.title}",
        "",
    ]
    for ch in outline.chunks:
        packages.append(f"## Pack {ch.index + 1}: {ch.title}")
        packages.append("")
        packages.append(
            f"- **Kind:** `{ch.kind or 'narrative'}`  ·  **Priority:** {ch.priority or 0}  ·  "
            f"**Words:** {ch.word_count}"
        )
        packages.append("")
        packages.append(ch.text.strip())
        packages.append("")
        packages.append("---")
        packages.append("")

    (job / "TRANSCRIPT.md").write_text("\n".join(transcript_parts), encoding="utf-8")
    (job / "PACKAGES.md").write_text("\n".join(packages), encoding="utf-8")
    if not (job / "README_SELF_CONTAINED.md").exists():
        (job / "README_SELF_CONTAINED.md").write_text(
            f"# Self-contained package\n\n**{outline.title}**\n\n"
            "Play `deskcast.mp4`. Read `TRANSCRIPT.md` / `PACKAGES.md`.\n",
            encoding="utf-8",
        )


def _report(
    source: Path,
    outline: Outline,
    script: Script,
    mp4: Path,
    *,
    visuals: str,
    assets: Path,
    desk: DeskMode | None = None,
) -> str:
    desk = desk or get_desk_mode(DEFAULT_DESK_MODE)
    status = "official" if desk.official else "UNOFFICIAL TEST — see PERSONAS_UNOFFICIAL.md"
    banner = unofficial_banner(desk)
    banner_block = f"\n> **Disclaimer:** {banner}\n" if banner else ""
    return f"""# DeskCast report

- **Source:** `{source}`
- **Title:** {outline.title}
- **Chunks:** {len(outline.chunks)}
- **Words (approx):** {outline.total_words}
- **Script lines:** {len(script.all_lines())}
- **Visuals:** `{visuals}`
- **Desk mode:** `{desk.id}` ({status})
- **Doc kind (logic):** `{outline.doc_kind}`
- **Assets:** `{assets}`
- **Output:** `{mp4}`
{banner_block}
## Logic

- Legal structure parse + episode planner for contracts / legislation
- Package kinds: definition, list, warning, procedure, qa, example, summary, narrative
- See `logic.json`, `STRUCTURE.md`, `EPISODE_PLAN.md` when present

## Hosts

- **{desk.pbp.name}** — {desk.pbp.role_label.lower()} ({desk.pbp.voice})
- **{desk.color.name}** — {desk.color.role_label.lower()} ({desk.color.voice})
- Mode label: {desk.label}

---

Copyright 2026 Susquehanna Timberwolf Lines, LLC
Licensed under the Apache License, Version 2.0
"""
