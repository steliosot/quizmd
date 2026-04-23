#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import random
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

try:
    from wcwidth import wcswidth as _wcwidth_wcswidth
except ModuleNotFoundError:
    _wcwidth_wcswidth = None

__version__ = "2.2.1"
DEFAULT_AI_PROVIDER = "auto"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-latest"
AI_PROVIDER_PRIORITY = ("gemini", "openai", "anthropic")
GEMINI_REQUESTS_PER_MINUTE = 15
MAX_AI_REQUEST_BYTES = 48_000
_GEMINI_REQUEST_TIMES: deque[float] = deque()

LOGO = r"""
▞▀▖   ▗    ▙▗▌▛▀▖
▌ ▌▌ ▌▄ ▀▜▘▌▘▌▌ ▌
▌▚▘▌ ▌▐ ▗▘ ▌ ▌▌ ▌
▝▘▘▝▀▘▀▘▀▀▘▘ ▘▀▀ 
"""

HELLO_QUIZ_TEMPLATE = """# Hello Quiz

## Question 1
What is 2 + 2?

- 3
- 4
- 5

Answer: 2
Type: single
Time: 20
Explanation: 2 + 2 equals 4.

## Question 2
Which are Python data types?

- list
- banana
- dict
- integer

Answer: 1,3,4
Type: multiple
Time: 25
Explanation: list, dict, and integer are valid Python data types.

## Question 3
What does this print?
```python
name = "Stelios"
print(name.upper())
```

- stelios
- STELIOS
- Name
- upper

Answer: 2
Type: single
Time: 25
Explanation: .upper() converts text to uppercase.
"""

HELLO_IMPOSTER_TEMPLATE = """# Hello Imposter Quiz

## Question 1
What happens when you do `arr = [1,2,3]; b = arr`?

- Both variables reference the same list in memory
- A new copy of the list is created for `b`
- Python prevents modification through `b`
- Only the first element is shared between them

Answer: 1
Imposters: 2
Type: single
Time: 30
Explanation: Assignment creates a reference, not a copy. Changes via `b` affect `arr`.

## Question 2
What does `arr * 3` do for a list?

- Repeats the list three times
- Converts all elements to strings
- Extends the list with three new empty elements
- Multiplies each element by 3

Answer: 1
Imposters: 4
Type: single
Time: 30
Explanation: `*` repeats the list, it does not apply multiplication to each element.

## Question 3
What does `arr.append([4,5])` do?

- Adds the list `[4,5]` as a single element
- Adds `4` and `5` as separate elements
- Replaces the last element with `[4,5]`
- Extends the list with `[4,5]`

Answer: 1
Imposters: 2,4
Type: single
Time: 30
Explanation: `append` adds one element, even if that element is a list. Using `extend` would add elements separately.
"""

HELLO_ESSAY_TEMPLATE = """# Essay Question: requirements basics

## Question
What is `requirements.txt` and why is it useful in Python projects?

## Instructions for Students
Write 5-10 lines.
Be clear and practical.

## Instructor Name
Stelios

## Hint
🤔 Hint: Think about dependencies, reproducibility, and collaboration.

## Evaluation Criteria (Total: 3 points)
1. **Dependency listing (1 point)**
- Mentions project packages are listed in one file
2. **Reproducibility (1 point)**
- Mentions same environment across machines
3. **Collaboration (1 point)**
- Mentions easier teamwork and avoids "works on my machine"

## Reference Answer
`requirements.txt` lists dependencies (often with pinned versions) so everyone can install the same environment and run the project consistently.

## AI Evaluation Rules
Evaluate only by the rubric above.
Do not use external knowledge.
Score = (points achieved / 3) x 100.

## Output Format
Score: XX%

Feedback:
- What the student did well
- What is missing
- 1-2 suggestions for improvement
"""

QUIZ_GUIDE_TEMPLATE = """# QuizMD Quick Start

## Run the MCQ starter

```bash
quizmd --validate hello-quiz.md
quizmd hello-quiz.md
```

## Run the imposter starter

```bash
quizmd --validate hello-imposter.md
quizmd hello-imposter.md
```

## Run the essay starter

```bash
quizmd --validate hello-essay.md
export GEMINI_API_KEY="your_key_here"  # or OPENAI_API_KEY / ANTHROPIC_API_KEY
quizmd hello-essay.md
```
"""

THEMES = {
    "dark": {
        "primary": "cyan",
        "secondary": "magenta",
        "accent": "yellow",
        "success": "green",
        "danger": "red",
        "panel": "cyan",
        "pt_primary": "ansicyan",
        "pt_title": "ansiwhite",
        "pt_timer": "ansiyellow",
        "pt_timer_warning": "ansimagenta",
        "pt_timer_danger": "ansired",
        "pt_instruction": "ansigray",
        "pt_selected_fg": "ansiwhite",
        "pt_selected_bg": "ansiblue",
        "pt_selected_fg_pulse": "ansiblue",
        "pt_selected_bg_pulse": "ansiwhite",
        "pt_marked_fg": "ansiwhite",
        "pt_marked_bg": "ansigreen",
        "pt_code": "ansiwhite",
        "pt_code_bg": "#1d2630",
    },
    "light": {
        "primary": "blue",
        "secondary": "magenta",
        "accent": "blue",
        "success": "green",
        "danger": "red",
        "panel": "blue",
        "pt_primary": "black",
        "pt_title": "black",
        "pt_code": "ansiblue",
        "pt_timer": "black",
        "pt_timer_warning": "ansired",
        "pt_timer_danger": "ansired",
        "pt_instruction": "black",
        "pt_selected_fg": "ansiwhite",
        "pt_selected_bg": "ansiblue",
        "pt_selected_fg_pulse": "ansiblue",
        "pt_selected_bg_pulse": "ansiwhite",
        "pt_marked_fg": "ansiwhite",
        "pt_marked_bg": "ansigreen",
        "pt_code_bg": "#eaf2ff",
    },
}


def _is_light_terminal() -> bool:
    colorfgbg = os.environ.get("COLORFGBG", "")
    if not colorfgbg:
        return False
    parts = colorfgbg.split(";")
    if len(parts) < 2:
        return False
    try:
        bg = int(parts[-1])
    except ValueError:
        return False
    return bg >= 7


def _theme_hint_from_env() -> str | None:
    """Best-effort theme detection from common terminal/editor environment hints."""
    candidates = [
        os.environ.get("TERMINAL_THEME", ""),
        os.environ.get("COLORSCHEME", ""),
        os.environ.get("ITERM_PROFILE", ""),
    ]
    joined = " ".join(candidates).strip().lower()
    if not joined:
        return None

    if any(token in joined for token in ("light", "day", "solarized light", "latte")):
        return "light"
    if any(token in joined for token in ("dark", "night", "solarized dark", "mocha")):
        return "dark"
    return None


def select_theme(name: str = "auto") -> dict:
    env_theme = os.environ.get("QUIZMD_THEME", "").strip().lower()
    if env_theme in THEMES:
        return THEMES[env_theme]

    if name == "dark":
        return THEMES["dark"]
    if name == "light":
        return THEMES["light"]
    env_hint = _theme_hint_from_env()
    if env_hint in THEMES:
        return THEMES[env_hint]
    return THEMES["light"] if _is_light_terminal() else THEMES["dark"]


def should_use_compact_layout(min_width: int = 100, columns: int | None = None) -> bool:
    if columns is None:
        columns = get_terminal_columns(default=min_width)
    return columns < min_width


def get_terminal_columns(default: int = 80) -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return default


def is_no_color_requested(cli_no_color: bool = False) -> bool:
    if cli_no_color:
        return True
    return bool(os.environ.get("NO_COLOR"))


def parse_int_list(raw_value: str, field_name: str, question_title: str, source: Path) -> list[int]:
    values = []

    for item in raw_value.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        try:
            values.append(int(stripped))
        except ValueError as exc:
            raise ValueError(
                f"{source}: invalid {field_name} value {stripped!r} in {question_title!r}"
            ) from exc

    if not values:
        raise ValueError(f"{source}: missing {field_name} values in {question_title!r}")

    return values


def parse_int_value(raw_value: str, field_name: str, question_title: str, source: Path) -> int:
    stripped = raw_value.strip()
    try:
        return int(stripped)
    except ValueError as exc:
        raise ValueError(
            f"{source}: invalid {field_name} value {stripped!r} in {question_title!r}"
        ) from exc


def validate_question(question: dict, source: Path) -> None:
    qtype = question["type"]
    correct = question["correct"]
    imposters = question.get("imposters", [])
    option_count = len(question["options"])

    if qtype not in {"single", "multiple"}:
        raise ValueError(
            f"{source}: unsupported question type {qtype!r} in {question['title']!r}"
        )

    if qtype == "single" and len(correct) != 1:
        raise ValueError(
            f"{source}: single-choice question {question['title']!r} must have exactly one answer"
        )

    seen = set()
    duplicates = set()
    for idx in correct:
        if idx in seen:
            duplicates.add(idx)
        seen.add(idx)
    duplicates = sorted(duplicates)
    if duplicates:
        raise ValueError(
            f"{source}: duplicate answer indexes {duplicates} in {question['title']!r}"
        )

    invalid_answers = [idx for idx in correct if idx < 1 or idx > option_count]
    if invalid_answers:
        raise ValueError(
            f"{source}: answer indexes {invalid_answers} are out of range in {question['title']!r}"
        )

    imposter_seen = set()
    imposter_duplicates = set()
    for idx in imposters:
        if idx in imposter_seen:
            imposter_duplicates.add(idx)
        imposter_seen.add(idx)
    imposter_duplicates = sorted(imposter_duplicates)
    if imposter_duplicates:
        raise ValueError(
            f"{source}: duplicate imposter indexes {imposter_duplicates} in {question['title']!r}"
        )

    invalid_imposters = [idx for idx in imposters if idx < 1 or idx > option_count]
    if invalid_imposters:
        raise ValueError(
            f"{source}: imposter indexes {invalid_imposters} are out of range in {question['title']!r}"
        )

    overlap = sorted(set(correct).intersection(imposters))
    if overlap:
        raise ValueError(
            f"{source}: imposter indexes {overlap} overlap with correct answers in {question['title']!r}"
        )

    time_limit = question["time_limit"]
    if time_limit is not None and time_limit <= 0:
        raise ValueError(
            f"{source}: time limit must be greater than zero in {question['title']!r}"
        )


