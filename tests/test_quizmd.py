import subprocess
import sys
import tempfile
import unittest
import os
import json
import re
import urllib.error
from unittest.mock import patch
from pathlib import Path

from quizmd import (
    THEMES,
    build_question_markup,
    collect_essay_answer_via_editor,
    detect_quiz_mode,
    evaluate_essay_deterministic_fallback,
    evaluate_essay_with_gemini,
    format_labels,
    display_width,
    parse_essay_markdown,
    parse_int_list,
    parse_int_value,
    parse_quiz_markdown,
    prompt_input,
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
                    self.assertGreaterEqual(len(questions), 5)
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
        )
        self.assertIsNone(result["score_percent"])
        self.assertTrue(result["ai_unavailable"])

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
            with self.assertRaisesRegex(RuntimeError, "do not use AI and do not need this key"):
                run_essay(essay, no_color=True)

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
        }
        with patch.dict("os.environ", {"GEMINI_API_KEY": "k"}, clear=True):
            with patch("quizmd.prompt_input", return_value=""):
                with patch("quizmd.collect_essay_answer_via_editor", return_value="student answer"):
                    with patch("quizmd.evaluate_essay_with_gemini", return_value=fake_grade):
                        with patch("quizmd.ask_yes_no", return_value=False):
                            with patch("quizmd.evaluate_essay_with_loading", return_value=fake_grade):
                                with patch("rich.console.Console.print"):
                                    run_essay(essay, no_color=True)

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
        self.assertIn("Select with Space, then Enter", normal)

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
        self.assertIn("┌", markup)
        self.assertIn("└", markup)
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


if __name__ == "__main__":
    unittest.main()
