# Contributing to quizmd

Thanks for your interest in contributing.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -q
```

## Development Workflow

1. Fork the repository.
2. Create a feature branch.
3. Make focused changes.
4. Add or update tests when behavior changes.
5. Run the full test suite.
6. Open a pull request with a clear description.

## Pull Request Checklist

- Code is readable and follows existing style.
- New behavior is covered by tests.
- Existing tests pass.
- README/docs are updated if user-facing behavior changed.
- No secrets or credentials are committed.

## Quiz Content Contributions

If you contribute quizzes under `quizzes/`:

- Use strict `quizmd` format (`#` title + `##` per question).
- Include `Answer:` and `Type:` for every question.
- Validate before submitting:

```bash
python quizmd.py --validate quizzes/your-quiz.md
```

## Reporting Bugs

Please include:

- OS and terminal (macOS/Linux/Windows, Terminal/iTerm/PowerShell, etc.)
- Python version
- Exact command you ran
- Error output
- A minimal quiz file that reproduces the issue

## Code of Conduct

By participating in this project, you agree to follow the Code of Conduct in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
