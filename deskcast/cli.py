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

from .pipeline import run_pipeline
from .slides import VisualMode

app = typer.Typer(add_completion=False, no_args_is_help=True, help="DeskCast — document → dual-host desk-cast video")
console = Console()


@app.command()
def run(
    source: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    out: Path = typer.Option(Path("out"), "--out", "-o", help="Output root directory"),
    max_chunks: int = typer.Option(10, "--max-chunks", min=2, max=40),
    no_llm: bool = typer.Option(False, "--no-llm", help="Force heuristic script (fastest on weak laptops)"),
    ollama_model: str = typer.Option("llama3.2:1b", "--ollama-model"),
    voice_a: str = typer.Option("en-US-GuyNeural", "--voice-a", help="Play-by-play edge-tts voice"),
    voice_b: str = typer.Option("en-US-JennyNeural", "--voice-b", help="Color edge-tts voice"),
    offline_tts: bool = typer.Option(False, "--offline-tts", help="Use pyttsx3 only"),
    visuals: str = typer.Option(
        "characters",
        "--visuals",
        "-v",
        help="slides | characters | hybrid (characters + b-roll folder)",
    ),
    broll: Optional[Path] = typer.Option(
        None,
        "--broll",
        help="Folder of images for hybrid B-roll (default: assets/broll)",
    ),
    assets: Optional[Path] = typer.Option(
        None,
        "--assets",
        help="Assets root (hosts/, set/, broll/). Default: project assets/",
    ),
) -> None:
    """Build a desk-cast MP4 from a PDF/DOCX/TXT/MD document."""
    mode = visuals.lower().strip()
    if mode not in ("slides", "characters", "hybrid"):
        raise typer.BadParameter("visuals must be slides, characters, or hybrid")
    mp4 = run_pipeline(
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
    )
    console.print(f"[bold]Video:[/bold] {mp4}")


@app.command("init-assets")
def init_assets(
    assets: Path = typer.Option(Path("assets"), "--assets", help="Where to write host/desk assets"),
) -> None:
    """Generate default Mike/Dana portraits and desk background."""
    from .characters import ensure_default_hosts

    paths = ensure_default_hosts(assets.resolve())
    for k, p in paths.items():
        console.print(f"[green]{k}[/green] → {p}")
    console.print("Drop your own PNGs over mike_pbp.png / dana_color.png anytime.")


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
