#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

__version__ = "0.1.0"

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
        "pt_marked_fg": "ansiwhite",
        "pt_marked_bg": "ansigreen",
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
        "pt_marked_fg": "ansiwhite",
        "pt_marked_bg": "ansigreen",
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
    while True:
        choice = prompt_input("Do you want to save your answers? [y/n]: ").strip().lower()
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


def build_question_markup(
    q: dict,
    theme: dict,
    selected: int,
    marked: set[int],
    remaining: int | None,
    is_multiple: bool,
    question_index: int = 1,
    total_questions: int = 1,
) -> str:
    instruction = "Select 1 or more answers with Space, then Enter" if is_multiple else "Select 1 answer with Space, then Enter"
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
    rendered_question_lines = []
    for raw_line, is_code in parsed_question_lines:
        if is_code:
            rendered = html.escape(raw_line.rstrip())
            if rendered:
                rendered = f"<style fg='{theme.get('pt_code', theme['pt_primary'])}'>{rendered}</style>"
            rendered_question_lines.append(rendered)
        else:
            rendered_question_lines.append(render_inline_markdown_for_prompt_toolkit(raw_line))

    visible_widths = [
        display_width(html.unescape(strip_prompt_toolkit_tags(line))) for line in rendered_question_lines
    ] or [0]
    question_width = max(40, max(visible_widths))
    question_box_top = "┌" + ("─" * (question_width + 2)) + "┐"
    question_box_bot = "└" + ("─" * (question_width + 2)) + "┘"

    lines = [
        f"<style fg='{theme['pt_instruction']}'><b>Question {question_index}/{total_questions}</b> {progress_bar}</style>"
        + (f"  <style fg='{timer_color}'>{timer_prefix} {remaining}s</style>" if remaining is not None else ""),
        "",
        f"<style fg='{theme['pt_title']}'>{question_box_top}</style>",
    ]
    for line in rendered_question_lines:
        visible = html.unescape(strip_prompt_toolkit_tags(line))
        padding = " " * max(0, question_width - display_width(visible))
        lines.append(f"<style fg='{theme['pt_title']}'>│ {line}{padding} │</style>")
    lines.extend([
        f"<style fg='{theme['pt_title']}'>{question_box_bot}</style>",
        "",
        f"<style fg='{theme['pt_instruction']}'>{html.escape(instruction)}</style>",
        "",
        f"<style fg='{theme['pt_instruction']}'>──────── Choices ────────</style>",
        "",
    ])

    for i, opt in enumerate(q["options"]):
        idx = i + 1
        pointer = "&gt;" if i == selected else " "
        if is_multiple:
            marker = "☑" if idx in marked else "☐"
        else:
            marker = "◉" if idx in marked else "○"

        if idx in marked:
            style = f"fg='{theme['pt_marked_fg']}' bg='{theme['pt_marked_bg']}'"
        elif i == selected:
            style = f"fg='{theme['pt_selected_fg']}' bg='{theme['pt_selected_bg']}'"
        else:
            style = f"fg='{theme['pt_primary']}'"

        lines.append(
            f"<style {style}>{pointer} {idx}. {html.escape(marker)} {render_inline_markdown_for_prompt_toolkit(opt)}</style>"
        )

    lines.append("")
    lines.append("")

    return "\n".join(lines)


async def ask_question(q, theme, question_index: int = 1, total_questions: int = 1):
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
    remaining = q["time_limit"]
    result = {"answer": None}
    is_multiple = q.get("type", "single") == "multiple"

    def render():
        return PromptHTML(
            build_question_markup(
                q,
                theme,
                selected,
                marked,
                remaining,
                is_multiple,
                question_index=question_index,
                total_questions=total_questions,
            )
        )

    control = FormattedTextControl(text=render)
    window = Window(content=control)
    kb = KeyBindings()

    @kb.add("up")
    def _(_):
        nonlocal selected
        selected = (selected - 1) % len(q["options"])
        control.text = render()

    @kb.add("down")
    def _(_):
        nonlocal selected
        selected = (selected + 1) % len(q["options"])
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


def run(title, questions, theme_name: str = "auto"):
    try:
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Running the quiz requires rich. Install dependencies from requirements.txt."
        ) from exc

    console = Console()
    console.print(LOGO)

    theme = select_theme(theme_name)
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
                ask_question(q, theme, question_index=i, total_questions=len(questions))
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

def main():
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
    args = parser.parse_args()

    try:
        title, questions = parse_quiz_markdown(args.file)
    except ValueError as exc:
        print(safe_for_stream(f"Validation failed: {exc}", sys.stderr), file=sys.stderr)
        raise SystemExit(1) from exc
    except OSError as exc:
        print(safe_for_stream(f"File error: {exc}", sys.stderr), file=sys.stderr)
        raise SystemExit(1) from exc

    if args.validate:
        print(safe_for_stream(f"Validation passed: {title} ({len(questions)} questions)", sys.stdout))
        return

    try:
        run(title, questions, theme_name=args.theme)
    except RuntimeError as exc:
        print(safe_for_stream(f"Runtime error: {exc}", sys.stderr), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
