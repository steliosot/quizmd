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

__version__ = "2.0.2"
DEFAULT_AI_PROVIDER = "gemini"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
GEMINI_REQUESTS_PER_MINUTE = 15
_GEMINI_REQUEST_TIMES: deque[float] = deque()

LOGO = r"""
▞▀▖   ▗    ▙▗▌▛▀▖
▌ ▌▌ ▌▄ ▀▜▘▌▘▌▌ ▌
▌▚▘▌ ▌▐ ▗▘ ▌ ▌▌ ▌
▝▘▘▝▀▘▀▘▀▀▘▘ ▘▀▀ 
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


def should_use_compact_layout(min_width: int = 100) -> bool:
    try:
        return os.get_terminal_size().columns < min_width
    except OSError:
        return False


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
                    or re.match(r"(?i)^(answer|type|time|explanation)\s*:", stripped) is not None
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

        for l in metadata_lines:
            stripped = l.strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                options.append(stripped[2:].strip())
                continue

            field_match = re.match(r"(?i)^(answer|type|time|explanation)\s*:\s*(.*)$", stripped)
            if field_match:
                key = field_match.group(1).lower()
                value = field_match.group(2)
                if key == "answer":
                    answer = parse_int_list(value, "answer", title, source)
                elif key == "type":
                    qtype = value.strip().lower()
                elif key == "time":
                    time_limit = parse_int_value(value, "time", title, source)
                else:
                    explanation = value.strip()
            else:
                raise ValueError(
                    f"{source}: unrecognized line {l!r} in question {title!r}. "
                    "Expected options ('- ...') or fields: Answer, Type, Time, Explanation."
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
            "explanation": explanation
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
    return ask_yes_no("Do you want to save your answers? [y/n]: ")


def ask_yes_no(prompt: str) -> bool:
    while True:
        choice = prompt_input(prompt).strip().lower()
        if choice in {"y", "yes"}:
            return True
        if choice in {"n", "no"}:
            return False


def prompt_input(prompt: str = "") -> str:
    try:
        return input(prompt)
    except EOFError as exc:
        raise RuntimeError("Interactive input is not available in this environment.") from exc


def save_attempt(quiz_title: str, score: int, questions: list[dict], answers: list[dict]) -> Path:
    attempt_dir = next_attempt_dir(quiz_title)

    payload = {
        "quiz_title": quiz_title,
        "score": score,
        "total_questions": len(questions),
        "answers": answers,
    }

    (attempt_dir / "answers.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    lines = [
        f"Quiz: {quiz_title}",
        f"Score: {score}/{len(questions)}",
        "",
    ]

    for item in answers:
        lines.extend([
            item["question_title"],
            item["question_text"],
            f"Selected: {item['selected_labels'] or 'No answer'}",
            f"Correct: {item['correct_labels']}",
            f"Result: {'Correct' if item['is_correct'] else 'Wrong'}",
            f"Explanation: {item['explanation'] or '-'}",
            "",
        ])

    (attempt_dir / "answers.txt").write_text("\n".join(lines), encoding="utf-8")
    return attempt_dir


def save_essay_attempt(quiz_title: str, payload: dict) -> Path:
    attempt_dir = next_attempt_dir(quiz_title)
    (attempt_dir / "answers.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
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


def _normalize_gemini_grade(raw_grade, expected_total_points: int) -> dict:
    if isinstance(raw_grade, list):
        if len(raw_grade) == 1 and isinstance(raw_grade[0], dict):
            raw_grade = raw_grade[0]
        else:
            raise ValueError("Gemini JSON returned a list instead of a single object")
    if not isinstance(raw_grade, dict):
        raise ValueError("Gemini JSON must be an object")

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
        raise ValueError(f"Gemini JSON missing key(s): {', '.join(missing_keys)}")

    try:
        graded_total = int(raw_grade["total_points"])
        points_awarded = float(raw_grade["points_awarded"])
        score_percent = float(raw_grade["score_percent"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Gemini JSON has invalid numeric values") from exc

    if graded_total != expected_total_points:
        raise ValueError(
            f"Gemini JSON total_points={graded_total} does not match rubric total={expected_total_points}"
        )
    if points_awarded < 0 or points_awarded > graded_total:
        raise ValueError("Gemini JSON points_awarded is out of valid range")

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
    }


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
    rubric_text = "\n".join(_rubric_lines(essay["criteria"]))
    prompt = (
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
                return _normalize_gemini_grade(graded, int(essay["total_points"]))
        except Exception as exc:  # network/parser/HTTP handling
            if isinstance(exc, KeyboardInterrupt):
                raise
            last_error = exc
            code = getattr(exc, "code", None)
            if isinstance(code, int):
                retryable = code == 429 or 500 <= code < 600
                if code == 429:
                    reason_code = "rate_limit"
                elif code == 404:
                    reason_code = "not_found"
                elif 500 <= code < 600:
                    reason_code = "server_error"
                else:
                    reason_code = "http_error"
            else:
                retryable = isinstance(exc, (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError))
                if isinstance(exc, TimeoutError):
                    reason_code = "timeout"
                elif isinstance(exc, urllib.error.URLError):
                    reason_code = "network_error"
                elif isinstance(exc, (ValueError, json.JSONDecodeError)):
                    reason_code = "invalid_response"
                else:
                    reason_code = "unknown_error"

        if attempt >= max_retries or not retryable:
            break
        sleep_seconds = (2 ** attempt) + random.uniform(0.1, 0.35)
        time.sleep(sleep_seconds)

    raise RuntimeError(f"[{reason_code}] Gemini evaluation failed after retries: {last_error}")


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
    }


def _format_possessive(name: str) -> str:
    text = name.strip()
    if not text:
        return ""
    if text.lower().endswith("s"):
        return f"{text}’"
    return f"{text}'s"


def _is_windows() -> bool:
    return os.name == "nt"


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
        "# When ready (vim): press Esc, type :wq!, then press Enter to save and exit.\n"
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
            subprocess.run(command, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            if _is_windows() and editor.lower() != "notepad":
                if ask_yes_no(f"Could not open '{editor}'. Open Notepad instead? [y/n]: "):
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
    is_multiple: bool,
    question_index: int = 1,
    total_questions: int = 1,
    pulse: bool = False,
    no_color: bool = False,
    compact: bool = False,
) -> str:
    instruction = "Select with Space, then Enter"
    question_type_badge = "[MULTI ☑]" if is_multiple else "[SINGLE ○]"
    progress_units = 10
    progress_fraction = question_index / total_questions if total_questions else 1
    filled_units = max(0, min(progress_units, int(round(progress_fraction * progress_units))))
    progress_bar = "█" * filled_units + "░" * (progress_units - filled_units)

    timer_color = theme["pt_timer"]
    timer_prefix = "⏱"
    if remaining is not None:
        if remaining < 5:
            timer_color = theme["pt_timer_danger"]
            timer_prefix = "😱"
        elif remaining <= 10:
            timer_color = theme["pt_timer_warning"]
            timer_prefix = "😱"

    parsed_question_lines = parse_question_lines(q["question"])
    rendered_question_lines: list[tuple[str, bool]] = []
    for raw_line, is_code in parsed_question_lines:
        if is_code:
            rendered = html.escape(raw_line.rstrip())
            rendered_question_lines.append((rendered, True))
        else:
            rendered_question_lines.append((render_inline_markdown_for_prompt_toolkit(raw_line), False))

    code_side_margin = 2
    visible_widths = [
        display_width(html.unescape(strip_prompt_toolkit_tags(line))) + (code_side_margin * 2 if is_code else 0)
        for line, is_code in rendered_question_lines
    ] or [0]
    question_width = max(40, max(visible_widths))
    question_box_top = "┌" + ("─" * (question_width + 2)) + "┐"
    question_box_bot = "└" + ("─" * (question_width + 2)) + "┘"

    if no_color:
        plain_progress = f"Question {question_index}/{total_questions} {progress_bar}"
        if remaining is not None:
            plain_progress += f"  {timer_prefix} {remaining}s"
        plain_progress += f"  {question_type_badge}"

        lines = [plain_progress]
        if not compact:
            lines.append("")
            lines.append(question_box_top)

        for idx, (line, is_code) in enumerate(rendered_question_lines):
            visible = html.unescape(strip_prompt_toolkit_tags(line))
            current_width = display_width(visible)
            plain_line = strip_prompt_toolkit_tags(line)
            if is_code:
                is_code_start = idx == 0 or not rendered_question_lines[idx - 1][1]
                is_code_end = idx == len(rendered_question_lines) - 1 or not rendered_question_lines[idx + 1][1]
                code_inner_width = max(0, question_width - (code_side_margin * 2))
                code_padding = " " * max(0, code_inner_width - current_width)
                if is_code_start and not compact:
                    lines.append(f"│ {' ' * question_width} │")
                code_line = f"{' ' * code_side_margin}{plain_line}{code_padding}{' ' * code_side_margin}"
                if compact:
                    lines.append(code_line)
                else:
                    lines.append(f"│ {code_line} │")
                if is_code_end and not compact:
                    lines.append(f"│ {' ' * question_width} │")
            else:
                padding = " " * max(0, question_width - current_width)
                if compact:
                    lines.append(f"{plain_line}")
                else:
                    lines.append(f"│ {plain_line}{padding} │")

        if not compact:
            lines.extend([question_box_bot, "", instruction, "", "-------- Choices --------", ""])
        else:
            lines.extend(["", instruction, "", "Choices:", ""])
    else:
        lines = [
            f"<style fg='{theme['pt_instruction']}'><b>Question {question_index}/{total_questions}</b> {progress_bar}</style>"
            + (f"  <style fg='{timer_color}'>{timer_prefix} {remaining}s</style>" if remaining is not None else "")
            + f"  <style fg='{theme['pt_instruction']}'>{html.escape(question_type_badge)}</style>",
            "",
        ]
        if not compact:
            lines.append(f"<style fg='{theme['pt_title']}'>{question_box_top}</style>")

        for idx, (line, is_code) in enumerate(rendered_question_lines):
            visible = html.unescape(strip_prompt_toolkit_tags(line))
            current_width = display_width(visible)
            if is_code:
                is_code_start = idx == 0 or not rendered_question_lines[idx - 1][1]
                is_code_end = idx == len(rendered_question_lines) - 1 or not rendered_question_lines[idx + 1][1]
                code_inner_width = max(0, question_width - (code_side_margin * 2))
                code_padding = " " * max(0, code_inner_width - current_width)
                code_style = f"fg='{theme.get('pt_code', theme['pt_primary'])}' bg='{theme['pt_code_bg']}'"
                if is_code_start and not compact:
                    spacer = f"<style {code_style}>{' ' * question_width}</style>"
                    lines.append(f"<style fg='{theme['pt_title']}'>│ {spacer} │</style>")
                code_line = (
                    f"<style {code_style}>"
                    f"{' ' * code_side_margin}{line}{code_padding}{' ' * code_side_margin}"
                    f"</style>"
                )
                if compact:
                    lines.append(code_line)
                else:
                    lines.append(f"<style fg='{theme['pt_title']}'>│ {code_line} │</style>")
                if is_code_end and not compact:
                    spacer = f"<style {code_style}>{' ' * question_width}</style>"
                    lines.append(f"<style fg='{theme['pt_title']}'>│ {spacer} │</style>")
            else:
                padding = " " * max(0, question_width - current_width)
                if compact:
                    lines.append(line)
                else:
                    lines.append(f"<style fg='{theme['pt_title']}'>│ {line}{padding} │</style>")

        if not compact:
            lines.extend([
                f"<style fg='{theme['pt_title']}'>{question_box_bot}</style>",
                "",
                f"<style fg='{theme['pt_instruction']}'>{html.escape(instruction)}</style>",
                "",
                f"<style fg='{theme['pt_instruction']}'>──────── Choices ────────</style>",
                "",
            ])
        else:
            lines.extend([
                "",
                f"<style fg='{theme['pt_instruction']}'>{html.escape(instruction)}</style>",
                "",
                f"<style fg='{theme['pt_instruction']}'>Choices:</style>",
                "",
            ])

    for i, opt in enumerate(q["options"]):
        idx = i + 1
        pointer = "&gt;" if i == selected else " "
        if is_multiple:
            marker = ("[x]" if idx in marked else "[ ]") if no_color else ("☑" if idx in marked else "☐")
        else:
            marker = ("(*)" if idx in marked else "( )") if no_color else ("◉" if idx in marked else "○")

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

        lines.append(
            (
                f"{'>' if i == selected else ' '} {idx}. {marker} "
                f"{strip_prompt_toolkit_tags(render_inline_markdown_for_prompt_toolkit(opt))}"
            )
            if no_color
            else f"<style {style}>{pointer} {idx}. {html.escape(marker)} {render_inline_markdown_for_prompt_toolkit(opt)}</style>"
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
    pulse = False
    remaining = q["time_limit"]
    result = {"answer": None}
    is_multiple = q.get("type", "single") == "multiple"

    def render():
        markup = build_question_markup(
            q,
            theme,
            selected,
            marked,
            remaining,
            is_multiple,
            question_index=question_index,
            total_questions=total_questions,
            pulse=pulse,
            no_color=no_color,
            compact=compact,
        )
        if no_color:
            return markup
        return PromptHTML(markup)

    control = FormattedTextControl(text=render)
    window = Window(content=control)
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

    @kb.add("enter")
    def _(event):
        result["answer"] = sorted(marked) if marked else None
        event.app.exit()

    @kb.add("c-c")
    def _(event):
        event.app.exit(exception=KeyboardInterrupt())

    app = Application(layout=Layout(HSplit([window])), key_bindings=kb)

    async def timer():
        nonlocal remaining
        if remaining is None:
            return
        while remaining > 0:
            await asyncio.sleep(1)
            remaining -= 1
            control.text = render()
            app.invalidate()
        if remaining == 0:
            result["answer"] = None
            app.exit()

    task = asyncio.create_task(timer())
    try:
        await app.run_async()
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    ans = result["answer"]
    return ans == q["correct"], ans


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


def run(title, questions, theme_name: str = "auto", no_color: bool = False):
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
    compact = should_use_compact_layout()
    saved_answers = []

    try:
        console.print(
            Panel(
                f"[bold {theme['primary']}]{title}[/bold {theme['primary']}]\n\n"
                "[bold]Rules:[/bold]\n"
                "- Use ↑/↓ to move\n"
                "- Press [bold]Space[/bold] to select an answer\n"
                "- Press [bold]Enter[/bold] to continue\n"
                "- Press [bold]Ctrl+C[/bold] to exit the quiz at any time\n\n"
                "Are you ready to start?\n"
                f"[bold {theme['accent']}]Press Enter... Let's go! 🚀[/bold {theme['accent']}]",
                border_style=theme["panel"]
            )
        )
        prompt_input()

        score = 0

        for i, q in enumerate(questions, start=1):
            if i > 1:
                console.print("\n")

            correct, ans = run_coroutine_sync(
                ask_question(
                    q,
                    theme,
                    question_index=i,
                    total_questions=len(questions),
                    no_color=no_color,
                    compact=compact,
                )
            )

            selected_labels = format_labels(q["options"], ans)
            correct_labels = format_labels(q["options"], q["correct"])

            if correct:
                console.print(f"[{theme['success']}]Correct[/{theme['success']}]")
                score += 1
            else:
                console.print(f"[{theme['danger']}]Wrong[/{theme['danger']}]")

            if q.get("explanation"):
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
                "correct_indexes": q["correct"],
                "correct_labels": correct_labels,
                "is_correct": correct,
                "explanation": q.get("explanation", ""),
            })

            prompt_input("Press Enter for the next question...")
            
        percentage = (score / len(questions)) * 100 if questions else 0.0
        wrong_topics = [item["question_title"] for item in saved_answers if not item["is_correct"]]
        if wrong_topics:
            quick_review = "\n".join(f"- {topic}" for topic in wrong_topics)
        else:
            quick_review = "- None, excellent work."

        summary = (
            f"[bold {theme['primary']}]Quiz Summary[/bold {theme['primary']}]\n\n"
            f"Score: [bold]{score}/{len(questions)}[/bold]\n"
            f"Percentage: [bold]{percentage:.1f}%[/bold]\n"
            f"Correct Answers: [bold]{score}[/bold]\n\n"
            f"[bold]Quick Review Topics:[/bold]\n{quick_review}"
        )
        console.print(Panel(summary, border_style=theme["panel"]))

        if ask_to_save_answers():
            try:
                attempt_dir = save_attempt(title, score, questions, saved_answers)
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
    ai_model: str = DEFAULT_GEMINI_MODEL,
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

    if ai_provider != "gemini":
        raise RuntimeError(f"Unsupported AI provider {ai_provider!r}. Only 'gemini' is supported in essay mode.")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Essay mode requires GEMINI_API_KEY.\n"
            "Standard multiple-choice quizzes do not use AI and do not need this key.\n"
            "Set it before running, e.g.:\n"
            "export GEMINI_API_KEY='your_key_here'"
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
        f"**✓ Press Enter to open your editor and write your answer.**"
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

        try:
            grade = evaluate_essay_with_loading(
                console,
                theme,
                evaluate_essay_with_gemini,
                instructor_name=essay.get("instructor_name", ""),
                essay=essay,
                student_answer=student_answer,
                api_key=api_key,
                model=ai_model,
                timeout=ai_timeout,
            )
        except RuntimeError as exc:
            fallback_reason = "unknown_error"
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
                "unknown_error": "unknown error",
            }
            reason_label = reason_labels.get(grade.get("ai_reason", ""), "unknown error")
            feedback_lines.append("")
            feedback_lines.append(
                f"- Note: AI unavailable ({reason_label}); deterministic fallback used."
            )

        feedback_heading = "Feedback"
        instructor_name = str(essay.get("instructor_name", "")).strip()
        if instructor_name:
            feedback_heading = f"Feedback from {_format_possessive(instructor_name)} notes"

        console.print(
            Panel(
                f"[bold {theme['primary']}]Score: {score_text}[/bold {theme['primary']}]\n\n"
                f"[bold]{feedback_heading}[/bold]\n"
                + "\n".join(feedback_lines),
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
            "ai_error": grade["ai_error"],
            "ai_reason": grade.get("ai_reason", "none"),
            "ai_provider": ai_provider,
            "ai_model": ai_model,
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
        "--ai-provider",
        default=DEFAULT_AI_PROVIDER,
        choices=["gemini"],
        help="AI provider for essay mode.",
    )
    parser.add_argument(
        "--ai-model",
        default=DEFAULT_GEMINI_MODEL,
        help="AI model name for essay mode.",
    )
    parser.add_argument(
        "--ai-timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds for AI evaluation requests.",
    )
    args = parser.parse_args()
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
            run(title, questions, theme_name=args.theme, no_color=no_color)
    except RuntimeError as exc:
        print(safe_for_stream(f"Runtime error: {exc}", sys.stderr), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
