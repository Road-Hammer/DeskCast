from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .characters import ensure_default_hosts, project_assets_dir
from .extract import extract_text
from .logic import enrich_outline, logic_summary
from .models import Outline, Script
from .outline import build_outline
from .render import assemble_video
from .script import generate_script
from .slides import VisualMode, render_slides
from .tts import synthesize_script

console = Console()


def run_pipeline(
    source: Path,
    *,
    out_root: Path | None = None,
    title: str | None = None,
    max_chunks: int = 10,
    use_llm: bool = True,
    ollama_model: str = "llama3.2:1b",
    voice_a: str = "en-US-GuyNeural",
    voice_b: str = "en-US-JennyNeural",
    offline_tts: bool = False,
    visuals: VisualMode = "characters",
    broll_dir: Path | None = None,
    assets_dir: Path | None = None,
) -> Path:
    source = source.expanduser().resolve()
    out_root = (out_root or Path("out")).expanduser().resolve()
    job_id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    job = out_root / job_id
    job.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(f"[bold]DeskCast[/bold] job [cyan]{job_id}[/cyan]\n{source}", border_style="red"))

    console.print("[bold]1/6 Extract[/bold]")
    text = extract_text(source)
    (job / "extracted.txt").write_text(text, encoding="utf-8")

    console.print("[bold]2/6 Outline + logic[/bold]")
    outline: Outline = build_outline(text, source, title=title, max_chunks=max_chunks)
    outline = enrich_outline(outline, text)
    logic = logic_summary(outline)
    (job / "outline.json").write_text(outline.model_dump_json(indent=2), encoding="utf-8")
    (job / "logic.json").write_text(
        __import__("json").dumps(logic, indent=2),
        encoding="utf-8",
    )
    console.print(
        f"  chunks={len(outline.chunks)} words≈{outline.total_words} "
        f"doc_kind=[cyan]{outline.doc_kind}[/cyan] kinds={logic.get('chunk_kinds')}"
    )

    console.print("[bold]3/6 Script[/bold] (logic rules; LLM if available)")
    script: Script = generate_script(
        outline,
        use_llm=use_llm,
        ollama_model=ollama_model,
    )
    (job / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"  lines={len(script.all_lines())} script_doc_kind={script.doc_kind}")

    console.print("[bold]4/6 TTS[/bold]")
    audio_dir = job / "audio"
    clips = synthesize_script(
        script,
        audio_dir,
        voice_a=voice_a,
        voice_b=voice_b,
        offline=offline_tts,
    )
    console.print(f"  clips={len(clips)}")

    console.print(f"[bold]5/6 Visuals[/bold] mode={visuals}")
    assets = assets_dir or project_assets_dir()
    ensure_default_hosts(assets)
    broll = broll_dir or (assets / "broll")
    slides = render_slides(
        script,
        outline,
        job / "slides",
        visuals=visuals,
        assets_dir=assets,
        broll_dir=broll,
    )
    console.print(f"  frames={len(slides)}  assets={assets}")

    console.print("[bold]6/6 FFmpeg assemble[/bold]")
    mp4 = assemble_video(slides, clips, job / "deskcast.mp4", work_dir=job / "work")

    report = _report(source, outline, script, mp4, visuals=visuals, assets=assets)
    (job / "report.md").write_text(report, encoding="utf-8")
    console.print(Panel.fit(f"[green]Done[/green]\n{mp4}", border_style="green"))
    return mp4


def _report(
    source: Path,
    outline: Outline,
    script: Script,
    mp4: Path,
    *,
    visuals: str,
    assets: Path,
) -> str:
    return f"""# DeskCast report

- **Source:** `{source}`
- **Title:** {outline.title}
- **Chunks:** {len(outline.chunks)}
- **Words (approx):** {outline.total_words}
- **Script lines:** {len(script.all_lines())}
- **Visuals:** `{visuals}`
- **Doc kind (logic):** `{outline.doc_kind}`
- **Assets:** `{assets}`
- **Output:** `{mp4}`

## Logic

- Detects study_guide / contract / ops_brief / report / general
- Tags chunks: definition, list, warning, procedure, qa, example, summary, narrative
- Priority scoring elevates warnings & study-critical packages
- See `logic.json` in the job folder for the full breakdown

## Hosts (phase 1)

- **Mike** — play-by-play (left, red)
- **Dana** — color analyst (right, blue)
- Active speaker is bright + ON AIR marker; other host is dimmed
- Swap portraits: put PNGs at `assets/hosts/mike_pbp.png` and `dana_color.png`
- Optional B-roll images: `assets/broll/*` with `--visuals hybrid`

## Next upgrades (other boxes)

- Piper local neural TTS voices
- Lip-sync talking heads (GPU)
- Gen AI B-roll

---

Copyright 2026 Susquehanna Timberwolf Lines, LLC
Licensed under the Apache License, Version 2.0
"""
