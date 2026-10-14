# AI-sfa working instructions

Read HANDOFF.md first for current scope and evidence. Keep it current at meaningful checkpoints.

- User-facing communication and project guides: Korean.
- Priority: full Stick Fighter feature analysis and app-verified feature probes. Dataset collection/training is deferred.
- Distinguish stored-state probes, inferred algorithms, and actual app/UI verification.
- Do not publish provided APKs, other users' animation/video originals, or decompiled app source.
- FPS order is (tween_fps, playback_fps).
- Run tests from repository root: `python -m unittest discover -s tests -v`.
- Generated probe files are reproducible with `python build_feature_probes.py`.
- Fetch current remote state before changing GitHub; preserve unrelated work.
