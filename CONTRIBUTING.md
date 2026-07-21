# Contributing to DeskCast

Thanks for helping improve DeskCast.

## License

- **You use DeskCast** under the [Apache License 2.0](LICENSE).  
- **Copyright** in the original project is held by **Susquehanna Timberwolf Lines, LLC**.  
- **Your patches** are accepted under the [Contributor License Agreement](CLA.md).

## Before you open a PR

1. Read [CLA.md](CLA.md).  
2. On the PR, post:

```text
I have read the CLA and I license my contributions under the CLA and Apache-2.0.
```

3. Keep changes focused; include a short description of *why*.  
4. Prefer laptop-friendly defaults (no hard GPU dependency).

## Development (Windows)

```powershell
cd path\to\deskcast
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m deskcast run samples\sample_brief.md --no-llm --max-chunks 4
```

## Code of collaboration

- Be respectful.  
- Do not commit secrets, large binaries, or third-party copyrighted PDFs.  
- Do not use the STWL / DeskCast trademarks except for reasonable attribution.

Questions: open a GitHub issue.
