# pypicocommands: split-off and packaging (2026-11-02)

- The finished common PicoScope module was copied out of Experiment-Skeleton-System (`Independent_Modules/Picoscope_Common`) into this standalone repository, with its own git. The old modules `Picoscope_5000D` and `Picoscope_pyPicoSDK` stay in the original project.
- Package name `pypicocommands` (free on PyPI when checked, HTTP 404). Layout `src/pypicocommands/`; public API `Picoscope`, `ExceptionPicoscope`, `ExceptionNotSupported`; console `python -m pypicocommands`.
- License MIT, copyright Andrea Dagmar Pajdarova 2026. Made during the author's vacation, so no employer claim is expected.
- New command `ALL <channel command>` (e.g. `ALL COUPLING DC`, `ALL OFF; A ON`, `ALL?`, `ALL RANGE?`): applies to all analog channels of the model (A-D before OPEN), all or nothing with rollback. Digital ports and `TRG` are not included on purpose. Simulator-tested only.
- Next: verify the 2000/3000/4000 families on real instruments at the work place, then TestPyPI and PyPI.
