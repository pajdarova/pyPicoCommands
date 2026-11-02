# Basic commands

## Preferences

- CLAUDE.md, MEMORY.md, subdirectory memory/ are kept directly in the project folder root for portability between machines and are integral part of the repository

- Files in the repository are in US English even that the conversation is in a different language


## Instructions

- At the start of a session, read this file and MEMORY.md (if it exists). The MEMORY.md should contain an index and short description of files in memory/ directory.

- At the end of the work, record very important new facts/decisions here and other in memory/. Update the index MEMORY.md.

- After brainstorming (Claude as sparring partner/advisor/opponent), summarize the key conclusions and decisions into a separate file in memory/ (e.g. memory/brainstorm_<topic>.md) — not the full transcript of the discussion, just the substance. Update the index MEMORY.md.

- Write detailed documentation of code into the source files. If the documentation is missing, add it in the well readable form.

- Commit and push only when the user asks.


# CLAUDE.md - project state

## What this is

`pypicocommands`: a text-command interface (`Picoscope.cmd("OPEN; A ON; ...")`) to PicoScope 2000/3000/4000/5000 series oscilloscopes, aimed at publication on PyPI. Origin: the common PicoScope module of the Experiment-Skeleton-System project, split off on 2026-11-02. GitHub: https://github.com/pajdarova/pyPicoCommands (branch `main`).

- Layout: `src/pypicocommands/` (`picoscope.py` main module, `identify.py`, `__main__.py`), `tests/test_picoscope.py` (simulator-based), `docs/` (hardware test plan, design notes imported from the original project).
- License: MIT (`LICENSE`). The code was written in the author's own time (vacation), not for the employer.
- The package does not bundle the PicoSDK drivers; the module loads them with ctypes (`PICO_SDK_DIR` may name the DLL folder).

## Python environment

- This project has no virtual environment of its own yet. Run the tests with the Python of the Experiment-Skeleton-System project (Python 3.14, `uv`), with the sources on the path:
  `PYTHONPATH=src <path to Experiment-Skeleton-System>/.venv/Scripts/python.exe -B -m unittest discover tests`
- Dependencies are deliberately not pinned (only `numpy` in `pyproject.toml`): the project runs on the freshest versions. If something breaks after an upgrade, fix the code or report it rather than pinning versions.
- Build check: `uv build` (wheel and sdist); test an install in a throw-away venv.

## Hardware status

- Verified on hardware: PicoScope 5000 series (5443D, ps5000a).
- NOT verified: 2000 (ps2000a), 3000 (ps3000a), 4000 (ps4000a); the checklist is `docs/HW_TEST_PLAN.md`. The `ALL` command was tested on the simulator only.
- Known open problem: the pulse-width qualifier on the 5443D does not discriminate pulse width (driver or hardware behavior, see `docs/design_and_hardware_notes.md`).

## Before publishing on PyPI

- Publish first to TestPyPI; the upload is done by the author with a project-scoped token.
- Keep the version in `src/pypicocommands/__init__.py` (read by `pyproject.toml`).
