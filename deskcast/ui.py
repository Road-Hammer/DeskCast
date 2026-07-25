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
"""Functional desktop UI for DeskCast (tkinter — no extra deps)."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from tkinter import (
    BooleanVar,
    DoubleVar,
    END,
    IntVar,
    Menu,
    StringVar,
    Tk,
    Toplevel,
    filedialog,
    messagebox,
    ttk,
)
from tkinter.scrolledtext import ScrolledText

from .characters import project_assets_dir
from .pipeline import plan_only, run_pipeline

APP_TITLE = "DeskCast — STWL"
OWNER = "Susquehanna Timberwolf Lines, LLC"

HELP_TEXT = """\
DeskCast — Help
Susquehanna Timberwolf Lines, LLC (STWL)

WHAT DESKCAST DOES
  DeskCast turns PDF, Word (DOCX), or text documents into dual-host
  “desk cast” videos: Mike (play-by-play) and Dana (color / risk), with
  speech, studio visuals, and FFmpeg assembly.

  For large contracts and legislation, DeskCast can:
  • Parse legal structure (Articles, Sections, Schedules, Appendices, …)
  • Build an episode plan so long instruments are not one endless video
  • Produce self-contained job folders (video + transcript + packages)

QUICK START
  1. Click Browse… and select a document (PDF recommended).
  2. Optionally set a Title (defaults from the file name).
  3. Choose an Output folder (default: ./out under the app folder).
  4. Click “1. Plan structure / episodes” first on large legal docs.
     Review the Activity log for profile, section count, and episodes.
  5. Click “2. Produce video(s)” when ready. Long jobs take time
     (TTS + FFmpeg). Leave the window open until Done.
  6. Click “Open last job folder” to play deskcast.mp4 / episodes.

RECOMMENDED OPTIONS (CONTRACTS & LEGISLATION)
  • Legal structure + episode planner — ON
  • Multi-episode split — ON for large instruments
  • Minutes / episode — 15–25 is a good desktop briefing length
  • Max packs / episode — 16–24 keeps laptop runs manageable
  • No LLM (rules only) — ON until a local model is configured
  • Offline TTS — ON only if you need zero network (system voices)
  • Visuals — “characters” for dual hosts; “slides” for text cards

OUTPUT FOLDER LAYOUT (AFTER PRODUCE)
  out/<job_id>/
    STRUCTURE.md       Full legal tree
    EPISODE_PLAN.md    Episode map
    MASTER_INDEX.md    Links to each episode video
    episodes/ep01/…    Per-episode deskcast.mp4 + TRANSCRIPT + PACKAGES
    deskcast.mp4       Copy of episode 1 (convenience)

  Plans (no video) land under:
    out/plans/plan_<timestamp>_…

CLI EQUIVALENTS
  python -m deskcast ui
  python -m deskcast plan path\\to\\doc.pdf --episode-minutes 20
  python -m deskcast run path\\to\\doc.pdf --legal --multi-episode --no-llm

REQUIREMENTS
  • Python 3.11+ environment with DeskCast installed
  • FFmpeg on PATH (or installed via winget Gyan.FFmpeg)
  • Network for edge-tts unless Offline TTS is checked

DISCLAIMER
  DeskCast is a briefing / training aid. It is not legal advice and not
  an official text of law or a substitute for the executed instrument.
  Confidential documents remain subject to your NDA / distribution rules.

© 2026 Susquehanna Timberwolf Lines, LLC
"""

FAQ_TEXT = """\
DeskCast — FAQ
Susquehanna Timberwolf Lines, LLC (STWL)

Q: What file types can I upload?
A: PDF (text layer), DOCX, TXT, and MD. Scanned PDFs need OCR first
   (empty text layer will fail extraction).

Q: Why Plan before Produce?
A: Plan is fast: it builds the legal tree and episode map without TTS
   or video. For a 70+ page addendum you can see “7 episodes × ~20 min”
   before spending an hour rendering. Always Plan first on big docs.

