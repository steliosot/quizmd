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
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

try:
    from wcwidth import wcswidth as _wcwidth_wcswidth
except ModuleNotFoundError:
    _wcwidth_wcswidth = None

__version__ = "2.4.0rc2"
DEFAULT_AI_PROVIDER = "auto"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-latest"
UI_CHOICES = ("classic", "next")
AI_PROVIDER_PRIORITY = ("gemini", "openai", "anthropic")
GEMINI_REQUESTS_PER_MINUTE = 15
MAX_AI_REQUEST_BYTES = 48_000
_GEMINI_REQUEST_TIMES: deque[float] = deque()
DEFAULT_ROOM_SERVER_CLOUD = "https://quizmd-server-1096434233875.europe-west1.run.app"
DEFAULT_ROOM_SERVER_LABEL = "Belgium"
ROOM_NAME_CITIES = ("berlin", "oslo", "london", "athens", "madrid", "dublin", "rome", "lisbon")
ROOM_NAME_ANIMALS = ("elephant", "fox", "otter", "panda", "koala", "falcon", "tiger", "whale")
ROOM_NAME_MIN_LEN = 3
ROOM_NAME_MAX_LEN = 64
ROOM_MIN_TIME_LIMIT_SECONDS = 5
ROOM_SAMPLE_QUIZ_TITLE = "Python Basics Beta (5Q)"
ROOM_SAMPLE_QUESTIONS = [
    {
        "title": "Question 1",
        "question": "What is 2 + 2?",
        "options": ["3", "4", "5", "6"],
        "correct": [2],
        "type": "single",
        "time_limit": 20,
        "explanation": "2 + 2 equals 4.",
    },
    {
        "title": "Question 2",
        "question": "Which are Python data types?",
        "options": ["list", "banana", "dict", "integer"],
        "correct": [1, 3, 4],
        "type": "multiple",
        "time_limit": 25,
        "explanation": "list, dict, and integer are valid Python data types.",
    },
    {
        "title": "Question 3",
        "question": "What does this print?\n```python\nname = \"Stelios\"\nprint(name.upper())\n```",
        "options": ["stelios", "STELIOS", "Name", "upper"],
        "correct": [2],
        "type": "single",
        "time_limit": 25,
        "explanation": ".upper() converts text to uppercase.",
    },
    {
        "title": "Question 4",
        "question": "What does `arr.append([4,5])` do?",
        "options": [
            "Adds the list [4,5] as a single element",
            "Adds 4 and 5 as separate elements",
            "Replaces the last element with [4,5]",
            "Extends the list with [4,5]",
        ],
        "correct": [1],
        "type": "single",
        "time_limit": 30,
        "explanation": "append adds one element, even when that element is another list.",
    },
    {
        "title": "Question 5",
        "question": "What happens after `arr = [1,2,3]; b = arr`?",
        "options": [
            "Both variables reference the same list in memory",
            "A new copy is created for b",
            "Only the first element is shared",
            "Python blocks updates through b",
        ],
        "correct": [1],
        "type": "single",
        "time_limit": 30,
        "explanation": "Assignment binds b to the same list object as arr.",
    },
]

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

## Local modes

```bash
quizmd --validate hello-quiz.md
quizmd hello-quiz.md
quizmd --validate hello-imposter.md
quizmd hello-imposter.md
```

## Essay mode

```bash
quizmd --validate hello-essay.md
export GEMINI_API_KEY="your_key_here"  # or OPENAI_API_KEY / ANTHROPIC_API_KEY
quizmd hello-essay.md
```

## Room modes (online)

```bash
quizmd room --create --mode compete --quiz hello-quiz.md
quizmd room --create --mode collaborate --quiz hello-quiz.md
quizmd room --create --mode boxing --quiz hello-quiz.md
quizmd room --join <room-name> [--token <room-token>]
```

