# Changelog

All notable changes to this project are documented in this file.

## v2.4.3rc2 - 2026-04-29

- Fixed confusing MCQ parser failure for challenge-style content:
  - when a standard quiz contains `### Easy/Normal/Hard` inside `## Category: ...`, `quizmd` now raises a targeted message telling users to switch to `# Challenge Quiz: <title>`.
- Includes full starter generation in `quizmd init` (including `hello-challenge.md`, `hello-debug.md`, and `hello-reverse.md`) for clean installs.

## v2.4.0rc2 - 2026-04-26

- Follow-up RC with room UX and reliability refinements:
  - room create now prints a clear host hint when no custom quiz is supplied:
    - `Tip: use --quiz filename to load your quiz.`
  - room token flow re-verified for open vs secure joins in CLI and server tests.
- Includes additional multiplayer/server hardening and coverage updates from recent review fixes.
- Intended as the next prerelease test build after `v2.4.0rc1`.

## v2.4.0rc1 - 2026-04-25

- Release candidate for the next stable line.
- Includes multiplayer room hardening updates, UX/prompt refinements, and test coverage improvements across quiz, essay, and room flows.
- Added optional room access token at create time (default open room):
  - interactive prompt `Require room token for joiners? [y/N]`
  - explicit flags `--require-token` / `--no-token`
  - join command/help now shows token as optional.
- Added friendly custom-room-name conflict error:
  - `Room name "<name>" already exists. Try another name.`
- Enhanced collaborate room mode:
  - per-question discussion phase (chat) before voting phase
  - submissions blocked during discussion with friendly message
  - phase events and reconnect payloads now include collaborate phase metadata.
- Added optional JSON room field `discussion_time` (seconds) for collaborate.
- Intended for validation testing before promoting to a stable `v2.4.0`.

## v2.3.0 - 2026-04-24

- Added multiplayer `boxing` mode (teacher/student chat session) in `quizmd room`.
- Added role-aware room flows:
  - `--mode boxing`
  - `--role teacher|student` (with interactive role pick when omitted)
- Added boxing runtime commands:
  - `/score <0-100>` (teacher only)
  - `/end` (teacher or student)
- Added auto transcript save for boxing sessions to `answers/room-sessions/`.
- Extended multiplayer server models/state/validation for boxing roles and score/end events.
- Added/updated tests for boxing room constraints, score permissions, end-session behavior, and CLI role plumbing.
- Improved room server UX:
  - cloud server preflight status messages (`online` / `getting ready` / `ready`)
  - friendly unavailable message when server cannot be reached
  - cloud-only default server flow (no local/cloud picker)
  - support for multiple configured cloud servers via `QUIZMD_ROOM_SERVERS` (interactive picker only when >1)
  - server capability detection for room modes (prevents unsupported mode selection when OpenAPI is available)
  - friendly message when selected mode is unsupported by current cloud server (for example boxing on older revisions)
  - clearer HTTP validation error text (structured 422 details are now readable)
  - join compatibility retry for legacy servers that reject join `role` field
  - explicit role-flag ignore for known non-boxing rooms
  - cleaner handling of lobby stdin EOF/disconnect events

## v2.2.1 - 2026-04-23

- Added `hello-imposter.md` starter generation in `quizmd init`.
- Updated init next-step output to include validate/run commands for imposter starter.
- Updated `QUIZ_GUIDE.md` scaffold with imposter starter commands.
- Extended init tests to cover imposter starter file creation and parsing.

## v2.2.0 - 2026-04-22

- Added Imposter Mode for MCQ quizzes via `Imposters:` metadata in quiz markdown.
- Added imposter interactions (`X` key), per-question feedback, and summary metrics:
  - Imposter precision
  - Imposter recall
  - False-flag count
- Added partial imposter scoring (`+1` correct flag, `-1` false flag, floor at 0) with per-question max points.
- Improved full-screen quiz flow to keep answer + explanation in one screen before advancing.
- Added compact/ultra-compact terminal rendering improvements for narrow widths.
- Added/updated tests for imposter parsing, scoring, rendering, and end-to-end persistence.
- Added a new example quiz: `quizzes/python-basics-imposter.md`.

## v2.1.1 - 2026-04-22

- Fixed low-time countdown rendering so timer always keeps visible seconds (no blank `😱  s` state).
- Improved terminal resize behavior in interactive quiz mode:
  - full-screen prompt rendering and clean redraws
  - dynamic compact-layout switching on width changes
  - safer ASCII-first compact header/badges on Windows narrow terminals
- Added tests for compact Windows header rendering and kept full suite green.

## v2.1.0 - 2026-04-22

- Added `quizmd init` fast-start scaffolding with starter MCQ/essay templates.
- Added multi-provider essay evaluation support for Gemini, OpenAI, and Anthropic.
- Added `--ai-provider auto` with key-priority and runtime failover (gemini -> openai -> anthropic).
- Improved provider-specific key errors and CLI help/docs for AI setup.
- Expanded test coverage for provider routing, auto fallback, and starter generation.

## v2.0.2 - 2026-04-21

- Hardened essay AI response normalization and retry fallback reason categories.
- Improved Windows editor fallback flow with explicit Notepad prompts.
- Added theme/readability and essay UX improvements from recent iterations.
- Added tests for parser and runtime edge cases across quiz and essay modes.

## v2.0.0 - 2026-04-21

- Introduced essay mode with Gemini-based rubric evaluation.
- Added essay parser/validation and CLI integration.
- Kept MCQ quizzes independent from AI keys and AI runtime.

## v1.0.0 - 2026-04-21

- Stable MCQ-only release baseline.
- Markdown quiz parser, interactive terminal runner, validation mode, and exports.