Q: What is “Legal structure + episode planner”?
A: DeskCast detects Articles, Sections, Schedules, Appendices, Chapters,
   etc., flattens them into packages, and groups packages into episodes
   by a minutes budget. Nothing is silently dropped from the plan.

Q: Multi-episode vs single episode?
A: Multi-episode (recommended for large contracts/legislation) writes
   episodes/ep01, ep02, … each with its own video and transcript.
   Single episode forces one long cast (can be very long / heavy).

Q: What do Minutes / episode and Max packs mean?
A: Minutes / episode is the target airtime budget used by the planner
   (source words ÷ words-per-minute estimate). Max packs / episode caps
   how many packages are rendered inside one episode for laptop safety.

Q: Why is production so slow?
A: Each spoken line is synthesized (edge-tts or offline voices), then
   frames are drawn and FFmpeg muxes audio. 100+ lines = many minutes.
   Multi-episode lets you render only what you need later (future UX);
   today Produce builds the full planned set.

Q: “No LLM (rules only)” — should I leave it on?
A: Yes for offline/confidential work and current laptop defaults.
   Uncheck only if a local Ollama (or compatible) model is running and
   you want script polish. Cloud APIs are not required and not advised
   for NDA materials.

Q: Offline TTS vs normal TTS?
A: Unchecked = edge-tts (needs network, clearer neural voices).
   Checked = pyttsx3 system voices (fully offline, often more robotic).

Q: Visuals: characters / hybrid / slides?
A: characters = dual desk hosts (default).
   hybrid = hosts + optional B-roll images from assets/broll.
   slides = text cards only (fastest, least “show-like”).

Q: Where is my video?
A: After Produce, use “Open last job folder”. Look for deskcast.mp4
   and/or episodes/ep01/deskcast.mp4. Self-contained files:
   TRANSCRIPT.md, PACKAGES.md, STRUCTURE.md, EPISODE_PLAN.md.

Q: Can I use this for legislation projects?
A: Yes. Legal mode is built for contracts and legislation-style
   structure (sections, amendments language, long instruments).
   Prefer multi-episode. Output is a briefing aid, not official law.

Q: The cast sounds clunky or repeats NDA banners.
A: Keep Legal mode on (strips many NDA headers). Prefer Plan → review
   STRUCTURE.md. Future offline TTS + local LLM refine will improve
   speech quality; rules already focus on shall/must and structure.

Q: FFmpeg / TTS errors?
A: Install FFmpeg (e.g. winget install Gyan.FFmpeg) and open a new
   terminal. Check ui_error.log under the output folder. Ensure the
   PDF has a real text layer (not only scanned images).

Q: Is my document uploaded to the cloud?
A: Produce uses local pipelines. edge-tts (default TTS) calls a
   Microsoft speech endpoint for audio only unless Offline TTS is on.
   Document text is not meant for third-party LLM APIs in confidential
   mode — keep “No LLM” on for NDA work.

Q: Who owns DeskCast?
A: Susquehanna Timberwolf Lines, LLC. Software is Apache-2.0; your
   document content remains yours / under its own confidentiality terms.

Q: Keyboard / workflow tips?
A: Plan → read the log → Produce only when episode count looks right.
   Start with episode minutes 20 and max packs 20–24 on 8 GB laptops.

Still stuck? Check the Activity log and out/ui_error.log, then re-run Plan.

© 2026 Susquehanna Timberwolf Lines, LLC
"""

ABOUT_TEXT = """\
DeskCast
Document → dual-host desk-cast video

Owner: Susquehanna Timberwolf Lines, LLC (STWL)
License: Apache-2.0 (see LICENSE; contributions under CLA.md)

Built for laptop-first, offline-capable briefing of complex
contracts and legislation-style instruments.