def parse_quiz_markdown(path: str):
    source = Path(path)
    text = source.read_text(encoding="utf-8")

    blocks = re.split(r"(?m)^##\s+", text)
    preamble_lines = [line.strip() for line in blocks[0].splitlines() if line.strip()]

    quiz_title = "Quiz"
    if preamble_lines:
        if preamble_lines[0].startswith("# "):
            quiz_title = preamble_lines[0][2:].strip() or "Quiz"
            preamble_lines = preamble_lines[1:]
        if preamble_lines:
            raise ValueError(
                f"{source}: unexpected content outside question blocks. "
                "Use '##' headers for each question."
            )

    questions = []

    for block in blocks[1:]:
        block = block.strip()
        if not block:
            continue

        lines = block.splitlines()
        if len(lines) < 2:
            if lines and not lines[0].startswith("# "):
                raise ValueError(
                    f"{source}: malformed question block {lines[0]!r} is missing the question text line"
                )
            continue

        title = lines[0].strip()
        body_lines = lines[1:]

        question_lines = []
        metadata_lines = []
        in_code_fence = False
        found_metadata = False

        for raw_line in body_lines:
            stripped = raw_line.strip()
            if stripped.startswith("```"):
                in_code_fence = not in_code_fence

            is_metadata_or_option = (
                not in_code_fence
                and (
                    stripped.startswith("- ")
                    or re.match(r"(?i)^(answer|type|time|explanation|imposters)\s*:", stripped) is not None
                )
            )

            if found_metadata or is_metadata_or_option:
                found_metadata = True
                metadata_lines.append(raw_line)
            else:
                question_lines.append(raw_line)

        question = "\n".join(question_lines).strip()
        if not question:
            raise ValueError(
                f"{source}: malformed question block {title!r} is missing the question text line"
            )

        options = []
        answer = []
        qtype = None
        time_limit = None
        explanation = ""
        imposters = []

        for l in metadata_lines:
            stripped = l.strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                options.append(stripped[2:].strip())
                continue

            field_match = re.match(r"(?i)^(answer|type|time|explanation|imposters)\s*:\s*(.*)$", stripped)
            if field_match:
                key = field_match.group(1).lower()
                value = field_match.group(2)
                if key == "answer":
                    answer = parse_int_list(value, "answer", title, source)
                elif key == "type":
                    qtype = value.strip().lower()
                elif key == "time":
                    time_limit = parse_int_value(value, "time", title, source)
                elif key == "imposters":
                    imposters = parse_int_list(value, "imposters", title, source)
                else:
                    explanation = value.strip()
            else:
                raise ValueError(
                    f"{source}: unrecognized line {l!r} in question {title!r}. "
                    "Expected options ('- ...') or fields: Answer, Type, Time, Explanation, Imposters."
                )

        if not options or not answer or qtype is None:
            missing_parts = []
            if not options:
                missing_parts.append("options")
            if not answer:
                missing_parts.append("answer")
            if qtype is None:
                missing_parts.append("type")
            raise ValueError(
                f"{source}: question {title!r} is missing required field(s): {', '.join(missing_parts)}"
            )

        question_data = {
            "title": title,
            "question": question,
            "options": options,
            "correct": sorted(answer),
            "type": qtype,
            "time_limit": time_limit,
            "explanation": explanation,
            "imposters": sorted(imposters),
        }
        validate_question(question_data, source)
        questions.append(question_data)

    if not questions:
        raise ValueError(f"{source}: no valid questions found. Add at least one '##' question block.")

    return quiz_title, questions


def detect_quiz_mode(path: str) -> str:
    source = Path(path)
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# Essay Question:"):
            return "essay"
        if line.startswith("# "):
            return "mcq"
        break
    raise ValueError(
        f"{source}: expected a top-level '# ...' title or '# Essay Question: ...' header"
    )


def parse_essay_markdown(path: str) -> tuple[str, dict]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        raise ValueError(f"{source}: empty essay markdown file")

    first_nonempty = ""
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped:
            first_nonempty = stripped
            break
    if not first_nonempty.startswith("# Essay Question:"):
        raise ValueError(
            f"{source}: essay quiz must start with '# Essay Question: <title>'"
        )
    title = first_nonempty.split(":", 1)[1].strip()
    if not title:
        raise ValueError(f"{source}: essay title cannot be empty")

    sections: list[tuple[str, list[str]]] = []
    current_name = None
    current_lines: list[str] = []
    started_sections = False

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("# Essay Question:") and not started_sections:
            continue
        if stripped.startswith("## "):
            started_sections = True
            if current_name is not None:
                sections.append((current_name, current_lines))
            current_name = stripped[3:].strip()
            current_lines = []
            continue
        if current_name is None:
            if stripped:
                raise ValueError(
                    f"{source}: unexpected content before first section heading '## ...'"
                )
            continue
        current_lines.append(raw_line)

    if current_name is not None:
        sections.append((current_name, current_lines))

    if not sections:
        raise ValueError(
            f"{source}: missing essay sections. Expected '## Question', '## Instructions for Students', "
            "'## Evaluation Criteria (Total: N points)', '## Reference Answer', "
            "'## AI Evaluation Rules', and '## Output Format'."
        )

    expected_names = {
        "Question",
        "Instructions for Students",
        "Reference Answer",
        "AI Evaluation Rules",
        "Output Format",
    }

    section_map: dict[str, str] = {}
    criteria_section_name = None
    for section_name, section_lines in sections:
        content = "\n".join(section_lines).strip()
        if section_name.lower().startswith("evaluation criteria"):
            if criteria_section_name is not None:
                raise ValueError(f"{source}: duplicate 'Evaluation Criteria' section")
            criteria_section_name = section_name
            section_map["Evaluation Criteria"] = content
        else:
            if section_name in section_map:
                raise ValueError(f"{source}: duplicate section {section_name!r}")
            section_map[section_name] = content

    missing = sorted(name for name in expected_names if name not in section_map)
    if criteria_section_name is None:
        missing.append("Evaluation Criteria (Total: N points)")
    if missing:
        raise ValueError(f"{source}: missing required section(s): {', '.join(missing)}")

    criteria_header_match = re.match(
        r"^Evaluation Criteria \(Total:\s*(\d+)\s*points?\)$",
        criteria_section_name or "",
        flags=re.IGNORECASE,
    )
    if not criteria_header_match:
        raise ValueError(
            f"{source}: evaluation criteria header must be exactly "
            "'## Evaluation Criteria (Total: N points)'"
        )
    total_points = int(criteria_header_match.group(1))
    if total_points <= 0:
        raise ValueError(f"{source}: evaluation criteria total points must be greater than zero")

    criteria_content = section_map["Evaluation Criteria"]
    if not criteria_content:
        raise ValueError(f"{source}: Evaluation Criteria section cannot be empty")

    criteria = []
    current = None
    for raw_line in criteria_content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        item_match = re.match(r"^\d+\.\s+\*\*(.+?)\s+\((\d+)\s*points?\)\*\*$", stripped, flags=re.IGNORECASE)
        if item_match:
            if current is not None:
                criteria.append(current)
            current = {
                "name": item_match.group(1).strip(),
                "points": int(item_match.group(2)),
                "details": [],
            }
            continue

        if stripped.startswith("- "):
            if current is None:
                raise ValueError(
                    f"{source}: criteria bullet {stripped!r} must be under a numbered criterion"
                )
            current["details"].append(stripped[2:].strip())
            continue

        raise ValueError(
            f"{source}: invalid line in Evaluation Criteria: {raw_line!r}. "
            "Use numbered criteria with bold labels and optional '-' bullets."
        )

    if current is not None:
        criteria.append(current)

    if not criteria:
        raise ValueError(f"{source}: no valid criteria found in Evaluation Criteria section")

    awarded_total = sum(item["points"] for item in criteria)
    if awarded_total != total_points:
        raise ValueError(
            f"{source}: criteria points sum to {awarded_total}, but header total is {total_points}"
        )

    for section_name in ("Question", "Instructions for Students", "Reference Answer", "AI Evaluation Rules", "Output Format"):
        if not section_map.get(section_name, "").strip():
            raise ValueError(f"{source}: section {section_name!r} cannot be empty")

    payload = {
        "mode": "essay",
        "title": title,
        "instructor_name": section_map.get("Instructor Name", "").strip(),
        "hint": section_map.get("Hint", "").strip(),
        "question": section_map["Question"],
        "instructions": section_map["Instructions for Students"],
        "criteria": criteria,
        "total_points": total_points,
        "reference_answer": section_map["Reference Answer"],
        "ai_evaluation_rules": section_map["AI Evaluation Rules"],
        "output_format": section_map["Output Format"],
        "source": str(source),
    }
    return title, payload


