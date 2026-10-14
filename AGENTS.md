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

## Accuracy-preserving token and handoff discipline

- Treat HANDOFF.md as a compact current-state entry point. Replace obsolete next steps; move historical detail to docs/history rather than appending it indefinitely. Preserve corrections and evidence in dedicated reports.
- In a new conversation, read HANDOFF.md and this file, then the named current report. Follow topic-specific links only as needed. Explicit user reading requests still take precedence.
- Within a conversation, reuse successfully read content and verified SHAs. Reread only when missing context or a possible change affects the decision. Do not reparse unchanged originals merely to recreate established counts.
- Print narrow excerpts and summaries. Filter tool metadata by exact names before printing; never dump the full registry. Inspect large JSON/XML/strings programmatically and return only relevant rows/counts. Keep original source, images and full dumps private.
- Batch independent reads; keep dependent analysis and writes sequential. Use purpose-built tools or local scripts when they reduce work without weakening verification. Do not add agents or skills solely to save tokens.
- Check known local evidence/cache paths before redownloading or decompiling. Reuse valid tools/extraction results in the same run. If absent, recover only files needed for the current question.
- Run relevant checks after a change, once. Repeat only after new changes, failures or unresolved concerns. Do not regenerate probes for documentation-only edits.
- Save meaningful findings, source locations, verification scope and remaining uncertainties. Avoid vague confidence percentages. A hypothesis must not silently become a confirmed rule during compaction.
- A handoff must state current priority, exact next action, blockers, protected files, environment/cache availability and validation status. Supply docs/HANDOFF-PROMPT.md when recommending a new conversation.
- Recommend a new conversation when repeated stale context, conflicting plans or bulky history make it more efficient. Do not claim automatic knowledge of remaining context capacity or promise zero degradation. Complete and persist the checkpoint first.

## Concrete low-output tool discipline

- Before retrieving broad commit/PR metadata, determine which fields are needed. Filter returned structures inside the tool call and print only those fields; do not print diffs or full audit JSON to obtain a SHA.
- For structured multi-file writes, keep content inside the orchestration call. Preserve UTF-8 rather than expanding Korean into Unicode escapes. Check for truncated command output before parsing or writing; do not repeat a large dump after a truncation without changing the transfer approach.
- Use relevant tools/skills when they improve accuracy or reduce unnecessary work. Tool discovery/loading is selective, and does not by itself justify redundant downloads or repeated reads.
- When new wasteful behavior is observed, update this guidance and the compact handoff at the next meaningful checkpoint. Keep performance/verification limits explicit rather than sacrificing accuracy to reduce tokens.

- For large assembly reads, count/select semantic annotations or address windows before printing. Size the output budget to the selected excerpt; if truncated, recover only the missing address window. Trace a closure’s enclosing function before treating its name as a global planner rule.

## Standing GitHub authorization — 2026-10-15

- The user explicitly approved publication of the AOT path report and granted standing authorization for future changes of the same scope: directly authored analysis reports, aggregate metadata, and handoff/workflow documentation in twoapple08/AI-sfa main.
- Continue those authorized writes without repeatedly asking for permission. Preserve remote changes and use an expected-head check. This authorization does not change system approval settings or guarantee automatic approval.
- This does not authorize publication of APK/SFA/video originals, decompiled source, assembly dumps, or changing protected predictions, optimizing File-2, training, or AI integration. If automatic review rejects an action despite the standing authorization, do not bypass it; report the stated reason.

- Do not infer remaining weekly usage or a number of available turns. The assistant cannot inspect that quota here. When the user reports a low budget, persist a concrete checkpoint and provide the current handoff prompt. User Android setup is already verified: do not repeat installation, pairing, getprop, or APK inventory unless a changed environment or connection failure requires it.

- APK 재패키징은 서명 성공만으로 완료로 세지 않는다. 최종 APK의 원본 lib/assets/res/resources.arsc 및 미수정 dex 항목 보존을 대조한다. raw-resource 빌드의 파일 누락 여부를 확인하고, 중간 실패본은 전달하지 않는다. Manifest는 전체 덤프 대신 package/provider/permission/component의 필요한 항목만 출력한다.
