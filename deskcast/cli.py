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

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .pipeline import plan_only, run_pipeline
from .slides import VisualMode

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="DeskCast — document → dual-host desk-cast video (STWL)",
)
console = Console()


@app.command()
def run(
    source: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    out: Path = typer.Option(Path("out"), "--out", "-o", help="Output root directory"),
    max_chunks: int = typer.Option(24, "--max-chunks", min=2, max=40),
    no_llm: bool = typer.Option(False, "--no-llm", help="Force heuristic script"),
    ollama_model: str = typer.Option("llama3.2:1b", "--ollama-model"),
    voice_a: str = typer.Option("en-US-GuyNeural", "--voice-a"),
    voice_b: str = typer.Option("en-US-JennyNeural", "--voice-b"),
    offline_tts: bool = typer.Option(False, "--offline-tts"),
    visuals: str = typer.Option("characters", "--visuals", "-v"),
    broll: Optional[Path] = typer.Option(None, "--broll"),
    assets: Optional[Path] = typer.Option(None, "--assets"),
    legal: bool = typer.Option(True, "--legal/--no-legal", help="Legal structure + episode planner"),
    episode_minutes: float = typer.Option(20.0, "--episode-minutes", min=5.0, max=120.0),
    multi_episode: bool = typer.Option(
        True, "--multi-episode/--single-episode", help="Split long legal docs into episodes"
    ),
) -> None:
    """Build desk-cast MP4(s) from a PDF/DOCX/TXT/MD document."""
    mode = visuals.lower().strip()
    if mode not in ("slides", "characters", "hybrid"):
        raise typer.BadParameter("visuals must be slides, characters, or hybrid")
    job = run_pipeline(
        source,
        out_root=out,
        title=title,
        max_chunks=max_chunks,
        use_llm=not no_llm,
        ollama_model=ollama_model,
        voice_a=voice_a,
        voice_b=voice_b,
        offline_tts=offline_tts,
        visuals=mode,  # type: ignore[arg-type]
        broll_dir=broll,
        assets_dir=assets,
        legal_mode=legal,
        episode_minutes=episode_minutes,
        multi_episode=multi_episode,
    )
    console.print(f"[bold]Job:[/bold] {job}")


@app.command("plan")
def plan_cmd(
    source: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    out: Path = typer.Option(Path("out") / "plans", "--out", "-o"),
    episode_minutes: float = typer.Option(20.0, "--episode-minutes", min=5.0, max=120.0),
) -> None:
    """Parse legal structure and write an episode plan (no video)."""
    doc, plan, dest = plan_only(
        source, title=title, out_dir=out, episode_minutes=episode_minutes
    )
    console.print(f"[bold]Profile:[/bold] {doc.profile}")
    console.print(f"[bold]Sections:[/bold] {doc.section_count}  words≈{doc.total_words}")
    console.print(f"[bold]Episodes:[/bold] {plan.total_episodes} (~{episode_minutes}m target)")
    for ep in plan.episodes:
        console.print(
            f"  {ep.id}: {ep.title}  packs={ep.pack_end - ep.pack_start}  "
            f"words={ep.word_count}  ~{ep.estimated_minutes}m"
        )
    console.print(f"[bold]Wrote:[/bold] {dest}")


@app.command()
def ui() -> None:
    """Launch the DeskCast desktop UI."""
    from .ui import main as ui_main

    ui_main()


@app.command("init-assets")
def init_assets(
    assets: Path = typer.Option(Path("assets"), "--assets"),
) -> None:
    """Generate default Mike/Dana portraits and desk background."""
    from .characters import ensure_default_hosts

    paths = ensure_default_hosts(assets.resolve())
    for k, p in paths.items():
        console.print(f"[green]{k}[/green] → {p}")


@app.command("version")
def version_cmd() -> None:
    from . import __copyright__, __license__, __owner__, __version__

    console.print(f"DeskCast {__version__}")
    console.print(__copyright__)
    console.print(f"Owner: {__owner__}")
    console.print(f"License: {__license__} (see LICENSE); contributions under CLA.md")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
