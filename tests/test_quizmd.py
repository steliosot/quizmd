import subprocess
import sys
import tempfile
import unittest
import os
import json
import re
import urllib.error
import io
import contextlib
import argparse
from unittest.mock import AsyncMock, patch
from pathlib import Path

from quizmd import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_ROOM_SERVER_CLOUD,
    _format_possessive,
    _room_connected_players,
    _room_configured_servers,
    _room_default_server,
    _room_player_label,
    _room_prompt_token_required,
    _room_quiz_payload_from_markdown,
    _room_quiz_payload_from_json,
    _save_room_session_transcript,
    _room_validate_name,
    _room_resolve_server,
    _room_server_online,
    _room_supported_modes,
    _default_model_for_provider,
    _available_ai_providers_by_priority,
    _env_key_for_provider,
    _evaluator_for_provider,
    _provider_display_name,
    _redacted_ai_error,
    _resolve_ai_provider,
    _score_encouragement,
    THEMES,
    build_question_markup,
    collect_essay_answer_inline,
    collect_essay_answer_via_editor,
    detect_quiz_mode,
    evaluate_essay_deterministic_fallback,
    evaluate_essay_with_anthropic,
    evaluate_essay_with_gemini,
    evaluate_essay_with_openai,
    format_labels,
    question_status_label,
    init_starter_files,
    display_width,
    parse_essay_markdown,
    parse_int_list,
    parse_int_value,
    parse_quiz_markdown,
    main,
    prompt_input,
    run,
    run_room_command,
    run_essay,
    run_coroutine_sync,
    safe_for_stream,
    save_attempt,
    save_essay_attempt,
    select_theme,
    should_use_compact_layout,
    is_no_color_requested,
    slugify,
)


QUIZ_DIR = Path("quizzes")
ESSAY_DIR = Path("essays")


