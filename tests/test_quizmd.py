import subprocess
import sys
import tempfile
import unittest
import os
import json
from unittest.mock import patch
from pathlib import Path

from quizmd import (
    THEMES,
    build_question_markup,
    format_labels,
    parse_int_list,
    parse_int_value,
    parse_quiz_markdown,
    prompt_input,
    run_coroutine_sync,
    safe_for_stream,
    save_attempt,
    select_theme,
    slugify,
)


QUIZ_DIR = Path("quizzes")


class QuizMarkdownTests(unittest.TestCase):
    def write_quiz(self, content: str) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(content)
            return handle.name

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

    def test_select_theme_uses_env_override(self):
        with patch.dict("os.environ", {"QUIZMD_THEME": "light"}, clear=False):
            theme = select_theme("auto")
            self.assertEqual(theme["pt_title"], THEMES["light"]["pt_title"])

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


if __name__ == "__main__":
    unittest.main()
