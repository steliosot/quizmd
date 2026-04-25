# quizmd

`quizmd` is a terminal quiz app for:
- Markdown MCQs (single/multiple)
- Imposter quizzes (spot misleading options)
- Essay quizzes (AI rubric scoring)
- Online room modes (compete/collaborate/boxing)

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
- `hello-essay.md` (essay mode)
- `QUIZ_GUIDE.md` (quick commands)

Run starters:

```bash
quizmd --validate hello-quiz.md
quizmd hello-quiz.md

quizmd --validate hello-imposter.md
quizmd hello-imposter.md

quizmd --validate hello-essay.md
export GEMINI_API_KEY="your_key_here"  # or OPENAI_API_KEY / ANTHROPIC_API_KEY
quizmd hello-essay.md
```

## Modes (What + How to Start)

### 1) Single / Multiple (Local MCQ)
- What: classic MCQ practice with timers.
- Start:

```bash
quizmd hello-quiz.md
```

### 2) Imposter (Local MCQ + Distractors)
- What: answer normally and flag misleading options.
- Start:

```bash
quizmd hello-imposter.md
```

### 3) Essay (AI Rubric Grading)
- What: write in editor, get rubric-based score + feedback.
- Start:

```bash
quizmd hello-essay.md
```

### 4) Room: Compete (Online)
- What: fastest correct answers win points.
- Start room:

```bash
quizmd room --create --mode compete --quiz hello-quiz.md
```

### 5) Room: Collaborate (Online)
- What: team must reach full consensus.
- Start room:

```bash
quizmd room --create --mode collaborate --quiz hello-quiz.md
```

### 6) Room: Boxing (Online Teacher/Student)
- What: live chat Q&A, teacher can score with `/score <0-100>`.
- Start room:

```bash
quizmd room --create --mode boxing --quiz hello-quiz.md
```

Join any room:

```bash
quizmd room --join <room-name> --token <room-token>
```

Room quiz requirement:
- In online room modes, each question `Time`/`time_limit` must be **5 seconds or higher**.

## `quizmd init` Coverage

Yes, `quizmd init` covers all mode types:
- MCQ single/multiple via `hello-quiz.md`
- Imposter via `hello-imposter.md`
- Essay via `hello-essay.md`
- Room modes by using `hello-quiz.md` with `--mode compete|collaborate|boxing`

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

- Boxing mode requires a boxing-capable room server revision.
- If cloud server is older, quizmd shows a friendly unsupported-mode message.
- Press `Ctrl+C` at any time to exit.
- Each multiple-choice question must have at least 2 non-empty options.
- If your question text includes markdown bullet lines, add an `Options:` line before answer choices to disambiguate parsing.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -q
```

Multiplayer server local dev note:
- Use Python 3.13 in `multiplayer/server` (`python3.13 -m venv .venv`), since Python 3.14 may fail dependency builds (`pydantic-core`).

## Community

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)
- [LICENSE](LICENSE)
