#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import re
import sys
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
        "primary": "ansicyan",
        "secondary": "magenta",
        "accent": "yellow",
        "success": "green",
        "danger": "red",
        "panel": "cyan",
        "pt_primary": "ansicyan",
        "pt_title": "ansiwhite",
        "pt_timer": "ansiyellow",
        "pt_instruction": "ansigray",
        "pt_selected_fg": "ansiwhite",
        "pt_selected_bg": "ansiblue",
        "pt_marked_fg": "ansiwhite",
        "pt_marked_bg": "ansigreen",
    },
    "light": {
        "primary": "ansiblue",
        "secondary": "ansimagenta",
        "accent": "ansiyellow",
        "success": "ansigreen",
        "danger": "ansired",
        "panel": "ansiblue",
        "pt_primary": "ansiblue",
        "pt_title": "ansiblack",
        "pt_timer": "ansimagenta",
        "pt_instruction": "ansiblack",
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


def select_theme(name: str = "auto") -> dict:
    env_theme = os.environ.get("QUIZMD_THEME", "").strip().lower()
    if env_theme in THEMES:
        return THEMES[env_theme]

    if name == "dark":
        return THEMES["dark"]
    if name == "light":
        return THEMES["light"]
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

        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            if lines and not lines[0].startswith("# "):
                raise ValueError(
                    f"{source}: malformed question block {lines[0]!r} is missing the question text line"
                )
            continue

        title = lines[0]
        question = lines[1]

        options = []
        answer = []
        qtype = None
        time_limit = None
        explanation = ""

        for l in lines[2:]:
            stripped = l.strip()
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
) -> str:
    instruction = "Select 1 or more answers with Space, then Enter" if is_multiple else "Select 1 answer with Space, then Enter"

    lines = [
        f"<style fg='{theme['pt_title']}'> {html.escape('🤔 ' + q['title'])}</style>",
        "",
        html.escape(q["question"]),
        f"<style fg='{theme['pt_timer']}'>Time left: {remaining}s</style>" if remaining is not None else "",
        "",
        f"<style fg='{theme['pt_instruction']}'>{html.escape(instruction)}</style>",
        "",
    ]

    for i, opt in enumerate(q["options"]):
        idx = i + 1
        pointer = "&gt;" if i == selected else " "
        checkbox = "[x]" if idx in marked else "[ ]"

        if idx in marked:
            style = f"fg='{theme['pt_marked_fg']}' bg='{theme['pt_marked_bg']}'"
        elif i == selected:
            style = f"fg='{theme['pt_selected_fg']}' bg='{theme['pt_selected_bg']}'"
        else:
            style = f"fg='{theme['pt_primary']}'"

        lines.append(
            f"<style {style}>{pointer} {idx}. {html.escape(checkbox)} {html.escape(opt)}</style>"
        )

    lines.append("")
    lines.append("")

    return "\n".join(lines)


async def ask_question(q, theme):
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
        return PromptHTML(build_question_markup(q, theme, selected, marked, remaining, is_multiple))

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
                f"[bold cyan]{title}[/bold cyan]\n\n"
                "[bold]Rules:[/bold]\n"
                "- Use ↑/↓ to move\n"
                "- Press [bold]Space[/bold] to select an answer\n"
                "- Press [bold]Enter[/bold] to continue\n\n"
                "Are you ready to start?\n"
                "[bold yellow]Press Enter... Let's go! 🚀[/bold yellow]",
                border_style="cyan"
            )
        )
        prompt_input()

        score = 0

        for q in questions:
            
            console.print(Panel(q["question"]))

            correct, ans = run_coroutine_sync(ask_question(q, theme))

            selected_labels = format_labels(q["options"], ans)
            correct_labels = format_labels(q["options"], q["correct"])

            if correct:
                console.print("[green]Correct[/green]")
                score += 1
            else:
                console.print("[red]Wrong[/red]")

            if q.get("explanation"):
                console.print(Panel(f"[bold]Explanation:[/bold]\n{q['explanation']}"))

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
            
        console.print(Panel(f"[bold cyan]Final Score: {score}/{len(questions)}[/bold cyan]"))

        if ask_to_save_answers():
            attempt_dir = save_attempt(title, score, questions, saved_answers)
            console.print(
                Panel(
                    f"[bold green]Answers saved successfully.[/bold green]\n{attempt_dir}",
                    border_style="green"
                )
            )

    except KeyboardInterrupt:
        console.print("\n\n")  # ← spacing BEFORE

        console.print(
            Panel(
                "[bold yellow]Thank you for trying! 👋[/bold yellow]",
                border_style="yellow"
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
        print(f"Validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except OSError as exc:
        print(f"File error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.validate:
        print(f"Validation passed: {title} ({len(questions)} questions)")
        return

    try:
        run(title, questions, theme_name=args.theme)
    except RuntimeError as exc:
        print(f"Runtime error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
