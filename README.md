# quizmd

`quizmd` is a terminal quiz app for:
- Markdown MCQs (single/multiple)
- Imposter quizzes (spot misleading options)
- Chaos quizzes (branch + recovery scenarios)
- Essay quizzes (AI rubric scoring)
- Online room types (compete/collaborate/eliminate)
- Terminal game modes (Alien Attack)

## Install

Recommended:

```bash
pip install quizmd
```

Update to latest:

```bash
pip install -U quizmd
```

From GitHub (latest repo state):

```bash
pip install "git+https://github.com/steliosot/quizmd.git"
```

Check install:

```bash
quizmd --version
```

## Quick Start

Create starter files:

```bash
quizmd init
```

This creates:
- `hello-quiz.md` (single + multiple MCQ)
- `hello-imposter.md` (imposter mode)
- `hello-debug.md` (debug mode)
- `hello-challenge.md` (challenge mode)
- `hello-reverse.md` (reverse mode)
- `hello-millionaire.md` (millionaire mode)
- `hello-chaos.md` (branching scenario mode)
- `hello-essay.md` (essay mode)
- `QUIZ_GUIDE.md` (quick commands)

Run starters:

```bash
quizmd --validate hello-quiz.md
quizmd hello-quiz.md

quizmd --validate hello-imposter.md
quizmd hello-imposter.md

quizmd --validate hello-chaos.md
quizmd hello-chaos.md

quizmd --validate hello-essay.md
export GEMINI_API_KEY="your_key_here"  # or OPENAI_API_KEY / ANTHROPIC_API_KEY
quizmd hello-essay.md
```

## Modes (What + How to Start)

### 1) Classic MCQ (Local)
- What: single/multiple-choice timed quiz.
- Start: `quizmd hello-quiz.md`

### 2) Imposter (Local)
- What: select correct answers and flag misleading options.
- Start: `quizmd hello-imposter.md`

### 3) Debug (Local)
- What: fix broken Python code with line-aware scoring.
- Start: `quizmd hello-debug.md`

### 4) Challenge (Local)
- What: category board + risk levels (stars scoring).
- Start: `quizmd hello-challenge.md`

### 5) Reverse (Local)
- What: infer code behavior/output in reverse-engineering style MCQs.
- Start: `quizmd hello-reverse.md`

### 6) Millionaire (Local)
- What: 15-question ladder with lifelines and safety nets.
- Start: `quizmd hello-millionaire.md`

### 7) Chaos (Local)
- What: branch + recovery scenario that rejoins at final decision.
- Start: `quizmd hello-chaos.md`

### 8) Essay (Local + AI)
- What: write a short response and get rubric feedback.
- Start: `quizmd hello-essay.md`

### 9) Room: Compete (Online)
- What: correct answers earn base points plus a small capped speed bonus.
- Start room: `quizmd room --create --mode compete --quiz hello-quiz.md`

### 10) Room: Collaborate (Online)
- What: discussion + voting phase, team consensus scoring.
- Start room: `quizmd room --create --mode collaborate --quiz hello-quiz.md`

### 11) Room: Eliminate (Online)
- What: wrong answers eliminate players from scoring, but everyone keeps playing for practice.
- Start room: `quizmd room --create --mode eliminate --quiz hello-quiz.md`

### 12) Game: Alien Attack (Terminal)
- What: arcade shooter mini-game.
- Start: `quizmd alien-attack`

Join any room:

```bash
quizmd room --join <room-name> [--token <room-token>]
```

Room behavior:
- Rooms are open by default in the CLI. Use `--require-token` to make a token-protected room.
- Auto-advance is the default. Use `--advance manual` if the host should type `/next` after each result.
- Compete/Eliminate scoring: correct answer = question points + up to 25% speed bonus; wrong answer = `0`.
- Finished rooms are ephemeral and are released by the room server after the final results.

Room quiz requirement:
- In online room types, each question `Time`/`time_limit` must be **5 seconds or higher**.
- For JSON room quizzes, optional `discussion_time` (seconds) controls collaborate chat phase per question.

## `quizmd init` Coverage

Yes, `quizmd init` covers all mode types:
- MCQ single/multiple via `hello-quiz.md`
- Imposter via `hello-imposter.md`
- Chaos via `hello-chaos.md`
- Essay via `hello-essay.md`
- Room types by using `hello-quiz.md` with `--mode compete|collaborate|eliminate`

## Essay Keys (Essay Mode Only)

MCQ quizzes do not require API keys.

Supported keys:
- `GEMINI_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

Auto provider order:
1. Gemini
2. OpenAI
3. Anthropic

Mac/Linux example:

```bash
export GEMINI_API_KEY="your_key_here"
```

Windows PowerShell example:

```powershell
$env:GEMINI_API_KEY="your_key_here"
```

## Validate Any Quiz

```bash
quizmd --validate quizzes/harry-potter-quiz.md
```

## Theme

```bash
quizmd --theme auto quizzes/harry-potter-quiz.md
quizmd --theme light quizzes/harry-potter-quiz.md
quizmd --theme dark quizzes/harry-potter-quiz.md
```

## Notes

- Local question modes support `Q` for graceful quit with summary.
- Press `Ctrl+C` at any time to exit.
- Each multiple-choice question must have at least 2 non-empty options.
- If your question text includes markdown bullet lines, add an `Options:` line before answer choices to disambiguate parsing.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests -q
```

## Related Repositories

- Room server: [steliosot/quizmd-server](https://github.com/steliosot/quizmd-server)
- Web app: [steliosot/quizmd-web](https://github.com/steliosot/quizmd-web)

This repository is the CLI/PyPI package.

## Community

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)
- [LICENSE](LICENSE)