def render_inline_markdown_for_prompt_toolkit(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<style fg='ansiyellow'>\1</style>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", escaped)
    return escaped


def parse_question_lines(question_text: str) -> list[tuple[str, bool]]:
    lines: list[tuple[str, bool]] = []
    in_code_fence = False
    for raw_line in question_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        lines.append((raw_line, in_code_fence))
    return lines or [("", False)]


def strip_prompt_toolkit_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def display_width(text: str) -> int:
    if _wcwidth_wcswidth is not None:
        width = _wcwidth_wcswidth(text)
        if width >= 0:
            return width

    # Fallback when wcwidth is unavailable or returns unknown width.
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in {"W", "F"} else 1
    return width


def truncate_for_display(text: str, max_width: int) -> str:
    if max_width <= 0:
        return ""
    if display_width(text) <= max_width:
        return text
    ellipsis = "…"
    allowed = max(1, max_width - display_width(ellipsis))
    out = ""
    for ch in text:
        if display_width(out + ch) > allowed:
            break
        out += ch
    return out + ellipsis


def wrap_and_truncate_text(text: str, max_width: int, max_lines: int = 2) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return [""]
    if max_width <= 0:
        return [""]

    words = cleaned.split(" ")
    lines: list[str] = []
    i = 0

    while i < len(words) and len(lines) < max_lines:
        current = words[i]
        i += 1
        if display_width(current) > max_width:
            current = truncate_for_display(current, max_width)
            lines.append(current)
            continue

        while i < len(words):
            candidate = f"{current} {words[i]}"
            if display_width(candidate) > max_width:
                break
            current = candidate
            i += 1
        lines.append(current)

    if i < len(words):
        last = lines[-1] if lines else ""
        lines[-1] = truncate_for_display(last, max(1, max_width - 1))
        if not lines[-1].endswith("…"):
            lines[-1] = truncate_for_display(lines[-1] + " …", max_width)

    return lines


def slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "quiz"


def next_attempt_dir(quiz_title: str) -> Path:
    answers_root = Path("answers")
    answers_root.mkdir(parents=True, exist_ok=True)

    base = slugify(quiz_title)
    attempt = 1

    while True:
        candidate = answers_root / f"{base}-{attempt}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        attempt += 1


def ask_to_save_answers() -> bool:
    return ask_yes_no("Save your answer locally on this device? (contains your text) [y/n]: ")


def ask_yes_no(prompt: str) -> bool:
    while True:
        choice = prompt_input(prompt).strip().lower()
        if choice in {"y", "yes"}:
            return True
        if choice in {"n", "no"}:
            return False


def init_starter_files(target_dir: str = ".", force: bool = False) -> list[Path]:
    base = Path(target_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    files_to_create = [
        ("hello-quiz.md", HELLO_QUIZ_TEMPLATE),
        ("hello-imposter.md", HELLO_IMPOSTER_TEMPLATE),
        ("hello-essay.md", HELLO_ESSAY_TEMPLATE),
        ("QUIZ_GUIDE.md", QUIZ_GUIDE_TEMPLATE),
    ]

    existing = [str(base / name) for name, _ in files_to_create if (base / name).exists()]
    if existing and not force:
        raise RuntimeError(
            "Refusing to overwrite existing file(s). Re-run with --force.\n"
            + "\n".join(existing)
        )

    created: list[Path] = []
    for name, content in files_to_create:
        out = base / name
        out.write_text(content, encoding="utf-8")
        created.append(out)
    return created


def prompt_input(prompt: str = "") -> str:
    try:
        return input(prompt)
    except EOFError as exc:
        raise RuntimeError("Interactive input is not available in this environment.") from exc


def save_attempt(
    quiz_title: str,
    score: int,
    questions: list[dict],
    answers: list[dict],
    total_score_possible: int | None = None,
) -> Path:
    attempt_dir = next_attempt_dir(quiz_title)
    if total_score_possible is None:
        total_score_possible = len(questions)

    payload = {
        "quiz_title": quiz_title,
        "score": score,
        "score_total": total_score_possible,
        "total_questions": len(questions),
        "answers": answers,
    }

    (attempt_dir / "answers.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    lines = [
        f"Quiz: {quiz_title}",
        f"Score: {score}/{total_score_possible}",
        "",
    ]

    for item in answers:
        imposter_selected = item.get("selected_imposter_labels", "")
        imposter_expected = item.get("expected_imposter_labels", "")
        lines.extend([
            item["question_title"],
            item["question_text"],
            f"Selected: {item['selected_labels'] or 'No answer'}",
            f"Correct: {item['correct_labels']}",
            f"Imposters flagged: {imposter_selected or '-'}",
            f"Expected imposters: {imposter_expected or '-'}",
            f"Result: {'Correct' if item['is_correct'] else 'Wrong'}",
            f"Explanation: {item['explanation'] or '-'}",
            "",
        ])

    (attempt_dir / "answers.txt").write_text("\n".join(lines), encoding="utf-8")
    return attempt_dir


def save_essay_attempt(quiz_title: str, payload: dict) -> Path:
    attempt_dir = next_attempt_dir(quiz_title)
    stored_payload = dict(payload)
    stored_payload["ai_error"] = _redacted_ai_error(
        str(stored_payload.get("ai_reason", "unknown_error")),
        bool(stored_payload.get("ai_unavailable", False)),
    )
    (attempt_dir / "answers.json").write_text(
        json.dumps(stored_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        f"Quiz: {quiz_title}",
        "",
        "Essay Question:",
        payload.get("question", ""),
        "",
        "Student Answer:",
        payload.get("student_answer", ""),
        "",
    ]

    score_percent = payload.get("score_percent")
    if score_percent is None:
        lines.append("Score: N/A (AI unavailable)")
    else:
        lines.append(f"Score: {score_percent:.2f}%")
    lines.append("")
    lines.append("Feedback:")
    for item in payload.get("did_well", []):
        lines.append(f"- Did well: {item}")
    for item in payload.get("missing", []):
        lines.append(f"- Missing: {item}")
    for item in payload.get("suggestions", []):
        lines.append(f"- Suggestion: {item}")

    (attempt_dir / "answers.txt").write_text("\n".join(lines), encoding="utf-8")
    return attempt_dir


def _wait_for_gemini_window(limit_per_minute: int = GEMINI_REQUESTS_PER_MINUTE) -> None:
    now = time.time()
    while _GEMINI_REQUEST_TIMES and (now - _GEMINI_REQUEST_TIMES[0]) >= 60:
        _GEMINI_REQUEST_TIMES.popleft()
    if len(_GEMINI_REQUEST_TIMES) < limit_per_minute:
        return
    wait_seconds = 60 - (now - _GEMINI_REQUEST_TIMES[0])
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def _extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model response did not contain valid JSON")
        return json.loads(stripped[start : end + 1])


def _coerce_text_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items
    return [str(value).strip()] if str(value).strip() else []


def _normalize_model_grade(raw_grade, expected_total_points: int, provider_name: str = "model") -> dict:
    if isinstance(raw_grade, list):
        if len(raw_grade) == 1 and isinstance(raw_grade[0], dict):
            raw_grade = raw_grade[0]
        else:
            raise ValueError(f"{provider_name} JSON returned a list instead of a single object")
    if not isinstance(raw_grade, dict):
        raise ValueError(f"{provider_name} JSON must be an object")

    required_keys = {
        "points_awarded",
        "total_points",
        "score_percent",
        "did_well",
        "missing",
        "suggestions",
    }
    missing_keys = sorted(required_keys - set(raw_grade.keys()))
    if missing_keys:
        raise ValueError(f"{provider_name} JSON missing key(s): {', '.join(missing_keys)}")

    try:
        graded_total = int(raw_grade["total_points"])
        points_awarded = float(raw_grade["points_awarded"])
        score_percent = float(raw_grade["score_percent"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{provider_name} JSON has invalid numeric values") from exc

    if graded_total != expected_total_points:
        raise ValueError(
            f"{provider_name} JSON total_points={graded_total} does not match rubric total={expected_total_points}"
        )
    if points_awarded < 0 or points_awarded > graded_total:
        raise ValueError(f"{provider_name} JSON points_awarded is out of valid range")

    expected_percent = (points_awarded / graded_total) * 100 if graded_total else 0.0
    if abs(expected_percent - score_percent) > 0.5:
        score_percent = expected_percent

    did_well = _coerce_text_list(raw_grade.get("did_well"))[:5]
    missing = _coerce_text_list(raw_grade.get("missing"))[:5]
    suggestions = _coerce_text_list(raw_grade.get("suggestions"))[:3]
    if not suggestions:
        suggestions = ["Strengthen your answer by explicitly covering each rubric criterion."]

    return {
        "points_awarded": points_awarded,
        "total_points": graded_total,
        "score_percent": score_percent,
        "did_well": did_well,
        "missing": missing,
        "suggestions": suggestions,
        "ai_unavailable": False,
        "ai_error": "",
        "ai_reason": "none",
        "scoring_mode": "llm_rubric",
        "scoring_confidence": "high",
    }


def _normalize_gemini_grade(raw_grade, expected_total_points: int) -> dict:
    return _normalize_model_grade(raw_grade, expected_total_points, provider_name="Gemini")


def _build_essay_eval_prompt(essay: dict, student_answer: str) -> str:
    rubric_text = "\n".join(_rubric_lines(essay["criteria"]))
    return (
        "You are grading one student answer using ONLY the supplied rubric and rules.\n"
        "Do not use external knowledge.\n\n"
        f"Question:\n{essay['question']}\n\n"
        f"Student Answer:\n{student_answer}\n\n"
        f"Evaluation Criteria (Total {essay['total_points']} points):\n{rubric_text}\n\n"
        f"Reference Answer:\n{essay['reference_answer']}\n\n"
        f"AI Evaluation Rules:\n{essay['ai_evaluation_rules']}\n\n"
        "Return strict JSON with keys:\n"
        "points_awarded (number), total_points (number), score_percent (number), "
        "did_well (array of strings), missing (array of strings), suggestions (array of strings).\n"
        "Ensure total_points matches the rubric total."
    )


def _classify_provider_error(exc: Exception) -> tuple[bool, str]:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        retryable = code == 429 or 500 <= code < 600
        if code == 429:
            return retryable, "rate_limit"
        if code == 401:
            return retryable, "unauthorized"
        if code == 403:
            return retryable, "forbidden"
        if code == 404:
            return retryable, "not_found"
        if 500 <= code < 600:
            return retryable, "server_error"
        return retryable, "http_error"

    retryable = isinstance(exc, (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError))
    if isinstance(exc, TimeoutError):
        return retryable, "timeout"
    if isinstance(exc, urllib.error.URLError):
        return retryable, "network_error"
    if isinstance(exc, (ValueError, json.JSONDecodeError)):
        return retryable, "invalid_response"
    return retryable, "unknown_error"


def _rubric_lines(criteria: list[dict]) -> list[str]:
    lines = []
    for idx, item in enumerate(criteria, start=1):
        lines.append(f"{idx}. {item['name']} ({item['points']} points)")
        for detail in item.get("details", []):
            lines.append(f"- {detail}")
    return lines


def _rubric_markdown(criteria: list[dict]) -> str:
    lines = []
    for idx, item in enumerate(criteria, start=1):
        lines.append(f"{idx}. **{item['name']} ({item['points']} points)**")
        for detail in item.get("details", []):
            lines.append(f"   - {detail}")
    return "\n".join(lines)


def evaluate_essay_with_gemini(
    essay: dict,
    student_answer: str,
    api_key: str,
    model: str,
    timeout: int,
    max_retries: int = 3,
) -> dict:
    prompt = _build_essay_eval_prompt(essay, student_answer)

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        },
    }
    body = json.dumps(payload).encode("utf-8")
    if len(body) > MAX_AI_REQUEST_BYTES:
        raise RuntimeError(
            "[payload_too_large] Essay content is too large for AI grading. "
            "Shorten the question/reference answer or reduce student answer length and retry."
        )
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    last_error = None
    reason_code = "unknown_error"
    for attempt in range(max_retries + 1):
        _wait_for_gemini_window()
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-goog-api-key": api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                _GEMINI_REQUEST_TIMES.append(time.time())
                response_payload = json.loads(response.read().decode("utf-8"))
                candidates = response_payload.get("candidates", [])
                if not candidates:
                    raise ValueError("Gemini response missing candidates")
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
                if not text.strip():
                    raise ValueError("Gemini response did not contain text output")
                graded = _extract_json_object(text)
                return _normalize_model_grade(graded, int(essay["total_points"]), provider_name="Gemini")
        except Exception as exc:  # network/parser/HTTP handling
            if isinstance(exc, KeyboardInterrupt):
                raise
            last_error = exc
            retryable, reason_code = _classify_provider_error(exc)

        if attempt >= max_retries or not retryable:
            break
        sleep_seconds = (2 ** attempt) + random.uniform(0.1, 0.35)
        time.sleep(sleep_seconds)

    raise RuntimeError(f"[{reason_code}] Gemini evaluation failed after retries: {last_error}")


def evaluate_essay_with_openai(
    essay: dict,
    student_answer: str,
    api_key: str,
    model: str,
    timeout: int,
    max_retries: int = 3,
) -> dict:
    prompt = _build_essay_eval_prompt(essay, student_answer)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Return valid JSON only. Follow the rubric exactly.",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    body = json.dumps(payload).encode("utf-8")
    if len(body) > MAX_AI_REQUEST_BYTES:
        raise RuntimeError(
            "[payload_too_large] Essay content is too large for AI grading. "
            "Shorten the question/reference answer or reduce student answer length and retry."
        )

    endpoint = "https://api.openai.com/v1/chat/completions"
    last_error = None
    reason_code = "unknown_error"
    for attempt in range(max_retries + 1):
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
                choices = response_payload.get("choices", [])
                if not choices:
                    raise ValueError("OpenAI response missing choices")
                message = choices[0].get("message", {})
                text = message.get("content", "")
                if isinstance(text, list):
                    text = "".join(item.get("text", "") for item in text if isinstance(item, dict))
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("OpenAI response did not contain text output")
                graded = _extract_json_object(text)
                return _normalize_model_grade(graded, int(essay["total_points"]), provider_name="OpenAI")
        except Exception as exc:  # network/parser/HTTP handling
            if isinstance(exc, KeyboardInterrupt):
                raise
            last_error = exc
            retryable, reason_code = _classify_provider_error(exc)

        if attempt >= max_retries or not retryable:
            break
        sleep_seconds = (2 ** attempt) + random.uniform(0.1, 0.35)
        time.sleep(sleep_seconds)

    raise RuntimeError(f"[{reason_code}] OpenAI evaluation failed after retries: {last_error}")


def evaluate_essay_with_anthropic(
    essay: dict,
    student_answer: str,
    api_key: str,
    model: str,
    timeout: int,
    max_retries: int = 3,
) -> dict:
    prompt = _build_essay_eval_prompt(essay, student_answer)
    payload = {
        "model": model,
        "max_tokens": 1000,
        "temperature": 0,
        "system": "Return valid JSON only. Follow the rubric exactly.",
        "messages": [{"role": "user", "content": prompt}],
    }
    body = json.dumps(payload).encode("utf-8")
    if len(body) > MAX_AI_REQUEST_BYTES:
        raise RuntimeError(
            "[payload_too_large] Essay content is too large for AI grading. "
            "Shorten the question/reference answer or reduce student answer length and retry."
        )

    endpoint = "https://api.anthropic.com/v1/messages"
    last_error = None
    reason_code = "unknown_error"
    for attempt in range(max_retries + 1):
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
                blocks = response_payload.get("content", [])
                if not isinstance(blocks, list) or not blocks:
                    raise ValueError("Anthropic response missing content")
                text = "".join(
                    block.get("text", "")
                    for block in blocks
                    if isinstance(block, dict) and block.get("type") == "text"
                )
                if not text.strip():
                    raise ValueError("Anthropic response did not contain text output")
                graded = _extract_json_object(text)
                return _normalize_model_grade(graded, int(essay["total_points"]), provider_name="Anthropic")
        except Exception as exc:  # network/parser/HTTP handling
            if isinstance(exc, KeyboardInterrupt):
                raise
            last_error = exc
            retryable, reason_code = _classify_provider_error(exc)

        if attempt >= max_retries or not retryable:
            break
        sleep_seconds = (2 ** attempt) + random.uniform(0.1, 0.35)
        time.sleep(sleep_seconds)

    raise RuntimeError(f"[{reason_code}] Anthropic evaluation failed after retries: {last_error}")


def evaluate_essay_deterministic_fallback(
    essay: dict,
    student_answer: str,
    error_message: str,
    reason_code: str = "unknown_error",
) -> dict:
    normalized_answer = re.sub(r"\s+", " ", student_answer.lower()).strip()
    did_well = []
    missing = []
    points_awarded = 0

    for criterion in essay["criteria"]:
        detail_tokens = []
        for detail in criterion.get("details", []):
            detail_tokens.extend(re.findall(r"[a-zA-Z]{4,}", detail.lower()))
        detail_tokens = [token for token in detail_tokens if token not in {"with", "that", "this", "from", "they", "them"}]

        matched = False
        if detail_tokens:
            unique_tokens = sorted(set(detail_tokens))
            hits = sum(1 for token in unique_tokens if token in normalized_answer)
            matched = hits >= max(1, len(unique_tokens) // 3)
        else:
            name_tokens = re.findall(r"[a-zA-Z]{4,}", criterion["name"].lower())
            matched = any(token in normalized_answer for token in name_tokens)

        if matched:
            points_awarded += criterion["points"]
            did_well.append(f"Covered: {criterion['name']}")
        else:
            missing.append(f"Missing: {criterion['name']}")

    total_points = essay["total_points"]
    suggestions = []
    if missing:
        suggestions.append("Address each missing criterion explicitly in separate sentences.")
        suggestions.append("Use concrete wording about why requirements.txt improves reproducibility and collaboration.")
    else:
        suggestions.append("Great coverage. Improve by adding one concise real-world example.")

    return {
        "points_awarded": None,
        "total_points": total_points,
        "score_percent": None,
        "did_well": did_well[:5],
        "missing": missing[:5],
        "suggestions": suggestions[:2],
        "ai_unavailable": True,
        "ai_error": error_message,
        "ai_reason": reason_code,
        "scoring_mode": "heuristic_fallback",
        "scoring_confidence": "low",
    }


def _format_possessive(name: str) -> str:
    text = name.strip()
    if not text:
        return ""
    if text.lower().endswith("s"):
        return f"{text}'"
    return f"{text}'s"


def _is_windows() -> bool:
    return os.name == "nt"


def _score_encouragement(score_percent: float | None) -> str:
    if score_percent is None:
        return ""
    if score_percent < 50:
        return "Don’t worry — try again! 💪"
    if score_percent <= 75:
        return "Great effort! With a bit more practice, you’ll be a star. ⭐"
    return "You’re rocking it! 🚀"


def _redacted_ai_error(reason_code: str, ai_unavailable: bool) -> str:
    if not ai_unavailable:
        return ""
    return f"AI unavailable ({reason_code or 'unknown_error'}). Detailed provider error omitted for privacy."


def _default_model_for_provider(ai_provider: str) -> str:
    if ai_provider == "gemini":
        return DEFAULT_GEMINI_MODEL
    if ai_provider == "openai":
        return DEFAULT_OPENAI_MODEL
    if ai_provider == "anthropic":
        return DEFAULT_ANTHROPIC_MODEL
    raise RuntimeError(f"Unsupported AI provider {ai_provider!r}.")


def _evaluator_for_provider(ai_provider: str):
    if ai_provider == "gemini":
        return evaluate_essay_with_gemini
    if ai_provider == "openai":
        return evaluate_essay_with_openai
    if ai_provider == "anthropic":
        return evaluate_essay_with_anthropic
    raise RuntimeError(f"Unsupported AI provider {ai_provider!r}.")


def _env_key_for_provider(ai_provider: str) -> str:
    if ai_provider == "gemini":
        return "GEMINI_API_KEY"
    if ai_provider == "openai":
        return "OPENAI_API_KEY"
    if ai_provider == "anthropic":
        return "ANTHROPIC_API_KEY"
    raise RuntimeError(f"Unsupported AI provider {ai_provider!r}.")


def _provider_display_name(ai_provider: str) -> str:
    if ai_provider == "gemini":
        return "Gemini"
    if ai_provider == "openai":
        return "OpenAI"
    if ai_provider == "anthropic":
        return "Claude"
    return ai_provider


def _platform_setup_hint_for_env_key(env_key: str) -> str:
    if _is_windows():
        return (
            "Windows (PowerShell):\n"
            f"$env:{env_key}='your_key_here'"
        )
    if os.name == "posix":
        return (
            "macOS/Linux:\n"
            f"export {env_key}='your_key_here'"
        )
    return (
        "macOS/Linux:\n"
        f"export {env_key}='your_key_here'\n"
        "Windows (PowerShell):\n"
        f"$env:{env_key}='your_key_here'"
    )


def _platform_setup_hint_for_any_ai_key() -> str:
    key_names = ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    if _is_windows():
        return "\n".join(f"$env:{key}='your_key_here'" for key in key_names)
    if os.name == "posix":
        return "\n".join(f"export {key}='your_key_here'" for key in key_names)
    mac_linux = "\n".join(f"export {key}='your_key_here'" for key in key_names)
    windows = "\n".join(f"$env:{key}='your_key_here'" for key in key_names)
    return f"macOS/Linux:\n{mac_linux}\nWindows (PowerShell):\n{windows}"


def _resolve_ai_provider(ai_provider: str) -> str:
    if ai_provider != "auto":
        return ai_provider
    for provider in AI_PROVIDER_PRIORITY:
        env_key = _env_key_for_provider(provider)
        if os.environ.get(env_key, "").strip():
            return provider
    return "auto"


def _available_ai_providers_by_priority() -> list[str]:
    providers = []
    for provider in AI_PROVIDER_PRIORITY:
        env_key = _env_key_for_provider(provider)
        if os.environ.get(env_key, "").strip():
            providers.append(provider)
    return providers


def collect_essay_answer_via_editor(question_title: str, question_text: str = "") -> str:
    editor = (os.environ.get("EDITOR") or "").strip()
    if not editor:
        if _is_windows():
            if ask_yes_no("No EDITOR is configured. Open Notepad now? [y/n]: "):
                editor = "notepad"
            else:
                raise RuntimeError(
                    "No editor configured on Windows. Set EDITOR or choose Notepad when prompted."
                )
        else:
            editor = "vi"

    header_line = question_text.strip() or question_title
    template = (
        f"# {header_line}\n\n"
        "# When ready: Press Esc, type :wq!, then Enter to save and exit (or :q! to quit without saving).\n"
        "# Write your answer below. Keep 5-10 lines.\n"
        "# Lines starting with '#' will be ignored.\n\n"
    )

    with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False, encoding="utf-8") as handle:
        temp_path = Path(handle.name)
        handle.write(template)
        handle.flush()

    try:
        command = shlex.split(editor) + [str(temp_path)]
        try:
            if _is_windows() and editor.lower() == "notepad":
                print("When ready, save and close Notepad, then return to this terminal.")
            subprocess.run(command, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            if _is_windows() and editor.lower() != "notepad":
                if ask_yes_no(f"Could not open '{editor}'. Open Notepad instead? [y/n]: "):
                    print("When ready, save and close Notepad, then return to this terminal.")
                    subprocess.run(["notepad", str(temp_path)], check=True)
                else:
                    raise RuntimeError(
                        f"Could not launch editor '{editor}'. Set EDITOR to a valid command."
                    ) from exc
            else:
                raise RuntimeError(
                    f"Could not launch editor '{editor}'. Set EDITOR to a valid command."
                ) from exc
        content = temp_path.read_text(encoding="utf-8")
        cleaned_lines = [line for line in content.splitlines() if not line.strip().startswith("#")]
        answer = "\n".join(cleaned_lines).strip()
        if not answer:
            raise RuntimeError("No essay answer was provided. Please write your answer in the editor.")
        return answer
    finally:
        temp_path.unlink(missing_ok=True)


def evaluate_essay_with_loading(console, theme: dict, evaluator, *args, **kwargs):
    try:
        from rich.progress import BarColumn
        from rich.progress import Progress
        from rich.progress import SpinnerColumn
        from rich.progress import TextColumn
        from rich.progress import TimeElapsedColumn
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Running the quiz requires rich. Install dependencies from requirements.txt."
        ) from exc

    import threading

    instructor_name = str(kwargs.pop("instructor_name", "")).strip()
    result: dict = {}

    def worker():
        try:
            result["value"] = evaluator(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - bubble up after animation stops
            result["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    if instructor_name:
        message = f"Reviewing your answer using {instructor_name}'s rubric and guidance..."
    else:
        message = "Reviewing your answer using the rubric and guidance..."

    text = f"[{theme['accent']}]{message}[/]" if not console.no_color else message
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(bar_width=24),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(text, total=None)
        while thread.is_alive():
            progress.update(task)
            time.sleep(0.1)

    thread.join()
    if "error" in result:
        raise result["error"]
    return result["value"]


def build_question_markup(
    q: dict,
    theme: dict,
    selected: int,
    marked: set[int],
    remaining: int | None,
    imposter_marked: set[int] | None = None,
    is_multiple: bool = False,
    imposter_mode: bool = False,
    question_index: int = 1,
    total_questions: int = 1,
    pulse: bool = False,
    timer_blink: bool = False,
    no_color: bool = False,
    compact: bool = False,
    terminal_width: int | None = None,
) -> str:
    if imposter_marked is None:
        imposter_marked = set()

    ultra_compact = bool(terminal_width is not None and terminal_width < 70)
    ascii_compact = compact and (_is_windows() or ultra_compact)
    separator = " | " if ascii_compact else " • "
    if imposter_mode:
        instruction = (
            "Sp/X/En"
            if ultra_compact
            else "Space/X/Enter"
        )
    else:
        instruction = (
            "Sp/En"
            if ultra_compact
            else ("Space select | Enter" if ascii_compact else "Space select • Enter")
        )
    mode_badge = "[I]" if (imposter_mode and ultra_compact) else ("[IMPOSTER]" if imposter_mode else "")
    question_type_badge = (
        "[M]" if (is_multiple and ultra_compact) else
        "[S]" if ((not is_multiple) and ultra_compact) else
        "[MULTI]" if (is_multiple and ascii_compact) else
        "[SINGLE]" if (not is_multiple and ascii_compact) else
        "[MULTI ☑]" if is_multiple else "[SINGLE ○]"
    )
    progress_units = 6 if ultra_compact else 10
    progress_fraction = question_index / total_questions if total_questions else 1
    filled_units = max(0, min(progress_units, int(round(progress_fraction * progress_units))))
    progress_bar = "█" * filled_units + "░" * (progress_units - filled_units)

    timer_color = theme["pt_timer"]
    timer_prefix = "TIME" if ascii_compact else "⏱"
    if remaining is not None:
        if remaining < 5:
            timer_color = theme["pt_timer_danger"]
            timer_prefix = "WARN" if ascii_compact else "😱"
        elif remaining <= 10:
            timer_color = theme["pt_timer_warning"]
            timer_prefix = "WARN" if ascii_compact else "😱"

    parsed_question_lines = parse_question_lines(q["question"])
    rendered_question_lines: list[tuple[str, bool]] = []
    for raw_line, is_code in parsed_question_lines:
        if is_code:
            rendered = html.escape(raw_line.rstrip())
            rendered_question_lines.append((rendered, True))
        else:
            rendered_question_lines.append((render_inline_markdown_for_prompt_toolkit(raw_line), False))

    code_side_margin = 2
    if no_color:
        timer_text = ""
        if remaining is not None:
            timer_text = f"{timer_prefix} {remaining}s"
        header = (
            f"{'Q' if ultra_compact else 'Question'} {question_index}/{total_questions} {progress_bar}"
            + (f"  {timer_text}" if timer_text else "")
            + (f"{separator}{mode_badge}" if mode_badge else "")
            + f"{separator}{question_type_badge}{separator}{instruction}"
        )
        lines = [header, ""]

        for line, is_code in rendered_question_lines:
            plain_line = strip_prompt_toolkit_tags(line)
            if is_code:
                lines.append(f"  {plain_line}")
            else:
                lines.append(plain_line)

        lines.extend(["", ""])
    else:
        timer_part = ""
        if remaining is not None:
            timer_value = f"{timer_prefix} {remaining}s"
            timer_part = f"  <style fg='{timer_color}'>{timer_value}</style>"

        header = (
            f"<style fg='{theme['pt_instruction']}'><b>{'Q' if ultra_compact else 'Question'} {question_index}/{total_questions}</b> {progress_bar}</style>"
            + timer_part
            + f" <style fg='{theme['pt_instruction']}'>{html.escape((separator + mode_badge) if mode_badge else '')}{html.escape(separator + question_type_badge + separator + instruction)}</style>"
        )
        lines = [header, ""]

        for line, is_code in rendered_question_lines:
            if is_code:
                code_style = f"fg='{theme.get('pt_code', theme['pt_primary'])}' bg='{theme['pt_code_bg']}'"
                lines.append(f"<style {code_style}>  {line}</style>")
            else:
                lines.append(line)

        lines.extend(["", ""])

    for i, opt in enumerate(q["options"]):
        idx = i + 1
        pointer = "&gt;" if i == selected else " "
        if is_multiple:
            if no_color or ascii_compact:
                marker = "[x]" if idx in marked else "[ ]"
            else:
                marker = "☑" if idx in marked else "☐"
        else:
            if no_color or ascii_compact:
                marker = "(*)" if idx in marked else "( )"
            else:
                marker = "◉" if idx in marked else "○"
        if imposter_mode:
            imposter_marker = ("[x]" if idx in imposter_marked else "[ ]") if (no_color or ascii_compact) else ("✖" if idx in imposter_marked else "·")
        else:
            imposter_marker = ""

        if idx in marked:
            style = f"fg='{theme['pt_marked_fg']}' bg='{theme['pt_marked_bg']}'"
        elif i == selected:
            if pulse:
                style = (
                    f"fg='{theme.get('pt_selected_fg_pulse', theme['pt_selected_fg'])}' "
                    f"bg='{theme.get('pt_selected_bg_pulse', theme['pt_selected_bg'])}'"
                )
            else:
                style = f"fg='{theme['pt_selected_fg']}' bg='{theme['pt_selected_bg']}'"
        else:
            style = f"fg='{theme['pt_primary']}'"

        if ultra_compact:
            option_plain = strip_prompt_toolkit_tags(render_inline_markdown_for_prompt_toolkit(opt))
            prefix_plain = f"{'>' if i == selected else ' '} {idx}. {marker}{(' ' + imposter_marker) if imposter_mode else ''} "
            continuation_prefix_plain = " " * len(prefix_plain)
            max_option_width = max(18, (terminal_width or 70) - len(prefix_plain) - 1)
            wrapped_lines = wrap_and_truncate_text(option_plain, max_option_width, max_lines=2)

            if no_color:
                lines.append(prefix_plain + wrapped_lines[0])
                for extra in wrapped_lines[1:]:
                    lines.append(continuation_prefix_plain + extra)
            else:
                first = f"<style {style}>{html.escape(prefix_plain + wrapped_lines[0])}</style>"
                lines.append(first)
                for extra in wrapped_lines[1:]:
                    lines.append(f"<style {style}>{html.escape(continuation_prefix_plain + extra)}</style>")
            continue

        lines.append(
            (
                f"{'>' if i == selected else ' '} {idx}. {marker}{(' ' + imposter_marker) if imposter_mode else ''} "
                f"{strip_prompt_toolkit_tags(render_inline_markdown_for_prompt_toolkit(opt))}"
            )
            if no_color
            else f"<style {style}>{pointer} {idx}. {html.escape(marker)}{(' ' + html.escape(imposter_marker)) if imposter_mode else ''} {render_inline_markdown_for_prompt_toolkit(opt)}</style>"
        )

    lines.append("")
    lines.append("")

    return "\n".join(lines)


async def ask_question(
    q,
    theme,
    question_index: int = 1,
    total_questions: int = 1,
    no_color: bool = False,
    compact: bool = False,
    full_screen: bool = False,
):
    try:
        from prompt_toolkit import Application
        from prompt_toolkit.formatted_text import HTML as PromptHTML
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Interactive quiz mode requires prompt_toolkit. Install dependencies from requirements.txt."
        ) from exc

    selected = 0
    marked = set()
    imposter_marked = set()
    pulse = False
    remaining = q["time_limit"]
    force_compact = compact
    current_columns = get_terminal_columns()
    current_compact = force_compact or should_use_compact_layout(columns=current_columns)
    result = {"answer": None, "imposters": []}
    submitted = False
    is_multiple = q.get("type", "single") == "multiple"
    expected_imposters = sorted(q.get("imposters", []))
    imposter_mode = bool(expected_imposters)

    def evaluate_submission(answer_indexes, imposter_indexes) -> dict:
        selected_answer = sorted(answer_indexes) if answer_indexes else []
        selected_imposters = sorted(imposter_indexes) if imposter_indexes else []
        answer_correct = selected_answer == q["correct"]

        if imposter_mode:
            expected_set = set(expected_imposters)
            selected_set = set(selected_imposters)
            true_positive = len(expected_set.intersection(selected_set))
            false_positive = len(selected_set - expected_set)
            false_negative = len(expected_set - selected_set)
            imposter_points = max(0, true_positive - false_positive)
            question_max_points = 1 + len(expected_imposters)
        else:
            true_positive = 0
            false_positive = 0
            false_negative = 0
            imposter_points = 0
            question_max_points = 1

        question_points = (1 if answer_correct else 0) + imposter_points
        is_perfect = answer_correct and (not imposter_mode or (false_positive == 0 and false_negative == 0))
        return {
            "answer_correct": answer_correct,
            "imposter_mode": imposter_mode,
            "expected_imposters": expected_imposters,
            "imposters_selected": selected_imposters,
            "imposter_true_positive": true_positive,
            "imposter_false_positive": false_positive,
            "imposter_false_negative": false_negative,
            "imposter_points": imposter_points,
            "question_points": question_points,
            "question_max_points": question_max_points,
            "is_perfect": is_perfect,
        }

    def render():
        markup = build_question_markup(
            q,
            theme,
            selected,
            marked,
            remaining,
            imposter_marked,
            is_multiple,
            imposter_mode=imposter_mode,
            question_index=question_index,
            total_questions=total_questions,
            pulse=pulse,
            timer_blink=bool(remaining is not None and remaining <= 10 and remaining % 2 == 0),
            no_color=no_color,
            compact=current_compact,
            terminal_width=current_columns,
        )
        if full_screen and submitted:
            grading = evaluate_submission(result["answer"], result["imposters"])
            is_answer_correct = grading["answer_correct"]
            is_correct = grading["is_perfect"]
            explanation = (q.get("explanation") or "").strip()
            if no_color:
                status = "Correct" if is_correct else "Wrong"
                markup += "\n" + status + "\n"
                markup += f"\nQuestion points: {grading['question_points']}/{grading['question_max_points']}\n"
                if imposter_mode:
                    flagged_labels = format_labels(q["options"], result["imposters"]) or "None"
                    expected_labels = format_labels(q["options"], expected_imposters) or "None"
                    markup += f"\nImposters flagged: {flagged_labels}\nExpected imposters: {expected_labels}\n"
                if explanation:
                    markup += f"\nExplanation\n{explanation}\n"
                markup += "\nPress Enter for the next question..."
                return markup

            status_style = theme["success"] if is_correct else theme["danger"]
            status = "Correct" if is_correct else "Wrong"
            markup += f"\n<style fg='{status_style}'><b>{status}</b></style>\n"
            markup += (
                f"\n<style fg='{theme['pt_instruction']}'>"
                f"Question points: {grading['question_points']}/{grading['question_max_points']}"
                f"</style>\n"
            )
            if imposter_mode:
                flagged_labels = format_labels(q["options"], result["imposters"]) or "None"
                expected_labels = format_labels(q["options"], expected_imposters) or "None"
                markup += (
                    f"\n<style fg='{theme['pt_title']}'>"
                    f"Imposters flagged: {html.escape(flagged_labels)}\n"
                    f"Expected imposters: {html.escape(expected_labels)}"
                    f"</style>\n"
                )
            if explanation:
                explanation_lines = [render_inline_markdown_for_prompt_toolkit(line) for line in explanation.splitlines()]
                markup += "\n<style fg='{0}'><b>Explanation</b></style>\n".format(theme["pt_title"])
                markup += "\n".join(explanation_lines) + "\n"
            markup += f"\n<style fg='{theme['pt_instruction']}'>Press Enter for the next question...</style>"
        if no_color:
            return markup
        return PromptHTML(markup)

    control = FormattedTextControl(text=render)
    window = Window(content=control, wrap_lines=True, always_hide_cursor=True)
    kb = KeyBindings()

    @kb.add("up")
    def _(_):
        nonlocal selected, pulse
        selected = (selected - 1) % len(q["options"])
        pulse = not pulse
        control.text = render()

    @kb.add("down")
    def _(_):
        nonlocal selected, pulse
        selected = (selected + 1) % len(q["options"])
        pulse = not pulse
        control.text = render()

    @kb.add("space")
    def _(_):
        idx = selected + 1
        if idx in marked:
            marked.remove(idx)
        else:
            if not is_multiple:
                marked.clear()
            marked.add(idx)
        control.text = render()

    @kb.add("x")
    def _(_):
        if not imposter_mode:
            return
        idx = selected + 1
        if idx in imposter_marked:
            imposter_marked.remove(idx)
        else:
            imposter_marked.add(idx)
        control.text = render()

    @kb.add("X")
    def _(_):
        if not imposter_mode:
            return
        idx = selected + 1
        if idx in imposter_marked:
            imposter_marked.remove(idx)
        else:
            imposter_marked.add(idx)
        control.text = render()

    @kb.add("enter")
    def _(event):
        nonlocal submitted
        if not submitted:
            result["answer"] = sorted(marked) if marked else None
            result["imposters"] = sorted(imposter_marked)
            if full_screen:
                submitted = True
                control.text = render()
                app.invalidate()
                return
        event.app.exit()

    @kb.add("c-c")
    def _(event):
        event.app.exit(exception=KeyboardInterrupt())

    app = Application(
        layout=Layout(HSplit([window])),
        key_bindings=kb,
        full_screen=full_screen,
        erase_when_done=full_screen,
    )

    def pt_columns(default: int) -> int:
        try:
            return int(app.output.get_size().columns)
        except Exception:
            return get_terminal_columns(default=default)

    current_columns = pt_columns(current_columns)
    if not force_compact:
        current_compact = should_use_compact_layout(columns=current_columns)
    control.text = render()

    async def timer():
        nonlocal remaining, submitted
        if remaining is None:
            return
        while remaining > 0 and not submitted:
            await asyncio.sleep(1)
            remaining -= 1
            if submitted:
                break
            control.text = render()
            app.invalidate()
        if remaining == 0 and not submitted:
            result["answer"] = None
            result["imposters"] = sorted(imposter_marked)
            if full_screen:
                submitted = True
                control.text = render()
                app.invalidate()
            else:
                app.exit()

    async def watch_resize():
        nonlocal current_columns, current_compact, pulse
        while True:
            await asyncio.sleep(0.2)
            columns = pt_columns(current_columns)
            if columns == current_columns:
                continue
            current_columns = columns
            if not force_compact:
                current_compact = should_use_compact_layout(columns=columns)
            pulse = not pulse
            control.text = render()
            app.invalidate()

    task = asyncio.create_task(timer())
    resize_task = asyncio.create_task(watch_resize())
    try:
        await app.run_async()
    finally:
        task.cancel()
        resize_task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        try:
            await resize_task
        except asyncio.CancelledError:
            pass

    ans = result["answer"]
    imposters_selected = result["imposters"]
    grading = evaluate_submission(ans, imposters_selected)
    return grading["is_perfect"], ans, imposters_selected, grading


def run_coroutine_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result = {"value": None, "error": None}

    def _runner():
        loop = asyncio.new_event_loop()
        try:
            result["value"] = loop.run_until_complete(coro)
        except Exception as exc:  # pragma: no cover - re-raised in caller thread
            result["error"] = exc
        finally:
            loop.close()

    import threading

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if result["error"] is not None:
        raise result["error"]
    return result["value"]


def safe_for_stream(text: str, stream) -> str:
    encoding = getattr(stream, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def format_labels(options: list[str], indexes: list[int] | None) -> str:
    if not indexes:
        return ""
    labels = []
    for idx in indexes:
        if 1 <= idx <= len(options):
            labels.append(f"{idx}. {options[idx - 1]}")
    return "; ".join(labels)


def run(title, questions, theme_name: str = "auto", no_color: bool = False, full_screen: bool = False):
    try:
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Running the quiz requires rich. Install dependencies from requirements.txt."
        ) from exc

    console = Console(no_color=no_color)
    console.print(LOGO)

    theme = select_theme(theme_name)
    quiz_has_imposters = any(bool(q.get("imposters")) for q in questions)
    saved_answers = []

    try:
        rules_text = (
            "[bold]Rules:[/bold]\n"
            "- Use ↑/↓ to move\n"
            "- Press [bold]Space[/bold] to select an answer\n"
            + ("- Press [bold]X[/bold] to mark/unmark imposter options\n" if quiz_has_imposters else "")
            + "- Press [bold]Enter[/bold] to continue\n"
            "- Press [bold]Ctrl+C[/bold] to exit the quiz at any time\n\n"
            "Are you ready to start?\n"
            f"[bold {theme['accent']}]Press Enter... Let's go! 🚀[/bold {theme['accent']}]"
        )
        console.print(
            Panel(
                f"[bold {theme['primary']}]{title}[/bold {theme['primary']}]\n\n"
                f"{rules_text}",
                border_style=theme["panel"]
            )
        )
        prompt_input()

        points_earned = 0
        total_points_possible = 0
        correct_answers_count = 0
        imposter_tp_total = 0
        imposter_fp_total = 0
        imposter_fn_total = 0

        for i, q in enumerate(questions, start=1):
            if i > 1 and not full_screen:
                console.print("\n")

            perfect, ans, imposter_ans, grading = run_coroutine_sync(
                ask_question(
                    q,
                    theme,
                    question_index=i,
                    total_questions=len(questions),
                    no_color=no_color,
                    compact=False,
                    full_screen=full_screen,
                )
            )

            selected_labels = format_labels(q["options"], ans)
            correct_labels = format_labels(q["options"], q["correct"])
            selected_imposter_labels = format_labels(q["options"], imposter_ans)
            expected_imposter_labels = format_labels(q["options"], q.get("imposters", []))
            points_earned += grading["question_points"]
            total_points_possible += grading["question_max_points"]
            if grading["answer_correct"]:
                correct_answers_count += 1
            imposter_tp_total += grading["imposter_true_positive"]
            imposter_fp_total += grading["imposter_false_positive"]
            imposter_fn_total += grading["imposter_false_negative"]

            if not full_screen:
                if grading["answer_correct"]:
                    console.print(f"[{theme['success']}]Correct[/{theme['success']}]")
                else:
                    console.print(f"[{theme['danger']}]Wrong[/{theme['danger']}]")
                console.print(
                    f"[{theme['secondary']}]Question points:[/{theme['secondary']}] "
                    f"{grading['question_points']}/{grading['question_max_points']}"
                )

            if q.get("imposters") and not full_screen:
                console.print(
                    f"[{theme['secondary']}]Imposters flagged:[/{theme['secondary']}] "
                    f"{selected_imposter_labels or 'None'}"
                )
                console.print(
                    f"[{theme['secondary']}]Expected imposters:[/{theme['secondary']}] "
                    f"{expected_imposter_labels or 'None'}"
                )

            if not full_screen and q.get("explanation"):
                console.print(
                    Panel(
                        Markdown(f"**Explanation**\n\n{q['explanation']}"),
                        border_style=theme["panel"],
                    )
                )

            saved_answers.append({
                "question_title": q["title"],
                "question_text": q["question"],
                "selected_indexes": ans or [],
                "selected_labels": selected_labels,
                "selected_imposters": imposter_ans or [],
                "selected_imposter_labels": selected_imposter_labels,
                "correct_indexes": q["correct"],
                "correct_labels": correct_labels,
                "expected_imposters": q.get("imposters", []),
                "expected_imposter_labels": expected_imposter_labels,
                "is_correct": perfect,
                "answer_correct": grading["answer_correct"],
                "question_points": grading["question_points"],
                "question_max_points": grading["question_max_points"],
                "imposter_true_positive": grading["imposter_true_positive"],
                "imposter_false_positive": grading["imposter_false_positive"],
                "imposter_false_negative": grading["imposter_false_negative"],
                "explanation": q.get("explanation", ""),
            })

            if not full_screen:
                prompt_input("Press Enter for the next question...")
            
        percentage = (points_earned / total_points_possible) * 100 if total_points_possible else 0.0
        wrong_topics = [item["question_title"] for item in saved_answers if not item["is_correct"]]
        if wrong_topics:
            quick_review = "\n".join(f"- {topic}" for topic in wrong_topics)
        else:
            quick_review = "- None, excellent work."

        precision = None
        recall = None
        if quiz_has_imposters:
            precision = (
                (imposter_tp_total / (imposter_tp_total + imposter_fp_total))
                if (imposter_tp_total + imposter_fp_total) > 0
                else None
            )
            recall = (
                (imposter_tp_total / (imposter_tp_total + imposter_fn_total))
                if (imposter_tp_total + imposter_fn_total) > 0
                else None
            )

        precision_text = f"{(precision * 100):.1f}%" if precision is not None else "N/A"
        recall_text = f"{(recall * 100):.1f}%" if recall is not None else "N/A"

        score_line = (
            f"Score: [bold]{points_earned}/{total_points_possible}[/bold]\n"
            if total_points_possible
            else f"Score: [bold]{points_earned}/0[/bold]\n"
        )

        summary = (
            f"[bold {theme['primary']}]Quiz Summary[/bold {theme['primary']}]\n\n"
            f"{score_line}"
            f"Percentage: [bold]{percentage:.1f}%[/bold]\n"
            f"Correct Answers: [bold]{correct_answers_count}[/bold]\n"
            + (
                f"Imposter Precision: [bold]{precision_text}[/bold]\n"
                f"Imposter Recall: [bold]{recall_text}[/bold]\n"
                f"False-flag Count: [bold]{imposter_fp_total}[/bold]\n"
                if quiz_has_imposters
                else ""
            )
            + "\n"
            f"[bold]Quick Review Topics:[/bold]\n{quick_review}"
        )
        console.print(Panel(summary, border_style=theme["panel"]))

        if ask_to_save_answers():
            try:
                attempt_dir = save_attempt(
                    title,
                    points_earned,
                    questions,
                    saved_answers,
                    total_score_possible=total_points_possible,
                )
                console.print(
                    Panel(
                        f"[bold {theme['success']}]Answers saved successfully.[/bold {theme['success']}]\n{attempt_dir}",
                        border_style=theme["success"],
                    )
                )
            except OSError as exc:
                console.print(
                    Panel(
                        f"[bold {theme['danger']}]Could not save answers:[/bold {theme['danger']}]\n{exc}",
                        border_style=theme["danger"],
                    )
                )

    except KeyboardInterrupt:
        console.print("\n\n")  # ← spacing BEFORE

        console.print(
            Panel(
                f"[bold {theme['accent']}]Thank you for trying! 👋[/bold {theme['accent']}]",
                border_style=theme["accent"],
            )
        )


def run_essay(
    essay: dict,
    theme_name: str = "auto",
    no_color: bool = False,
    ai_provider: str = DEFAULT_AI_PROVIDER,
    ai_model: str = "",
    ai_timeout: int = 30,
):
    try:
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Running the quiz requires rich. Install dependencies from requirements.txt."
        ) from exc

    requested_provider = ai_provider
    if ai_provider == "auto":
        provider_candidates = _available_ai_providers_by_priority()
    else:
        provider_candidates = [_resolve_ai_provider(ai_provider)]

    if not provider_candidates:
        raise RuntimeError(
            "Essay mode with provider 'auto' requires at least one key.\n"
            "Checked in priority order: GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY.\n"
            "Set one before running, e.g.:\n"
            f"{_platform_setup_hint_for_any_ai_key()}"
        )

    # Start with first candidate; this may be replaced by failover in auto mode.
    resolved_provider = provider_candidates[0]
    resolved_model = ai_model.strip() if ai_model else _default_model_for_provider(resolved_provider)
    if requested_provider != "auto":
        env_key = _env_key_for_provider(resolved_provider)
        if not os.environ.get(env_key, "").strip():
            raise RuntimeError(
                f"Essay mode with provider '{resolved_provider}' requires {env_key}.\n"
                "Standard multiple-choice quizzes do not use AI and do not need this key.\n"
                "Set it before running, e.g.:\n"
                f"{_platform_setup_hint_for_env_key(env_key)}"
            )

    theme = select_theme(theme_name)
    console = Console(no_color=no_color)
    console.print(LOGO)
    title = essay["title"]
    question = essay["question"]
    instructions = essay["instructions"]
    hint_text = essay.get("hint", "").strip() or "🤔 Hint: Focus on the key points your instructor expects."
    intro_markdown = (
        f"## Question\n\n{question}\n\n"
        f"## Instructions\n\n{instructions}\n\n"
        f"## Hint\n\n{hint_text}\n\n"
        f"**⏎ Press Enter to open your editor and write your answer.**"
    )

    try:
        console.print(
            Panel(
                Markdown(intro_markdown, code_theme="monokai"),
                title=f"[bold {theme['primary']}]{title}[/bold {theme['primary']}]",
                border_style=theme["panel"],
            )
        )
        prompt_input()
        student_answer = collect_essay_answer_via_editor(title, question)

        if no_color:
            console.print("✓ Answer captured.")
        else:
            console.print(f"[bold {theme['success']}]✓ Answer captured.[/bold {theme['success']}]")

        provider_name = _provider_display_name(resolved_provider)
        provider_chip = f"✓ Connected: {provider_name} ({resolved_model})"
        if no_color:
            console.print(provider_chip)
        else:
            console.print(
                Panel(
                    f"[bold {theme['success']}]✓[/bold {theme['success']}] "
                    f"[bold {theme['primary']}]{provider_name}[/bold {theme['primary']}] "
                    f"[{theme['pt_instruction']}]({resolved_model})[/]",
                    border_style=theme["success"],
                )
            )

        grade = None
        fallback_message = ""
        fallback_reason = "unknown_error"
        attempted_providers: list[str] = []

        if requested_provider == "auto":
            for idx, provider in enumerate(provider_candidates):
                env_key = _env_key_for_provider(provider)
                api_key = os.environ.get(env_key, "").strip()
                if not api_key:
                    continue
                evaluator = _evaluator_for_provider(provider)
                model_for_provider = (
                    ai_model.strip() if ai_model and idx == 0 else _default_model_for_provider(provider)
                )
                attempted_providers.append(provider)
                try:
                    grade = evaluate_essay_with_loading(
                        console,
                        theme,
                        evaluator,
                        instructor_name=essay.get("instructor_name", ""),
                        essay=essay,
                        student_answer=student_answer,
                        api_key=api_key,
                        model=model_for_provider,
                        timeout=ai_timeout,
                    )
                    resolved_provider = provider
                    resolved_model = model_for_provider
                    break
                except RuntimeError as exc:
                    fallback_message = str(exc)
                    if fallback_message.startswith("[") and "]" in fallback_message:
                        fallback_reason = fallback_message[1 : fallback_message.index("]")]

            if grade is None:
                grade = evaluate_essay_deterministic_fallback(
                    essay,
                    student_answer,
                    fallback_message or "All AI providers failed.",
                    reason_code=fallback_reason,
                )
                if attempted_providers:
                    attempted_chain = " -> ".join(attempted_providers)
                    grade["suggestions"] = list(grade.get("suggestions", []))
                    grade["suggestions"].append(
                        f"Auto provider failover attempted: {attempted_chain}"
                    )
        else:
            env_key = _env_key_for_provider(resolved_provider)
            api_key = os.environ.get(env_key, "").strip()
            if not api_key:
                raise RuntimeError(
                    f"Essay mode with provider '{resolved_provider}' requires {env_key}.\n"
                    "Standard multiple-choice quizzes do not use AI and do not need this key.\n"
                    "Set it before running, e.g.:\n"
                    f"{_platform_setup_hint_for_env_key(env_key)}"
                )
            evaluator = _evaluator_for_provider(resolved_provider)
            try:
                grade = evaluate_essay_with_loading(
                    console,
                    theme,
                    evaluator,
                    instructor_name=essay.get("instructor_name", ""),
                    essay=essay,
                    student_answer=student_answer,
                    api_key=api_key,
                    model=resolved_model,
                    timeout=ai_timeout,
                )
            except RuntimeError as exc:
                fallback_message = str(exc)
                if fallback_message.startswith("[") and "]" in fallback_message:
                    fallback_reason = fallback_message[1 : fallback_message.index("]")]
                grade = evaluate_essay_deterministic_fallback(
                    essay,
                    student_answer,
                    fallback_message,
                    reason_code=fallback_reason,
                )

        if grade["score_percent"] is None:
            score_text = "N/A (AI unavailable)"
        else:
            score_text = f"{grade['score_percent']:.2f}%"
        encouragement = _score_encouragement(grade["score_percent"])

        feedback_lines = []
        for item in grade["did_well"]:
            feedback_lines.append(f"- Did well: {item}")
        for item in grade["missing"]:
            feedback_lines.append(f"- Missing: {item}")
        for item in grade["suggestions"]:
            feedback_lines.append(f"- Suggestion: {item}")
        if not feedback_lines:
            feedback_lines.append("- Feedback unavailable.")

        if grade["ai_unavailable"]:
            reason_labels = {
                "rate_limit": "rate limit reached",
                "not_found": "model or endpoint not found",
                "server_error": "provider server error",
                "http_error": "HTTP error",
                "timeout": "request timeout",
                "network_error": "network error",
                "invalid_response": "unexpected model response shape",
                "payload_too_large": "payload too large",
                "unauthorized": "invalid API key or auth",
                "forbidden": "forbidden by provider",
                "unknown_error": "unknown error",
            }
            reason_label = reason_labels.get(grade.get("ai_reason", ""), "unknown error")
            feedback_lines.append("")
            feedback_lines.append(
                f"- Note: AI unavailable ({reason_label}); deterministic fallback used."
            )
            feedback_lines.append("- Scoring mode: heuristic fallback (approximate).")

        feedback_heading = "Feedback"
        instructor_name = str(essay.get("instructor_name", "")).strip()
        if instructor_name:
            feedback_heading = f"Feedback from {_format_possessive(instructor_name)} notes"

        feedback_body = (
            f"[bold {theme['primary']}]Score: {score_text}[/bold {theme['primary']}]\n\n"
            + (f"[bold]{encouragement}[/bold]\n\n" if encouragement else "")
            + f"[bold]{feedback_heading}[/bold]\n"
            + "\n".join(feedback_lines)
        )
        console.print(
            Panel(
                feedback_body,
                border_style=theme["panel"],
            )
        )

        if ask_yes_no("Do you want to see the rubric? [y/n]: "):
            rubric_markdown = _rubric_markdown(essay["criteria"])
            console.print(
                Panel(
                    Markdown(rubric_markdown, code_theme="monokai"),
                    title=f"[bold {theme['primary']}]Rubric[/bold {theme['primary']}]",
                    border_style=theme["panel"],
                )
            )

        payload = {
            "mode": "essay",
            "quiz_title": title,
            "question": question,
            "student_answer": student_answer,
            "points_awarded": grade["points_awarded"],
            "total_points": grade["total_points"],
            "score_percent": grade["score_percent"],
            "did_well": grade["did_well"],
            "missing": grade["missing"],
            "suggestions": grade["suggestions"],
            "ai_unavailable": grade["ai_unavailable"],
            "ai_error": _redacted_ai_error(grade.get("ai_reason", "unknown_error"), grade["ai_unavailable"]),
            "ai_reason": grade.get("ai_reason", "none"),
            "scoring_mode": grade.get("scoring_mode", "unknown"),
            "scoring_confidence": grade.get("scoring_confidence", "unknown"),
            "ai_provider": resolved_provider,
            "ai_provider_requested": requested_provider,
            "ai_model": resolved_model,
        }

        if ask_to_save_answers():
            attempt_dir = save_essay_attempt(title, payload)
            console.print(
                Panel(
                    f"[bold {theme['success']}]Answers saved successfully.[/bold {theme['success']}]\n{attempt_dir}",
                    border_style=theme["success"],
                )
            )
    except KeyboardInterrupt:
        console.print("\n\n")
        console.print(
            Panel(
                f"[bold {theme['accent']}]Thank you for trying! 👋[/bold {theme['accent']}]",
                border_style=theme["accent"],
            )
        )


def main():
    # Improve default Unicode behavior on Windows consoles where possible.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

    raw_args = sys.argv[1:]
    if raw_args and raw_args[0] == "init":
        init_parser = argparse.ArgumentParser(description="Create starter quiz files.")
        init_parser.add_argument(
            "--dir",
            default=".",
            help="Directory where starter files will be created (default: current directory).",
        )
        init_parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing starter files if they already exist.",
        )
        args = init_parser.parse_args(raw_args[1:])
        try:
            created = init_starter_files(args.dir, force=args.force)
        except OSError as exc:
            print(safe_for_stream(f"File error: {exc}", sys.stderr), file=sys.stderr)
            raise SystemExit(1) from exc
        except RuntimeError as exc:
            print(safe_for_stream(f"Runtime error: {exc}", sys.stderr), file=sys.stderr)
            raise SystemExit(1) from exc

        print("Created starter files:")
        for path in created:
            print(f"- {path}")
        print("")
        print("Next steps:")
        created_by_name = {path.name: path for path in created}
        hello_quiz = created_by_name.get("hello-quiz.md")
        hello_imposter = created_by_name.get("hello-imposter.md")
        hello_essay = created_by_name.get("hello-essay.md")
        if hello_quiz:
            print(f"quizmd --validate {hello_quiz}")
            print(f"quizmd {hello_quiz}")
        if hello_imposter:
            print(f"quizmd --validate {hello_imposter}")
            print(f"quizmd {hello_imposter}")
        if hello_essay:
            print(f"quizmd --validate {hello_essay}")
        print("Set one AI key for essay mode (MCQ quizzes do not need keys):")
        print(_platform_setup_hint_for_any_ai_key())
        if hello_essay:
            print(f"quizmd {hello_essay}")
        return

    parser = argparse.ArgumentParser(description="Run markdown quizzes in the terminal.")
    parser.add_argument("file", help="Path to a quiz markdown file.")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate quiz file structure and exit without starting the interactive quiz.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--theme",
        choices=["auto", "dark", "light"],
        default="auto",
        help="Color theme for the interactive quiz UI.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colors/styled symbols (also enabled automatically when NO_COLOR is set).",
    )
    parser.add_argument(
        "--full-screen",
        action="store_true",
        help="Render each question in full-screen mode (one question view at a time).",
    )
    parser.add_argument(
        "--ai-provider",
        default=DEFAULT_AI_PROVIDER,
        choices=["auto", "gemini", "openai", "anthropic"],
        help="AI provider for essay mode. 'auto' priority: gemini -> openai -> anthropic.",
    )
    parser.add_argument(
        "--ai-model",
        default="",
        help="AI model name for essay mode (defaults by provider).",
    )
    parser.add_argument(
        "--ai-timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds for AI evaluation requests.",
    )
    args = parser.parse_args()
    if args.ai_timeout <= 0:
        parser.error("--ai-timeout must be greater than zero")
    no_color = is_no_color_requested(args.no_color)

    try:
        mode = detect_quiz_mode(args.file)
        if mode == "essay":
            title, essay = parse_essay_markdown(args.file)
        else:
            title, questions = parse_quiz_markdown(args.file)
    except ValueError as exc:
        print(safe_for_stream(f"Validation failed: {exc}", sys.stderr), file=sys.stderr)
        raise SystemExit(1) from exc
    except OSError as exc:
        print(safe_for_stream(f"File error: {exc}", sys.stderr), file=sys.stderr)
        raise SystemExit(1) from exc

    if args.validate:
        if mode == "essay":
            print(safe_for_stream(
                f"Validation passed: Essay Question: {title} ({essay['total_points']} points)",
                sys.stdout,
            ))
        else:
            print(safe_for_stream(f"Validation passed: {title} ({len(questions)} questions)", sys.stdout))
        return

    try:
        if mode == "essay":
            run_essay(
                essay,
                theme_name=args.theme,
                no_color=no_color,
                ai_provider=args.ai_provider,
                ai_model=args.ai_model,
                ai_timeout=args.ai_timeout,
            )
        else:
            run(title, questions, theme_name=args.theme, no_color=no_color, full_screen=args.full_screen)
    except RuntimeError as exc:
        print(safe_for_stream(f"Runtime error: {exc}", sys.stderr), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
