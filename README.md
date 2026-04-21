# quizmd

`quizmd` runs markdown-based quizzes in the terminal with timers, single/multiple choice support, and answer export.

## Install

Install directly from GitHub:

```bash
pip install "git+https://github.com/steliosot/quizmd.git"
```

Then check the CLI:

```bash
quizmd --version
```

## Run a Quiz

If you want the bundled examples, clone the repo:

```bash
git clone https://github.com/steliosot/quizmd.git
cd quizmd
quizmd quizzes/harry-potter-quiz.md
```

Validate quiz files without running the interactive UI:

```bash
quizmd --validate quizzes/harry-potter-quiz.md
```

## Example Quizzes Included

- `quizzes/harry-potter-quiz.md`
- `quizzes/world-geography-quiz.md`
- `quizzes/python-basics-quiz.md`
- `quizzes/math-foundations-quiz.md`
- `quizzes/history-and-civics-quiz.md`
- `quizzes/general-science-quiz.md`

## Simple Quiz Example

Create a file named `my-quiz.md`:

```markdown
# My First Quiz

## Question 1
What is 2 + 2?

- 3
- 4
- 5

Answer: 2
Type: single
Time: 20
Explanation: 2 + 2 is 4.
```

Run it:

```bash
quizmd --validate my-quiz.md
quizmd my-quiz.md
```

## Guide: How to Create a Quiz

1. Start with a single `#` quiz title.
2. Add each question as a `##` block.
3. Put the question text on the next line.
4. Add answer options using `- ` bullet lines.
5. Add required fields:
   - `Answer:` (1-based indexes, comma-separated for multiple)
   - `Type:` (`single` or `multiple`)
6. Add optional fields:
   - `Time:` positive integer seconds
   - `Explanation:` any text
7. Run `quizmd --validate your-quiz.md` before sharing.

## Quiz File Rules

- Each question must start with `##`.
- Text outside the title and `##` blocks is rejected.
- `Answer:` is required and must be valid indexes.
- `Type:` is required and must be `single` or `multiple`.
- Duplicate answers like `Answer: 2,2` are rejected.
- `Time:` (if present) must be greater than zero.

## Common Validation Errors

- `missing required field(s): options`
- `missing required field(s): answer`
- `missing required field(s): type`
- `duplicate answer indexes`
- `unsupported question type`
- `unexpected content outside question blocks`
- `no valid questions found`

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -q
```