class QuizMarkdownTests(unittest.TestCase):
    def write_quiz(self, content: str) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(content)
            return handle.name

    def write_valid_essay(self) -> str:
        return self.write_quiz(
            "# Essay Question: requirements.txt\n\n"
            "## Question\n"
            "What is requirements.txt?\n\n"
            "## Instructions for Students\n"
            "Write 5-10 lines.\n\n"
            "## Instructor Name\n"
            "Stelios\n\n"
            "## Evaluation Criteria (Total: 4 points)\n"
            "1. **Dependency problem (1 point)**\n"
            "- Different versions can conflict\n"
            "2. **Reproducibility (1 point)**\n"
            "- Same environment for others\n"
            "3. **Collaboration (1 point)**\n"
            "- Avoid works-on-my-machine\n"
            "4. **Version tracking (1 point)**\n"
            "- Pin versions for debugging\n\n"
            "## Reference Answer\n"
            "A requirements file pins dependencies.\n\n"
            "## AI Evaluation Rules\n"
            "Use only criteria.\n\n"
            "## Output Format\n"
            "Score and feedback bullets.\n"
        )

    def test_parse_sample_quiz(self):
        title, questions = parse_quiz_markdown("quizzes/harry-potter-quiz.md")
        self.assertEqual(title, "🦉 Harry Potter Quiz")
        self.assertEqual(len(questions), 10)
        self.assertEqual(questions[0]["correct"], [2])
        self.assertEqual(questions[5]["type"], "multiple")

    def test_parse_quiz_with_imposters_field(self):
        quiz_path = self.write_quiz(
            "# Imposter Quiz\n\n"
            "## Question 1\n"
            "What does pip install -r requirements.txt do?\n\n"
            "- Installs listed dependencies\n"
            "- Creates a virtual environment\n"
            "- Upgrades Python itself\n"
            "- Removes unlisted packages by default\n\n"
            "Answer: 1\n"
            "Imposters: 2,4\n"
            "Type: single\n"
            "Time: 20\n"
            "Explanation: Installs packages from the requirements file.\n"
        )
        try:
            title, questions = parse_quiz_markdown(quiz_path)
            self.assertEqual(title, "Imposter Quiz")
            self.assertEqual(questions[0]["imposters"], [2, 4])
        finally:
            Path(quiz_path).unlink(missing_ok=True)

    def test_parse_quiz_with_imposters_overlap_fails(self):
        quiz_path = self.write_quiz(
            "# Imposter Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 2\n"
            "Imposters: 2\n"
            "Type: single\n"
        )
        try:
            with self.assertRaisesRegex(ValueError, "overlap with correct answers"):
                parse_quiz_markdown(quiz_path)
        finally:
            Path(quiz_path).unlink(missing_ok=True)

    def test_parse_quiz_with_imposters_out_of_range_fails(self):
        quiz_path = self.write_quiz(
            "# Imposter Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1\n"
            "Imposters: 3\n"
            "Type: single\n"
        )
        try:
            with self.assertRaisesRegex(ValueError, "imposter indexes .* out of range"):
                parse_quiz_markdown(quiz_path)
        finally:
            Path(quiz_path).unlink(missing_ok=True)

    def test_parse_all_quizzes_in_repository(self):
        quiz_files = sorted(QUIZ_DIR.glob("*.md"))
        self.assertGreaterEqual(len(quiz_files), 6)

        for quiz_file in quiz_files:
            with self.subTest(quiz=str(quiz_file)):
                mode = detect_quiz_mode(str(quiz_file))
                if mode == "essay":
                    title, payload = parse_essay_markdown(str(quiz_file))
                    self.assertTrue(title.strip())
                    self.assertGreater(payload["total_points"], 0)
                    self.assertTrue(payload["question"].strip())
                    self.assertTrue(payload["reference_answer"].strip())
                    self.assertTrue(payload["criteria"])
                else:
                    title, questions = parse_quiz_markdown(str(quiz_file))
                    self.assertTrue(title.strip())
                    min_questions = 3 if any(q.get("imposters") for q in questions) else 5
                    self.assertGreaterEqual(len(questions), min_questions)
                    for question in questions:
                        self.assertTrue(question["title"].strip())
                        self.assertTrue(question["question"].strip())
                        self.assertGreaterEqual(len(question["options"]), 2)
                        self.assertIn(question["type"], {"single", "multiple"})
                        self.assertGreaterEqual(len(question["correct"]), 1)
                        for idx in question["correct"]:
                            self.assertTrue(1 <= idx <= len(question["options"]))
                        if question["time_limit"] is not None:
                            self.assertGreater(question["time_limit"], 0)

    def test_validate_cli_passes_for_all_quizzes(self):
        quiz_files = sorted(QUIZ_DIR.glob("*.md"))
        self.assertTrue(quiz_files)

        for quiz_file in quiz_files:
            with self.subTest(quiz=str(quiz_file)):
                result = subprocess.run(
                    [sys.executable, "quizmd.py", "--validate", str(quiz_file)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                self.assertIn("Validation passed", result.stdout)

    def test_parse_all_essay_examples_in_repository(self):
        essay_files = sorted(ESSAY_DIR.glob("*.md"))
        self.assertGreaterEqual(len(essay_files), 3)

        for essay_file in essay_files:
            with self.subTest(essay=str(essay_file)):
                mode = detect_quiz_mode(str(essay_file))
                self.assertEqual(mode, "essay")
                title, payload = parse_essay_markdown(str(essay_file))
                self.assertTrue(title.strip())
                self.assertGreater(payload["total_points"], 0)
                self.assertTrue(payload["question"].strip())
                self.assertTrue(payload["instructions"].strip())
                self.assertTrue(payload["reference_answer"].strip())
                self.assertTrue(payload["criteria"])

    def test_validate_cli_passes_for_all_essay_examples(self):
        essay_files = sorted(ESSAY_DIR.glob("*.md"))
        self.assertTrue(essay_files)

        for essay_file in essay_files:
            with self.subTest(essay=str(essay_file)):
                result = subprocess.run(
                    [sys.executable, "quizmd.py", "--validate", str(essay_file)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                self.assertIn("Validation passed: Essay Question:", result.stdout)

    def test_parse_valid_essay_markdown(self):
        essay_path = self.write_valid_essay()
        title, essay = parse_essay_markdown(essay_path)
        self.assertEqual(title, "requirements.txt")
        self.assertEqual(essay["total_points"], 4)
        self.assertEqual(len(essay["criteria"]), 4)
        self.assertEqual(essay["instructor_name"], "Stelios")
        Path(essay_path).unlink()

    def test_parse_essay_keeps_inline_code_and_code_fences(self):
        essay_path = self.write_quiz(
            "# Essay Question: code sample\n\n"
            "## Question\n"
            "Explain what `requirements.txt` does for this setup:\n"
            "```bash\n"
            "pip install -r requirements.txt\n"
            "```\n\n"
            "## Instructions for Students\n"
            "Answer clearly.\n\n"
            "## Evaluation Criteria (Total: 1 points)\n"
            "1. **Accuracy (1 point)**\n"
            "- Mentions dependencies and reproducibility\n\n"
            "## Reference Answer\n"
            "It installs listed dependencies.\n\n"
            "## AI Evaluation Rules\n"
            "Only use criteria.\n\n"
            "## Output Format\n"
            "Score and feedback.\n"
        )
        _, essay = parse_essay_markdown(essay_path)
        self.assertIn("`requirements.txt`", essay["question"])
        self.assertIn("```bash", essay["question"])
        self.assertIn("pip install -r requirements.txt", essay["question"])
        Path(essay_path).unlink()

    def test_parse_essay_missing_required_sections_fail(self):
        section_patterns = {
            "Question": "missing required section\\(s\\): Question",
            "Instructions for Students": "missing required section\\(s\\): Instructions for Students",
            "Reference Answer": "missing required section\\(s\\): Reference Answer",
            "AI Evaluation Rules": "missing required section\\(s\\): AI Evaluation Rules",
            "Output Format": "missing required section\\(s\\): Output Format",
        }
        for section_name, error_pattern in section_patterns.items():
            with self.subTest(section=section_name):
                essay_path = self.write_valid_essay()
                text = Path(essay_path).read_text(encoding="utf-8")
                text = re.sub(
                    rf"\n## {re.escape(section_name)}\n.*?(?=\n## |\Z)",
                    "\n",
                    text,
                    flags=re.DOTALL,
                )
                Path(essay_path).write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, error_pattern):
                    parse_essay_markdown(essay_path)
                Path(essay_path).unlink()

    def test_parse_essay_missing_reference_answer_fails(self):
        essay_path = self.write_quiz(
            "# Essay Question: requirements.txt\n\n"
            "## Question\nQ\n\n"
            "## Instructions for Students\nI\n\n"
            "## Evaluation Criteria (Total: 1 points)\n"
            "1. **Only criterion (1 point)**\n"
            "- detail\n\n"
            "## AI Evaluation Rules\nR\n\n"
            "## Output Format\nO\n"
        )
        with self.assertRaisesRegex(ValueError, "missing required section\\(s\\): Reference Answer"):
            parse_essay_markdown(essay_path)
        Path(essay_path).unlink()

    def test_parse_essay_points_mismatch_fails(self):
        essay_path = self.write_quiz(
            "# Essay Question: requirements.txt\n\n"
            "## Question\nQ\n\n"
            "## Instructions for Students\nI\n\n"
            "## Evaluation Criteria (Total: 4 points)\n"
            "1. **Only criterion (1 point)**\n"
            "- detail\n\n"
            "## Reference Answer\nA\n\n"
            "## AI Evaluation Rules\nR\n\n"
            "## Output Format\nO\n"
        )
        with self.assertRaisesRegex(ValueError, "criteria points sum"):
            parse_essay_markdown(essay_path)
        Path(essay_path).unlink()

    def test_parse_essay_empty_output_format_fails(self):
        essay_path = self.write_quiz(
            "# Essay Question: requirements.txt\n\n"
            "## Question\nQ\n\n"
            "## Instructions for Students\nI\n\n"
            "## Evaluation Criteria (Total: 1 points)\n"
            "1. **Only criterion (1 point)**\n"
            "- detail\n\n"
            "## Reference Answer\nA\n\n"
            "## AI Evaluation Rules\nR\n\n"
            "## Output Format\n\n"
        )
        with self.assertRaisesRegex(ValueError, "Output Format.*cannot be empty"):
            parse_essay_markdown(essay_path)
        Path(essay_path).unlink()

    def test_collect_essay_answer_via_editor(self):
        seen_template = {"value": ""}

        def fake_editor(cmd, check):
            target = Path(cmd[-1])
            seen_template["value"] = target.read_text(encoding="utf-8")
            target.write_text("Line 1\nLine 2\n", encoding="utf-8")

        with patch("subprocess.run", side_effect=fake_editor):
            with patch.dict("os.environ", {"EDITOR": "fake-editor"}, clear=False):
                answer = collect_essay_answer_via_editor("Sample")
        self.assertEqual(answer, "Line 1\nLine 2")
        self.assertIn(":wq!", seen_template["value"])

    def test_collect_essay_answer_template_includes_question_text(self):
        seen_template = {"value": ""}

        def fake_editor(cmd, check):
            target = Path(cmd[-1])
            seen_template["value"] = target.read_text(encoding="utf-8")
            target.write_text("Line 1\n", encoding="utf-8")

        with patch("subprocess.run", side_effect=fake_editor):
            with patch.dict("os.environ", {"EDITOR": "fake-editor"}, clear=False):
                answer = collect_essay_answer_via_editor("Title", "Why do we use .venv?")
        self.assertEqual(answer, "Line 1")
        self.assertIn("# Why do we use .venv?", seen_template["value"])

    def test_collect_essay_answer_inline_stops_on_end(self):
        with patch("builtins.print"):
            with patch("quizmd.prompt_input", side_effect=["Line 1", "Line 2", "/end"]):
                answer = collect_essay_answer_inline("Sample", "Question")
        self.assertEqual(answer, "Line 1\nLine 2")

    def test_collect_essay_answer_inline_rejects_empty_answer(self):
        with patch("builtins.print"):
            with patch("quizmd.prompt_input", side_effect=["", "   ", "/end"]):
                with self.assertRaisesRegex(RuntimeError, "No essay answer"):
                    collect_essay_answer_inline("Sample", "Question")

    def test_format_possessive_handles_names_ending_with_s(self):
        self.assertEqual(_format_possessive("Stelios"), "Stelios'")
        self.assertEqual(_format_possessive("Anna"), "Anna's")

    def test_score_encouragement_ranges(self):
        self.assertEqual(_score_encouragement(49.99), "Don’t worry — try again! 💪")
        self.assertEqual(
            _score_encouragement(50.0),
            "Great effort! With a bit more practice, you’ll be a star. ⭐",
        )
        self.assertEqual(
            _score_encouragement(75.0),
            "Great effort! With a bit more practice, you’ll be a star. ⭐",
        )
        self.assertEqual(_score_encouragement(75.01), "You’re rocking it! 🚀")

    def test_collect_essay_answer_windows_notepad_prompt(self):
        def fake_editor(cmd, check):
            Path(cmd[-1]).write_text("Windows answer\n", encoding="utf-8")

        with patch("quizmd._is_windows", return_value=True):
            with patch.dict("os.environ", {}, clear=True):
                with patch("quizmd.ask_yes_no", return_value=True):
                    with patch("subprocess.run", side_effect=fake_editor):
                        with patch("builtins.print") as mocked_print:
                            answer = collect_essay_answer_via_editor("Sample")
        self.assertEqual(answer, "Windows answer")
        self.assertTrue(any("save and close Notepad" in str(call) for call in mocked_print.call_args_list))

    def test_collect_essay_answer_windows_notepad_prompt_declined(self):
        with patch("quizmd._is_windows", return_value=True):
            with patch.dict("os.environ", {}, clear=True):
                with patch("quizmd.ask_yes_no", return_value=False):
                    with self.assertRaisesRegex(RuntimeError, "No editor configured on Windows"):
                        collect_essay_answer_via_editor("Sample")

    def test_collect_essay_answer_windows_fallback_when_editor_fails(self):
        calls = {"n": 0}

        def flaky_editor(cmd, check):
            calls["n"] += 1
            if calls["n"] == 1:
                raise FileNotFoundError("missing")
            Path(cmd[-1]).write_text("Recovered answer\n", encoding="utf-8")

        with patch("quizmd._is_windows", return_value=True):
            with patch.dict("os.environ", {"EDITOR": "missing-editor"}, clear=False):
                with patch("quizmd.ask_yes_no", return_value=True):
                    with patch("subprocess.run", side_effect=flaky_editor):
                        answer = collect_essay_answer_via_editor("Sample")
        self.assertEqual(answer, "Recovered answer")
        self.assertGreaterEqual(calls["n"], 2)

    def test_gemini_evaluation_success(self):
        essay = {
            "question": "Q",
            "criteria": [{"name": "A", "points": 1, "details": ["x"]}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
        }

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self):
                payload = {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": json.dumps({
                                        "points_awarded": 1,
                                        "total_points": 1,
                                        "score_percent": 100,
                                        "did_well": ["A"],
                                        "missing": [],
                                        "suggestions": ["Good"],
                                    })}
                                ]
                            }
                        }
                    ]
                }
                return json.dumps(payload).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = evaluate_essay_with_gemini(essay, "student", "k", "gemini-1.5-flash", 5, max_retries=0)
        self.assertEqual(result["score_percent"], 100.0)
        self.assertFalse(result["ai_unavailable"])

    def test_gemini_retries_then_success(self):
        essay = {
            "question": "Q",
            "criteria": [{"name": "A", "points": 1, "details": ["x"]}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
        }

        class FakeHTTPError(Exception):
            def __init__(self, code):
                super().__init__(f"HTTP {code}")
                self.code = code

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self):
                payload = {
                    "candidates": [{"content": {"parts": [{"text": json.dumps({
                        "points_awarded": 1,
                        "total_points": 1,
                        "score_percent": 100,
                        "did_well": ["A"],
                        "missing": [],
                        "suggestions": ["Good"],
                    })}]}}]
                }
                return json.dumps(payload).encode("utf-8")

        calls = {"n": 0}
        def flaky_urlopen(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise FakeHTTPError(429)
            return FakeResponse()

        with patch("urllib.request.urlopen", side_effect=flaky_urlopen):
            with patch("time.sleep", return_value=None):
                result = evaluate_essay_with_gemini(essay, "student", "k", "gemini-1.5-flash", 5, max_retries=2)
        self.assertEqual(result["total_points"], 1)
        self.assertGreaterEqual(calls["n"], 2)

    def test_gemini_normalizes_single_item_list_response(self):
        essay = {
            "question": "Q",
            "criteria": [{"name": "A", "points": 1, "details": ["x"]}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
        }

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self):
                model_json = [{
                    "points_awarded": 1,
                    "total_points": 1,
                    "score_percent": 99.0,
                    "did_well": "good coverage",
                    "missing": None,
                    "suggestions": ("be concise",),
                }]
                payload = {"candidates": [{"content": {"parts": [{"text": json.dumps(model_json)}]}}]}
                return json.dumps(payload).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = evaluate_essay_with_gemini(essay, "student", "k", "gemini-1.5-flash", 5, max_retries=0)
        self.assertEqual(result["total_points"], 1)
        self.assertEqual(result["did_well"], ["good coverage"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["suggestions"], ["be concise"])

    def test_gemini_retry_exhaustion_raises(self):
        essay = {
            "question": "Q",
            "criteria": [{"name": "A", "points": 1, "details": ["x"]}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
        }
        class FakeHTTPError(Exception):
            def __init__(self, code):
                super().__init__(f"HTTP {code}")
                self.code = code

        with patch("urllib.request.urlopen", side_effect=FakeHTTPError(500)):
            with patch("time.sleep", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "Gemini evaluation failed"):
                    evaluate_essay_with_gemini(essay, "student", "k", "gemini-1.5-flash", 5, max_retries=1)

    def test_gemini_payload_too_large_fails_before_network(self):
        essay = {
            "question": "Q" * 30_000,
            "criteria": [{"name": "A", "points": 1, "details": ["x"]}],
            "total_points": 1,
            "reference_answer": "R" * 30_000,
            "ai_evaluation_rules": "Rules",
        }
        with patch("urllib.request.urlopen") as mocked_urlopen:
            with self.assertRaisesRegex(RuntimeError, "payload_too_large"):
                evaluate_essay_with_gemini(essay, "student", "k", "gemini-1.5-flash", 5, max_retries=0)
        mocked_urlopen.assert_not_called()

    def test_openai_evaluation_success(self):
        essay = {
            "question": "Q",
            "criteria": [{"name": "A", "points": 1, "details": ["x"]}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
        }

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self):
                payload = {
                    "choices": [
                        {"message": {"content": json.dumps({
                            "points_awarded": 1,
                            "total_points": 1,
                            "score_percent": 100,
                            "did_well": ["A"],
                            "missing": [],
                            "suggestions": ["Good"],
                        })}}
                    ]
                }
                return json.dumps(payload).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = evaluate_essay_with_openai(essay, "student", "k", "gpt-4o-mini", 5, max_retries=0)
        self.assertEqual(result["score_percent"], 100.0)
        self.assertFalse(result["ai_unavailable"])

    def test_anthropic_evaluation_success(self):
        essay = {
            "question": "Q",
            "criteria": [{"name": "A", "points": 1, "details": ["x"]}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
        }

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self):
                payload = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "points_awarded": 1,
                                "total_points": 1,
                                "score_percent": 100,
                                "did_well": ["A"],
                                "missing": [],
                                "suggestions": ["Good"],
                            }),
                        }
                    ]
                }
                return json.dumps(payload).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = evaluate_essay_with_anthropic(essay, "student", "k", "claude-3-5-haiku-latest", 5, max_retries=0)
        self.assertEqual(result["score_percent"], 100.0)
        self.assertFalse(result["ai_unavailable"])

    def test_provider_helpers(self):
        self.assertEqual(_env_key_for_provider("gemini"), "GEMINI_API_KEY")
        self.assertEqual(_env_key_for_provider("openai"), "OPENAI_API_KEY")
        self.assertEqual(_env_key_for_provider("anthropic"), "ANTHROPIC_API_KEY")
        self.assertEqual(_default_model_for_provider("openai"), DEFAULT_OPENAI_MODEL)
        self.assertEqual(_default_model_for_provider("anthropic"), DEFAULT_ANTHROPIC_MODEL)
        self.assertIs(_evaluator_for_provider("openai"), evaluate_essay_with_openai)
        self.assertIs(_evaluator_for_provider("anthropic"), evaluate_essay_with_anthropic)
        with patch.dict("os.environ", {"GEMINI_API_KEY": "g", "OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"}, clear=True):
            self.assertEqual(_resolve_ai_provider("auto"), "gemini")
        with patch.dict("os.environ", {"OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"}, clear=True):
            self.assertEqual(_resolve_ai_provider("auto"), "openai")
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "a"}, clear=True):
            self.assertEqual(_resolve_ai_provider("auto"), "anthropic")
        with patch.dict("os.environ", {"GEMINI_API_KEY": "g", "OPENAI_API_KEY": "o"}, clear=True):
            self.assertEqual(_available_ai_providers_by_priority(), ["gemini", "openai"])
        self.assertEqual(_provider_display_name("openai"), "OpenAI")
        self.assertEqual(_provider_display_name("anthropic"), "Claude")

    def test_deterministic_fallback_no_score(self):
        essay = {
            "criteria": [
                {"name": "Dependency problem", "points": 1, "details": ["versions conflict"]},
                {"name": "Collaboration", "points": 1, "details": ["works on my machine"]},
            ],
            "total_points": 2,
        }
        result = evaluate_essay_deterministic_fallback(
            essay,
            "Different versions conflict in projects.",
            "network down",
            reason_code="network_error",
        )
        self.assertIsNone(result["score_percent"])
        self.assertTrue(result["ai_unavailable"])
        self.assertEqual(result["ai_reason"], "network_error")
        self.assertEqual(result["scoring_mode"], "heuristic_fallback")
        self.assertEqual(result["scoring_confidence"], "low")

    def test_redacted_ai_error_helper(self):
        self.assertEqual(
            _redacted_ai_error("network_error", True),
            "AI unavailable (network_error). Detailed provider error omitted for privacy.",
        )
        self.assertEqual(_redacted_ai_error("none", False), "")

    def test_run_essay_missing_api_key_fails(self):
        essay = {
            "title": "Sample",
            "question": "Q",
            "instructions": "I",
            "criteria": [{"name": "A", "points": 1, "details": []}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
            "output_format": "Format",
        }
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "requires at least one key"):
                run_essay(essay, no_color=True)

    def test_run_essay_missing_api_key_windows_hint(self):
        essay = {
            "title": "Sample",
            "question": "Q",
            "instructions": "I",
            "criteria": [{"name": "A", "points": 1, "details": []}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
            "output_format": "Format",
        }
        with patch("quizmd._is_windows", return_value=True):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaises(RuntimeError) as ctx:
                    run_essay(essay, no_color=True)
        self.assertIn("$env:GEMINI_API_KEY='your_key_here'", str(ctx.exception))

    def test_mcq_validate_does_not_require_gemini_key(self):
        env = os.environ.copy()
        env.pop("GEMINI_API_KEY", None)
        env.pop("NO_COLOR", None)
        result = subprocess.run(
            [sys.executable, "quizmd.py", "--validate", "quizzes/python-basics-quiz.md"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Validation passed", result.stdout)

    def test_run_essay_success_with_mocked_ai(self):
        essay = {
            "title": "Sample",
            "question": "Q",
            "instructions": "I",
            "criteria": [{"name": "A", "points": 1, "details": []}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
            "output_format": "Format",
        }
        fake_grade = {
            "points_awarded": 1,
            "total_points": 1,
            "score_percent": 100.0,
            "did_well": ["A"],
            "missing": [],
            "suggestions": ["Great"],
            "ai_unavailable": False,
            "ai_error": "",
            "ai_reason": "none",
            "scoring_mode": "llm_rubric",
            "scoring_confidence": "high",
        }
        with patch.dict("os.environ", {"GEMINI_API_KEY": "k"}, clear=True):
            with patch("quizmd.prompt_input", return_value=""):
                with patch("quizmd.collect_essay_answer_via_editor", return_value="student answer"):
                    with patch("quizmd.evaluate_essay_with_gemini", return_value=fake_grade):
                        with patch("quizmd.ask_yes_no", return_value=False):
                            with patch("quizmd.evaluate_essay_with_loading", return_value=fake_grade):
                                with patch("rich.console.Console.print"):
                                    run_essay(essay, no_color=True)

    def test_run_essay_next_ui_uses_inline_answer_collection(self):
        essay = {
            "title": "Sample",
            "question": "Q",
            "instructions": "I",
            "criteria": [{"name": "A", "points": 1, "details": []}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
            "output_format": "Format",
        }
        fake_grade = {
            "points_awarded": 1,
            "total_points": 1,
            "score_percent": 100.0,
            "did_well": ["A"],
            "missing": [],
            "suggestions": ["Great"],
            "ai_unavailable": False,
            "ai_error": "",
            "ai_reason": "none",
            "scoring_mode": "llm_rubric",
            "scoring_confidence": "high",
        }
        with patch.dict("os.environ", {"GEMINI_API_KEY": "k"}, clear=True):
            with patch("quizmd.collect_essay_answer_inline", return_value="student answer") as mocked_inline:
                with patch("quizmd.collect_essay_answer_via_editor") as mocked_editor:
                    with patch("quizmd.ask_yes_no", return_value=False):
                        with patch("quizmd.evaluate_essay_with_loading", return_value=fake_grade):
                            with patch("rich.console.Console.print"):
                                run_essay(essay, no_color=True, ui="next")
        mocked_inline.assert_called_once()
        mocked_editor.assert_not_called()

    def test_run_essay_openai_uses_default_model_and_key(self):
        essay = {
            "title": "Sample",
            "question": "Q",
            "instructions": "I",
            "criteria": [{"name": "A", "points": 1, "details": []}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
            "output_format": "Format",
        }
        fake_grade = {
            "points_awarded": 1,
            "total_points": 1,
            "score_percent": 100.0,
            "did_well": ["A"],
            "missing": [],
            "suggestions": ["Great"],
            "ai_unavailable": False,
            "ai_error": "",
            "ai_reason": "none",
            "scoring_mode": "llm_rubric",
            "scoring_confidence": "high",
        }
        with patch.dict("os.environ", {"OPENAI_API_KEY": "k"}, clear=True):
            with patch("quizmd.prompt_input", return_value=""):
                with patch("quizmd.collect_essay_answer_via_editor", return_value="student answer"):
                    with patch("quizmd.ask_yes_no", return_value=False):
                        with patch("quizmd.evaluate_essay_with_loading", return_value=fake_grade) as mocked_loading:
                            with patch("rich.console.Console.print"):
                                run_essay(essay, no_color=True, ai_provider="openai", ai_model="")
        self.assertEqual(mocked_loading.call_args.kwargs["model"], DEFAULT_OPENAI_MODEL)

    def test_run_essay_openai_missing_key_fails(self):
        essay = {
            "title": "Sample",
            "question": "Q",
            "instructions": "I",
            "criteria": [{"name": "A", "points": 1, "details": []}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
            "output_format": "Format",
        }
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "requires OPENAI_API_KEY"):
                run_essay(essay, no_color=True, ai_provider="openai")

    def test_run_essay_openai_missing_key_posix_hint(self):
        essay = {
            "title": "Sample",
            "question": "Q",
            "instructions": "I",
            "criteria": [{"name": "A", "points": 1, "details": []}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
            "output_format": "Format",
        }
        with patch("quizmd._is_windows", return_value=False):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaises(RuntimeError) as ctx:
                    run_essay(essay, no_color=True, ai_provider="openai")
        self.assertIn("export OPENAI_API_KEY='your_key_here'", str(ctx.exception))

    def test_run_essay_auto_priority_prefers_gemini(self):
        essay = {
            "title": "Sample",
            "question": "Q",
            "instructions": "I",
            "criteria": [{"name": "A", "points": 1, "details": []}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
            "output_format": "Format",
        }
        fake_grade = {
            "points_awarded": 1,
            "total_points": 1,
            "score_percent": 100.0,
            "did_well": ["A"],
            "missing": [],
            "suggestions": ["Great"],
            "ai_unavailable": False,
            "ai_error": "",
            "ai_reason": "none",
            "scoring_mode": "llm_rubric",
            "scoring_confidence": "high",
        }
        with patch.dict(
            "os.environ",
            {"GEMINI_API_KEY": "g", "OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"},
            clear=True,
        ):
            with patch("quizmd.prompt_input", return_value=""):
                with patch("quizmd.collect_essay_answer_via_editor", return_value="student answer"):
                    with patch("quizmd.ask_yes_no", return_value=False):
                        with patch("quizmd.evaluate_essay_with_loading", return_value=fake_grade) as mocked_loading:
                            with patch("rich.console.Console.print"):
                                run_essay(essay, no_color=True, ai_provider="auto", ai_model="")
        self.assertIs(mocked_loading.call_args.args[2], evaluate_essay_with_gemini)

    def test_run_essay_auto_falls_back_to_openai_if_gemini_fails(self):
        essay = {
            "title": "Sample",
            "question": "Q",
            "instructions": "I",
            "criteria": [{"name": "A", "points": 1, "details": []}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
            "output_format": "Format",
        }
        fake_grade = {
            "points_awarded": 1,
            "total_points": 1,
            "score_percent": 100.0,
            "did_well": ["A"],
            "missing": [],
            "suggestions": ["Great"],
            "ai_unavailable": False,
            "ai_error": "",
            "ai_reason": "none",
            "scoring_mode": "llm_rubric",
            "scoring_confidence": "high",
        }

        calls = {"n": 0}
        seen_evaluators = []

        def fake_loading(*args, **kwargs):
            calls["n"] += 1
            seen_evaluators.append(args[2])
            if calls["n"] == 1:
                raise RuntimeError("[timeout] Gemini timeout")
            return fake_grade

        with patch.dict(
            "os.environ",
            {"GEMINI_API_KEY": "g", "OPENAI_API_KEY": "o"},
            clear=True,
        ):
            with patch("quizmd.prompt_input", return_value=""):
                with patch("quizmd.collect_essay_answer_via_editor", return_value="student answer"):
                    with patch("quizmd.ask_yes_no", return_value=False):
                        with patch("quizmd.evaluate_essay_with_loading", side_effect=fake_loading):
                            with patch("rich.console.Console.print"):
                                run_essay(essay, no_color=True, ai_provider="auto", ai_model="")
        self.assertEqual(calls["n"], 2)
        self.assertIs(seen_evaluators[0], evaluate_essay_with_gemini)
        self.assertIs(seen_evaluators[1], evaluate_essay_with_openai)

    def test_run_essay_auto_failover_displays_actual_connected_provider(self):
        essay = {
            "title": "Sample",
            "question": "Q",
            "instructions": "I",
            "criteria": [{"name": "A", "points": 1, "details": []}],
            "total_points": 1,
            "reference_answer": "R",
            "ai_evaluation_rules": "Rules",
            "output_format": "Format",
        }
        fake_grade = {
            "points_awarded": 1,
            "total_points": 1,
            "score_percent": 100.0,
            "did_well": ["A"],
            "missing": [],
            "suggestions": ["Great"],
            "ai_unavailable": False,
            "ai_error": "",
            "ai_reason": "none",
            "scoring_mode": "llm_rubric",
            "scoring_confidence": "high",
        }
        calls = {"n": 0}

        def fake_loading(*args, **kwargs):
            calls["n"] += 1
            evaluator = args[2]
            if evaluator is evaluate_essay_with_gemini:
                raise RuntimeError("[timeout] Gemini timeout")
            return fake_grade

        out = io.StringIO()
        with patch.dict("os.environ", {"GEMINI_API_KEY": "g", "OPENAI_API_KEY": "o"}, clear=True):
            with patch("quizmd.prompt_input", return_value=""):
                with patch("quizmd.collect_essay_answer_via_editor", return_value="student answer"):
                    with patch("quizmd.ask_yes_no", return_value=False):
                        with patch("quizmd.evaluate_essay_with_loading", side_effect=fake_loading):
                            with contextlib.redirect_stdout(out):
                                run_essay(essay, no_color=True, ai_provider="auto", ai_model="")

        output = out.getvalue()
        self.assertEqual(calls["n"], 2)
        self.assertIn("Connected: OpenAI", output)
        self.assertNotIn("Connected: Gemini", output)

    def test_save_essay_attempt_outputs_files(self):
        payload = {
            "mode": "essay",
            "quiz_title": "Essay Quiz",
            "question": "Q",
            "student_answer": "A",
            "points_awarded": 3,
            "total_points": 4,
            "score_percent": 75.0,
            "did_well": ["x"],
            "missing": ["y"],
            "suggestions": ["z"],
            "ai_unavailable": False,
            "ai_error": "",
            "ai_reason": "none",
            "scoring_mode": "llm_rubric",
            "scoring_confidence": "high",
            "ai_provider": "gemini",
            "ai_model": "gemini-1.5-flash",
        }
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                attempt_dir = save_essay_attempt("Essay Quiz", payload)
                self.assertTrue((attempt_dir / "answers.json").exists())
                self.assertTrue((attempt_dir / "answers.txt").exists())
            finally:
                os.chdir(old_cwd)

    def test_save_essay_attempt_redacts_ai_error(self):
        payload = {
            "mode": "essay",
            "quiz_title": "Essay Quiz",
            "question": "Q",
            "student_answer": "A",
            "points_awarded": None,
            "total_points": 4,
            "score_percent": None,
            "did_well": [],
            "missing": ["x"],
            "suggestions": ["y"],
            "ai_unavailable": True,
            "ai_error": "HTTP 500 raw provider body ...",
            "ai_reason": "server_error",
            "scoring_mode": "heuristic_fallback",
            "scoring_confidence": "low",
            "ai_provider": "gemini",
            "ai_model": "gemini-flash-latest",
        }
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                attempt_dir = save_essay_attempt("Essay Quiz", payload)
                stored = json.loads((attempt_dir / "answers.json").read_text(encoding="utf-8"))
                self.assertEqual(
                    stored["ai_error"],
                    "AI unavailable (server_error). Detailed provider error omitted for privacy.",
                )
            finally:
                os.chdir(old_cwd)

    def test_validate_cli_fails_for_invalid_quiz(self):
        quiz_path = self.write_quiz(
            "# Broken Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Type: single\n"
        )
        result = subprocess.run(
            [sys.executable, "quizmd.py", "--validate", quiz_path],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Validation failed", result.stderr)

        Path(quiz_path).unlink()

    def test_validate_cli_fails_with_missing_file(self):
        result = subprocess.run(
            [sys.executable, "quizmd.py", "--validate", "quizzes/does-not-exist.md"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("File error", result.stderr)

    def test_cli_ai_timeout_must_be_positive(self):
        result = subprocess.run(
            [sys.executable, "quizmd.py", "--ai-timeout", "0", "--validate", "quizzes/python-basics-quiz.md"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--ai-timeout must be greater than zero", result.stderr)

    def test_cli_help_mentions_auto_provider_priority(self):
        result = subprocess.run(
            [sys.executable, "quizmd.py", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("auto", result.stdout)
        self.assertIn("'auto' priority: gemini ->", result.stdout)
        self.assertIn("openai -> anthropic", result.stdout)

    def test_invalid_answer_value_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: one\n"
            "Type: single\n"
        )

        with self.assertRaisesRegex(ValueError, "invalid answer value"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_invalid_time_value_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1\n"
            "Type: single\n"
            "Time: soon\n"
        )

        with self.assertRaisesRegex(ValueError, "invalid time value"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_zero_or_negative_time_value_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1\n"
            "Type: single\n"
            "Time: 0\n"
        )

        with self.assertRaisesRegex(ValueError, "time limit must be greater than zero"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_out_of_range_answer_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 3\n"
            "Type: single\n"
        )

        with self.assertRaisesRegex(ValueError, "out of range"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_missing_answer_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Type: single\n"
        )

        with self.assertRaisesRegex(ValueError, "missing required field\\(s\\): answer"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_missing_options_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "Answer: 1\n"
            "Type: single\n"
        )

        with self.assertRaisesRegex(ValueError, "missing required field\\(s\\): options"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_blank_option_text_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- \n"
            "- B\n\n"
            "Answer: 2\n"
            "Type: single\n"
        )

        with self.assertRaisesRegex(ValueError, "blank option text"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_question_must_have_at_least_two_options(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n\n"
            "Answer: 1\n"
            "Type: single\n"
        )

        with self.assertRaisesRegex(ValueError, "at least two options"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_missing_type_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1\n"
        )

        with self.assertRaisesRegex(ValueError, "missing required field\\(s\\): type"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_invalid_type_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1\n"
            "Type: essay\n"
        )

        with self.assertRaisesRegex(ValueError, "unsupported question type"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_duplicate_answer_indexes_raise_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1,1\n"
            "Type: multiple\n"
        )

        with self.assertRaisesRegex(ValueError, "duplicate answer indexes"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_single_choice_with_multiple_answers_is_rejected(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1,2\n"
            "Type: single\n"
        )

        with self.assertRaisesRegex(ValueError, "must have exactly one answer"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_no_questions_raises_clear_error(self):
        quiz_path = self.write_quiz("# Empty Quiz\n")

        with self.assertRaisesRegex(ValueError, "no valid questions found"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_malformed_block_missing_question_text_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
        )

        with self.assertRaisesRegex(ValueError, "missing the question text line"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_unexpected_content_outside_question_blocks_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "This text should not be outside a question block.\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1\n"
            "Type: single\n"
        )

        with self.assertRaisesRegex(ValueError, "unexpected content outside question blocks"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_unrecognized_line_in_question_raises_clear_error(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Hint: this should not be allowed\n"
            "Answer: 1\n"
            "Type: single\n"
        )

        with self.assertRaisesRegex(ValueError, "unrecognized line"):
            parse_quiz_markdown(quiz_path)

        Path(quiz_path).unlink()

    def test_parser_accepts_indented_options_and_spaced_fields(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "   - A\n"
            "   - B\n\n"
            "Answer : 2\n"
            "Type : single\n"
            "Time : 10\n"
        )
        _, questions = parse_quiz_markdown(quiz_path)
        self.assertEqual(questions[0]["correct"], [2])
        self.assertEqual(questions[0]["type"], "single")
        self.assertEqual(questions[0]["time_limit"], 10)
        Path(quiz_path).unlink()

    def test_parser_accepts_multiline_question_with_code_fence(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "What is the time complexity of this code?\n"
            "```python\n"
            "for i in items:\n"
            "    print(i)\n"
            "```\n\n"
            "- O(1)\n"
            "- O(n)\n"
            "- O(n^2)\n\n"
            "Answer: 2\n"
            "Type: single\n"
        )
        _, questions = parse_quiz_markdown(quiz_path)
        self.assertIn("```python", questions[0]["question"])
        self.assertIn("for i in items:", questions[0]["question"])
        self.assertEqual(questions[0]["correct"], [2])
        Path(quiz_path).unlink()

    def test_question_bullet_list_requires_options_marker(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Read this list first:\n"
            "- A key fact\n"
            "- Another fact\n\n"
            "- Correct option\n"
            "- Wrong option\n\n"
            "Answer: 1\n"
            "Type: single\n"
        )
        with self.assertRaisesRegex(ValueError, "Add an 'Options:' line"):
            parse_quiz_markdown(quiz_path)
        Path(quiz_path).unlink()

    def test_question_bullet_list_with_options_marker_is_allowed(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Read this list first:\n"
            "- A key fact\n"
            "- Another fact\n\n"
            "Options:\n"
            "- Correct option\n"
            "- Wrong option\n\n"
            "Answer: 1\n"
            "Type: single\n"
        )
        _, questions = parse_quiz_markdown(quiz_path)
        self.assertIn("- A key fact", questions[0]["question"])
        self.assertEqual(questions[0]["options"], ["Correct option", "Wrong option"])
        Path(quiz_path).unlink()

    def test_blank_explanation_is_allowed(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1\n"
            "Type: single\n"
            "Explanation:   \n"
        )

        _, questions = parse_quiz_markdown(quiz_path)
        self.assertEqual(questions[0]["explanation"], "")

        Path(quiz_path).unlink()

    def test_parse_int_helpers(self):
        source = Path("dummy.md")
        values = parse_int_list("1, 2,3", "answer", "Q1", source)
        self.assertEqual(values, [1, 2, 3])
        value = parse_int_value(" 25 ", "time", "Q1", source)
        self.assertEqual(value, 25)

    def test_prompt_input_raises_runtime_error_on_eof(self):
        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaisesRegex(RuntimeError, "Interactive input is not available"):
                prompt_input("Enter: ")

    def test_run_coroutine_sync_with_running_loop(self):
        async def inner():
            return run_coroutine_sync(self._example_coro())

        result = run_coroutine_sync(inner())
        self.assertEqual(result, "ok")

    async def _example_coro(self):
        return "ok"

    def test_slugify_and_format_labels_helpers(self):
        self.assertEqual(slugify("  Data Science Quiz! "), "data-science-quiz")
        self.assertEqual(slugify("###"), "quiz")
        labels = format_labels(["A", "B", "C"], [1, 3])
        self.assertEqual(labels, "1. A; 3. C")
        self.assertEqual(format_labels(["A"], None), "")

    def test_display_width_handles_cjk_and_emoji(self):
        self.assertEqual(display_width("abc"), 3)
        self.assertGreaterEqual(display_width("😱"), 2)
        self.assertGreaterEqual(display_width("日本"), 4)

    def test_select_theme_uses_env_override(self):
        with patch.dict("os.environ", {"QUIZMD_THEME": "light"}, clear=False):
            theme = select_theme("auto")
            self.assertEqual(theme["pt_title"], THEMES["light"]["pt_title"])

    def test_select_theme_uses_terminal_theme_hint(self):
        with patch.dict("os.environ", {"TERMINAL_THEME": "Light"}, clear=False):
            theme = select_theme("auto")
            self.assertEqual(theme["pt_title"], THEMES["light"]["pt_title"])

    def test_select_theme_uses_colorscheme_hint(self):
        with patch.dict("os.environ", {"COLORSCHEME": "Dark Plus"}, clear=False):
            theme = select_theme("auto")
            self.assertEqual(theme["pt_title"], THEMES["dark"]["pt_title"])

    def test_no_color_detection_from_cli_or_env(self):
        self.assertTrue(is_no_color_requested(True))
        with patch.dict("os.environ", {"NO_COLOR": "1"}, clear=False):
            self.assertTrue(is_no_color_requested(False))

    def test_compact_layout_detection_from_terminal_width(self):
        with patch("os.get_terminal_size", return_value=os.terminal_size((80, 24))):
            self.assertTrue(should_use_compact_layout())
        with patch("os.get_terminal_size", return_value=os.terminal_size((140, 24))):
            self.assertFalse(should_use_compact_layout())

    def test_safe_for_stream_handles_non_utf8_encodings(self):
        class FakeStream:
            encoding = "cp1252"

        text = safe_for_stream("Validation passed: 🦉 Harry Potter Quiz", FakeStream())
        self.assertIn("Validation passed:", text)

    def test_save_attempt_writes_json_and_text_outputs(self):
        questions = [
            {
                "title": "Question 1",
                "question": "Pick one",
                "options": ["A", "B"],
                "correct": [2],
                "type": "single",
                "time_limit": 10,
                "explanation": "Because B",
            }
        ]
        answers = [
            {
                "question_title": "Question 1",
                "question_text": "Pick one",
                "selected_indexes": [2],
                "selected_labels": "2. B",
                "correct_indexes": [2],
                "correct_labels": "2. B",
                "is_correct": True,
                "explanation": "Because B",
            }
        ]

        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                attempt_dir = save_attempt("Demo Quiz", 1, questions, answers)
                self.assertTrue((attempt_dir / "answers.json").exists())
                self.assertTrue((attempt_dir / "answers.txt").exists())

                payload = json.loads((attempt_dir / "answers.json").read_text(encoding="utf-8"))
                self.assertEqual(payload["quiz_title"], "Demo Quiz")
                self.assertEqual(payload["score"], 1)
                self.assertEqual(payload["total_questions"], 1)
                self.assertEqual(len(payload["answers"]), 1)

                text_output = (attempt_dir / "answers.txt").read_text(encoding="utf-8")
                self.assertIn("Quiz: Demo Quiz", text_output)
                self.assertIn("Score: 1/1", text_output)
                self.assertIn("Result: Correct", text_output)
            finally:
                os.chdir(old_cwd)

    def test_question_status_label_non_imposter(self):
        self.assertEqual(
            question_status_label({"imposter_mode": False, "answer_correct": True}),
            "Correct",
        )
        self.assertEqual(
            question_status_label({"imposter_mode": False, "answer_correct": False}),
            "Wrong",
        )

    def test_question_status_label_imposter_mode(self):
        self.assertEqual(
            question_status_label(
                {"imposter_mode": True, "is_perfect": True, "question_points": 2}
            ),
            "Correct",
        )
        self.assertEqual(
            question_status_label(
                {"imposter_mode": True, "is_perfect": False, "question_points": 1}
            ),
            "Partially Correct",
        )
        self.assertEqual(
            question_status_label(
                {"imposter_mode": True, "is_perfect": False, "question_points": 0}
            ),
            "Wrong",
        )

    def test_run_imposter_mode_saves_imposter_fields_end_to_end(self):
        questions = [
            {
                "title": "Question 1",
                "question": "Pick the true statement",
                "options": ["Correct", "Wrong A", "Wrong B"],
                "correct": [1],
                "imposters": [2, 3],
                "type": "single",
                "time_limit": 20,
                "explanation": "Because statement 1 is true.",
            }
        ]
        grading = {
            "answer_correct": True,
            "imposter_mode": True,
            "expected_imposters": [2, 3],
            "imposters_selected": [2],
            "imposter_true_positive": 1,
            "imposter_false_positive": 0,
            "imposter_false_negative": 1,
            "imposter_points": 1,
            "question_points": 2,
            "question_max_points": 3,
            "is_perfect": False,
        }

        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                def fake_run_coroutine(coro):
                    # Prevent un-awaited coroutine warnings in tests that bypass async execution.
                    try:
                        coro.close()
                    except Exception:
                        pass
                    return (False, [1], [2], grading)

                with patch("quizmd.prompt_input", return_value=""):
                    with patch("quizmd.run_coroutine_sync", side_effect=fake_run_coroutine):
                        with patch("quizmd.ask_to_save_answers", return_value=True):
                            with patch("rich.console.Console.print"):
                                run("Imposter Demo", questions, no_color=True, full_screen=False)

                attempt_dir = Path("answers/imposter-demo-1")
                self.assertTrue((attempt_dir / "answers.json").exists())
                payload = json.loads((attempt_dir / "answers.json").read_text(encoding="utf-8"))
                self.assertEqual(payload["score"], 2)
                self.assertEqual(payload["score_total"], 3)
                self.assertEqual(payload["answers"][0]["selected_imposters"], [2])
                self.assertEqual(payload["answers"][0]["expected_imposters"], [2, 3])
                self.assertEqual(payload["answers"][0]["question_points"], 2)
                self.assertEqual(payload["answers"][0]["question_max_points"], 3)
                self.assertEqual(payload["answers"][0]["result_label"], "Partially Correct")
            finally:
                os.chdir(old_cwd)

    def test_build_question_markup_escapes_special_characters(self):
        question = {
            "title": "Question <1>",
            "question": "Is 2 < 3 & 4 > 1?",
            "options": ["Yes & always", "No <never>"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }

        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=10,
            is_multiple=False,
        )

        self.assertIn("Is 2 &lt; 3 &amp; 4 &gt; 1?", str(markup))

    def test_build_question_markup_supports_basic_markdown_and_emoji(self):
        question = {
            "title": "Question 1",
            "question": "Pick **one** emoji: 🧠",
            "options": ["`A`", "*B*"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }

        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=10,
            is_multiple=False,
        )
        rendered = str(markup)
        self.assertIn("<b>one</b>", rendered)
        self.assertIn("🧠", rendered)
        self.assertIn("ansiyellow", rendered)
        self.assertIn("<i>B</i>", rendered)

    def test_build_question_markup_uses_single_and_multiple_symbols(self):
        base_question = {
            "title": "Question 1",
            "question": "Pick",
            "options": ["A", "B"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }

        single_markup = build_question_markup(
            base_question,
            THEMES["dark"],
            selected=0,
            marked={1},
            remaining=10,
            is_multiple=False,
        )
        self.assertIn("◉", single_markup)
        self.assertIn("○", single_markup)
        self.assertIn("[SINGLE ○]", single_markup)

        multiple_markup = build_question_markup(
            base_question,
            THEMES["dark"],
            selected=0,
            marked={1},
            remaining=10,
            is_multiple=True,
        )
        self.assertIn("☑", multiple_markup)
        self.assertIn("☐", multiple_markup)
        self.assertIn("[MULTI ☑]", multiple_markup)

    def test_build_question_markup_no_color_plain_output(self):
        question = {
            "title": "Question 1",
            "question": "Pick one",
            "options": ["A", "B"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }
        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked={1},
            remaining=10,
            is_multiple=False,
            no_color=True,
        )
        self.assertNotIn("<style", markup)
        self.assertIn("(*)", markup)

    def test_build_question_markup_shows_progress_and_timer_states(self):
        question = {
            "title": "Question 1",
            "question": "Pick one",
            "options": ["A", "B"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }

        normal = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=20,
            is_multiple=False,
            question_index=3,
            total_questions=10,
        )
        warning = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=8,
            is_multiple=False,
            question_index=3,
            total_questions=10,
        )
        danger = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=4,
            is_multiple=False,
            question_index=3,
            total_questions=10,
        )

        self.assertIn("Question 3/10", normal)
        self.assertIn("ansiyellow", normal)
        self.assertIn("ansimagenta", warning)
        self.assertIn("ansired", danger)
        self.assertIn("Space select • Enter", normal)

    def test_build_question_markup_blinks_timer_under_ten_seconds(self):
        question = {
            "title": "Question 1",
            "question": "Pick one",
            "options": ["A", "B"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }
        blink = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=8,
            is_multiple=False,
            timer_blink=True,
        )
        self.assertIn("😱", blink)
        self.assertIn("8s", blink)

    def test_build_question_markup_imposter_mode_instructions_and_markers(self):
        question = {
            "title": "Question 1",
            "question": "Pick one",
            "options": ["A", "B", "C"],
            "correct": [1],
            "imposters": [2, 3],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }
        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=1,
            marked={1},
            remaining=9,
            imposter_marked={2},
            is_multiple=False,
            imposter_mode=True,
        )
        self.assertIn("[2 IMPOSTERS]", markup)
        self.assertIn("Space/X/Enter", markup)
        self.assertIn("✖", markup)

    def test_build_question_markup_next_ui_shows_selection_chips(self):
        question = {
            "title": "Question 1",
            "question": "Pick one",
            "options": ["A", "B", "C"],
            "correct": [1],
            "imposters": [2],
            "type": "multiple",
            "time_limit": 10,
            "explanation": "",
        }
        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=1,
            marked={1, 3},
            remaining=9,
            imposter_marked={2},
            is_multiple=True,
            imposter_mode=True,
            ui="next",
        )
        self.assertIn("[selected]", markup)
        self.assertIn("[imposter]", markup)
        self.assertIn("[x]", markup)

    def test_build_question_markup_next_ui_no_color_is_ascii_safe(self):
        question = {
            "title": "Question 1",
            "question": "Pick one",
            "options": ["A", "B"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }
        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked={1},
            remaining=9,
            is_multiple=False,
            ui="next",
            no_color=True,
        )
        self.assertIn("[selected]", markup)
        self.assertNotIn("◉", markup)
        self.assertNotIn("☑", markup)

    def test_build_question_markup_single_imposter_badge(self):
        question = {
            "title": "Question 1",
            "question": "Pick one",
            "options": ["A", "B", "C"],
            "correct": [1],
            "imposters": [2],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }
        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=12,
            imposter_marked=set(),
            is_multiple=False,
            imposter_mode=True,
        )
        self.assertIn("[1 IMPOSTER]", markup)
        self.assertNotIn("[2 IMPOSTERS]", markup)

    def test_build_question_markup_no_imposter_badge_without_imposters(self):
        question = {
            "title": "Question 1",
            "question": "Pick one",
            "options": ["A", "B"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }
        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=12,
            imposter_marked=set(),
            is_multiple=False,
            imposter_mode=False,
        )
        self.assertNotIn("IMPOSTER", markup)

    def test_build_question_markup_ultra_compact_wraps_and_truncates_options(self):
        question = {
            "title": "Question 1",
            "question": "Pick one",
            "options": [
                "This is a very long option text that should wrap and then truncate when terminal width is tiny."
            ],
            "correct": [1],
            "imposters": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }
        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=9,
            imposter_marked=set(),
            is_multiple=False,
            imposter_mode=True,
            terminal_width=60,
            compact=True,
        )
        self.assertIn("Q 1/1", markup)
        self.assertIn("Sp/X/En", markup)
        self.assertIn("…", markup)

    def test_build_question_markup_compact_windows_uses_ascii_safe_header(self):
        question = {
            "title": "Question 1",
            "question": "Pick one",
            "options": ["A", "B"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }
        with patch("quizmd._is_windows", return_value=True):
            compact = build_question_markup(
                question,
                THEMES["dark"],
                selected=0,
                marked=set(),
                remaining=8,
                is_multiple=False,
                compact=True,
            )
        self.assertIn("WARN 8s", compact)
        self.assertIn("[SINGLE]", compact)
        self.assertIn("Space select | Enter", compact)

    def test_build_question_markup_handles_multiline_question_box(self):
        question = {
            "title": "Question 1",
            "question": "Line one\n```python\nprint('x')\n```",
            "options": ["A", "B"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }
        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=10,
            is_multiple=False,
            question_index=1,
            total_questions=2,
        )
        self.assertIn("print", markup)
        self.assertNotIn("```", markup)
        self.assertIn("bg='#1d2630'", markup)

    def test_build_question_markup_pulse_style_for_selected_choice(self):
        question = {
            "title": "Question 1",
            "question": "Pick",
            "options": ["A", "B"],
            "correct": [1],
            "type": "single",
            "time_limit": 10,
            "explanation": "",
        }
        markup = build_question_markup(
            question,
            THEMES["dark"],
            selected=0,
            marked=set(),
            remaining=10,
            is_multiple=False,
            question_index=1,
            total_questions=2,
            pulse=True,
        )
        self.assertIn("bg='ansiwhite'", markup)

    def test_main_smoke_routes_to_mcq_runner(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1\n"
            "Type: single\n"
        )
        try:
            with patch("sys.argv", ["quizmd.py", quiz_path]):
                with patch("quizmd.run") as mocked_run:
                    main()
            mocked_run.assert_called_once()
        finally:
            Path(quiz_path).unlink(missing_ok=True)

    def test_main_full_screen_flag_routes_to_mcq_runner(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1\n"
            "Type: single\n"
        )
        try:
            with patch("sys.argv", ["quizmd.py", "--full-screen", quiz_path]):
                with patch("quizmd.run") as mocked_run:
                    main()
            mocked_run.assert_called_once()
            _, kwargs = mocked_run.call_args
            self.assertTrue(kwargs.get("full_screen"))
        finally:
            Path(quiz_path).unlink(missing_ok=True)

    def test_main_next_ui_flag_routes_to_mcq_runner(self):
        quiz_path = self.write_quiz(
            "# Test Quiz\n\n"
            "## Question 1\n"
            "Pick one\n\n"
            "- A\n"
            "- B\n\n"
            "Answer: 1\n"
            "Type: single\n"
        )
        try:
            with patch("sys.argv", ["quizmd.py", "--ui", "next", quiz_path]):
                with patch("quizmd.run") as mocked_run:
                    main()
            _, kwargs = mocked_run.call_args
            self.assertEqual(kwargs.get("ui"), "next")
        finally:
            Path(quiz_path).unlink(missing_ok=True)

    def test_main_smoke_routes_to_essay_runner(self):
        essay_path = self.write_valid_essay()
        try:
            with patch("sys.argv", ["quizmd.py", essay_path]):
                with patch("quizmd.run_essay") as mocked_run_essay:
                    main()
            mocked_run_essay.assert_called_once()
        finally:
            Path(essay_path).unlink(missing_ok=True)

    def test_main_next_ui_flag_routes_to_essay_runner(self):
        essay_path = self.write_valid_essay()
        try:
            with patch("sys.argv", ["quizmd.py", "--ui", "next", essay_path]):
                with patch("quizmd.run_essay") as mocked_run_essay:
                    main()
            _, kwargs = mocked_run_essay.call_args
            self.assertEqual(kwargs.get("ui"), "next")
        finally:
            Path(essay_path).unlink(missing_ok=True)

    def test_init_starter_files_creates_expected_files(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                created = init_starter_files(".")
                created_names = sorted(path.name for path in created)
                self.assertEqual(
                    created_names,
                    ["QUIZ_GUIDE.md", "hello-essay.md", "hello-imposter.md", "hello-quiz.md"],
                )
                self.assertTrue(Path("hello-quiz.md").exists())
                self.assertTrue(Path("hello-imposter.md").exists())
                self.assertTrue(Path("hello-essay.md").exists())
                self.assertTrue(Path("QUIZ_GUIDE.md").exists())
                # Ensure starter templates are valid with current strict parsers.
                parse_quiz_markdown("hello-quiz.md")
                parse_quiz_markdown("hello-imposter.md")
                parse_essay_markdown("hello-essay.md")
            finally:
                os.chdir(old_cwd)

    def test_init_starter_files_refuses_overwrite_without_force(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                init_starter_files(".")
                with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
                    init_starter_files(".")
            finally:
                os.chdir(old_cwd)

    def test_main_init_subcommand_runs(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                with patch("sys.argv", ["quizmd.py", "init"]):
                    main()
                self.assertTrue(Path("hello-quiz.md").exists())
                self.assertTrue(Path("hello-imposter.md").exists())
                self.assertTrue(Path("hello-essay.md").exists())
            finally:
                os.chdir(old_cwd)

    def test_main_init_next_ui_creates_same_starter_files(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                with patch("sys.argv", ["quizmd.py", "init", "--ui", "next"]):
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        main()
                out = buf.getvalue()
                self.assertTrue(Path("hello-quiz.md").exists())
                self.assertTrue(Path("hello-imposter.md").exists())
                self.assertTrue(Path("hello-essay.md").exists())
                self.assertTrue(Path("QUIZ_GUIDE.md").exists())
                self.assertIn("Try it out:", out)
                self.assertIn("quizmd hello-quiz.md", out)
                self.assertNotIn("Next steps:", out)
                self.assertNotIn("Room modes (online):", out)
            finally:
                os.chdir(old_cwd)

    def test_main_init_prints_platform_specific_env_hint(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                with patch("quizmd._is_windows", return_value=True):
                    with patch("sys.argv", ["quizmd.py", "init"]):
                        buf = io.StringIO()
                        with contextlib.redirect_stdout(buf):
                            main()
                out = buf.getvalue()
                self.assertIn("$env:GEMINI_API_KEY=", out)
            finally:
                os.chdir(old_cwd)

    def test_room_validate_name_rejects_empty_after_normalization(self):
        with self.assertRaisesRegex(RuntimeError, "Invalid room name"):
            _room_validate_name("!!!")

    def test_room_validate_name_rejects_too_short(self):
        with self.assertRaisesRegex(RuntimeError, "Minimum length"):
            _room_validate_name("ab")

    def test_room_validate_name_normalizes_valid_input(self):
        normalized = _room_validate_name("Berlin Elephant 3")
        self.assertEqual(normalized, "berlin-elephant-3")

    def test_room_default_server_uses_env_override(self):
        with patch.dict(os.environ, {"QUIZMD_ROOM_SERVER": "http://localhost:9000"}, clear=False):
            self.assertEqual(_room_default_server(), "http://localhost:9000")

    def test_room_default_server_falls_back_to_cloud(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_room_default_server(), DEFAULT_ROOM_SERVER_CLOUD)

    def test_room_configured_servers_parses_multiple(self):
        with patch.dict(
            os.environ,
            {"QUIZMD_ROOM_SERVERS": "Belgium|https://a.example;US|https://b.example"},
            clear=True,
        ):
            servers = _room_configured_servers()
        self.assertEqual(
            servers,
            [("Belgium", "https://a.example"), ("US", "https://b.example")],
        )

    def test_room_resolve_server_uses_single_without_prompt(self):
        with patch("quizmd._room_configured_servers", return_value=[("Belgium", "https://a.example")]):
            with patch("quizmd._select_with_space") as mocked_select:
                label, server = _room_resolve_server(
                    explicit_server="",
                    theme_name="auto",
                    no_color=True,
                )
        self.assertEqual((label, server), ("Belgium", "https://a.example"))
        mocked_select.assert_not_called()

    def test_room_server_online_falls_back_to_openapi(self):
        with patch("quizmd._room_get_json", side_effect=[RuntimeError("404"), {"openapi": "3.1.0"}]):
            self.assertTrue(_room_server_online("https://quizmd-server.example"))

    def test_room_supported_modes_from_openapi_schema_ref(self):
        openapi_payload = {
            "openapi": "3.1.0",
            "components": {
                "schemas": {
                    "Mode": {"type": "string", "enum": ["compete", "collaborate", "boxing"]},
                    "CreateRoomRequest": {
                        "type": "object",
                        "properties": {"mode": {"$ref": "#/components/schemas/Mode"}},
                    },
                }
            },
        }
        with patch("quizmd._room_get_json", return_value=openapi_payload):
            self.assertEqual(
                _room_supported_modes("https://quizmd-server.example"),
                {"compete", "collaborate", "boxing"},
            )

    def test_room_supported_modes_returns_none_when_openapi_unavailable(self):
        with patch("quizmd._room_get_json", side_effect=RuntimeError("boom")):
            self.assertIsNone(_room_supported_modes("https://quizmd-server.example"))

    def test_room_prompt_token_required_defaults_to_no(self):
        with patch("sys.stdin.isatty", return_value=True):
            with patch("quizmd.prompt_input", return_value=""):
                self.assertFalse(_room_prompt_token_required())

    def test_room_prompt_token_required_accepts_yes(self):
        with patch("sys.stdin.isatty", return_value=True):
            with patch("quizmd.prompt_input", return_value="y"):
                self.assertTrue(_room_prompt_token_required())

    def test_room_connected_players_keeps_roles(self):
        payload = {
            "players": [
                {"name": "Mary", "role": "student", "connected": True},
                {"name": "Tim", "role": "teacher", "connected": True},
                {"name": "Offline", "role": "teacher", "connected": False},
            ]
        }
        rows = _room_connected_players(payload)
        self.assertEqual(rows, [{"name": "Mary", "role": "student"}, {"name": "Tim", "role": "teacher"}])
        self.assertEqual(_room_player_label("Mary", "student"), "Mary (student)")
        self.assertEqual(_room_player_label("Alex", "participant"), "Alex")

    def test_save_room_session_transcript_outputs_json(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                path = _save_room_session_transcript(
                    room_name="berlin-elephant",
                    mode="boxing",
                    display_name="Mary",
                    role="student",
                    transcript=[{"type": "chat", "ts": 1.0, "payload": {"text": "Hi"}}],
                    final_score=80,
                    scored_by="Tim",
                    ended_by="Mary",
                    ended_by_role="student",
                )
                self.assertTrue(path.exists())
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["mode"], "boxing")
                self.assertEqual(payload["participant"]["role"], "student")
                self.assertEqual(payload["final_score"], 80)
            finally:
                os.chdir(old_cwd)

    def test_run_room_command_create_boxing_passes_host_role(self):
        args = argparse.Namespace(
            create="__AUTO__",
            join=None,
            name="Mary",
            server="http://127.0.0.1:8011",
            mode="boxing",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="teacher",
            require_token=False,
            no_token=True,
        )
        created = {
            "ws_url": "ws://127.0.0.1:8011/rooms/ABCDEFGH/ws",
            "room_code": "ABCDEFGH",
            "host_player_id": "p_host",
            "host_player_token": "tok",
            "host_display_name": "Mary",
            "room_name": "berlin-elephant-1",
            "mode": "boxing",
            "host_role": "teacher",
        }
        with patch("quizmd._room_supported_modes", return_value={"compete", "collaborate", "boxing"}):
            with patch("quizmd._room_load_quiz_payload", return_value=("Sample", [{"question": "q"}])):
                with patch("quizmd._room_generate_name", return_value="berlin-elephant-1"):
                    with patch("quizmd._room_create_request", return_value=created) as mocked_create:
                        with patch("quizmd._room_ensure_server_ready", return_value=None):
                            with patch("quizmd._run_room_waiting_loop", new=AsyncMock(return_value=0)):
                                result = run_room_command(args)
        self.assertEqual(result, 0)
        self.assertEqual(mocked_create.call_args.kwargs["host_role"], "teacher")
        self.assertFalse(mocked_create.call_args.kwargs["token_required"])

    def test_run_room_command_create_require_token_flag(self):
        args = argparse.Namespace(
            create="__AUTO__",
            join=None,
            name="Mary",
            server="http://127.0.0.1:8011",
            mode="compete",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="",
            require_token=True,
            no_token=False,
        )
        created = {
            "ws_url": "ws://127.0.0.1:8011/rooms/ABCDEFGH/ws",
            "room_code": "ABCDEFGH",
            "host_player_id": "p_host",
            "host_player_token": "tok",
            "host_display_name": "Mary",
            "room_name": "berlin-elephant-1",
            "mode": "compete",
            "token_required": True,
            "room_token": "secure_token_123",
        }
        with patch("quizmd._room_supported_modes", return_value={"compete", "collaborate", "boxing"}):
            with patch("quizmd._room_load_quiz_payload", return_value=("Sample", [{"question": "q"}])):
                with patch("quizmd._room_generate_name", return_value="berlin-elephant-1"):
                    with patch("quizmd._room_create_request", return_value=created) as mocked_create:
                        with patch("quizmd._room_ensure_server_ready", return_value=None):
                            with patch("quizmd._run_room_waiting_loop", new=AsyncMock(return_value=0)):
                                result = run_room_command(args)
        self.assertEqual(result, 0)
        self.assertTrue(mocked_create.call_args.kwargs["token_required"])

    def test_run_room_command_create_prompt_token_yes_sets_required(self):
        args = argparse.Namespace(
            create="__AUTO__",
            join=None,
            name="Mary",
            server="http://127.0.0.1:8011",
            mode="compete",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="",
            require_token=False,
            no_token=False,
        )
        created = {
            "ws_url": "ws://127.0.0.1:8011/rooms/ABCDEFGH/ws",
            "room_code": "ABCDEFGH",
            "host_player_id": "p_host",
            "host_player_token": "tok",
            "host_display_name": "Mary",
            "room_name": "berlin-elephant-1",
            "mode": "compete",
            "token_required": True,
            "room_token": "secure_token_123",
        }
        with patch("quizmd._room_supported_modes", return_value={"compete", "collaborate", "boxing"}):
            with patch("quizmd._room_load_quiz_payload", return_value=("Sample", [{"question": "q"}])):
                with patch("quizmd._room_generate_name", return_value="berlin-elephant-1"):
                    with patch("quizmd._room_prompt_token_required", return_value=True) as mocked_prompt:
                        with patch("quizmd._room_create_request", return_value=created) as mocked_create:
                            with patch("quizmd._room_ensure_server_ready", return_value=None):
                                with patch("quizmd._run_room_waiting_loop", new=AsyncMock(return_value=0)):
                                    result = run_room_command(args)
        self.assertEqual(result, 0)
        self.assertTrue(mocked_create.call_args.kwargs["token_required"])
        mocked_prompt.assert_called_once()

    def test_run_room_command_create_prompt_token_no_sets_open_room(self):
        args = argparse.Namespace(
            create="__AUTO__",
            join=None,
            name="Mary",
            server="http://127.0.0.1:8011",
            mode="compete",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="",
            require_token=False,
            no_token=False,
        )
        created = {
            "ws_url": "ws://127.0.0.1:8011/rooms/ABCDEFGH/ws",
            "room_code": "ABCDEFGH",
            "host_player_id": "p_host",
            "host_player_token": "tok",
            "host_display_name": "Mary",
            "room_name": "berlin-elephant-1",
            "mode": "compete",
            "token_required": False,
            "room_token": "",
        }
        with patch("quizmd._room_supported_modes", return_value={"compete", "collaborate", "boxing"}):
            with patch("quizmd._room_load_quiz_payload", return_value=("Sample", [{"question": "q"}])):
                with patch("quizmd._room_generate_name", return_value="berlin-elephant-1"):
                    with patch("quizmd._room_prompt_token_required", return_value=False) as mocked_prompt:
                        with patch("quizmd._room_create_request", return_value=created) as mocked_create:
                            with patch("quizmd._room_ensure_server_ready", return_value=None):
                                with patch("quizmd._run_room_waiting_loop", new=AsyncMock(return_value=0)):
                                    result = run_room_command(args)
        self.assertEqual(result, 0)
        self.assertFalse(mocked_create.call_args.kwargs["token_required"])
        mocked_prompt.assert_called_once()

    def test_run_room_command_create_without_quiz_prints_tip(self):
        args = argparse.Namespace(
            create="__AUTO__",
            join=None,
            name="Mary",
            server="http://127.0.0.1:8011",
            mode="compete",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="",
            require_token=False,
            no_token=True,
        )
        created = {
            "ws_url": "ws://127.0.0.1:8011/rooms/ABCDEFGH/ws",
            "room_code": "ABCDEFGH",
            "host_player_id": "p_host",
            "host_player_token": "tok",
            "host_display_name": "Mary",
            "room_name": "berlin-elephant-1",
            "mode": "compete",
            "token_required": False,
            "room_token": "",
        }
        with patch("quizmd._room_supported_modes", return_value={"compete", "collaborate", "boxing"}):
            with patch("quizmd._room_load_quiz_payload", return_value=("Sample", [{"question": "q"}])):
                with patch("quizmd._room_generate_name", return_value="berlin-elephant-1"):
                    with patch("quizmd._room_create_request", return_value=created):
                        with patch("quizmd._room_ensure_server_ready", return_value=None):
                            with patch("quizmd._run_room_waiting_loop", new=AsyncMock(return_value=0)):
                                buffer = io.StringIO()
                                with contextlib.redirect_stdout(buffer):
                                    result = run_room_command(args)
        self.assertEqual(result, 0)
        self.assertIn("Tip: use --quiz filename to load your quiz.", buffer.getvalue())

    def test_run_room_command_create_named_room_conflict_has_friendly_error(self):
        args = argparse.Namespace(
            create="stelios",
            join=None,
            name="Mary",
            server="http://127.0.0.1:8011",
            mode="compete",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="",
            require_token=False,
            no_token=True,
        )
        with patch("quizmd._room_supported_modes", return_value={"compete", "collaborate", "boxing"}):
            with patch("quizmd._room_load_quiz_payload", return_value=("Sample", [{"question": "q"}])):
                with patch(
                    "quizmd._room_create_request",
                    side_effect=RuntimeError("Request failed: 409 Room name already exists"),
                ):
                    with patch("quizmd._room_ensure_server_ready", return_value=None):
                        with self.assertRaisesRegex(RuntimeError, 'Room name "stelios" already exists. Try another name.'):
                            run_room_command(args)

    def test_run_room_command_create_boxing_unsupported_shows_friendly_error(self):
        args = argparse.Namespace(
            create="__AUTO__",
            join=None,
            name="Mary",
            server="https://quizmd-server.example",
            mode="boxing",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="teacher",
        )
        with patch("quizmd._room_ensure_server_ready", return_value=None):
            with patch("quizmd._room_supported_modes", return_value={"compete", "collaborate"}):
                with self.assertRaisesRegex(RuntimeError, "not supported by this cloud server"):
                    run_room_command(args)

    def test_run_room_command_join_boxing_prompts_role(self):
        args = argparse.Namespace(
            create=None,
            join="berlin-elephant-1",
            name="Stelios",
            token="tok_12345678",
            server="http://127.0.0.1:8011",
            mode="",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="",
        )
        joined = {
            "ws_url": "ws://127.0.0.1:8011/rooms/ABCDEFGH/ws",
            "room_code": "ABCDEFGH",
            "player_id": "p_1",
            "player_token": "tok",
            "display_name": "Stelios",
            "room_name": "berlin-elephant-1",
            "mode": "boxing",
            "player_role": "student",
        }
        with patch("quizmd._room_info_request", return_value={"mode": "boxing"}):
            with patch("quizmd._select_with_space", return_value="student"):
                with patch("quizmd._room_join_by_name_request", return_value=joined) as mocked_join:
                    with patch("quizmd._room_ensure_server_ready", return_value=None):
                        with patch("quizmd._run_room_waiting_loop", new=AsyncMock(return_value=0)):
                            result = run_room_command(args)
        self.assertEqual(result, 0)
        self.assertEqual(mocked_join.call_args.kwargs["role"], "student")
        self.assertEqual(mocked_join.call_args.kwargs["room_token"], "tok_12345678")

    def test_run_room_command_join_ignores_role_for_non_boxing_room(self):
        args = argparse.Namespace(
            create=None,
            join="berlin-elephant-1",
            name="Stelios",
            token="tok_12345678",
            server="http://127.0.0.1:8011",
            mode="",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="teacher",
        )
        joined = {
            "ws_url": "ws://127.0.0.1:8011/rooms/ABCDEFGH/ws",
            "room_code": "ABCDEFGH",
            "player_id": "p_1",
            "player_token": "tok",
            "display_name": "Stelios",
            "room_name": "berlin-elephant-1",
            "mode": "compete",
            "player_role": "participant",
        }
        with patch("quizmd._room_info_request", return_value={"mode": "compete"}):
            with patch("quizmd._room_join_by_name_request", return_value=joined) as mocked_join:
                with patch("quizmd._room_ensure_server_ready", return_value=None):
                    with patch("quizmd._run_room_waiting_loop", new=AsyncMock(return_value=0)):
                        result = run_room_command(args)
        self.assertEqual(result, 0)
        self.assertEqual(mocked_join.call_args.kwargs["role"], "")
        self.assertEqual(mocked_join.call_args.kwargs["room_token"], "tok_12345678")

    def test_run_room_command_join_retries_without_role_on_legacy_server(self):
        args = argparse.Namespace(
            create=None,
            join="berlin-elephant-1",
            name="Stelios",
            token="tok_12345678",
            server="http://127.0.0.1:8011",
            mode="",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="student",
        )
        joined = {
            "ws_url": "ws://127.0.0.1:8011/rooms/ABCDEFGH/ws",
            "room_code": "ABCDEFGH",
            "player_id": "p_1",
            "player_token": "tok",
            "display_name": "Stelios",
            "room_name": "berlin-elephant-1",
            "mode": "boxing",
            "player_role": "student",
        }
        side_effects = [
            RuntimeError("Request failed: 422 body.role: Extra inputs are not permitted"),
            joined,
        ]
        with patch("quizmd._room_info_request", return_value={}):
            with patch("quizmd._room_join_by_name_request", side_effect=side_effects) as mocked_join:
                with patch("quizmd._room_ensure_server_ready", return_value=None):
                    with patch("quizmd._run_room_waiting_loop", new=AsyncMock(return_value=0)):
                        result = run_room_command(args)
        self.assertEqual(result, 0)
        self.assertEqual(mocked_join.call_count, 2)
        self.assertEqual(mocked_join.call_args_list[0].kwargs["role"], "student")
        self.assertEqual(mocked_join.call_args_list[0].kwargs["room_token"], "tok_12345678")
        self.assertEqual(mocked_join.call_args_list[1].kwargs["role"], "")
        self.assertEqual(mocked_join.call_args_list[1].kwargs["room_token"], "tok_12345678")

    def test_run_room_command_join_prompts_for_token_when_required(self):
        args = argparse.Namespace(
            create=None,
            join="berlin-elephant-1",
            name="Stelios",
            token="",
            server="http://127.0.0.1:8011",
            mode="",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="",
        )
        joined = {
            "ws_url": "ws://127.0.0.1:8011/rooms/ABCDEFGH/ws",
            "room_code": "ABCDEFGH",
            "player_id": "p_1",
            "player_token": "tok",
            "display_name": "Stelios",
            "room_name": "berlin-elephant-1",
            "mode": "compete",
            "player_role": "participant",
        }
        with patch("quizmd._room_info_request", return_value={"mode": "compete", "token_required": True}):
            with patch("quizmd.prompt_input", return_value="secure_token_123"):
                with patch("quizmd._room_join_by_name_request", return_value=joined) as mocked_join:
                    with patch("quizmd._room_ensure_server_ready", return_value=None):
                        with patch("quizmd._run_room_waiting_loop", new=AsyncMock(return_value=0)):
                            result = run_room_command(args)
        self.assertEqual(result, 0)
        self.assertEqual(mocked_join.call_args.kwargs["room_token"], "secure_token_123")

    def test_run_room_command_join_retries_after_missing_token_error(self):
        args = argparse.Namespace(
            create=None,
            join="berlin-elephant-1",
            name="Stelios",
            token="",
            server="http://127.0.0.1:8011",
            mode="",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="",
        )
        joined = {
            "ws_url": "ws://127.0.0.1:8011/rooms/ABCDEFGH/ws",
            "room_code": "ABCDEFGH",
            "player_id": "p_1",
            "player_token": "tok",
            "display_name": "Stelios",
            "room_name": "berlin-elephant-1",
            "mode": "compete",
            "player_role": "participant",
        }
        side_effects = [
            RuntimeError("Request failed: 422 body.room_token: Field required"),
            joined,
        ]
        with patch("quizmd._room_info_request", return_value={"mode": "compete"}):
            with patch("quizmd.prompt_input", return_value="secure_token_123"):
                with patch("quizmd._room_join_by_name_request", side_effect=side_effects) as mocked_join:
                    with patch("quizmd._room_ensure_server_ready", return_value=None):
                        with patch("quizmd._run_room_waiting_loop", new=AsyncMock(return_value=0)):
                            result = run_room_command(args)
        self.assertEqual(result, 0)
        self.assertEqual(mocked_join.call_count, 2)
        self.assertEqual(mocked_join.call_args_list[0].kwargs["room_token"], "")
        self.assertEqual(mocked_join.call_args_list[1].kwargs["room_token"], "secure_token_123")

    def test_run_room_command_server_unavailable_friendly_error(self):
        args = argparse.Namespace(
            create=None,
            join="berlin-elephant-1",
            name="Stelios",
            token="",
            server="https://quizmd-server.example",
            mode="",
            quiz="",
            theme="auto",
            no_color=True,
            full_screen=False,
            role="",
        )
        with patch(
            "quizmd._room_ensure_server_ready",
            side_effect=RuntimeError(
                "Unfortunately, the cloud server is not available for the moment. Please try again later."
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "not available for the moment"):
                run_room_command(args)

    def test_room_json_payload_validation_rejects_bad_options(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "quiz_title": "Bad Quiz",
                        "questions": [
                            {
                                "title": "Q1",
                                "question": "Pick one",
                                "options": ["A"],
                                "correct": [1],
                                "type": "single",
                                "time_limit": 20,
                            }
                        ],
                    }
                )
            )
            path = handle.name
        try:
            with self.assertRaisesRegex(ValueError, "must have at least 2 options"):
                _room_quiz_payload_from_json(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_room_json_payload_validation_rejects_duplicate_correct(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "quiz_title": "Bad Quiz",
                        "questions": [
                            {
                                "title": "Q1",
                                "question": "Pick one",
                                "options": ["A", "B"],
                                "correct": [1, 1],
                                "type": "single",
                                "time_limit": 20,
                            }
                        ],
                    }
                )
            )
            path = handle.name
        try:
            with self.assertRaisesRegex(ValueError, "must have exactly one answer"):
                _room_quiz_payload_from_json(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_room_json_payload_validation_rejects_time_limit_below_5(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "quiz_title": "Bad Quiz",
                        "questions": [
                            {
                                "title": "Q1",
                                "question": "Pick one",
                                "options": ["A", "B"],
                                "correct": [1],
                                "type": "single",
                                "time_limit": 4,
                            }
                        ],
                    }
                )
            )
            path = handle.name
        try:
            with self.assertRaisesRegex(ValueError, "requires Time/time_limit >= 5 seconds"):
                _room_quiz_payload_from_json(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_room_json_payload_accepts_discussion_time(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "quiz_title": "Room Quiz",
                        "questions": [
                            {
                                "title": "Q1",
                                "question": "Pick one",
                                "options": ["A", "B"],
                                "correct": [1],
                                "type": "single",
                                "time_limit": 20,
                                "discussion_time": 15,
                            }
                        ],
                    }
                )
            )
            path = handle.name
        try:
            _title, questions = _room_quiz_payload_from_json(path)
            self.assertEqual(questions[0]["discussion_time"], 15)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_room_json_payload_rejects_negative_discussion_time(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "quiz_title": "Room Quiz",
                        "questions": [
                            {
                                "title": "Q1",
                                "question": "Pick one",
                                "options": ["A", "B"],
                                "correct": [1],
                                "type": "single",
                                "time_limit": 20,
                                "discussion_time": -1,
                            }
                        ],
                    }
                )
            )
            path = handle.name
        try:
            with self.assertRaisesRegex(ValueError, "discussion_time must be >= 0"):
                _room_quiz_payload_from_json(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_room_markdown_payload_validation_rejects_time_below_5(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(
                "# Demo\n\n"
                "## Q1\n"
                "What is 2+2?\n\n"
                "- 4\n"
                "- 5\n\n"
                "Answer: 1\n"
                "Type: single\n"
                "Time: 4\n"
                "Explanation: test\n"
            )
            path = handle.name
        try:
            with self.assertRaisesRegex(ValueError, "requires Time/time_limit >= 5 seconds"):
                _room_quiz_payload_from_markdown(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_run_room_command_create_rejects_time_below_5_before_request(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(
                "# Demo Quiz\n\n"
                "## Q1\n"
                "Pick one\n\n"
                "- A\n"
                "- B\n\n"
                "Answer: 1\n"
                "Type: single\n"
                "Time: 4\n"
                "Explanation: test\n"
            )
            quiz_path = handle.name

        args = argparse.Namespace(
            create="__AUTO__",
            join=None,
            name="Mary",
            token="",
            server="http://127.0.0.1:8011",
            mode="compete",
            quiz=quiz_path,
            theme="auto",
            no_color=True,
            full_screen=False,
            role="",
            require_token=False,
            no_token=True,
        )
        try:
            with patch("quizmd._room_supported_modes", return_value={"compete", "collaborate", "boxing"}):
                with patch("quizmd._room_generate_name", return_value="berlin-elephant-1"):
                    with patch("quizmd._room_ensure_server_ready", return_value=None):
                        with patch("quizmd._room_create_request") as mocked_create:
                            with self.assertRaisesRegex(RuntimeError, "requires Time/time_limit >= 5 seconds"):
                                run_room_command(args)
                            mocked_create.assert_not_called()
        finally:
            Path(quiz_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
