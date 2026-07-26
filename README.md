# DeskCast

**Turn long documents into dual-host “desk cast” videos — on a laptop, without a GPU.**

DeskCast is a local pipeline from **Susquehanna Timberwolf Lines, LLC (STWL)** that reads a PDF, Word doc, or text file and produces a broadcast-style MP4: two hosts (play-by-play + color analyst), smart content logic, speech, studio visuals, and FFmpeg assembly.

Built first on modest hardware (8 GB RAM class) so the same project runs on stronger machines later.

---

### GitHub About (short)

```text
Document → dual-host desk-cast video. Local pipeline: extract, logic-aware script, TTS, studio characters, FFmpeg. Laptop-first. Apache-2.0. © 2026 Susquehanna Timberwolf Lines, LLC
```

**Suggested topics:** `video` `tts` `document-processing` `pdf` `ffmpeg` `broadcast` `cli` `python` `deskcast` `stwl` `apache-2.0`

---

## Product description

DeskCast helps you **explain dense material out loud** without sitting in an editor for hours. Drop in a study guide, ops brief, contract pack, or report; DeskCast:

1. **Extracts** text from PDF / DOCX / TXT / MD  
2. **Outlines** the document into packages  
3. **Classifies** content (study guide, contract, ops brief, etc.) and tags each package (definition, warning, procedure, list, …)  
4. **Writes dual-host commentary** — Mike (tempo) and Dana (nuance / exam tips / risk) with smoother transitions  
5. **Synthesizes speech** (edge-tts online, or offline system voices)  
6. **Renders a studio desk** with photoreal hosts, lower-thirds, ON AIR, and source ticker  
7. **Muxes** audio + frames with FFmpeg into `deskcast.mp4`

Optional: Ollama/OpenAI for richer scripts; hybrid B-roll stills behind the desk.

### Who it’s for

- Operators and trainers who need a **desk breakdown** of a long PDF  
- Study / certification content that benefits from **exam-tip style color**  
- Small teams who want **local** generation, not a cloud video SaaS  

### What it is not

- Not a Hollywood text-to-video model (no Sora-class gen film on the laptop profile)  
- Not a full NLE; it **assembles** a show from document logic + VO + graphics  

---

## Pipeline

```
PDF / DOCX / TXT / MD
        │
        ▼
   extract text ──► chunk + outline
        │
        ▼
   content logic (doc kind + package tags)
        │
        ▼
   dual script (Play-by-play + Color)
   · rules engine (smooth desk flow)
   · optional LLM (Ollama / OpenAI-compatible)
        │
        ▼
   TTS (edge-tts, or offline pyttsx3)
        │
        ▼
   studio frames (characters / hybrid / slides)
        │
        ▼
   FFmpeg mux → out/<job>/deskcast.mp4
```

## Quick start (Windows)

```powershell
cd $env:USERPROFILE\Python_Projects\deskcast
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Optional: install FFmpeg if missing
winget install -e --id Gyan.FFmpeg

# Generate default host portraits + desk set
python -m deskcast init-assets

# Desktop UI (plan + produce)
python -m deskcast ui

# Plan legal structure / episodes only (no video)
python -m deskcast plan path\to\contract.pdf --episode-minutes 20

# Run on a sample / your doc (characters mode is default)
python -m deskcast run path\to\document.pdf --title "Game Day Desk Cast" --no-llm

# Large contracts / legislation (structure + multi-episode)
python -m deskcast run path\to\addendum.pdf --legal --multi-episode --episode-minutes 20 --max-chunks 24 --no-llm
```

Open a **new** terminal after installing FFmpeg so `ffmpeg` is on PATH.

### Desktop UI

```powershell
python -m deskcast ui
# or: deskcast-ui
```

- Browse PDF/DOCX/TXT → **Plan structure / episodes** → **Produce video(s)**
- **Help** menu / **F1** / **FAQ** buttons for usage notes
- Legal mode + multi-episode recommended for long contracts and legislation

### Legal structure & episodes

| Command / flag | Purpose |
|----------------|---------|
| `deskcast plan` | Parse Articles/Sections/Schedules; write `STRUCTURE.md` + `EPISODE_PLAN.md` |
| `--legal` / `--no-legal` | Use legal tree + planner (default on) |
| `--multi-episode` / `--single-episode` | Split long instruments vs one cast |
| `--episode-minutes N` | Target airtime budget per episode |

