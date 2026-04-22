# Changelog

All notable changes to this project are documented in this file.

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
