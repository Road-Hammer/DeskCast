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

# Run on a sample / your doc (characters mode is default)
python -m deskcast run path\to\document.pdf --title "Game Day Desk Cast" --no-llm
```

Open a **new** terminal after installing FFmpeg so `ffmpeg` is on PATH.

### Visual modes (phase 1 characters)

| Mode | Flag | What you get |
|------|------|----------------|
| **characters** (default) | `--visuals characters` | Dual desk hosts (Mike/Dana), active speaker lit, lower-thirds |
| **hybrid** | `--visuals hybrid` | Same + cycles images from `assets/broll/` behind the desk |
| **slides** | `--visuals slides` | Classic text-card graphics only |

```text
assets/
  hosts/mike_pbp.png      # replace with your art
  hosts/dana_color.png
  set/desk_bg.png
  broll/*.jpg             # optional stills for --visuals hybrid
```

### Useful flags

```text
--title "My Show"
--visuals characters     # or hybrid / slides
--broll path\to\images
--max-chunks 12          # keep short on weak laptops
--voice-a en-US-GuyNeural
--voice-b en-US-JennyNeural
--offline-tts            # pyttsx3 only (no network)
--no-llm                 # force heuristic script (fastest)
--ollama-model llama3.2:1b
```

## Outputs

```text
out/<job_id>/
  extracted.txt
  outline.json
  script.json
  audio/                 # per-line wav/mp3
  slides/                # png frames
  deskcast.mp4           # final video
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