Long jobs write `out/<job>/episodes/ep01/…` plus `MASTER_INDEX.md`.

### Visual modes (phase 1 characters)

| Mode | Flag | What you get |
|------|------|----------------|
| **characters** (default) | `--visuals characters` | Dual desk hosts, active speaker lit, lower-thirds |
| **hybrid** | `--visuals hybrid` | Same + cycles images from `assets/broll/` behind the desk |
| **slides** | `--visuals slides` | Classic text-card graphics only |

### Desk modes (host pairs)

| Mode | Flag | Pair | Status |
|------|------|------|--------|
| **sports** (default) | `--desk-mode sports` | Mike + Dana | Official STWL |
| **clear_channel** | `--desk-mode clear_channel` | Bo + Dale | **Unofficial test** |
| **night_watch** | `--desk-mode night_watch` | Art + Dana | **Unofficial test** (Art) |

Bo, Dale, and Art are STWL **working names for internal product testing only** — not licensed likenesses or real radio brands. If testing goes well we may pursue licenses; otherwise we design original hosts with a similar essence. See [`PERSONAS_UNOFFICIAL.md`](PERSONAS_UNOFFICIAL.md).

```text
assets/
  hosts/mike_pbp.png      # official
  hosts/dana_color.png
  hosts/bo_overnight.png  # unofficial test (placeholder if missing)
  hosts/dale_road.png
  hosts/art_nightwatch.png
  set/desk_bg.png
  broll/*.jpg             # optional stills for --visuals hybrid
```

### Useful flags

```text
--title "My Show"
--visuals characters     # or hybrid / slides
--desk-mode sports       # or clear_channel / night_watch
--broll path\to\images
--max-chunks 24          # packs per episode (2–40)
--voice-a en-US-GuyNeural   # optional; defaults to desk host voice
--voice-b en-US-JennyNeural
--offline-tts            # pyttsx3 only (no network)
--no-llm                 # force heuristic script (fastest)
--ollama-model llama3.2:1b
--legal / --no-legal
--multi-episode / --single-episode
--episode-minutes 20
```

## Outputs

```text
out/<job_id>/
  extracted.txt
  STRUCTURE.md / structure.json   # legal tree (when --legal)
  EPISODE_PLAN.md                 # multi-episode map
  MASTER_INDEX.md
  episodes/ep01/deskcast.mp4      # per-episode packages
  deskcast.mp4                    # convenience copy of ep01
  outline.json / script.json
  TRANSCRIPT.md / PACKAGES.md
  report.md
```

## Built-in logic (no GPU)

DeskCast classifies the document and each package, then changes commentary tone:

| Doc kinds | Chunk kinds |
|-----------|-------------|
| `study_guide`, `contract`, `ops_brief`, `report`, `general` | `definition`, `list`, `warning`, `procedure`, `qa`, `example`, `summary`, `narrative` |

Examples:
- **Study guides** → exam-tip color, definition drills, trap warnings  
- **Contracts** → obligation / risk language  
- **Ops briefs** → timeline + critical path  

Each job writes `logic.json` with kinds, priorities, and rules applied.

## Hardware profile

| Component | Default on weak laptop |
|-----------|-------------------------|
| Script    | Heuristic dual-host (no LLM) or tiny Ollama model |
| TTS       | `edge-tts` (free network) or `pyttsx3` offline |
| Video     | 1280×720, slideshow + audio, libx264 ultrafast |
| RAM       | Avoids loading big local video/LLM models |

## License & copyright

**Copyright 2026 Susquehanna Timberwolf Lines, LLC**

| | |
|--|--|
| **Outbound license** | [Apache License 2.0](LICENSE) — free to use, modify, and ship (with attribution) |
| **Copyright owner** | Susquehanna Timberwolf Lines, LLC (STWL) keeps ownership of the original work |
| **Inbound contributions** | [CLA.md](CLA.md) — contributors keep their copyright, license patches to STWL so collab stays clean |
| **Notice file** | [NOTICE](NOTICE) · [COPYRIGHT.md](COPYRIGHT.md) |

```text
Copyright 2026 Susquehanna Timberwolf Lines, LLC
Licensed under the Apache License, Version 2.0
```

### Contributing

1. Open a PR.  
2. Confirm the CLA (see `CLA.md`), e.g. comment:  
   `I have read the CLA and I license my contributions under the CLA and Apache-2.0.`  
3. Maintainers may require that confirmation before merge.