© 2026 Susquehanna Timberwolf Lines, LLC
"""


class DeskCastApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_TITLE)
        self.root.minsize(720, 560)
        self.root.geometry("880x640")

        self.source = StringVar()
        self.title_var = StringVar()
        self.out_dir = StringVar(value=str(Path.cwd() / "out"))
        self.episode_minutes = DoubleVar(value=20.0)
        self.max_chunks = IntVar(value=24)
        self.legal_mode = BooleanVar(value=True)
        self.multi_episode = BooleanVar(value=True)
        self.no_llm = BooleanVar(value=True)
        self.offline_tts = BooleanVar(value=False)
        self.visuals = StringVar(value="characters")
        self.status = StringVar(value="Ready.")
        self._busy = False
        self._last_job: Path | None = None

        self._build_menu()
        self._build()

    def _build_menu(self) -> None:
        menubar = Menu(self.root)
        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="Help…", command=self._show_help, accelerator="F1")
        help_menu.add_command(label="FAQ…", command=self._show_faq)
        help_menu.add_separator()
        help_menu.add_command(label="About DeskCast…", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)
        self.root.bind("<F1>", lambda _e: self._show_help())

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 6}
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="DeskCast", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, sticky="w", **pad
        )
        head_right = ttk.Frame(frm)
        head_right.grid(row=0, column=1, columnspan=2, sticky="e", **pad)
        ttk.Label(head_right, text=OWNER, font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        ttk.Button(head_right, text="Help", command=self._show_help, width=8).pack(
            side="left", padx=2
        )
        ttk.Button(head_right, text="FAQ", command=self._show_faq, width=8).pack(
            side="left", padx=2
        )

        # Source
        ttk.Label(frm, text="Document").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.source, width=70).grid(
            row=1, column=1, sticky="ew", **pad
        )
        ttk.Button(frm, text="Browse…", command=self._browse).grid(row=1, column=2, **pad)

        ttk.Label(frm, text="Title (optional)").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.title_var, width=70).grid(
            row=2, column=1, columnspan=2, sticky="ew", **pad
        )

        ttk.Label(frm, text="Output folder").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.out_dir, width=70).grid(
            row=3, column=1, sticky="ew", **pad
        )
        ttk.Button(frm, text="Browse…", command=self._browse_out).grid(row=3, column=2, **pad)

        # Options frame
        opt = ttk.LabelFrame(frm, text="Production options", padding=10)
        opt.grid(row=4, column=0, columnspan=3, sticky="ew", **pad)

        ttk.Checkbutton(opt, text="Legal structure + episode planner", variable=self.legal_mode).grid(
            row=0, column=0, sticky="w", padx=4, pady=2
        )
        ttk.Checkbutton(opt, text="Multi-episode split", variable=self.multi_episode).grid(
            row=0, column=1, sticky="w", padx=4, pady=2
        )
        ttk.Checkbutton(opt, text="No LLM (rules only)", variable=self.no_llm).grid(
            row=1, column=0, sticky="w", padx=4, pady=2
        )
        ttk.Checkbutton(opt, text="Offline TTS (pyttsx3)", variable=self.offline_tts).grid(
            row=1, column=1, sticky="w", padx=4, pady=2
        )

        ttk.Label(opt, text="Minutes / episode").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Spinbox(
            opt, from_=8, to=60, increment=1, textvariable=self.episode_minutes, width=8
        ).grid(row=2, column=1, sticky="w", padx=4)

        ttk.Label(opt, text="Max packs / episode").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        ttk.Spinbox(opt, from_=4, to=40, textvariable=self.max_chunks, width=8).grid(
            row=3, column=1, sticky="w", padx=4
        )

        ttk.Label(opt, text="Visuals").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        ttk.Combobox(
            opt,
            textvariable=self.visuals,
            values=["characters", "hybrid", "slides"],
            state="readonly",
            width=14,
        ).grid(row=4, column=1, sticky="w", padx=4)

        # Actions
        act = ttk.Frame(frm)
        act.grid(row=5, column=0, columnspan=3, sticky="ew", **pad)
        self.btn_plan = ttk.Button(act, text="1. Plan structure / episodes", command=self._plan)
        self.btn_plan.pack(side="left", padx=4)
        self.btn_run = ttk.Button(act, text="2. Produce video(s)", command=self._run)
        self.btn_run.pack(side="left", padx=4)
        self.btn_open = ttk.Button(act, text="Open last job folder", command=self._open_job)
        self.btn_open.pack(side="left", padx=4)
        ttk.Button(act, text="Help", command=self._show_help).pack(side="right", padx=4)
        ttk.Button(act, text="FAQ", command=self._show_faq).pack(side="right", padx=4)

        # Log
        ttk.Label(frm, text="Activity log").grid(row=6, column=0, sticky="w", **pad)
        self.log = ttk.Treeview(frm, columns=("msg",), show="headings", height=16)
        self.log.heading("msg", text="Message")
        self.log.column("msg", width=800)
        self.log.grid(row=7, column=0, columnspan=3, sticky="nsew", **pad)
        scroll = ttk.Scrollbar(frm, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.grid(row=7, column=3, sticky="ns")

        ttk.Label(frm, textvariable=self.status).grid(
            row=8, column=0, columnspan=3, sticky="w", **pad
        )

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(7, weight=1)

        self._log(f"{APP_TITLE} — {OWNER}")
        self._log("Drop a contract or legislation PDF, Plan first, then Produce.")
        self._log("Help menu or F1 for full help · FAQ button for common questions.")

    def _show_help(self) -> None:
        self._show_text_window("DeskCast — Help", HELP_TEXT, width=84, height=36)

    def _show_faq(self) -> None:
        self._show_text_window("DeskCast — FAQ", FAQ_TEXT, width=84, height=36)

    def _show_about(self) -> None:
        messagebox.showinfo("About DeskCast", ABOUT_TEXT)

    def _show_text_window(
        self,
        title: str,
        body: str,
        *,
        width: int = 80,
        height: int = 32,
    ) -> None:
        win = Toplevel(self.root)
        win.title(title)
        win.geometry("720x520")
        win.minsize(480, 320)
        win.transient(self.root)

        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=title, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 6))

        text = ScrolledText(
            outer,
            wrap="word",
            width=width,
            height=height,
            font=("Consolas", 10),
            relief="solid",
            borderwidth=1,
        )
        text.pack(fill="both", expand=True)
        text.insert("1.0", body)
        text.configure(state="disabled")

        btns = ttk.Frame(outer)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")
        if "FAQ" in title:
            ttk.Button(btns, text="Open Help…", command=lambda: (win.destroy(), self._show_help())).pack(
                side="right", padx=6
            )
        else:
            ttk.Button(btns, text="Open FAQ…", command=lambda: (win.destroy(), self._show_faq())).pack(
                side="right", padx=6
            )

        win.bind("<Escape>", lambda _e: win.destroy())
        win.focus_set()

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select document",
            filetypes=[
                ("Documents", "*.pdf;*.docx;*.txt;*.md"),
                ("PDF", "*.pdf"),
                ("Word", "*.docx"),
                ("Text", "*.txt;*.md"),
                ("All", "*.*"),
            ],
        )
        if path:
            self.source.set(path)
            if not self.title_var.get().strip():
                self.title_var.set(Path(path).stem.replace("_", " "))

    def _browse_out(self) -> None:
        path = filedialog.askdirectory(title="Output folder")
        if path:
            self.out_dir.set(path)

    def _log(self, msg: str) -> None:
        self.log.insert("", END, values=(msg,))
        self.log.yview_moveto(1.0)
        self.status.set(msg[:120])
        self.root.update_idletasks()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.btn_plan.configure(state=state)
        self.btn_run.configure(state=state)

    def _plan(self) -> None:
        if self._busy:
            return
        src = Path(self.source.get().strip())
        if not src.is_file():
            messagebox.showerror("DeskCast", "Choose a valid source document first.")
            return
        self._set_busy(True)
        self._log(f"Planning: {src.name}")

        def work():
            try:
                doc, plan, dest = plan_only(
                    src,
                    title=self.title_var.get().strip() or None,
                    out_dir=Path(self.out_dir.get()) / "plans",
                    episode_minutes=float(self.episode_minutes.get()),
                )
                self._last_job = dest

                def done():
                    self._log(f"Profile: {doc.profile} | sections: {doc.section_count} | words≈{doc.total_words}")
                    self._log(f"Episodes: {plan.total_episodes} (~{self.episode_minutes.get()}m target)")
                    for ep in plan.episodes:
                        self._log(
                            f"  {ep.id}: {ep.title} | packs={ep.pack_end - ep.pack_start} | "
                            f"~{ep.estimated_minutes}m"
                        )
                    self._log(f"Wrote plan → {dest}")
                    self._set_busy(False)
                    messagebox.showinfo(
                        "DeskCast",
                        f"Plan ready.\n\nProfile: {doc.profile}\n"
                        f"Episodes: {plan.total_episodes}\n\n{dest}",
                    )

                self.root.after(0, done)
            except Exception as e:
                err = traceback.format_exc()

                def fail():
                    self._log(f"ERROR: {e}")
                    self._set_busy(False)
                    messagebox.showerror("DeskCast plan failed", str(e))

                self.root.after(0, fail)
                Path(self.out_dir.get()).mkdir(parents=True, exist_ok=True)
                (Path(self.out_dir.get()) / "ui_error.log").write_text(err, encoding="utf-8")

        threading.Thread(target=work, daemon=True).start()

    def _run(self) -> None:
        if self._busy:
            return
        src = Path(self.source.get().strip())
        if not src.is_file():
            messagebox.showerror("DeskCast", "Choose a valid source document first.")
            return
        if not messagebox.askyesno(
            "DeskCast",
            "Produce video(s) now?\n\n"
            "Long contracts may take many minutes (TTS + FFmpeg).\n"
            "Legal multi-episode mode is recommended for large instruments.",
        ):
            return

        self._set_busy(True)
        self._log(f"Producing: {src.name}")

        def progress(msg: str) -> None:
            # strip rich markup lightly
            plain = msg.replace("[bold]", "").replace("[/bold]", "")
            plain = plain.replace("[cyan]", "").replace("[/cyan]", "")
            plain = plain.replace("[green]", "").replace("[/green]", "")
            self.root.after(0, lambda m=plain: self._log(m))

        def work():
            try:
                # Ensure ffmpeg on PATH if winget install exists
                _ensure_ffmpeg_path()
                job = run_pipeline(
                    src,
                    out_root=Path(self.out_dir.get()),
                    title=self.title_var.get().strip() or None,
                    max_chunks=int(self.max_chunks.get()),
                    use_llm=not self.no_llm.get(),
                    offline_tts=self.offline_tts.get(),
                    visuals=self.visuals.get(),  # type: ignore[arg-type]
                    assets_dir=project_assets_dir(),
                    legal_mode=self.legal_mode.get(),
                    episode_minutes=float(self.episode_minutes.get()),
                    multi_episode=self.multi_episode.get(),
                    progress=progress,
                )
                self._last_job = job

                def done():
                    self._log(f"Done → {job}")
                    self._set_busy(False)
                    messagebox.showinfo("DeskCast", f"Production complete.\n\n{job}")

                self.root.after(0, done)
            except Exception as e:
                err = traceback.format_exc()

                def fail():
                    self._log(f"ERROR: {e}")
                    self._set_busy(False)
                    messagebox.showerror("DeskCast produce failed", str(e))

                self.root.after(0, fail)
                try:
                    Path(self.out_dir.get()).mkdir(parents=True, exist_ok=True)
                    (Path(self.out_dir.get()) / "ui_error.log").write_text(err, encoding="utf-8")
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def _open_job(self) -> None:
        path = self._last_job
        if path is None or not path.exists():
            # try out dir
            out = Path(self.out_dir.get())
            if out.is_dir():
                path = out
            else:
                messagebox.showinfo("DeskCast", "No job folder yet.")
                return
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    def run(self) -> None:
        self.root.mainloop()


def _ensure_ffmpeg_path() -> None:
    local = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    if not local.is_dir():
        return
    for p in local.rglob("ffmpeg.exe"):
        bin_dir = str(p.parent)
        if bin_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        break


def main() -> None:
    DeskCastApp().run()


if __name__ == "__main__":
    main()
