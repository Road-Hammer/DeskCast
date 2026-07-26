# Unofficial host personas — internal testing only

**Owner:** Susquehanna Timberwolf Lines, LLC (STWL)  
**Product:** DeskCast  
**Status:** Product / UX testing — **not** production branding for public release

---

## What this is

DeskCast’s **official** dual-host pair is:

| Role | Name | Status |
|------|------|--------|
| Play-by-play / tempo | **Mike** | Official STWL persona |
| Color / risk | **Dana** | Official STWL persona |

For product testing we also ship **three additional STWL working-name personas**:

| Working name | Desk mode | Role | Status |
|--------------|-----------|------|--------|
| **Bo** | Clear channel overnight | Lead / overnight host | **Unofficial test** |
| **Dale** | Clear channel overnight | Road / practical color | **Unofficial test** |
| **Art** | Night Watch | Late-night lead | **Unofficial test** |

These names and “essences” (warm overnight lane, trucker clear-channel grit, late-night open-lines curiosity) are **internal design placeholders**. They are inspired by the *feel* of classic overnight AM radio hosting styles in the abstract — not by any claim of identity, endorsement, employment, or license.

---

## What this is not

- **Not** a likeness, voice clone, or impersonation of any real person  
- **Not** use of any real DJ’s legal name, stage name, catchphrase trademark, show title, or call-sign branding  
- **Not** an official product of, or affiliation with, any radio network, syndicate, or estate  
- **Not** cleared for public marketing, App Store / website hero art, or paid client deliverables under these working names  

Any resemblance to living or historical broadcasters is **coincidental at the essence level only**. We deliberately use **different names** (Bo, Dale, Art) and STWL-owned copy.

---

## Desk modes in the product

| Mode id | Pair | Official? |
|---------|------|-----------|
| `sports` | Mike + Dana | Yes |
| `clear_channel` | Bo + Dale | No — unofficial test |
| `night_watch` | Art + Dana | No — Art is unofficial test; Dana remains official |

CLI: `--desk-mode sports|clear_channel|night_watch`  
UI: **Desk mode** combobox under Production options.

Jobs using unofficial modes write a short disclaimer into `report.md` and show an **UNOFFICIAL** tag on character frames when practical.

---

## Path after testing

1. **If testing goes well** — STWL may reach out about a proper **license** or collaboration for named talent / estate rights, and only then use real names, likenesses, or trademarks under written agreement.  
2. **If licensing is unavailable or unwanted** — we **redesign** fully original hosts that keep a *similar essence* (warm overnight companion, road-smart color, late-night curiosity) under new STWL-owned names, art, and voices.  
3. Until (1) or (2) is complete, keep these three marked **unofficial** everywhere they appear (UI labels, help text, reports, this file).

---

## Developer notes

- Registry: `deskcast/hosts.py` (`HostProfile`, `DeskMode`, `DESK_MODES`)  
- Portraits: `assets/hosts/{stem}.png` — placeholders auto-drawn if missing  
- Default voices (edge-tts): see each `HostProfile.voice`  
- Script banks still author against Mike/Dana strings; `apply_host_names_to_script()` remaps speakers and in-dialogue names per desk mode  

---

## Contact / ownership

Copyright © 2026 Susquehanna Timberwolf Lines, LLC.  
DeskCast is licensed under the Apache License, Version 2.0 — see `LICENSE` and `COPYRIGHT.md`.  
Persona *concepts* in this file are STWL product design materials for testing; they do not create third-party rights.