Room quiz requirement:
- For online room modes, each question `Time`/`time_limit` must be 5 seconds or higher.
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

    blank_options = [idx for idx, option in enumerate(question["options"], start=1) if not str(option).strip()]
    if blank_options:
        raise ValueError(
            f"{source}: blank option text at indexes {blank_options} in {question['title']!r}"
        )

    if option_count < 2:
        raise ValueError(
            f"{source}: question {question['title']!r} must include at least two options"
        )

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

        field_pattern = re.compile(r"(?i)^(answer|type|time|explanation|imposters)\s*:\s*(.*)$")
        option_pattern = re.compile(r"^\s*-\s*(.*)$")
        option_with_content_pattern = re.compile(r"^\s*-\s+\S.*$")

        # Track code-fence state per line so markdown in question text doesn't get parsed as metadata.
        line_info = []
        in_code_fence = False
        for raw_line in body_lines:
            stripped = raw_line.strip()
            line_info.append({
                "raw": raw_line,
                "stripped": stripped,
                "in_code": in_code_fence,
            })
            if stripped.startswith("```"):
                in_code_fence = not in_code_fence

        first_field_idx = None
        for idx, info in enumerate(line_info):
            if info["in_code"]:
                continue
            if field_pattern.match(info["stripped"]):
                first_field_idx = idx
                break

        option_start_idx = None
        option_end_idx = None
        if first_field_idx is not None:
            scan = first_field_idx - 1
            while (
                scan >= 0
                and not line_info[scan]["in_code"]
                and not line_info[scan]["stripped"]
            ):
                scan -= 1

            option_end_idx = scan
            while (
                scan >= 0
                and not line_info[scan]["in_code"]
                and (
                    option_with_content_pattern.match(line_info[scan]["raw"]) is not None
                    or line_info[scan]["stripped"] == "-"
                )
            ):
                scan -= 1
            option_start_idx = scan + 1

            if option_start_idx > option_end_idx:
                option_start_idx = None
                option_end_idx = None

            # If options are present but not directly adjacent to the first metadata field,
            # keep legacy behavior by treating from the first option onward as metadata.
            # This preserves clear "unrecognized line" failures for malformed mixes like:
            # options -> unexpected line -> Answer/Type.
            if option_start_idx is None:
                for idx, info in enumerate(line_info[:first_field_idx]):
                    if info["in_code"]:
                        continue
                    if option_with_content_pattern.match(info["raw"]) is not None or info["stripped"] == "-":
                        option_start_idx = idx
                        break

        if option_start_idx is None:
            question_lines = body_lines[:first_field_idx] if first_field_idx is not None else body_lines
            metadata_lines = body_lines[first_field_idx:] if first_field_idx is not None else []
        else:
            question_lines = body_lines[:option_start_idx]
            metadata_lines = body_lines[option_start_idx:]

        # Optional explicit separator to disambiguate question markdown lists from answer options.
        question_nonempty_indexes = [idx for idx, raw in enumerate(question_lines) if raw.strip()]
        has_explicit_options_marker = False
        if question_nonempty_indexes:
            marker_idx = question_nonempty_indexes[-1]
            marker_text = question_lines[marker_idx].strip().lower().rstrip(":")
            if marker_text in {"options", "choices"}:
                has_explicit_options_marker = True
                question_lines = question_lines[:marker_idx]

        question_has_bullets = any(
            (
                not line_info[idx]["in_code"]
                and option_with_content_pattern.match(line_info[idx]["raw"]) is not None
            )
            for idx in range(len(question_lines))
        )

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
        seen_field = False

        for l in metadata_lines:
            stripped = l.strip()
            if not stripped:
                continue
            option_match = option_pattern.match(l)
            if option_match:
                if seen_field:
                    raise ValueError(
                        f"{source}: options must appear before metadata fields in question {title!r}"
                    )
                option_text = option_match.group(1).strip()
                if not option_text:
                    raise ValueError(
                        f"{source}: blank option text in question {title!r} is not allowed"
                    )
                options.append(option_text)
                continue

            field_match = field_pattern.match(stripped)
            if field_match:
                key = field_match.group(1).lower()
                value = field_match.group(2)
                seen_field = True
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

        if question_has_bullets and options and not has_explicit_options_marker:
            raise ValueError(
                f"{source}: question {title!r} contains markdown bullet lines and answer options. "
                "Add an 'Options:' line before answer choices to disambiguate."
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


def render_init_next_screen(created: list[Path] | None = None, target_dir: str = ".") -> None:
    """Render the experimental vNext init welcome without changing file behavior."""
    try:
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ModuleNotFoundError:
        print(f"QuizMD {__version__}")
        print("Write quizzes in Markdown. Run them in the terminal.")
        print(f"Folder: {Path(target_dir).expanduser().resolve()}")
        return

    console = Console()
    folder = Path(target_dir).expanduser().resolve()
    console.print(
        Panel(
            f"[bold cyan]QuizMD[/bold cyan] [dim]v{__version__}[/dim]\n"
            "[green]Write quizzes in Markdown. Run them in the terminal.[/green]\n"
            f"[dim]Folder:[/dim] {folder}",
            border_style="bright_blue",
            box=box.ROUNDED,
        )
    )

    modes = Table.grid(expand=True)
    modes.add_column(ratio=1)
    modes.add_column(ratio=1)
    modes.add_column(ratio=1)
    modes.add_row(
        "[bold]1 Classic[/bold]\n[dim]Fast MCQ practice[/dim]\n[green]No AI key[/green]",
        "[bold]2 Imposter[/bold]\n[dim]Spot misleading answers[/dim]\n[green]No AI key[/green]",
        "[bold]3 Essay[/bold]\n[dim]Rubric + AI feedback[/dim]\n[yellow]Needs AI key[/yellow]",
    )
    console.print(Panel(modes, title="[bold]Recommended quiz types[/bold]", border_style="cyan"))

    rooms = Table.grid(expand=True)
    rooms.add_column(ratio=1)
    rooms.add_column(ratio=1)
    rooms.add_column(ratio=1)
    rooms.add_row(
        "[bold]Compete[/bold]\n[dim]Fast live quiz race[/dim]",
        "[bold]Collaborate[/bold]\n[dim]Team consensus quiz[/dim]",
        "[bold]Boxing[/bold]\n[dim]One-to-one teacher check[/dim]",
    )
    console.print(Panel(rooms, title="[bold]Room modes[/bold]", border_style="magenta"))

    if created is not None:
        labels = {
            "hello-quiz.md": "Single + multiple choice",
            "hello-imposter.md": "Imposter distractor spotting",
            "hello-essay.md": "Short answer with AI feedback",
            "QUIZ_GUIDE.md": "Starter commands and notes",
        }
        created_text = "\n".join(
            f"- {path} [dim][{labels.get(path.name, 'Created file')}][/dim]"
            for path in created
        )
        console.print(
            Panel(
                created_text,
                title="[bold green]Created starter files[/bold green]",
                border_style="green",
            )
        )


def prompt_input(prompt: str = "") -> str:
    try:
        return input(prompt)
    except EOFError as exc:
        raise RuntimeError("Interactive input is not available in this environment.") from exc


def _room_http_base(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return DEFAULT_ROOM_SERVER_CLOUD
    if "://" not in raw:
        if raw.startswith("localhost") or raw.startswith("127."):
            raw = f"http://{raw}"
        else:
            raw = f"https://{raw}"
    parsed = urllib.parse.urlparse(raw)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme == "http" and host.endswith(".run.app"):
        parsed = parsed._replace(scheme="https")
    return urllib.parse.urlunparse(parsed).rstrip("/")


def _room_default_server() -> str:
    servers = _room_configured_servers()
    return servers[0][1]


def _room_configured_servers() -> list[tuple[str, str]]:
    raw_list = os.environ.get("QUIZMD_ROOM_SERVERS", "").strip()
    if raw_list:
        servers: list[tuple[str, str]] = []
        seen_urls: set[str] = set()
        for token in re.split(r"[,\n;]+", raw_list):
            item = token.strip()
            if not item:
                continue
            label = ""
            url = ""
            if "|" in item:
                label, url = item.split("|", 1)
            elif "=" in item:
                label, url = item.split("=", 1)
            else:
                url = item
            normalized = _room_http_base(url)
            if not normalized or normalized in seen_urls:
                continue
            parsed = urllib.parse.urlparse(normalized)
            fallback_label = parsed.hostname or "Cloud"
            servers.append(((label.strip() or fallback_label), normalized))
            seen_urls.add(normalized)
        if servers:
            return servers

    env_server = os.environ.get("QUIZMD_ROOM_SERVER", "").strip()
    if env_server:
        return [(DEFAULT_ROOM_SERVER_LABEL, _room_http_base(env_server))]
    return [(DEFAULT_ROOM_SERVER_LABEL, DEFAULT_ROOM_SERVER_CLOUD)]


def _room_resolve_server(
    *,
    explicit_server: str,
    theme_name: str,
    no_color: bool,
) -> tuple[str, str]:
    if explicit_server.strip():
        return "Cloud", _room_http_base(explicit_server)

    servers = _room_configured_servers()
    if len(servers) == 1:
        return servers[0]

    options = [(f"{label} ({url})", url) for label, url in servers]
    selected_url = _select_with_space(
        "Server:",
        options,
        theme_name=theme_name,
        no_color=no_color,
    )
    for label, url in servers:
        if url == selected_url:
            return label, url
    return "Cloud", selected_url


def _room_server_online(server: str) -> bool:
    base = _room_http_base(server)
    try:
        payload = _room_get_json(f"{base}/healthz", timeout=5)
        if str(payload.get("status", "")).lower() == "ok":
            return True
    except RuntimeError:
        pass
    try:
        payload = _room_get_json(f"{base}/openapi.json", timeout=5)
    except RuntimeError:
        return False
    return isinstance(payload, dict) and "openapi" in payload


def _room_supported_modes(server: str) -> set[str] | None:
    """Return supported room modes from OpenAPI when available."""
    base = _room_http_base(server)
    try:
        payload = _room_get_json(f"{base}/openapi.json", timeout=6)
    except RuntimeError:
        return None
    if not isinstance(payload, dict):
        return None

    components = payload.get("components", {})
    if not isinstance(components, dict):
        return None
    schemas = components.get("schemas", {})
    if not isinstance(schemas, dict):
        return None

    def _normalize_enum(values: object) -> set[str] | None:
        if not isinstance(values, list):
            return None
        normalized = {str(item).strip().lower() for item in values if str(item).strip()}
        return normalized or None

    mode_schema = schemas.get("Mode")
    if isinstance(mode_schema, dict):
        enum_values = _normalize_enum(mode_schema.get("enum"))
        if enum_values:
            return enum_values

    create_schema = schemas.get("CreateRoomRequest")
    if not isinstance(create_schema, dict):
        return None
    properties = create_schema.get("properties", {})
    if not isinstance(properties, dict):
        return None
    mode_property = properties.get("mode")
    if not isinstance(mode_property, dict):
        return None

    enum_values = _normalize_enum(mode_property.get("enum"))
    if enum_values:
        return enum_values

    ref = mode_property.get("$ref")
    if not isinstance(ref, str) or "/" not in ref:
        return None
    ref_name = ref.rsplit("/", 1)[-1]
    ref_schema = schemas.get(ref_name)
    if not isinstance(ref_schema, dict):
        return None
    return _normalize_enum(ref_schema.get("enum"))


def _room_ensure_server_ready(server_label: str, server: str) -> None:
    print(f"Checking cloud server status ({server_label})...", flush=True)
    if _room_server_online(server):
        print("Cloud server is online.", flush=True)
        return

    print("Cloud server is getting ready...", flush=True)
    for _ in range(3):
        time.sleep(1.5)
        if _room_server_online(server):
            print("Cloud server is ready.", flush=True)
            return

    raise RuntimeError(
        "Unfortunately, the cloud server is not available for the moment. "
        "Please try again later."
    )


def _room_ws_base(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    force_tls = host.endswith(".run.app")
    if scheme == "https":
        parsed = parsed._replace(scheme="wss")
    elif scheme == "http":
        parsed = parsed._replace(scheme="wss" if force_tls else "ws")
    elif scheme == "ws" and force_tls:
        parsed = parsed._replace(scheme="wss")
    return urllib.parse.urlunparse(parsed).rstrip("/")


def _room_ws_url_with_auth(ws_base: str, room_code: str, player_id: str, token: str) -> str:
    parsed = urllib.parse.urlparse(_room_ws_base(ws_base))
    path = parsed.path or f"/rooms/{room_code}/ws"
    if not path.endswith("/ws"):
        path = f"/rooms/{room_code}/ws"
    query = urllib.parse.urlencode({"player_id": player_id, "token": token})
    return urllib.parse.urlunparse(parsed._replace(path=path, query=query))


def _room_http_error(exc: urllib.error.HTTPError) -> str:
    def _format_detail(detail: object) -> str:
        if isinstance(detail, list):
            parts: list[str] = []
            for item in detail:
                if isinstance(item, dict):
                    message = str(item.get("msg") or item.get("message") or "").strip()
                    location = item.get("loc")
                    if isinstance(location, (list, tuple)) and location:
                        location_text = ".".join(str(x) for x in location)
                        if message:
                            parts.append(f"{location_text}: {message}")
                            continue
                    if message:
                        parts.append(message)
                        continue
                parts.append(str(item))
            return "; ".join(part for part in parts if part) or str(detail)
        return str(detail)

    status = getattr(exc, "code", "HTTP error")
    body = ""
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        body = ""
    detail = body
    if body:
        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                detail = _format_detail(payload.get("detail") or payload)
        except Exception:
            detail = body
    else:
        detail = str(exc.reason or "request failed")
    return f"{status} {detail}"


def _room_join_role_unsupported(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    if "body.role" not in lowered and " role" not in lowered and "role " not in lowered:
        return False
    indicators = (
        "extra inputs are not permitted",
        "extra_forbidden",
        "unexpected field",
        "unexpected keyword",
        "not permitted",
    )
    return any(token in lowered for token in indicators)


def _room_join_token_unsupported(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    if "room_token" not in lowered:
        return False
    indicators = (
        "extra inputs are not permitted",
        "extra_forbidden",
        "unexpected field",
        "unexpected keyword",
        "not permitted",
    )
    return any(token in lowered for token in indicators)


def _room_join_missing_token(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    if "room_token" not in lowered and "room token" not in lowered:
        return False
    indicators = (
        "field required",
        "missing",
        "string should have at least",
        "string_too_short",
        "too_short",
        "token is required",
    )
    return any(token in lowered for token in indicators)


def _room_post_json(url: str, payload: dict, timeout: int = 20) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Request failed: {_room_http_error(exc)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Server returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Server returned unexpected response.")
    return parsed


def _room_get_json(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Request failed: {_room_http_error(exc)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Server returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Server returned unexpected response.")
    return parsed


def _room_info_request(*, server: str, room_ref: str) -> dict:
    quoted = urllib.parse.quote(room_ref.strip().lower(), safe="")
    return _room_get_json(f"{_room_http_base(server)}/join/{quoted}")


def _room_create_request(
    *,
    server: str,
    mode: str,
    room_name: str,
    host_name: str,
    host_role: str = "",
    token_required: bool = False,
    quiz_title: str,
    questions: list[dict],
) -> dict:
    payload = {
        "mode": mode,
        "room_name": room_name,
        "quiz_title": quiz_title,
        "host_name": host_name,
        "questions": questions,
    }
    if host_role:
        payload["host_role"] = host_role
    payload["token_required"] = token_required
    return _room_post_json(
        f"{_room_http_base(server)}/rooms",
        payload,
    )


def _room_join_by_name_request(
    *,
    server: str,
    room_name: str,
    room_token: str = "",
    player_name: str,
    role: str = "",
) -> dict:
    quoted = urllib.parse.quote(room_name.strip().lower(), safe="")
    payload = {"player_name": player_name}
    if room_token:
        payload["room_token"] = room_token
    if role:
        payload["role"] = role
    return _room_post_json(
        f"{_room_http_base(server)}/rooms/by-name/{quoted}/join",
        payload,
    )


def _room_random_player_name() -> str:
    adjectives = ("Sneaky", "Curious", "Quick", "Brave", "Calm", "Happy", "Sharp", "Wise")
    animals = ("Fox", "Panda", "Otter", "Falcon", "Tiger", "Whale", "Koala", "Llama")
    return f"{random.choice(adjectives)} {random.choice(animals)}"


def _room_normalize_name(raw: str) -> str:
    candidate = raw.lower().strip()
    candidate = re.sub(r"[^a-z0-9]+", "-", candidate)
    candidate = re.sub(r"-+", "-", candidate).strip("-")
    return candidate


def _room_validate_name(raw: str, field_name: str = "room name") -> str:
    normalized = _room_normalize_name(raw)
    if not normalized:
        raise RuntimeError(f"Invalid {field_name}. Use letters/numbers/hyphens only.")
    if len(normalized) < ROOM_NAME_MIN_LEN:
        raise RuntimeError(f"Invalid {field_name}. Minimum length is {ROOM_NAME_MIN_LEN} characters.")
    if len(normalized) > ROOM_NAME_MAX_LEN:
        raise RuntimeError(f"Invalid {field_name}. Maximum length is {ROOM_NAME_MAX_LEN} characters.")
    return normalized


def _room_generate_name() -> str:
    while True:
        candidate = f"{random.choice(ROOM_NAME_CITIES)}-{random.choice(ROOM_NAME_ANIMALS)}-{random.randint(1, 9)}"
        if ROOM_NAME_MIN_LEN <= len(candidate) <= ROOM_NAME_MAX_LEN:
            return candidate


def _room_prompt_token_required() -> bool:
    if not sys.stdin.isatty():
        return False
    while True:
        raw = prompt_input("Require room token for joiners? [y/N]: ").strip().lower()
        if not raw:
            return False
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please answer y or n.")


def _room_validate_json_question(question: dict, source: Path, index: int) -> dict:
    title = str(question.get("title") or f"Question {index}").strip()
    text = str(question.get("question") or "").strip()
    options_raw = question.get("options")
    correct_raw = question.get("correct")
    qtype = str(question.get("type") or "single").strip().lower()
    time_raw = question.get("time_limit", 30)
    discussion_raw = question.get("discussion_time", None)

    if not text:
        raise ValueError(f"{source}: question {index} is missing non-empty 'question' text")
    if not isinstance(options_raw, list):
        raise ValueError(f"{source}: question {index} has invalid 'options' (must be a list)")
    options = [str(item).strip() for item in options_raw]
    if len(options) < 2:
        raise ValueError(f"{source}: question {index} must have at least 2 options")
    if any(not option for option in options):
        raise ValueError(f"{source}: question {index} contains blank options")
    if not isinstance(correct_raw, list) or not correct_raw:
        raise ValueError(f"{source}: question {index} requires non-empty 'correct' indexes")
    try:
        correct = [int(value) for value in correct_raw]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source}: question {index} has non-integer values in 'correct'") from exc

    try:
        time_limit = int(time_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source}: question {index} has invalid 'time_limit' value {time_raw!r}") from exc
    if time_limit < ROOM_MIN_TIME_LIMIT_SECONDS:
        raise ValueError(
            f"{source}: question {index} has invalid 'time_limit' value {time_limit}. "
            f"Room mode requires Time/time_limit >= {ROOM_MIN_TIME_LIMIT_SECONDS} seconds."
        )

    discussion_time = None
    if discussion_raw not in (None, ""):
        try:
            discussion_time = int(discussion_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{source}: question {index} has invalid 'discussion_time' value {discussion_raw!r}"
            ) from exc
        if discussion_time < 0:
            raise ValueError(
                f"{source}: question {index} has invalid 'discussion_time' value {discussion_time}. "
                "discussion_time must be >= 0 seconds."
            )

    normalized = {
        "title": title or f"Question {index}",
        "question": text,
        "options": options,
        "correct": correct,
        "type": qtype,
        "time_limit": time_limit,
        "discussion_time": discussion_time,
        "explanation": str(question.get("explanation") or "").strip(),
    }
    validate_question(normalized, source)
    return normalized


def _room_quiz_payload_from_json(path: str) -> tuple[str, list[dict]]:
    source = Path(path)
    content = source.read_text(encoding="utf-8")
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("JSON quiz file must be an object with quiz_title and questions.")
    title = str(payload.get("quiz_title") or "").strip()
    questions = payload.get("questions")
    if not title:
        raise ValueError("JSON quiz file requires non-empty quiz_title.")
    if not isinstance(questions, list) or not questions:
        raise ValueError("JSON quiz file requires non-empty questions list.")
    normalized = []
    for idx, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            raise ValueError(f"{source}: question {idx} must be an object")
        normalized.append(_room_validate_json_question(q, source, idx))
    return title, normalized


def _room_quiz_payload_from_markdown(path: str) -> tuple[str, list[dict]]:
    title, questions = parse_quiz_markdown(path)
    normalized = []
    for idx, q in enumerate(questions, start=1):
        row = (
            {
                "title": str(q.get("title") or "Question").strip(),
                "question": str(q.get("question") or "").strip(),
                "options": list(q.get("options") or []),
                "correct": [int(x) for x in list(q.get("correct") or [])],
                "type": str(q.get("type") or "single"),
                "time_limit": int(q.get("time_limit") or 30),
                "explanation": str(q.get("explanation") or "").strip(),
            }
        )
        if row["time_limit"] < ROOM_MIN_TIME_LIMIT_SECONDS:
            source = Path(path)
            raise ValueError(
                f"{source}: question {idx} has invalid Time value {row['time_limit']}. "
                f"Room mode requires Time/time_limit >= {ROOM_MIN_TIME_LIMIT_SECONDS} seconds."
            )
        normalized.append(row)
    return title, normalized


def _room_load_quiz_payload(path: str | None) -> tuple[str, list[dict]]:
    if not path:
        return ROOM_SAMPLE_QUIZ_TITLE, json.loads(json.dumps(ROOM_SAMPLE_QUESTIONS))

    quiz_path = Path(path).expanduser()
    if not quiz_path.exists():
        raise RuntimeError(f"Quiz file not found: {quiz_path}")

    if quiz_path.suffix.lower() == ".json":
        try:
            return _room_quiz_payload_from_json(str(quiz_path))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Invalid JSON quiz file: {exc}") from exc

    mode = detect_quiz_mode(str(quiz_path))
    if mode == "essay":
        raise RuntimeError("Essay files are not supported for room mode. Use a multiple-choice quiz file.")
    try:
        return _room_quiz_payload_from_markdown(str(quiz_path))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Invalid markdown quiz file: {exc}") from exc


def _room_connected_players(payload: dict) -> list[dict[str, str]]:
    players = payload.get("players", [])
    if not isinstance(players, list):
        return []
    connected: list[dict[str, str]] = []
    for row in players:
        if not isinstance(row, dict) or not row.get("connected"):
            continue
        name = str(row.get("name") or "Unknown")
        role = str(row.get("role") or "participant").lower()
        connected.append({"name": name, "role": role})
    connected.sort(key=lambda row: row["name"].lower())
    return connected


def _room_player_label(name: str, role: str) -> str:
    if role in {"teacher", "student"}:
        return f"{name} ({role})"
    return name


def _save_room_session_transcript(
    *,
    room_name: str,
    mode: str,
    display_name: str,
    role: str,
    transcript: list[dict[str, object]],
    final_score: int | None,
    scored_by: str,
    ended_by: str,
    ended_by_role: str,
) -> Path:
    root = Path("answers") / "room-sessions"
    root.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    file_base = f"{slugify(room_name)}-{slugify(display_name)}-{ts}"
    out = root / f"{file_base}.json"
    counter = 2
    while out.exists():
        out = root / f"{file_base}-{counter}.json"
        counter += 1

    payload = {
        "room_name": room_name,
        "mode": mode,
        "participant": {
            "name": display_name,
            "role": role or "participant",
        },
        "final_score": final_score,
        "scored_by": scored_by,
        "ended_by": ended_by,
        "ended_by_role": ended_by_role,
        "events": transcript,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _select_with_space(
    title: str,
    options: list[tuple[str, str]],
    *,
    theme_name: str,
    no_color: bool,
) -> str:
    if not options:
        raise RuntimeError("No options available.")

    try:
        from prompt_toolkit import Application
        from prompt_toolkit.formatted_text import HTML as PromptHTML
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
    except ModuleNotFoundError:
        print(title)
        for idx, (label, _) in enumerate(options, start=1):
            print(f"  {idx}. {label}")
        while True:
            raw = prompt_input("Select option number: ").strip()
            if raw.isdigit():
                pos = int(raw)
                if 1 <= pos <= len(options):
                    return options[pos - 1][1]

    theme = select_theme(theme_name)
    selected = 0
    chosen = 0

    def render():
        lines = [
            f"<style fg='{theme['pt_title']}'><b>{html.escape(title)}</b></style>",
            f"<style fg='{theme['pt_instruction']}'>Use ↑/↓, Space to select, Enter to confirm.</style>",
            "",
        ]
        for idx, (label, _) in enumerate(options):
            pointer = "&gt;" if idx == selected else " "
            marker = "[x]" if idx == chosen else "[ ]"
            if no_color:
                lines.append(f"{'>' if idx == selected else ' '} {marker} {label}")
            else:
                style = (
                    f"fg='{theme['pt_selected_fg']}' bg='{theme['pt_selected_bg']}'"
                    if idx == selected
                    else f"fg='{theme['pt_primary']}'"
                )
                lines.append(f"<style {style}>{pointer} {html.escape(marker)} {html.escape(label)}</style>")
        markup = "\n".join(lines)
        return markup if no_color else PromptHTML(markup)

    control = FormattedTextControl(text=render)
    window = Window(content=control, wrap_lines=True, always_hide_cursor=True)
    kb = KeyBindings()

    @kb.add("up")
    def _(_event):
        nonlocal selected
        selected = (selected - 1) % len(options)
        control.text = render()

    @kb.add("down")
    def _(_event):
        nonlocal selected
        selected = (selected + 1) % len(options)
        control.text = render()

    @kb.add("space")
    def _(_event):
        nonlocal chosen
        chosen = selected
        control.text = render()

    @kb.add("enter")
    def _(event):
        event.app.exit(result=options[chosen][1])

    @kb.add("c-c")
    def _(event):
        event.app.exit(exception=KeyboardInterrupt())

    app = Application(layout=Layout(HSplit([window])), key_bindings=kb, full_screen=False)
    try:
        return app.run()
    except Exception:
        print(title)
        for idx, (label, _) in enumerate(options, start=1):
            print(f"  {idx}. {label}")
        while True:
            raw = prompt_input("Select option number: ").strip()
            if raw.isdigit():
                pos = int(raw)
                if 1 <= pos <= len(options):
                    return options[pos - 1][1]


def _read_lobby_line_nonblocking(timeout: float = 0.15) -> str | None:
    if not sys.stdin or not hasattr(sys.stdin, "fileno"):
        return None
    if os.name == "nt":
        return None
    try:
        import select
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
    except (OSError, ValueError):
        return None
    if not ready:
        return None
    line = sys.stdin.readline()
    if line == "":
        raise RuntimeError("Interactive input is not available in this environment.")
    return line.rstrip("\r\n")


async def _run_room_waiting_loop(
    *,
    ws_base: str,
    room_code: str,
    player_id: str,
    token: str,
    display_name: str,
    room_name: str,
    is_host: bool,
    room_mode: str,
    player_role: str,
    theme_name: str,
    no_color: bool,
    full_screen: bool,
) -> int:
    try:
        import websockets
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Room mode requires 'websockets'. Reinstall quizmd to get multiplayer dependencies."
        ) from exc

    ws_url = _room_ws_url_with_auth(ws_base, room_code, player_id, token)
    theme = select_theme(theme_name)
    boxing_mode = room_mode == "boxing"
    connected_players: list[dict[str, str]] = []
    known_connected: set[tuple[str, str]] = set()
    resolved_player_role = (player_role or "participant").lower()
    in_quiz = False
    session_started = False
    final_score: int | None = None
    scored_by = ""
    ended_by = ""
    ended_by_role = ""
    stop = asyncio.Event()
    current_question_index: int | None = None
    current_total_questions = 0
    current_mode = room_mode
    current_phase = ""
    pending_question_payload: dict[str, object] | None = None
    prompted_rounds: set[tuple[int, int]] = set()
    transcript: list[dict[str, object]] = []

    def _record(event_type: str, payload: dict[str, object]) -> None:
        transcript.append(
            {
                "type": event_type,
                "ts": time.time(),
                "payload": payload,
            }
        )

    async def _prompt_and_submit_answer(
        *,
        q_payload: dict[str, object],
        question_index: int,
        total_questions: int,
        deadline_epoch: float | None,
    ) -> None:
        nonlocal in_quiz
        round_key = (question_index, int(deadline_epoch or 0))
        if round_key in prompted_rounds:
            return
        prompted_rounds.add(round_key)

        q = {
            "title": f"Question {question_index + 1}",
            "question": str(q_payload.get("question") or ""),
            "options": list(q_payload.get("options") or []),
            "correct": [-1],
            "type": "multiple" if str(q_payload.get("type") or "single") == "multiple" else "single",
            "time_limit": int(q_payload.get("time_limit") or 30),
            "explanation": "",
            "imposters": [],
        }
        in_quiz = True
        try:
            _perfect, answers, _imposters, _grading = await ask_question(
                q,
                theme,
                question_index=question_index + 1,
                total_questions=max(1, total_questions),
                no_color=no_color,
                compact=False,
                full_screen=full_screen,
            )
        except KeyboardInterrupt:
            await ws.send(json.dumps({"type": "leave_room", "payload": {}}))
            stop.set()
            return
        finally:
            in_quiz = False

        if answers:
            await ws.send(
                json.dumps(
                    {
                        "type": "submit_answer",
                        "payload": {"question_index": question_index, "answers": answers},
                    }
                )
            )
        else:
            print("No answer submitted. Waiting for round result...")
        _record(
            "answer_submitted",
            {
                "question_index": question_index,
                "answers": answers,
            },
        )

    try:
        ws_context = websockets.connect(ws_url, open_timeout=10, close_timeout=5)
    except Exception as exc:
        raise RuntimeError(f"Could not connect to room websocket: {exc}") from exc

    try:
        ws = await ws_context.__aenter__()
    except Exception as exc:
        raise RuntimeError(f"Could not connect to room websocket: {exc}") from exc

    try:
        print("")
        print(f"Connected as {display_name}.")
        print(f'Share "{room_name}" with your friends.')
        if is_host:
            print("Type /start when you are ready.")
        print("Chat enabled. Type message and press Enter.")
        if boxing_mode:
            print("Commands: /start (host), /players, /score <0-100> (teacher), /end, /help, /quit")
        else:
            print("Commands: /start (host), /players, /help, /quit")
        await ws.send(json.dumps({"type": "ready_toggle", "payload": {"ready": True}}))

        async def recv_loop():
            nonlocal connected_players
            nonlocal known_connected
            nonlocal resolved_player_role
            nonlocal in_quiz
            nonlocal session_started
            nonlocal current_question_index
            nonlocal current_total_questions
            nonlocal current_mode
            nonlocal current_phase
            nonlocal pending_question_payload
            nonlocal final_score
            nonlocal scored_by
            nonlocal ended_by
            nonlocal ended_by_role
            while not stop.is_set():
                try:
                    raw = await ws.recv()
                except Exception:
                    if not stop.is_set():
                        print("Disconnected from room server.")
                        _record("disconnected", {"reason": "websocket closed"})
                    stop.set()
                    return
                try:
                    event = json.loads(raw)
                except Exception:
                    continue
                etype = event.get("type")
                payload = event.get("payload", {})

                if etype == "chat_message":
                    sender = payload.get("from", "Unknown")
                    text = payload.get("text", "")
                    sender_role = str(payload.get("from_role") or "participant")
                    print(f"[{sender}] {text}")
                    _record("chat_message", {"from": str(sender), "from_role": sender_role, "text": str(text)})
                    continue

                if etype in {"connected", "lobby_update"}:
                    rows = payload.get("players", [])
                    if isinstance(rows, list):
                        for row in rows:
                            if not isinstance(row, dict):
                                continue
                            if str(row.get("player_id") or "") == player_id:
                                resolved_player_role = str(row.get("role") or resolved_player_role).lower()
                    connected_players = _room_connected_players(payload)
                    current_set = {(row["name"], row["role"]) for row in connected_players}
                    for name, role in sorted(current_set - known_connected, key=lambda pair: pair[0].lower()):
                        print(f"{_room_player_label(name, role)} joined.")
                        _record("player_joined", {"name": name, "role": role})
                    for name, role in sorted(known_connected - current_set, key=lambda pair: pair[0].lower()):
                        print(f"{_room_player_label(name, role)} left.")
                        _record("player_left", {"name": name, "role": role})
                    known_connected = current_set
                    continue

                if etype == "error":
                    print(f"Server: {payload.get('message', 'Unknown error')}")
                    _record("error", {"message": str(payload.get("message", "Unknown error"))})
                    continue

                if etype == "game_started":
                    if boxing_mode:
                        session_started = True
                        print("Ready to start!")
                        print("Session is live. Teacher can ask the first question.")
                    else:
                        in_quiz = False
                        print("Game is starting now.")
                    _record("game_started", {"mode": room_mode})
                    continue

                if etype == "question":
                    if boxing_mode:
                        continue
                    current_mode = str(payload.get("mode") or current_mode or "compete")
                    q_payload = payload.get("question", {})
                    current_question_index = int(payload.get("question_index", 0))
                    current_total_questions = int(payload.get("total_questions", 0))
                    pending_question_payload = {
                        "question": q_payload if isinstance(q_payload, dict) else {},
                        "question_index": current_question_index,
                        "total_questions": current_total_questions,
                    }
                    phase = str(payload.get("phase") or "voting").lower()
                    deadline_epoch = payload.get("deadline_epoch")
                    if current_mode == "collaborate" and phase == "discussion":
                        current_phase = "discussion"
                        continue
                    if current_mode == "collaborate":
                        current_phase = "voting"
                    await _prompt_and_submit_answer(
                        q_payload=pending_question_payload["question"],
                        question_index=current_question_index,
                        total_questions=max(1, current_total_questions),
                        deadline_epoch=float(deadline_epoch or 0),
                    )
                    continue

                if etype == "phase_changed":
                    if boxing_mode:
                        continue
                    phase = str(payload.get("phase") or "").lower()
                    qidx = int(payload.get("question_index", current_question_index or 0))
                    if current_mode != "collaborate":
                        continue
                    if phase and phase == current_phase:
                        continue
                    if phase == "discussion":
                        current_phase = "discussion"
                        seconds = int(payload.get("discussion_seconds") or 0)
                        print(f"Discussion phase ({seconds}s). Chat now; voting opens next.")
                        _record(
                            "phase_changed",
                            {
                                "phase": "discussion",
                                "question_index": qidx,
                                "seconds": seconds,
                            },
                        )
                        continue
                    if phase == "voting":
                        current_phase = "voting"
                        print("Voting phase started. Submit your answer now.")
                        _record(
                            "phase_changed",
                            {
                                "phase": "voting",
                                "question_index": qidx,
                            },
                        )
                        if pending_question_payload and int(pending_question_payload.get("question_index", -1)) == qidx:
                            await _prompt_and_submit_answer(
                                q_payload=pending_question_payload.get("question", {}),
                                question_index=qidx,
                                total_questions=max(1, int(pending_question_payload.get("total_questions", 0))),
                                deadline_epoch=float(payload.get("deadline_epoch") or 0),
                            )
                        continue

                if etype == "round_result":
                    if boxing_mode:
                        continue
                    in_quiz = False
                    qidx = int(payload.get("question_index", -1))
                    print("")
                    print(f"Round {qidx + 1} result:")
                    players = payload.get("players", [])
                    if isinstance(players, list):
                        for row in players:
                            name = row.get("name", "Unknown")
                            mark = "correct" if bool(row.get("is_correct", False)) else "wrong"
                            delta = row.get("delta")
                            score = row.get("score")
                            if delta is not None and score is not None:
                                print(f"  - {name}: {mark}, delta={delta}, score={score}")
                            else:
                                print(f"  - {name}: {mark}")
                    _record("round_result", {"payload": payload})
                    continue

                if etype == "consensus_retry":
                    if boxing_mode:
                        continue
                    in_quiz = False
                    print("")
                    print(payload.get("message", "Not consensus, try again"))
                    wrong = payload.get("wrong_names", [])
                    missing = payload.get("missing_names", [])
                    if wrong:
                        print("Wrong answers from: " + ", ".join(wrong))
                    if missing:
                        print("Missing answers from: " + ", ".join(missing))
                    _record("consensus_retry", {"payload": payload})
                    continue

                if etype == "scoreboard":
                    if boxing_mode:
                        continue
                    print("")
                    print("Scoreboard:")
                    players = payload.get("players", [])
                    if isinstance(players, list):
                        for row in players:
                            print(f"  - {row.get('name', 'Unknown')}: {row.get('score', 0)}")
                    _record("scoreboard", {"payload": payload})
                    continue

                if etype == "boxing_score":
                    score_value = payload.get("score")
                    score_by = str(payload.get("by") or "Teacher")
                    if score_value is not None:
                        print(f"Score updated: {score_value}% (by {score_by}).")
                    else:
                        print(f"Score updated by {score_by}.")
                    _record(
                        "boxing_score",
                        {
                            "score": score_value,
                            "by": score_by,
                            "by_role": str(payload.get("by_role") or ""),
                        },
                    )
                    continue

                if etype == "game_finished":
                    print("")
                    if boxing_mode:
                        print("Session ended.")
                    else:
                        print("Game finished.")
                    reason = payload.get("reason")
                    if reason:
                        print(f"Reason: {reason}")
                    score_payload = payload.get("final_score")
                    if isinstance(score_payload, int):
                        final_score = score_payload
                        print(f"Final score: {final_score}%")
                    scored_by = str(payload.get("scored_by") or "")
                    ended_by = str(payload.get("ended_by") or "")
                    ended_by_role = str(payload.get("ended_by_role") or "")
                    _record("game_finished", {"payload": payload})
                    stop.set()
                    return

        recv_task = asyncio.create_task(recv_loop())
        try:
            while not stop.is_set():
                if in_quiz and not boxing_mode:
                    await asyncio.sleep(0.1)
                    continue
                if os.name == "nt":
                    try:
                        text = (await asyncio.to_thread(prompt_input, "")).strip()
                    except RuntimeError:
                        stop.set()
                        break
                else:
                    try:
                        line = _read_lobby_line_nonblocking(timeout=0.15)
                    except RuntimeError:
                        print("Input stream closed. Leaving room...")
                        try:
                            await ws.send(json.dumps({"type": "leave_room", "payload": {}}))
                        except Exception:
                            pass
                        stop.set()
                        break
                    if line is None:
                        await asyncio.sleep(0.05)
                        continue
                    text = line.strip()

                if not text:
                    continue
                if text == "/quit":
                    await ws.send(json.dumps({"type": "leave_room", "payload": {}}))
                    stop.set()
                    break
                if text == "/players":
                    if connected_players:
                        labels = [_room_player_label(row["name"], row["role"]) for row in connected_players]
                        print("Connected: " + ", ".join(labels))
                    else:
                        print("No connected players shown yet.")
                    continue
                if text == "/help":
                    if boxing_mode:
                        print("Commands: /start (host), /players, /score <0-100> (teacher), /end, /help, /quit")
                    else:
                        print("Commands: /start (host), /players, /help, /quit")
                    continue
                if text == "/start":
                    if not is_host:
                        print("Only the room host can start.")
                        continue
                    await ws.send(json.dumps({"type": "ready_toggle", "payload": {"ready": True}}))
                    await asyncio.sleep(0.15)
                    await ws.send(json.dumps({"type": "start_game", "payload": {}}))
                    print("Start requested...")
                    continue
                if boxing_mode and text.startswith("/score"):
                    if resolved_player_role != "teacher":
                        print("Only the teacher can use /score.")
                        continue
                    match = re.match(r"^/score\s+(-?\d+)\s*$", text)
                    if not match:
                        print("Usage: /score <0-100>")
                        continue
                    score_value = int(match.group(1))
                    await ws.send(json.dumps({"type": "set_score", "payload": {"score": score_value}}))
                    continue
                if boxing_mode and text == "/end":
                    await ws.send(
                        json.dumps(
                            {
                                "type": "end_session",
                                "payload": {"reason": "Session ended by participant."},
                            }
                        )
                    )
                    continue

                await ws.send(json.dumps({"type": "chat_message", "payload": {"text": text}}))
        finally:
            stop.set()
            recv_task.cancel()
            try:
                await recv_task
            except asyncio.CancelledError:
                pass
    finally:
        try:
            await ws_context.__aexit__(None, None, None)
        except Exception:
            pass
    if boxing_mode:
        transcript_path = _save_room_session_transcript(
            room_name=room_name,
            mode=room_mode,
            display_name=display_name,
            role=resolved_player_role,
            transcript=transcript,
            final_score=final_score,
            scored_by=scored_by,
            ended_by=ended_by,
            ended_by_role=ended_by_role,
        )
        print(f"Session transcript saved: {transcript_path}")
    return 0


def run_room_command(args: argparse.Namespace) -> int:
    no_color = is_no_color_requested(args.no_color)
    theme_name = args.theme
    requested_role = str(args.role or "").strip().lower()
    if requested_role and requested_role not in {"teacher", "student"}:
        raise RuntimeError("Invalid role. Use --role teacher or --role student.")

    server_label, server = _room_resolve_server(
        explicit_server=str(args.server or ""),
        theme_name=theme_name,
        no_color=no_color,
    )
    _room_ensure_server_ready(server_label, server)
    if args.server or len(_room_configured_servers()) > 1:
        print(f"Using server: {server_label} ({server})", flush=True)

    if args.create is not None:
        requested_name = "" if args.create == "__AUTO__" else str(args.create)
        supported_modes = _room_supported_modes(server)
        mode_choices = [
            ("Compete", "compete"),
            ("Collaborate", "collaborate"),
            ("Boxing (Teacher/Student Chat)", "boxing"),
        ]
        if supported_modes:
            mode_choices = [choice for choice in mode_choices if choice[1] in supported_modes]
        if not mode_choices:
            raise RuntimeError(
                "This cloud server did not report any supported room modes. "
                "Please try again later or check server deployment."
            )

        mode = args.mode or _select_with_space(
            "Mode:",
            mode_choices,
            theme_name=theme_name,
            no_color=no_color,
        )
        if supported_modes and mode not in supported_modes:
            supported_text = ", ".join(sorted(supported_modes))
            raise RuntimeError(
                f"Selected mode '{mode}' is not supported by this cloud server yet. "
                f"Supported modes: {supported_text}. "
                "Please deploy/update quizmd-server or choose another mode."
            )
        host_role = requested_role
        if mode == "boxing" and not host_role:
            host_role = _select_with_space(
                "Your role in this boxing room:",
                [("Teacher", "teacher"), ("Student", "student")],
                theme_name=theme_name,
                no_color=no_color,
            )
        if mode != "boxing":
            host_role = ""
        if getattr(args, "require_token", False):
            token_required = True
        elif getattr(args, "no_token", False):
            token_required = False
        else:
            token_required = _room_prompt_token_required()
        host_name = (args.name or "").strip()
        if not host_name:
            suggested = _room_random_player_name()
            host_name = prompt_input(f"Enter name [{suggested}]: ").strip() or suggested
        auto_room_name = not requested_name.strip()
        room_name = _room_validate_name(requested_name) if requested_name.strip() else _room_generate_name()
        quiz_title, questions = _room_load_quiz_payload(args.quiz)
        created = None
        for _attempt in range(6):
            print(f"Room name: {room_name}")
            try:
                created = _room_create_request(
                    server=server,
                    mode=mode,
                    room_name=room_name,
                    host_name=host_name,
                    host_role=host_role,
                    token_required=token_required,
                    quiz_title=quiz_title,
                    questions=questions,
                )
                break
            except RuntimeError as exc:
                error_text = str(exc)
                if auto_room_name and "409" in error_text:
                    room_name = _room_generate_name()
                    continue
                if not auto_room_name and "409" in error_text and "already exists" in error_text.lower():
                    raise RuntimeError(f'Room name "{room_name}" already exists. Try another name.') from exc
                raise
        if created is None:
            raise RuntimeError("Could not create a unique room name. Please retry.")
        print("")
        print(f"Room created by: {created.get('host_display_name', host_name)}")
        print(f"Room name: {created.get('room_name', room_name)}")
        token_required = bool(created.get("token_required", token_required))
        room_token = str(created.get("room_token") or "").strip()
        if token_required and room_token:
            print(f"Room token: {room_token}")
        if mode == "boxing":
            role_label = str(created.get("host_role") or host_role or "teacher")
            print(f"Role: {role_label}")
        print(f"Quiz: {quiz_title} ({len(questions)} questions)")
        if not args.quiz:
            print("Tip: use --quiz filename to load your quiz.")
        print(f'Share "{created.get("room_name", room_name)}" with your friends.')
        if token_required and room_token:
            share_command = (
                f'quizmd room --join "{created.get("room_name", room_name)}" '
                f'--token "{room_token}" --name "FriendName"'
            )
        else:
            share_command = (
                f'quizmd room --join "{created.get("room_name", room_name)}" '
                f'--name "FriendName"'
            )
        print(f"Join command: {share_command}")
        print("Ready and waiting. Share the room name with your friends.")
        return asyncio.run(
            _run_room_waiting_loop(
                ws_base=str(created.get("ws_url") or _room_ws_base(server)),
                room_code=str(created.get("room_code") or ""),
                player_id=str(created.get("host_player_id") or ""),
                token=str(created.get("host_player_token") or ""),
                display_name=str(created.get("host_display_name") or host_name),
                room_name=str(created.get("room_name") or room_name),
                is_host=True,
                room_mode=str(created.get("mode") or mode),
                player_role=str(created.get("host_role") or host_role or "participant"),
                theme_name=theme_name,
                no_color=no_color,
                full_screen=args.full_screen,
            )
        )

    room_name = _room_validate_name(str(args.join or ""))
    player_name = (args.name or "").strip()
    if not player_name:
        suggested = _room_random_player_name()
        player_name = prompt_input(f"Enter name [{suggested}]: ").strip() or suggested

    join_role = requested_role
    room_info = {}
    try:
        room_info = _room_info_request(server=server, room_ref=room_name)
    except RuntimeError:
        room_info = {}
    token_required = bool(room_info.get("token_required", False))
    room_token = str(getattr(args, "token", "") or "").strip()
    if token_required and not room_token:
        room_token = prompt_input("Enter room token: ").strip()
    if token_required and not room_token:
        raise RuntimeError("Room token is required to join this room.")

    detected_mode = str(room_info.get("mode") or "").lower()
    if detected_mode == "boxing":
        if not join_role:
            join_role = _select_with_space(
                "Your role in this boxing room:",
                [("Teacher", "teacher"), ("Student", "student")],
                theme_name=theme_name,
                no_color=no_color,
            )
    elif detected_mode and join_role:
        # Keep compatibility with users passing --role on non-boxing rooms.
        print("Role flag ignored: this room is not in boxing mode.")
        join_role = ""

    attempt_plan: list[tuple[str, str]] = [(room_token, join_role)]
    if join_role:
        attempt_plan.append((room_token, ""))
    if room_token:
        attempt_plan.append(("", join_role))
    if room_token and join_role:
        attempt_plan.append(("", ""))
    seen_attempts: set[tuple[str, str]] = set()
    attempts: list[tuple[str, str]] = []
    for item in attempt_plan:
        if item in seen_attempts:
            continue
        seen_attempts.add(item)
        attempts.append(item)

    joined = None
    last_error: RuntimeError | None = None
    while attempts:
        attempt_token, attempt_role = attempts.pop(0)
        try:
            joined = _room_join_by_name_request(
                server=server,
                room_name=room_name,
                room_token=attempt_token,
                player_name=player_name,
                role=attempt_role,
            )
            break
        except RuntimeError as exc:
            last_error = exc
            error_text = str(exc)
            if not room_token and _room_join_missing_token(error_text):
                prompted = prompt_input("Enter room token: ").strip()
                if not prompted:
                    raise RuntimeError("Room token is required to join this room.") from exc
                room_token = prompted
                fresh_plan: list[tuple[str, str]] = [(room_token, join_role)]
                if join_role:
                    fresh_plan.append((room_token, ""))
                fresh_plan.append(("", join_role))
                if join_role:
                    fresh_plan.append(("", ""))
                attempts = []
                seen_attempts = set()
                for item in fresh_plan:
                    if item in seen_attempts:
                        continue
                    seen_attempts.add(item)
                    attempts.append(item)
                continue
            if attempt_role and _room_join_role_unsupported(error_text):
                print("Server compatibility mode: retrying join without role field.")
                continue
            if attempt_token and _room_join_token_unsupported(error_text):
                print("Server compatibility mode: retrying join without room token field.")
                continue
            raise
    if joined is None:
        if last_error is not None:
            raise last_error
        raise RuntimeError("Could not join room due to an unexpected error.")
    print(f'Joined room "{joined.get("room_name", room_name)}" as {joined.get("display_name", player_name)}.')
    if str(joined.get("mode") or room_info.get("mode") or "").lower() == "boxing":
        joined_role = str(joined.get("player_role") or join_role or "participant")
        print(f"Role: {joined_role}")
    return asyncio.run(
        _run_room_waiting_loop(
            ws_base=str(joined.get("ws_url") or _room_ws_base(server)),
            room_code=str(joined.get("room_code") or ""),
            player_id=str(joined.get("player_id") or ""),
            token=str(joined.get("player_token") or ""),
            display_name=str(joined.get("display_name") or player_name),
            room_name=str(joined.get("room_name") or room_name),
            is_host=False,
            room_mode=str(joined.get("mode") or room_info.get("mode") or "compete"),
            player_role=str(joined.get("player_role") or join_role or "participant"),
            theme_name=theme_name,
            no_color=no_color,
            full_screen=args.full_screen,
        )
    )


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
        result_label = item.get("result_label")
        if not result_label:
            result_label = "Correct" if item.get("is_correct") else "Wrong"
        lines.extend([
            item["question_title"],
            item["question_text"],
            f"Selected: {item['selected_labels'] or 'No answer'}",
            f"Correct: {item['correct_labels']}",
            f"Imposters flagged: {imposter_selected or '-'}",
            f"Expected imposters: {imposter_expected or '-'}",
            f"Result: {result_label}",
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


def collect_essay_answer_inline(question_title: str, question_text: str = "") -> str:
    """Collect a short essay directly in the terminal for the vNext prototype."""
    print("")
    print("Type your answer below.")
    print("Write 4-8 lines. Type /end on a new line when finished.")
    print("")
    lines: list[str] = []
    while True:
        line = prompt_input("> ")
        if line.strip().lower() == "/end":
            break
        lines.append(line)

    answer = "\n".join(lines).strip()
    if not answer:
        raise RuntimeError("No essay answer was provided. Type your answer before /end.")
    return answer


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
    ui: str = "classic",
) -> str:
    if imposter_marked is None:
        imposter_marked = set()

    ultra_compact = bool(terminal_width is not None and terminal_width < 70)
    ascii_compact = no_color or (compact and (_is_windows() or ultra_compact))
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
    imposter_count = len(q.get("imposters", [])) if imposter_mode else 0
    imposter_badge = ""
    if imposter_count == 1:
        imposter_badge = "[1 IMPOSTER]"
    elif imposter_count > 1:
        imposter_badge = f"[{imposter_count} IMPOSTERS]"
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
            + (f"{separator}{imposter_badge}" if imposter_badge else "")
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
            + f" <style fg='{theme['pt_instruction']}'>{html.escape((separator + imposter_badge) if imposter_badge else '')}{html.escape(separator + question_type_badge + separator + instruction)}</style>"
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
        if ui == "next":
            if is_multiple:
                marker = "[x]" if idx in marked else "[ ]"
            else:
                marker = "(*)" if idx in marked else "( )"
        elif is_multiple:
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
            if ui == "next":
                imposter_marker = "(x)" if idx in imposter_marked else ""
            else:
                imposter_marker = ("[x]" if idx in imposter_marked else "[ ]") if (no_color or ascii_compact) else ("✖" if idx in imposter_marked else "·")
        else:
            imposter_marker = ""
        selected_chip = ""

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
            chips_plain = " ".join(chip for chip in (selected_chip, imposter_marker) if chip)
            prefix_plain = f"{'>' if i == selected else ' '} {idx}. {marker}{(' ' + chips_plain) if chips_plain else ''} "
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

        chips = " ".join(chip for chip in (selected_chip, imposter_marker) if chip)
        if no_color:
            lines.append(
                f"{'>' if i == selected else ' '} {idx}. {marker}{(' ' + chips) if chips else ''} "
                f"{strip_prompt_toolkit_tags(render_inline_markdown_for_prompt_toolkit(opt))}"
            )
        else:
            chip_text = f" {html.escape(chips)}" if chips else ""
            lines.append(
                f"<style {style}>{pointer} {idx}. {html.escape(marker)}{chip_text} "
                f"{render_inline_markdown_for_prompt_toolkit(opt)}</style>"
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
    ui: str = "classic",
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
            ui=ui,
        )
        if full_screen and submitted:
            grading = evaluate_submission(result["answer"], result["imposters"])
            status = question_status_label(grading)
            explanation = (q.get("explanation") or "").strip()
            if no_color:
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

            status_style = question_status_style(theme, status)
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


def question_status_label(grading: dict) -> str:
    """Return user-facing per-question status text.

    For imposter mode we surface partial credit explicitly.
    """
    if grading.get("imposter_mode"):
        if grading.get("is_perfect"):
            return "Correct"
        if grading.get("question_points", 0) > 0:
            return "Partially Correct"
        return "Wrong"
    return "Correct" if grading.get("answer_correct") else "Wrong"


def question_status_style(theme: dict, status: str) -> str:
    if status == "Correct":
        return theme["success"]
    if status == "Partially Correct":
        return theme["accent"]
    return theme["danger"]


def render_essay_feedback_next(console, theme: dict, grade: dict, feedback_heading: str) -> None:
    try:
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.table import Table
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Running the quiz requires rich. Install dependencies from requirements.txt."
        ) from exc

    score = grade.get("score_percent")
    score_text = "N/A" if score is None else f"{score:.2f}%"
    score_table = Table.grid(expand=True)
    score_table.add_column(ratio=1)
    score_table.add_column(ratio=1)
    score_table.add_column(ratio=1)
    score_table.add_row(
        f"[bold {theme['primary']}]Score[/bold {theme['primary']}]\n{score_text}",
        f"[bold {theme['primary']}]Points[/bold {theme['primary']}]\n"
        f"{grade.get('points_awarded', 0)}/{grade.get('total_points', 0)}",
        f"[bold {theme['primary']}]Mode[/bold {theme['primary']}]\n"
        f"{grade.get('scoring_mode', 'unknown')}",
    )
    console.print(Panel(score_table, border_style=theme["panel"]))

    def bullets(items: list[str], fallback: str) -> str:
        values = items or [fallback]
        return "\n".join(f"- {item}" for item in values)

    feedback_markdown = (
        f"## {feedback_heading}\n\n"
        "### Did well\n"
        f"{bullets(grade.get('did_well', []), 'No strengths were reported.')}\n\n"
        "### Missing\n"
        f"{bullets(grade.get('missing', []), 'Nothing major is missing.')}\n\n"
        "### Suggestions\n"
        f"{bullets(grade.get('suggestions', []), 'No extra suggestions.')}"
    )
    console.print(Panel(Markdown(feedback_markdown, code_theme="monokai"), border_style=theme["panel"]))


def run(
    title,
    questions,
    theme_name: str = "auto",
    no_color: bool = False,
    full_screen: bool = False,
    ui: str = "classic",
):
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
    has_multiple = any(str(q.get("type", "single")) == "multiple" for q in questions)
    has_single = any(str(q.get("type", "single")) != "multiple" for q in questions)
    saved_answers = []

    try:
        rule_lines = ["[bold]Rules:[/bold]"]
        if quiz_has_imposters:
            rule_lines.append("- Select correct answer(s) and flag misleading options (those are there to trick you)")
            rule_lines.append(
                "- Use [bold]↑/↓[/bold] to move, [bold]Space[/bold] for correct choices, "
                "[bold]X[/bold] for imposters, [bold]Enter[/bold] to submit"
            )
            rule_lines.append("- Imposter scoring: +1 correct flag, -1 false flag (minimum 0 imposter points)")
        elif has_multiple and not has_single:
            rule_lines.append("- Select all options you believe are correct")
            rule_lines.append(
                "- Use [bold]↑/↓[/bold] to move, [bold]Space[/bold] to toggle choices, "
                "[bold]Enter[/bold] to submit"
            )
            rule_lines.append("- You get points when your final set matches the expected correct set")
        elif has_single and not has_multiple:
            rule_lines.append("- Pick the one best answer")
            rule_lines.append(
                "- Use [bold]↑/↓[/bold] to move, press [bold]Space[/bold] to select, "
                "[bold]Enter[/bold] to submit"
            )
            rule_lines.append("- Correct answer gives full question points")
        else:
            rule_lines.append("- Questions include single-choice and multiple-choice items")
            rule_lines.append(
                "- Use [bold]↑/↓[/bold] to move, [bold]Space[/bold] to select/toggle, "
                "[bold]Enter[/bold] to submit"
            )
            rule_lines.append("- Single-choice gives full points; multiple-choice needs the exact correct set")

        rule_lines.append("- Complete all questions before timers")
        rule_lines.append("- Press [bold]Ctrl+C[/bold] to exit at any time")
        rules_text = (
            "\n".join(rule_lines)
            + "\n\nAre you ready to start?\n"
            + f"[bold {theme['accent']}]Press Enter... Let's go! 🚀[/bold {theme['accent']}]"
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
                    ui=ui,
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
            status = question_status_label(grading)

            if not full_screen:
                status_style = question_status_style(theme, status)
                console.print(f"[{status_style}]{status}[/{status_style}]")
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
                "result_label": status,
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
    ui: str = "classic",
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
        + (
            "**Type your answer in the terminal. Write 4-8 lines, then type `/end`.**"
            if ui == "next"
            else "**⏎ Press Enter to open your editor and write your answer.**"
        )
    )

    try:
        console.print(
            Panel(
                Markdown(intro_markdown, code_theme="monokai"),
                title=f"[bold {theme['primary']}]{title}[/bold {theme['primary']}]",
                border_style=theme["panel"],
            )
        )
        if ui != "next":
            prompt_input()
        if ui == "next":
            student_answer = collect_essay_answer_inline(title, question)
        else:
            student_answer = collect_essay_answer_via_editor(title, question)

        if no_color:
            console.print("✓ Answer captured.")
        else:
            console.print(f"[bold {theme['success']}]✓ Answer captured.[/bold {theme['success']}]")

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

        if not grade["ai_unavailable"]:
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

        if ui == "next":
            if encouragement:
                console.print(f"[bold {theme['accent']}]{encouragement}[/bold {theme['accent']}]")
            render_essay_feedback_next(console, theme, grade, feedback_heading)
        else:
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
    if raw_args and raw_args[0] == "room":
        room_parser = argparse.ArgumentParser(description="Join or create multiplayer rooms.")
        mode_group = room_parser.add_mutually_exclusive_group(required=True)
        mode_group.add_argument(
            "--create",
            nargs="?",
            const="__AUTO__",
            metavar="ROOM_NAME",
            help="Create a room (optional custom name). If omitted, a room name is generated.",
        )
        mode_group.add_argument(
            "--join",
            metavar="ROOM_NAME",
            help="Join an existing room by room name.",
        )
        room_parser.add_argument(
            "--name",
            default="",
            help="Display name. If omitted, quizmd suggests a random name.",
        )
        room_parser.add_argument(
            "--token",
            default="",
            help="Room token for join commands (required on secure servers).",
        )
        token_group = room_parser.add_mutually_exclusive_group()
        token_group.add_argument(
            "--require-token",
            action="store_true",
            help="Require a room token for all joiners when creating a room.",
        )
        token_group.add_argument(
            "--no-token",
            action="store_true",
            help="Disable room token requirement when creating a room.",
        )
        room_parser.add_argument(
            "--server",
            default="",
            help="Room server URL override. By default quizmd uses configured cloud server(s).",
        )
        room_parser.add_argument(
            "--mode",
            choices=["compete", "collaborate", "boxing"],
            default="",
            help="Room mode for create. If omitted, choose interactively.",
        )
        room_parser.add_argument(
            "--role",
            choices=["teacher", "student"],
            default="",
            help="Role for boxing mode. If omitted, choose interactively.",
        )
        room_parser.add_argument(
            "--quiz",
            default="",
            help="Quiz file to host (markdown or JSON). Defaults to built-in sample quiz.",
        )
        room_parser.add_argument(
            "--theme",
            choices=["auto", "dark", "light"],
            default="auto",
            help="Color theme for interactive room setup and questions.",
        )
        room_parser.add_argument(
            "--no-color",
            action="store_true",
            help="Disable colors/styled symbols (also enabled with NO_COLOR).",
        )
        room_parser.add_argument(
            "--full-screen",
            action="store_true",
            help="Render room questions in full-screen mode.",
        )
        args = room_parser.parse_args(raw_args[1:])
        try:
            return run_room_command(args)
        except ValueError as exc:
            print(safe_for_stream(f"Validation failed: {exc}", sys.stderr), file=sys.stderr)
            raise SystemExit(1) from exc
        except OSError as exc:
            print(safe_for_stream(f"File error: {exc}", sys.stderr), file=sys.stderr)
            raise SystemExit(1) from exc
        except RuntimeError as exc:
            print(safe_for_stream(f"Runtime error: {exc}", sys.stderr), file=sys.stderr)
            raise SystemExit(1) from exc

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
        init_parser.add_argument(
            "--ui",
            choices=UI_CHOICES,
            default="classic",
            help="Use an experimental UI surface for init output.",
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

        if args.ui == "next":
            render_init_next_screen(created, target_dir=args.dir)
            print("")
            print("Try it out:")
            print("quizmd hello-quiz.md")
            return

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
        if hello_quiz:
            print("")
            print("Room modes (online):")
            print(f"quizmd room --create --mode compete --quiz {hello_quiz}")
            print(f"quizmd room --create --mode collaborate --quiz {hello_quiz}")
            print(f"quizmd room --create --mode boxing --quiz {hello_quiz}")
            print("quizmd room --join <room-name> [--token <room-token>]")
            print("Room quiz requirement: Time/time_limit must be >= 5 seconds for online modes.")
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
        "--ui",
        choices=UI_CHOICES,
        default="classic",
        help="Use an experimental UI surface for quiz and essay interactions.",
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
                ui=args.ui,
            )
        else:
            run(
                title,
                questions,
                theme_name=args.theme,
                no_color=no_color,
                full_screen=args.full_screen,
                ui=args.ui,
            )
    except RuntimeError as exc:
        print(safe_for_stream(f"Runtime error: {exc}", sys.stderr), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
