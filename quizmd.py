#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import asyncio
import html
import json
import math
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

__version__ = "2.4.3rc11"
DEFAULT_AI_PROVIDER = "auto"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-latest"
QUIZMD_DOCS_URL = "https://steliosot.github.io/quizmd-docs/"
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

HELLO_DEBUG_TEMPLATE = """# Debug Quiz: Python Foundations

## Question 1
There are two errors. Fix the function so it runs correctly.

Broken:
```python
def greet(name)
    print("Hello, " + name
```

Fixed:
```python
def greet(name):
    print("Hello, " + name)
```

Type: debug
Hint: Start at line 1, then check missing punctuation on line 2.
AI Note: Accept equivalent fixes that preserve behavior, including single quotes or f-strings.
Explanation: Function definitions need a trailing colon, and print call needs a closing parenthesis.

## Question 2
There are two errors. Fix indentation and the variable reference.

Broken:
```python
def average(nums):
total = sum(nums)
    return total / len(num)
```

Fixed:
```python
def average(nums):
    total = sum(nums)
    return total / len(nums)
```

Type: debug
Hint: The issue starts on line 2, then look at the last token on line 3.
AI Note: Accept equivalent numeric-average implementations if they keep the same result and handle lists correctly.
Explanation: Python requires indentation inside the function body, and `num` should be `nums`.

## Question 3
There are three errors. Make this function safely return the last item.

Broken:
```python
def pick_last(items)
    if len(items) == 0:
        return items[0]
    return items[len(items)]
```

Fixed:
```python
def pick_last(items):
    if len(items) == 0:
        return None
    return items[len(items) - 1]
```

Type: debug
Hint: Check line 1 first, then the return logic on lines 3 and 4.
AI Note: Accept alternatives that safely return None on empty input and the true last element otherwise.
Explanation: Add function colon, guard empty list with None, and use last index `len(items) - 1`.
"""

HELLO_CHALLENGE_TEMPLATE = """# Challenge Quiz: General Knowledge Stars

## Category: Geography
Which river flows through Paris?

### Easy
- Thames
- Seine
- Danube
Answer: 2
Type: single
Explanation: Paris is built along the Seine River.

### Normal
- Seine
- Loire
- Rhine
Answer: 1
Type: single
Explanation: The Seine is the river that runs through Paris.

### Hard
- Seine
- Oise
- Garonne
- Rhone
Answer: 1
Type: single
Explanation: The Seine is correct; the others are major French rivers but not the one through central Paris.

## Category: Literature
Who wrote *Pride and Prejudice*?

### Easy
- Jane Austen
- Charles Dickens
- Mary Shelley
Answer: 1
Type: single
Explanation: Jane Austen published *Pride and Prejudice* in 1813.

### Normal
- Jane Austen
- Emily Bronte
- George Eliot
Answer: 1
Type: single
Explanation: The novel is one of Jane Austen's best-known works.

### Hard
- Jane Austen
- Charlotte Bronte
- Virginia Woolf
- Thomas Hardy
Answer: 1
Type: single
Explanation: Jane Austen is the correct author.

## Category: Science
What gas do plants absorb from the atmosphere during photosynthesis?

### Easy
- Oxygen
- Carbon dioxide
- Nitrogen
Answer: 2
Type: single
Explanation: Plants use carbon dioxide and release oxygen.

### Normal
- Carbon dioxide
- Helium
- Hydrogen
Answer: 1
Type: single
Explanation: Carbon dioxide is absorbed and used to produce glucose.

### Hard
- Carbon dioxide
- Methane
- Neon
- Argon
Answer: 1
Type: single
Explanation: Carbon dioxide is the key input gas for photosynthesis.

## Category: Athletics
How long is an Olympic marathon (approximately)?

### Easy
- 21.1 km
- 42.2 km
- 50 km
Answer: 2
Type: single
Explanation: The official marathon distance is 42.195 km.

### Normal
- 42.195 km
- 40.000 km
- 45.000 km
Answer: 1
Type: single
Explanation: Olympic marathons use the standard 42.195 km distance.

### Hard
- 42.195 km
- 26.2 miles
- about 42.2 km
- all of the above
Answer: 4
Type: single
Explanation: 42.195 km equals 26.2 miles and is commonly rounded to about 42.2 km.

## Category: History
In which year did World War II end?

### Easy
- 1945
- 1939
- 1950
Answer: 1
Type: single
Explanation: WWII ended in 1945.

### Normal
- 1945
- 1944
- 1946
Answer: 1
Type: single
Explanation: The war ended in 1945 in both Europe and Asia.

### Hard
- 1945
- 1943
- 1947
- 1939
Answer: 1
Type: single
Explanation: 1939 is the start year; 1945 is the end year.

## Category: Lifestyle
Which habits are generally linked to better sleep quality?

### Easy
- Consistent sleep schedule
- Late caffeine every evening
- Bright screens right before bed
Answer: 1
Type: single
Explanation: A regular sleep schedule supports healthy sleep.

### Normal
- Keep a stable bedtime and wake time
- Exercise only at midnight
- Drink energy drinks before bed
Answer: 1
Type: single
Explanation: Consistency helps regulate the body's sleep rhythm.

### Hard
- Keep a consistent schedule
- Limit caffeine late in the day
- Reduce bright screen exposure before bed
- all of the above
Answer: 4
Type: single
Explanation: All three habits are evidence-based sleep hygiene practices.
"""

HELLO_REVERSE_TEMPLATE = """# Reverse Quiz: Python Reverse Engineering

## Question 1
Output:
HELLO
HELLO
HELLO

Which code produced this?

```python
# A
for i in range(3):
    print("HELLO")
```

```python
# B
for i in range(1, 3):
    print("HELLO")
```

```python
# C
print("HELLO" * 3)
```

Options:
- A only
- B only
- C only
- A and C

Answer: 1
Type: single
Explanation: Only option A prints HELLO on three separate lines.

## Question 2
This program should print only even numbers from 0 to 10 (inclusive).
Which implementation is correct?

```python
# A
for i in range(11):
    if i % 2 == 0:
        print(i)
```

```python
# B
for i in range(1, 11):
    print(i)
```

```python
# C
for i in range(11):
    if i % 2 == 1:
        print(i)
```

Options:
- A
- B
- C
- B and C

Answer: 1
Type: single
Explanation: A checks parity and includes 0..10.

## Question 3
Bug-fix reverse engineering:
This code should print numbers 1 to 5, but currently prints 0 to 4.

```python
for i in range(5):
    print(i)
```

Which change fixes it?

Options:
- range(1, 6)
- range(5, 1)
- range(0, 6)
- keep range(5)

Answer: 1
Type: single
Explanation: range(1, 6) yields 1, 2, 3, 4, 5.

## Question 4
Output:
2
4
6
8

Which rules can generate this output?

Options:
- Print the first four positive even numbers
- Print multiples of 2 from 2 through 8
- Print square numbers from 1 through 4
- Print odd numbers from 1 through 7

Answer: 1,2
Type: multiple
Explanation: Both A and B describe the same generated sequence.

## Question 5
Output:
3
2
1

Which code produced this?

```python
# A
for i in range(3, 0, -1):
    print(i)
```

```python
# B
for i in range(3):
    print(i)
```

```python
# C
for i in range(1, 4):
    print(i)
```

Options:
- A
- B
- C
- B and C

Answer: 1
Type: single
Explanation: Only A iterates downward from 3 to 1.
"""

HELLO_MILLIONAIRE_TEMPLATE = """# Millionaire Quiz: Fun Trivia Ladder
Friend Name: Stelios

## Question 1
What is the capital of France?

- Berlin
- Madrid
- Paris
- Rome

Answer: 3
Type: single
Hint: It is often called the City of Light.
Explanation: Paris is the capital city of France.

## Question 2
Which planet is known as the Red Planet?

- Earth
- Mars
- Venus
- Jupiter

Answer: 2
Type: single
Hint: This planet is named after the Roman god of war.
Explanation: Mars is often called the Red Planet.

## Question 3
How many continents are there on Earth?

- 5
- 6
- 7
- 8

Answer: 3
Type: single
Hint: Think of the Olympic rings plus two more.
Explanation: There are 7 continents.

## Question 4
Which ocean is the largest?

- Atlantic
- Indian
- Arctic
- Pacific

Answer: 4
Type: single
Hint: It is the ocean that touches Asia, Oceania, and the Americas.
Explanation: The Pacific Ocean is the largest.

## Question 5
What is 12 x 12?

- 124
- 144
- 132
- 112

Answer: 2
Type: single
Hint: A dozen multiplied by a dozen.
Explanation: 12 multiplied by 12 equals 144.

## Question 6
Which language is primarily spoken in Brazil?

- Spanish
- Portuguese
- French
- Italian

Answer: 2
Type: single
Hint: It is not Spanish and comes from Europe's west coast.
Explanation: Portuguese is the main language of Brazil.

## Question 7
What gas do humans need to breathe?

- Carbon dioxide
- Nitrogen
- Oxygen
- Helium

Answer: 3
Type: single
Hint: It makes up about 21% of Earth's atmosphere.
Explanation: Humans rely on oxygen for respiration.

## Question 8
Which number is prime?

- 21
- 29
- 39
- 49

Answer: 2
Type: single
Hint: Pick the only option with exactly two positive divisors.
Explanation: 29 is a prime number.

## Question 9
Which country hosted the 2016 Summer Olympics?

- China
- Greece
- Brazil
- Japan

Answer: 3
Type: single
Hint: The host city was Rio de Janeiro.
Explanation: Rio de Janeiro, Brazil hosted the 2016 Summer Olympics.

## Question 10
What is the square root of 256?

- 12
- 14
- 16
- 18

Answer: 3
Type: single
Hint: It is 2 raised to the power of 4.
Explanation: 16 x 16 = 256.

## Question 11
Which scientist proposed the theory of relativity?

- Isaac Newton
- Albert Einstein
- Nikola Tesla
- Galileo Galilei

Answer: 2
Type: single
Hint: Think of the scientist behind E=mc².
Explanation: Einstein proposed relativity.

## Question 12
What is the chemical symbol for gold?

- Ag
- Gd
- Au
- Go

Answer: 3
Type: single
Hint: The symbol comes from the Latin word “aurum”.
Explanation: The symbol for gold is Au.

## Question 13
In computing, what does CPU stand for?

- Central Process Unit
- Central Processing Unit
- Computer Processing Utility
- Core Processor Unit

Answer: 2
Type: single
Hint: The middle word is “Processing”.
Explanation: CPU means Central Processing Unit.

## Question 14
Which year did the first iPhone launch?

- 2005
- 2007
- 2009
- 2010

Answer: 2
Type: single
Time: 180
Hint: It launched one year before the App Store.
Explanation: The first iPhone launched in 2007.

## Question 15
Which city is known as the City of Canals and Gondolas?

- Lisbon
- Amsterdam
- Venice
- Vienna

Answer: 3
Type: single
Hint: It is the Italian city famous for gondolas.
Explanation: Venice is famous for canals and gondolas.
"""

HELLO_CHAOS_TEMPLATE = """# Chaos: Cleaning a CSV Dataset
Type: chaos
Title: Missing values in studio_ghibli_movies.csv
Skills: csv, DictReader, missing-values, data-cleaning
Difficulty: medium

## Scenario
You are cleaning `studio_ghibli_movies.csv` using Python.
Your script loads the file with `csv.DictReader` and must fix missing values in `year` and `music_by`.

## Decision 1
What is your first action?

- A. Loop through rows and check whether `year` or `music_by` is missing
- B. Convert every column to integer immediately
- C. Delete every row that has a missing value
- D. Use `csv.reader` and hard-coded column indexes

Answer: A
Score: 3

### Feedback
Good first step. You are checking the target fields directly.

### Chaos if A
Some missing values are whitespace-only (for example `"   "`), so a raw `== ""` check misses them.

### Chaos if B
Your script crashes with `ValueError` because some fields are text and some `year` values are missing.

### Chaos if C
You risk losing useful rows that only have one missing field.

### Chaos if D
Index-based access becomes fragile if column order changes.

## Path A
### Recovery A
What should you do now?

- A. Use `value.strip() == ""` for missing checks
- B. Ignore whitespace-only values
- C. Replace all spaces in the file globally
- D. Convert values to `int` first

Answer: A
Score: 3

### Feedback
Correct. `strip()` turns whitespace-only strings into empty strings.

## Path B
### Recovery B
What should you do before converting values?

- A. Validate missing values first, then convert only cleaned numeric fields
- B. Delete the file and download it again
- C. Convert the header row to integer
- D. Run `int(row["title"])`

Answer: A
Score: 2

### Feedback
Recovered. Clean and validate before type conversion.

## Path C
### Recovery C
What is a better cleaning strategy?

- A. Keep the row and fill only missing target fields
- B. Delete every row with any empty value
- C. Delete the entire `music_by` column
- D. Ignore missing values

Answer: A
Score: 2

### Feedback
Recovered. Targeted cleaning is safer than deleting records.

## Path D
### Recovery D
Why is `csv.DictReader` better here?

- A. It lets you use named fields like `row["music_by"]`
- B. It automatically fixes missing values
- C. It automatically converts all numbers
- D. It removes duplicates

Answer: A
Score: 2

### Feedback
Correct. Named-column access is clearer and less error-prone.

## Final Decision
After cleaning, what should you do?

- A. Save cleaned rows to `studio_ghibli_movies_clean.csv` and run checks again
- B. Print cleaned rows only
- C. Overwrite original file without a cleaned copy
- D. Save as plain `.txt` without headers

Answer: A
Score: 4

### Final feedback
Good decision. Save, then verify the cleaned dataset.

## Result
Maximum score: 10

- 9-10: Excellent. Strong cleaning workflow.
- 6-8: Good. Some recovery needed.
- 3-5: Partial understanding. Review missing-value handling and `DictReader`.
- 0-2: Needs practice. Review CSV loading and safe cleaning.
"""

QUIZ_GUIDE_TEMPLATE = """# QuizMD Quick Start

## Local modes

```bash
quizmd --validate hello-quiz.md
quizmd hello-quiz.md
quizmd --validate hello-imposter.md
quizmd hello-imposter.md
quizmd --validate hello-debug.md
quizmd hello-debug.md
quizmd --validate hello-challenge.md
quizmd hello-challenge.md
quizmd --validate hello-reverse.md
quizmd hello-reverse.md
quizmd --validate hello-millionaire.md
quizmd hello-millionaire.md
quizmd --validate hello-chaos.md
quizmd hello-chaos.md
```

Millionaire timing:
- Default is 120 seconds per question.
- If `Time:` is provided, it is capped at 120 seconds.
- `Ask AI` lifeline is optional (available only when an AI key is configured).

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
        "pt_imposter_fg": "ansiwhite",
        "pt_imposter_bg": "ansired",
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
        "pt_imposter_fg": "ansiwhite",
        "pt_imposter_bg": "ansired",
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


def _is_light_theme(theme: dict) -> bool:
    return theme is THEMES["light"]


def _prompt_ui_palette(theme: dict) -> dict[str, str]:
    """Prompt-toolkit colors tuned for readability on both dark/light terminals.

    Keep core text on terminal default foreground so full-screen prompt_toolkit
    views stay readable even when auto theme detection picks the wrong background.
    """
    if _is_light_theme(theme):
        return {
            "logo": "ansiblue",
            "title": "default",
            "body": "default",
            "muted": "default",
            "accent": "ansiblue",
            "secondary": "ansimagenta",
            "warning": "ansimagenta",
            "danger": "ansired",
            "success": "ansigreen",
            "border": "ansiblue",
            "label": "ansiblue bold",
            "selected_fg": "ansiwhite",
            "selected_bg": "ansiblue",
            "changed_fg": "ansiblack",
            "changed_bg": "#ffdede",
        }
    return {
        "logo": "ansicyan",
        "title": "default",
        "body": "default",
        "muted": "default",
        "accent": "ansiyellow",
        "secondary": "ansimagenta",
        "warning": "ansiyellow",
        "danger": "ansired",
        "success": "ansigreen",
        "border": "ansiblue",
        "label": "ansicyan bold",
        "selected_fg": "ansiblack",
        "selected_bg": "ansicyan",
        "changed_fg": "ansiwhite",
        "changed_bg": "#6b3a3a",
    }


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


def parse_quiz_markdown(path: str, text_override: str | None = None):
    source = Path(path)
    text = text_override if text_override is not None else source.read_text(encoding="utf-8")

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

        # Guard against challenge-style difficulty headings being parsed as plain MCQ text.
        if title.lower().startswith("category:"):
            for raw in body_lines:
                stripped = raw.strip().lower()
                if re.match(r"^###\s*(easy|normal|hard)\s*$", stripped):
                    raise ValueError(
                        f"{source}: found challenge difficulty heading {raw.strip()!r} in question {title!r}. "
                        "Use '# Challenge Quiz: <title>' at the top for category difficulty quizzes."
                    )

        field_pattern = re.compile(r"(?i)^(answer|type|time|points|score|hint|explanation|imposters)\s*:\s*(.*)$")
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
        hint = ""
        imposters = []
        points = 1.0
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
                elif key in {"points", "score"}:
                    try:
                        points = float(value.strip())
                    except ValueError as exc:
                        raise ValueError(
                            f"{source}: points must be a number in question {title!r}"
                        ) from exc
                    if not math.isfinite(points):
                        raise ValueError(
                            f"{source}: points must be a finite number in question {title!r}"
                        )
                    if points <= 0:
                        raise ValueError(
                            f"{source}: points must be greater than zero in question {title!r}"
                        )
                elif key == "imposters":
                    imposters = parse_int_list(value, "imposters", title, source)
                elif key == "hint":
                    hint = value.strip()
                else:
                    explanation = value.strip()
            else:
                if stripped.startswith("### "):
                    raise ValueError(
                        f"{source}: unrecognized line {l!r} in question {title!r}. "
                        "This looks like challenge difficulty syntax. "
                        "Use '# Challenge Quiz: <title>' at the top and '### Easy/Normal/Hard' inside each category."
                    )
                raise ValueError(
                    f"{source}: unrecognized line {l!r} in question {title!r}. "
                    "Expected options ('- ...') or fields: Answer, Type, Time, Points, Hint, Explanation, Imposters."
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
            "points": points,
            "hint": hint,
            "explanation": explanation,
            "imposters": sorted(imposters),
        }
        validate_question(question_data, source)
        questions.append(question_data)

    if not questions:
        raise ValueError(f"{source}: no valid questions found. Add at least one '##' question block.")

    return quiz_title, questions


CHALLENGE_DIFFICULTY_ORDER = ("easy", "normal", "hard")
CHALLENGE_STARS_BY_DIFFICULTY = {"easy": 1, "normal": 2, "hard": 3}
CHALLENGE_DEFAULT_TIME_LIMIT_SECONDS = 45
REVERSE_DEFAULT_TIME_LIMIT_SECONDS = 45
MILLIONAIRE_TOTAL_QUESTIONS = 15
MILLIONAIRE_DEFAULT_TIME_LIMIT_SECONDS = 120
MILLIONAIRE_MAX_TIME_LIMIT_SECONDS = 120
MILLIONAIRE_LIFELINES = ("50-50", "Ask the People", "Call a Friend")
MILLIONAIRE_SAFETY_NET_QUESTIONS = (2, 5, 10, 15)
MILLIONAIRE_POINTS_LADDER = (
    100,
    200,
    300,
    500,
    1_000,
    2_000,
    4_000,
    8_000,
    16_000,
    32_000,
    64_000,
    125_000,
    250_000,
    500_000,
    1_000_000,
)


def parse_challenge_markdown(path: str) -> tuple[str, list[dict]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not lines:
        raise ValueError(f"{source}: empty challenge markdown file")

    first_nonempty = ""
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped:
            first_nonempty = stripped
            break
    if not first_nonempty.lower().startswith("# challenge quiz:"):
        raise ValueError(f"{source}: challenge quiz must start with '# Challenge Quiz: <title>'")
    quiz_title = first_nonempty.split(":", 1)[1].strip()
    if not quiz_title:
        raise ValueError(f"{source}: challenge quiz title cannot be empty")

    category_pattern = re.compile(r"^##\s+Category:\s*(.+?)\s*$", flags=re.IGNORECASE)
    difficulty_pattern = re.compile(r"^###\s*(Easy|Normal|Hard)\s*$", flags=re.IGNORECASE)
    field_pattern = re.compile(r"(?i)^(answer|type|time|explanation)\s*:\s*(.*)$")
    option_pattern = re.compile(r"^\s*-\s*(.*)$")

    category_blocks: list[tuple[str, list[str]]] = []
    current_category_name: str | None = None
    current_category_lines: list[str] = []
    in_code_fence = False
    saw_header = False

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.lower().startswith("# challenge quiz:") and not saw_header:
            saw_header = True
            continue
        if stripped.startswith("```"):
            if current_category_name is not None:
                current_category_lines.append(raw_line)
            in_code_fence = not in_code_fence
            continue
        if (
            not in_code_fence
            and (match := category_pattern.match(stripped)) is not None
        ):
            if current_category_name is not None:
                category_blocks.append((current_category_name, current_category_lines))
            current_category_name = match.group(1).strip()
            current_category_lines = []
            continue
        if current_category_name is None:
            if stripped:
                raise ValueError(
                    f"{source}: unexpected content before first category. Use '## Category: <name>'."
                )
            continue
        current_category_lines.append(raw_line)

    if current_category_name is not None:
        category_blocks.append((current_category_name, current_category_lines))

    if not category_blocks:
        raise ValueError(f"{source}: no categories found. Add at least one '## Category: <name>' block.")

    seen_categories: set[str] = set()
    categories: list[dict] = []

    for category_name, block_lines in category_blocks:
        if not category_name:
            raise ValueError(f"{source}: category name cannot be empty")
        normalized_name = category_name.casefold()
        if normalized_name in seen_categories:
            raise ValueError(f"{source}: duplicate category name {category_name!r}")
        seen_categories.add(normalized_name)

        line_info: list[dict] = []
        in_code = False
        for raw_line in block_lines:
            stripped = raw_line.strip()
            line_info.append({"raw": raw_line, "stripped": stripped, "in_code": in_code})
            if stripped.startswith("```"):
                in_code = not in_code

        difficulty_indexes: list[tuple[int, str]] = []
        for idx, info in enumerate(line_info):
            if info["in_code"]:
                continue
            match = difficulty_pattern.match(info["stripped"])
            if match is not None:
                difficulty_indexes.append((idx, match.group(1).lower()))

        if not difficulty_indexes:
            raise ValueError(
                f"{source}: category {category_name!r} is missing difficulty sections. "
                "Add '### Easy', '### Normal', and '### Hard'."
            )

        question_lines = block_lines[: difficulty_indexes[0][0]]
        shared_question_text = "\n".join(question_lines).strip()

        difficulties: dict[str, dict] = {}
        for i, (start_idx, diff_name) in enumerate(difficulty_indexes):
            end_idx = difficulty_indexes[i + 1][0] if i + 1 < len(difficulty_indexes) else len(block_lines)
            body_lines = block_lines[start_idx + 1 : end_idx]

            if diff_name in difficulties:
                raise ValueError(f"{source}: category {category_name!r} has duplicate difficulty {diff_name!r}")

            options: list[str] = []
            answer: list[int] = []
            qtype = "single"
            explanation = ""
            time_limit = CHALLENGE_DEFAULT_TIME_LIMIT_SECONDS
            seen_field = False
            question_override_lines: list[str] = []
            parsing_question_override = True

            for raw_line in body_lines:
                stripped = raw_line.strip()
                if not stripped:
                    if parsing_question_override and question_override_lines:
                        question_override_lines.append(raw_line)
                    continue

                if parsing_question_override:
                    starts_option = option_pattern.match(raw_line) is not None
                    starts_field = field_pattern.match(stripped) is not None
                    if not starts_option and not starts_field:
                        question_override_lines.append(raw_line)
                        continue
                    parsing_question_override = False

                option_match = option_pattern.match(raw_line)
                if option_match:
                    if seen_field:
                        raise ValueError(
                            f"{source}: options must appear before metadata fields in category {category_name!r}, "
                            f"difficulty {diff_name!r}"
                        )
                    option_text = option_match.group(1).strip()
                    if not option_text:
                        raise ValueError(
                            f"{source}: blank option text in category {category_name!r}, difficulty {diff_name!r}"
                        )
                    options.append(option_text)
                    continue

                field_match = field_pattern.match(stripped)
                if field_match is None:
                    raise ValueError(
                        f"{source}: unrecognized line {raw_line!r} in category {category_name!r}, difficulty {diff_name!r}. "
                        "Expected options ('- ...') or fields: Answer, Type, Time, Explanation."
                    )

                seen_field = True
                field_name = field_match.group(1).lower()
                field_value = field_match.group(2)
                title = f"{category_name} [{diff_name}]"
                if field_name == "answer":
                    answer = parse_int_list(field_value, "answer", title, source)
                elif field_name == "type":
                    qtype = field_value.strip().lower() or "single"
                elif field_name == "time":
                    time_limit = parse_int_value(field_value, "time", title, source)
                else:
                    explanation = field_value.strip()

            question_override_text = "\n".join(question_override_lines).strip()
            question_text = question_override_text or shared_question_text
            if not question_text:
                raise ValueError(
                    f"{source}: category {category_name!r}, difficulty {diff_name!r} is missing question text. "
                    "Add shared text under '## Category: ...' or add question text directly under this difficulty heading."
                )

            if not options:
                raise ValueError(
                    f"{source}: category {category_name!r}, difficulty {diff_name!r} is missing options"
                )
            if not answer:
                raise ValueError(
                    f"{source}: category {category_name!r}, difficulty {diff_name!r} is missing answer"
                )
            if qtype != "single":
                raise ValueError(
                    f"{source}: challenge mode supports only Type: single in category {category_name!r}, "
                    f"difficulty {diff_name!r}"
                )
            if len(answer) != 1:
                raise ValueError(
                    f"{source}: challenge mode requires exactly one correct answer in category {category_name!r}, "
                    f"difficulty {diff_name!r}"
                )

            question_data = {
                "title": f"{category_name} [{diff_name.title()}]",
                "question": question_text,
                "options": options,
                "correct": sorted(answer),
                "type": qtype,
                "time_limit": time_limit,
                "explanation": explanation,
                "imposters": [],
            }
            validate_question(question_data, source)
            difficulties[diff_name] = question_data

        missing_difficulties = [d for d in CHALLENGE_DIFFICULTY_ORDER if d not in difficulties]
        if missing_difficulties:
            human = ", ".join(d.title() for d in missing_difficulties)
            raise ValueError(
                f"{source}: category {category_name!r} is missing required difficulty section(s): {human}"
            )

        categories.append(
            {
                "category": category_name,
                "question": shared_question_text,
                "difficulties": difficulties,
            }
        )

    return quiz_title, categories


def parse_reverse_markdown(path: str) -> tuple[str, list[dict]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    first_nonempty = ""
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped:
            first_nonempty = stripped
            break
    if not first_nonempty.lower().startswith("# reverse quiz:"):
        raise ValueError(f"{source}: reverse quiz must start with '# Reverse Quiz: <title>'")

    title, questions = parse_quiz_markdown(path)
    for question in questions:
        if question.get("imposters"):
            raise ValueError(
                f"{source}: reverse quiz does not support Imposters in question {question['title']!r}"
            )
        raw_limit = question.get("time_limit")
        try:
            parsed_limit = int(raw_limit) if raw_limit is not None else 0
        except (TypeError, ValueError):
            parsed_limit = 0
        if parsed_limit <= 0:
            question["time_limit"] = REVERSE_DEFAULT_TIME_LIMIT_SECONDS
        else:
            question["time_limit"] = parsed_limit

    if title.lower().startswith("reverse quiz:"):
        cleaned = title.split(":", 1)[1].strip()
        if cleaned:
            title = cleaned
    return title, questions


def parse_millionaire_markdown(path: str) -> tuple[str, list[dict]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    first_nonempty = ""
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped:
            first_nonempty = stripped
            break
    if not first_nonempty.lower().startswith("# millionaire quiz:"):
        raise ValueError(f"{source}: millionaire quiz must start with '# Millionaire Quiz: <title>'")

    friend_name = "Friend"
    blocks = re.split(r"(?m)^##\s+", text)
    preamble_raw = blocks[0].splitlines()
    preamble_nonempty = [line.strip() for line in preamble_raw if line.strip()]
    if preamble_nonempty and preamble_nonempty[0].startswith("# "):
        preamble_nonempty = preamble_nonempty[1:]
    friend_match_re = re.compile(r"(?i)^friend\s+name\s*:\s*(.+)$")
    seen_friend = False
    cleaned_preamble_lines: list[str] = []
    for raw_line in preamble_raw:
        stripped = raw_line.strip()
        if not stripped:
            cleaned_preamble_lines.append(raw_line)
            continue
        if stripped.startswith("# "):
            cleaned_preamble_lines.append(raw_line)
            continue
        friend_match = friend_match_re.match(stripped)
        if friend_match:
            if seen_friend:
                raise ValueError(f"{source}: duplicate 'Friend Name:' in millionaire preamble.")
            friend_name = friend_match.group(1).strip() or "Friend"
            seen_friend = True
            continue
        raise ValueError(
            f"{source}: unexpected preamble line {stripped!r}. "
            "Allowed lines: '# Millionaire Quiz: <title>' and optional 'Friend Name: <name>'."
        )

    sanitized_text = "\n".join(cleaned_preamble_lines)
    if len(blocks) > 1:
        sanitized_text = sanitized_text + "\n## " + "\n## ".join(blocks[1:])

    try:
        title, questions = parse_quiz_markdown(path, text_override=sanitized_text)
    except ValueError as exc:
        message = str(exc)
        if "time limit must be greater than zero" in message:
            raise ValueError(
                f"{message}. In millionaire mode, omit 'Time:' to use the default "
                f"{MILLIONAIRE_DEFAULT_TIME_LIMIT_SECONDS}s, or set a positive value up to "
                f"{MILLIONAIRE_MAX_TIME_LIMIT_SECONDS}s."
            ) from exc
        raise
    if len(questions) != MILLIONAIRE_TOTAL_QUESTIONS:
        raise ValueError(
            f"{source}: millionaire mode requires exactly {MILLIONAIRE_TOTAL_QUESTIONS} questions "
            f"(found {len(questions)})"
        )

    for question in questions:
        if question.get("imposters"):
            raise ValueError(
                f"{source}: millionaire quiz does not support Imposters in question {question['title']!r}"
            )

        qtype = str(question.get("type") or "single").strip().lower()
        if qtype != "single":
            raise ValueError(
                f"{source}: millionaire mode supports only Type: single "
                f"(question {question['title']!r} has Type: {qtype})"
            )

        raw_limit = question.get("time_limit")
        try:
            parsed_limit = int(raw_limit) if raw_limit is not None else 0
        except (TypeError, ValueError):
            parsed_limit = 0

        if parsed_limit <= 0:
            question["time_limit"] = MILLIONAIRE_DEFAULT_TIME_LIMIT_SECONDS
        else:
            question["time_limit"] = min(parsed_limit, MILLIONAIRE_MAX_TIME_LIMIT_SECONDS)
        question["friend_name"] = friend_name

    if title.lower().startswith("millionaire quiz:"):
        cleaned = title.split(":", 1)[1].strip()
        if cleaned:
            title = cleaned
    return title, questions


def _parse_chaos_score(value: str, source: Path, context: str) -> int:
    raw = (value or "").strip()
    if not raw:
        raise ValueError(f"{source}: missing Score value in {context}")
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ValueError(f"{source}: invalid Score value {raw!r} in {context}") from exc
    if parsed <= 0:
        raise ValueError(f"{source}: Score must be a positive integer in {context}")
    return parsed


def _parse_chaos_question_block(lines: list[str], source: Path, context: str) -> dict:
    option_pattern = re.compile(r"^\s*-\s*([A-Da-d])\.\s*(.+?)\s*$")
    answer_pattern = re.compile(r"(?i)^answer\s*:\s*([A-Za-z])\s*$")
    score_pattern = re.compile(r"(?i)^score\s*:\s*(.+?)\s*$")

    question_lines: list[str] = []
    options: list[dict] = []
    seen_labels: set[str] = set()
    answer_label: str | None = None
    score_value: int | None = None
    saw_option = False
    saw_answer = False

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            continue

        option_match = option_pattern.match(raw_line)
        if option_match:
            if saw_answer:
                raise ValueError(f"{source}: options must appear before Answer/Score in {context}")
            label = option_match.group(1).upper()
            text = option_match.group(2).strip()
            if label in seen_labels:
                raise ValueError(f"{source}: duplicate option label {label!r} in {context}")
            if not text:
                raise ValueError(f"{source}: blank option text for {label!r} in {context}")
            seen_labels.add(label)
            options.append({"label": label, "text": text})
            saw_option = True
            continue

        answer_match = answer_pattern.match(stripped)
        if answer_match:
            answer_label = answer_match.group(1).upper()
            saw_answer = True
            continue

        score_match = score_pattern.match(stripped)
        if score_match:
            score_value = _parse_chaos_score(score_match.group(1), source, context)
            saw_answer = True
            continue

        if saw_option:
            raise ValueError(
                f"{source}: unrecognized line {raw_line!r} in {context}. "
                "Expected Answer:/Score: after option list."
            )
        question_lines.append(stripped)

    question_text = "\n".join(question_lines).strip()
    if not question_text:
        raise ValueError(f"{source}: missing question text in {context}")
    if len(options) < 2:
        raise ValueError(f"{source}: {context} must define at least 2 options")
    if answer_label is None:
        raise ValueError(f"{source}: missing Answer in {context}")
    if score_value is None:
        raise ValueError(f"{source}: missing Score in {context}")

    option_labels = [item["label"] for item in options]
    if answer_label not in option_labels:
        raise ValueError(
            f"{source}: Answer {answer_label!r} is not present in options for {context}"
        )

    return {
        "question": question_text,
        "options": options,
        "answer": answer_label,
        "score": score_value,
    }


def _parse_chaos_tiers(lines: list[str], source: Path) -> tuple[int, list[dict]]:
    max_pattern = re.compile(r"(?i)^maximum\s+score\s*:\s*(\d+)\s*$")
    tier_pattern = re.compile(r"^\s*[-*]?\s*(\d+)\s*[–-]\s*(\d+)\s*:\s*(.+?)\s*$")

    max_score: int | None = None
    tiers: list[dict] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            continue
        max_match = max_pattern.match(stripped)
        if max_match:
            if max_score is not None:
                raise ValueError(f"{source}: duplicate 'Maximum score:' line in Result")
            max_score = int(max_match.group(1))
            continue
        tier_match = tier_pattern.match(stripped)
        if tier_match:
            low = int(tier_match.group(1))
            high = int(tier_match.group(2))
            text = tier_match.group(3).strip()
            if low > high:
                raise ValueError(
                    f"{source}: invalid Result range {low}-{high}; minimum cannot exceed maximum"
                )
            if not text:
                raise ValueError(f"{source}: empty tier message in Result for range {low}-{high}")
            tiers.append({"min": low, "max": high, "text": text})
            continue
        raise ValueError(
            f"{source}: unrecognized Result line {raw_line!r}. "
            "Expected 'Maximum score: N' or range tiers like '- 6-8: ...'."
        )

    if max_score is None:
        raise ValueError(f"{source}: missing 'Maximum score: N' in Result")
    if not tiers:
        raise ValueError(f"{source}: Result must include at least one score tier line")
    return max_score, tiers


def parse_chaos_markdown(path: str) -> tuple[str, dict]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        raise ValueError(f"{source}: empty chaos markdown file")

    first_nonempty = ""
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped:
            first_nonempty = stripped
            break
    if not first_nonempty.lower().startswith("# chaos:"):
        raise ValueError(f"{source}: chaos quiz must start with '# Chaos: <title>'")

    title = first_nonempty.split(":", 1)[1].strip()
    if not title:
        raise ValueError(f"{source}: chaos title cannot be empty")

    sections: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    preamble_lines: list[str] = []
    saw_header = False

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.lower().startswith("# chaos:") and not saw_header:
            saw_header = True
            continue
        if stripped.startswith("## "):
            if current_name is not None:
                sections.append((current_name, current_lines))
            current_name = stripped[3:].strip()
            current_lines = []
            continue
        if current_name is None:
            preamble_lines.append(raw_line)
        else:
            current_lines.append(raw_line)

    if current_name is not None:
        sections.append((current_name, current_lines))

    allowed_meta = {"type", "title", "skills", "difficulty"}
    metadata: dict[str, str] = {}
    for raw_line in preamble_lines:
        stripped = raw_line.strip()
        if not stripped:
            continue
        match = re.match(r"(?i)^([a-z][a-z0-9_\-\s]*)\s*:\s*(.+?)\s*$", stripped)
        if match is None:
            raise ValueError(
                f"{source}: unrecognized preamble line {raw_line!r}. "
                "Allowed metadata keys: Type, Title, Skills, Difficulty."
            )
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        if key not in allowed_meta:
            raise ValueError(
                f"{source}: unsupported metadata key {match.group(1)!r}. "
                "Allowed keys: Type, Title, Skills, Difficulty."
            )
        if key in metadata:
            raise ValueError(f"{source}: duplicate metadata key {match.group(1)!r}")
        metadata[key] = value

    if "type" in metadata and metadata["type"].strip().lower() != "chaos":
        raise ValueError(f"{source}: preamble 'Type:' must be 'chaos' for chaos quizzes")

    section_map: dict[str, list[str]] = {}
    section_display: dict[str, str] = {}
    section_order: list[str] = []
    for name, body in sections:
        normalized = name.strip().casefold()
        if normalized in section_map:
            raise ValueError(f"{source}: duplicate section header '## {name}'")
        section_map[normalized] = body
        section_display[normalized] = name.strip()
        section_order.append(normalized)

    if "scenario" not in section_map:
        raise ValueError(f"{source}: missing required section '## Scenario'")
    if "decision 1" not in section_map:
        raise ValueError(f"{source}: missing required section '## Decision 1'")
    if "final decision" not in section_map:
        raise ValueError(f"{source}: missing required section '## Final Decision'")
    if "result" not in section_map:
        raise ValueError(f"{source}: missing required section '## Result'")

    scenario_text = "\n".join(line for line in section_map["scenario"]).strip()
    if not scenario_text:
        raise ValueError(f"{source}: Scenario section cannot be empty")

    def split_h3_subsections(lines_block: list[str], context: str) -> tuple[list[str], dict[str, list[str]]]:
        main_lines: list[str] = []
        sub_sections: dict[str, list[str]] = {}
        current_sub: str | None = None
        current_sub_lines: list[str] = []
        for raw_line in lines_block:
            stripped = raw_line.strip()
            if stripped.startswith("### "):
                if current_sub is not None:
                    key = current_sub.casefold()
                    if key in sub_sections:
                        raise ValueError(f"{source}: duplicate subsection '### {current_sub}' in {context}")
                    sub_sections[key] = current_sub_lines
                current_sub = stripped[4:].strip()
                current_sub_lines = []
                continue
            if current_sub is None:
                main_lines.append(raw_line)
            else:
                current_sub_lines.append(raw_line)
        if current_sub is not None:
            key = current_sub.casefold()
            if key in sub_sections:
                raise ValueError(f"{source}: duplicate subsection '### {current_sub}' in {context}")
            sub_sections[key] = current_sub_lines
        return main_lines, sub_sections

    decision_main, decision_sub = split_h3_subsections(section_map["decision 1"], "Decision 1")
    decision = _parse_chaos_question_block(decision_main, source, "Decision 1")

    feedback_lines = decision_sub.get("feedback")
    if feedback_lines is None:
        raise ValueError(f"{source}: Decision 1 must include '### Feedback'")
    decision_feedback = "\n".join(feedback_lines).strip()
    if not decision_feedback:
        raise ValueError(f"{source}: Decision 1 Feedback cannot be empty")

    chaos_events: dict[str, str] = {}
    for key, value in decision_sub.items():
        if key == "feedback":
            continue
        match = re.match(r"^chaos if ([a-d])$", key)
        if match is None:
            raise ValueError(
                f"{source}: unsupported subsection under Decision 1: '### {key}'. "
                "Expected '### Feedback' or '### Chaos if <A-D>'."
            )
        label = match.group(1).upper()
        if label in chaos_events:
            raise ValueError(f"{source}: duplicate chaos event block for option {label}")
        event_text = "\n".join(value).strip()
        if not event_text:
            raise ValueError(f"{source}: Chaos event text cannot be empty for option {label}")
        chaos_events[label] = event_text

    option_labels = [item["label"] for item in decision["options"]]
    for label in option_labels:
        if label not in chaos_events:
            raise ValueError(f"{source}: missing '### Chaos if {label}' in Decision 1")
    for label in list(chaos_events.keys()):
        if label not in option_labels:
            raise ValueError(f"{source}: chaos event exists for unknown option {label}")

    expected_order = (
        ["scenario", "decision 1"]
        + [f"path {label.lower()}" for label in option_labels]
        + ["final decision", "result"]
    )
    for label in option_labels:
        key = f"path {label.lower()}"
        if key not in section_map:
            raise ValueError(
                f"{source}: missing required section '## Path {label}'.\n"
                f"Add a matching branch for option {label} with:\n"
                f"## Path {label}\n"
                f"### Recovery {label}\n"
                "...\n"
                "### Feedback\n"
                "...\n"
                "Tip: run `quizmd init` and use `hello-chaos.md` as the reference template."
            )

    expected_sections = set(expected_order)
    extras = [name for name in section_order if name not in expected_sections]
    if extras:
        human = ", ".join(f"## {section_display.get(name, name)}" for name in extras)
        raise ValueError(
            f"{source}: unsupported chaos section(s): {human}. "
            "Only Scenario, Decision 1, Path <A-D>, Final Decision, and Result are allowed."
        )

    paths: dict[str, dict] = {}

    if section_order != expected_order:
        raise ValueError(
            f"{source}: chaos sections must follow strict order: "
            + " -> ".join([f"## {name.title()}" for name in expected_order])
        )

    for label in option_labels:
        key = f"path {label.lower()}"
        path_main, path_sub = split_h3_subsections(section_map[key], f"Path {label}")
        if any(line.strip() for line in path_main):
            raise ValueError(
                f"{source}: Path {label} must use subsection blocks only. "
                "Move content under '### Recovery <letter>' or '### Feedback'."
            )
        recovery_key = f"recovery {label.lower()}"
        recovery_lines = path_sub.get(recovery_key)
        if recovery_lines is None:
            raise ValueError(f"{source}: Path {label} must include '### Recovery {label}'")
        recovery = _parse_chaos_question_block(recovery_lines, source, f"Path {label} Recovery")
        feedback_lines = path_sub.get("feedback")
        if feedback_lines is None:
            raise ValueError(f"{source}: Path {label} must include '### Feedback'")
        path_feedback = "\n".join(feedback_lines).strip()
        if not path_feedback:
            raise ValueError(f"{source}: Path {label} Feedback cannot be empty")
        for key in path_sub:
            if key not in {recovery_key, "feedback"}:
                raise ValueError(
                    f"{source}: unsupported subsection '### {key}' in Path {label}. "
                    f"Expected only '### Recovery {label}' and '### Feedback'."
                )
        paths[label] = {
            "recovery": recovery,
            "feedback": path_feedback,
        }

    final_main, final_sub = split_h3_subsections(section_map["final decision"], "Final Decision")
    final_decision = _parse_chaos_question_block(final_main, source, "Final Decision")
    final_feedback_lines = final_sub.get("final feedback")
    if final_feedback_lines is None:
        raise ValueError(f"{source}: Final Decision must include '### Final feedback'")
    final_feedback = "\n".join(final_feedback_lines).strip()
    if not final_feedback:
        raise ValueError(f"{source}: Final Decision feedback cannot be empty")
    for key in final_sub:
        if key != "final feedback":
            raise ValueError(
                f"{source}: unsupported subsection '### {key}' in Final Decision. "
                "Expected only '### Final feedback'."
            )

    maximum_score, tiers = _parse_chaos_tiers(section_map["result"], source)
    canonical_maximum = (
        int(decision["score"])
        + max(int(paths[label]["recovery"]["score"]) for label in paths)
        + int(final_decision["score"])
    )
    if maximum_score != canonical_maximum:
        raise ValueError(
            f"{source}: Maximum score mismatch. Result declares {maximum_score}, "
            f"but canonical max is {canonical_maximum} (Decision 1 + best Recovery + Final Decision)."
        )

    payload = {
        "title": title,
        "metadata": metadata,
        "scenario": scenario_text,
        "decision1": {
            **decision,
            "feedback": decision_feedback,
            "chaos_events": chaos_events,
        },
        "paths": paths,
        "final_decision": {
            **final_decision,
            "feedback": final_feedback,
        },
        "result": {
            "maximum_score": maximum_score,
            "tiers": tiers,
        },
    }
    return title, payload


def _normalize_code_lines(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _debug_changed_line_numbers(broken_code: str, fixed_code: str) -> list[int]:
    broken_lines = _normalize_code_lines(broken_code)
    fixed_lines = _normalize_code_lines(fixed_code)
    max_len = max(len(broken_lines), len(fixed_lines))
    changed: list[int] = []
    for idx in range(max_len):
        broken_line = broken_lines[idx] if idx < len(broken_lines) else ""
        fixed_line = fixed_lines[idx] if idx < len(fixed_lines) else ""
        if broken_line != fixed_line:
            changed.append(idx + 1)
    return changed


def _score_debug_submission(broken_code: str, fixed_code: str, student_code: str) -> dict:
    def _python_ast_equivalent(left_code: str, right_code: str) -> bool:
        try:
            left_tree = ast.parse(left_code)
            right_tree = ast.parse(right_code)
        except SyntaxError:
            return False
        return ast.dump(left_tree, include_attributes=False) == ast.dump(right_tree, include_attributes=False)

    broken_lines = _normalize_code_lines(broken_code)
    fixed_lines = _normalize_code_lines(fixed_code)
    student_lines = _normalize_code_lines(student_code)
    changed_lines = _debug_changed_line_numbers(broken_code, fixed_code)

    fixed_count = 0
    for line_no in changed_lines:
        fixed_line = fixed_lines[line_no - 1] if line_no - 1 < len(fixed_lines) else ""
        student_line = student_lines[line_no - 1] if line_no - 1 < len(student_lines) else ""
        if student_line == fixed_line:
            fixed_count += 1

    def _is_comment_or_blank(line: str) -> bool:
        stripped = line.strip()
        return (not stripped) or stripped.startswith("#")

    def _semantic_fallback_allowed() -> bool:
        # AST-equivalence is great for formatting-only code changes, but comments
        # are not part of the AST. For comment/blank-line fixes, keep exact mode.
        for line_no in changed_lines:
            broken_line = broken_lines[line_no - 1] if line_no - 1 < len(broken_lines) else ""
            fixed_line = fixed_lines[line_no - 1] if line_no - 1 < len(fixed_lines) else ""
            if _is_comment_or_blank(broken_line) or _is_comment_or_blank(fixed_line):
                return False
        return True

    max_points = len(changed_lines) if changed_lines else 1
    exact_match = student_lines == fixed_lines
    semantic_match = False
    if not exact_match:
        semantic_match = _semantic_fallback_allowed() and _python_ast_equivalent(
            "\n".join(student_lines),
            "\n".join(fixed_lines),
        )
        if semantic_match:
            fixed_count = max_points
    is_perfect = exact_match or semantic_match
    if is_perfect:
        scoring_mode = "exact" if exact_match else "python_ast"
    else:
        scoring_mode = "line_exact"
    return {
        "fixed_count": fixed_count,
        "total_errors": max_points,
        "question_points": fixed_count,
        "question_max_points": max_points,
        "is_perfect": is_perfect,
        "changed_lines": changed_lines,
        "exact_match": exact_match,
        "semantic_match": semantic_match,
        "scoring_mode": scoring_mode,
        "ai_reviewed": False,
        "ai_accepted": False,
        "ai_provider": "",
        "ai_reason": "",
        "ai_confidence": "",
    }


def _build_debug_ai_eval_prompt(question: dict, student_code: str, deterministic: dict) -> str:
    changed = ", ".join(str(n) for n in deterministic.get("changed_lines", [])) or "None"
    ai_note = (question.get("ai_note") or "").strip()
    note_block = f"\nTeacher AI note:\n{ai_note}\n" if ai_note else ""
    return (
        "You are validating a student's Python debug fix.\n"
        "A deterministic checker already compared exact changed lines and did not confirm a perfect fix.\n"
        "Your job: decide if the student's code is still semantically correct and should be accepted.\n\n"
        "Rules:\n"
        "- Accept equivalent solutions that preserve intended behavior, even with different structure.\n"
        "- Reject if syntax errors remain, runtime behavior is wrong, or required fixes are missing.\n"
        "- Be strict but fair.\n"
        f"{note_block}\n"
        f"Question prompt:\n{question.get('prompt', '').strip()}\n\n"
        f"Broken code:\n```python\n{question.get('broken_code', '').strip()}\n```\n\n"
        f"Reference fixed code:\n```python\n{question.get('fixed_code', '').strip()}\n```\n\n"
        f"Student submitted code:\n```python\n{student_code.strip()}\n```\n\n"
        f"Expected changed lines from deterministic diff: {changed}\n"
        f"Deterministic score: {deterministic.get('question_points', 0)}/{deterministic.get('question_max_points', 0)}\n\n"
        "Return strict JSON only with keys:\n"
        "- accept (boolean)\n"
        "- confidence (one of: low, medium, high)\n"
        "- reason (short string)\n"
    )


def _normalize_debug_ai_review(raw_review, provider_name: str = "model") -> dict:
    if isinstance(raw_review, list):
        if len(raw_review) == 1 and isinstance(raw_review[0], dict):
            raw_review = raw_review[0]
        else:
            raise ValueError(f"{provider_name} JSON returned a list instead of a single object")
    if not isinstance(raw_review, dict):
        raise ValueError(f"{provider_name} JSON must be an object")
    if "accept" not in raw_review:
        raise ValueError(f"{provider_name} JSON missing key: accept")

    raw_accept = raw_review.get("accept")
    if isinstance(raw_accept, bool):
        accept = raw_accept
    elif isinstance(raw_accept, str):
        accept = raw_accept.strip().lower() in {"true", "yes", "y", "1", "accept", "accepted"}
    else:
        accept = bool(raw_accept)

    confidence = str(raw_review.get("confidence", "medium")).strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    reason = str(raw_review.get("reason", "")).strip() or "No reason provided."
    return {"accept": accept, "confidence": confidence, "reason": reason}


def evaluate_debug_with_gemini(
    question: dict,
    student_code: str,
    deterministic: dict,
    api_key: str,
    model: str,
    timeout: int,
    max_retries: int = 2,
) -> dict:
    prompt = _build_debug_ai_eval_prompt(question, student_code, deterministic)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    body = json.dumps(payload).encode("utf-8")
    if len(body) > MAX_AI_REQUEST_BYTES:
        raise RuntimeError("[payload_too_large] Debug payload too large for AI review.")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    last_error = None
    reason_code = "unknown_error"
    for attempt in range(max_retries + 1):
        _wait_for_gemini_window()
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json", "X-goog-api-key": api_key},
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
                review = _extract_json_object(text)
                return _normalize_debug_ai_review(review, provider_name="Gemini")
        except Exception as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            last_error = exc
            retryable, reason_code = _classify_provider_error(exc)
        if attempt >= max_retries or not retryable:
            break
        time.sleep((2 ** attempt) + random.uniform(0.1, 0.35))
    raise RuntimeError(f"[{reason_code}] Gemini debug review failed after retries: {last_error}")


def evaluate_debug_with_openai(
    question: dict,
    student_code: str,
    deterministic: dict,
    api_key: str,
    model: str,
    timeout: int,
    max_retries: int = 2,
) -> dict:
    prompt = _build_debug_ai_eval_prompt(question, student_code, deterministic)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    body = json.dumps(payload).encode("utf-8")
    if len(body) > MAX_AI_REQUEST_BYTES:
        raise RuntimeError("[payload_too_large] Debug payload too large for AI review.")

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
                review = _extract_json_object(text)
                return _normalize_debug_ai_review(review, provider_name="OpenAI")
        except Exception as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            last_error = exc
            retryable, reason_code = _classify_provider_error(exc)

        if attempt >= max_retries or not retryable:
            break
        time.sleep((2 ** attempt) + random.uniform(0.1, 0.35))

    raise RuntimeError(f"[{reason_code}] OpenAI debug review failed after retries: {last_error}")


def evaluate_debug_with_anthropic(
    question: dict,
    student_code: str,
    deterministic: dict,
    api_key: str,
    model: str,
    timeout: int,
    max_retries: int = 2,
) -> dict:
    prompt = _build_debug_ai_eval_prompt(question, student_code, deterministic)
    payload = {
        "model": model,
        "max_tokens": 800,
        "temperature": 0,
        "system": "Return valid JSON only.",
        "messages": [{"role": "user", "content": prompt}],
    }
    body = json.dumps(payload).encode("utf-8")
    if len(body) > MAX_AI_REQUEST_BYTES:
        raise RuntimeError("[payload_too_large] Debug payload too large for AI review.")

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
                review = _extract_json_object(text)
                return _normalize_debug_ai_review(review, provider_name="Anthropic")
        except Exception as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            last_error = exc
            retryable, reason_code = _classify_provider_error(exc)

        if attempt >= max_retries or not retryable:
            break
        time.sleep((2 ** attempt) + random.uniform(0.1, 0.35))

    raise RuntimeError(f"[{reason_code}] Anthropic debug review failed after retries: {last_error}")


def _apply_debug_ai_override(grading: dict, review: dict, provider: str) -> dict:
    merged = dict(grading)
    merged["ai_reviewed"] = True
    merged["ai_provider"] = provider
    merged["ai_reason"] = str(review.get("reason", "")).strip()
    merged["ai_confidence"] = str(review.get("confidence", "")).strip()
    accepted = bool(review.get("accept"))
    merged["ai_accepted"] = accepted
    if accepted and not merged.get("is_perfect"):
        merged["fixed_count"] = int(merged.get("question_max_points", merged.get("fixed_count", 0)))
        merged["question_points"] = int(merged.get("question_max_points", merged.get("question_points", 0)))
        merged["is_perfect"] = True
        merged["scoring_mode"] = "ai_semantic"
    return merged


def _extract_labeled_code_block(
    lines: list[str],
    label: str,
    source: Path,
    question_title: str,
) -> tuple[list[str], int, int]:
    label_idx = None
    target = f"{label}:"
    for idx, raw_line in enumerate(lines):
        if raw_line.strip().lower() == target.lower():
            label_idx = idx
            break
    if label_idx is None:
        raise ValueError(f"{source}: question {question_title!r} is missing '{label}:' section")

    start = label_idx + 1
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines) or not lines[start].strip().startswith("```"):
        raise ValueError(
            f"{source}: question {question_title!r} '{label}:' must be followed by a fenced code block"
        )

    code_lines: list[str] = []
    end = None
    for idx in range(start + 1, len(lines)):
        if lines[idx].strip().startswith("```"):
            end = idx
            break
        code_lines.append(lines[idx])
    if end is None:
        raise ValueError(
            f"{source}: question {question_title!r} '{label}:' code block is missing closing fence"
        )
    if not any(line.strip() for line in code_lines):
        raise ValueError(f"{source}: question {question_title!r} '{label}:' code block cannot be empty")

    return code_lines, label_idx, end


def parse_debug_markdown(path: str) -> tuple[str, list[dict]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")

    blocks = re.split(r"(?m)^##\s+", text)
    preamble_lines = [line.strip() for line in blocks[0].splitlines() if line.strip()]

    quiz_title = "Debug Quiz"
    if preamble_lines:
        if preamble_lines[0].startswith("# "):
            quiz_title = preamble_lines[0][2:].strip() or "Debug Quiz"
            preamble_lines = preamble_lines[1:]
        if preamble_lines:
            raise ValueError(
                f"{source}: unexpected content outside debug question blocks. Use '##' headers."
            )

    questions: list[dict] = []
    field_pattern = re.compile(r"(?i)^(type|hint|explanation|ai\s*note)\s*:\s*(.*)$")

    for block in blocks[1:]:
        block = block.strip("\n")
        if not block.strip():
            continue

        lines = block.splitlines()
        title = lines[0].strip()
        body = lines[1:]
        if not body:
            raise ValueError(f"{source}: malformed debug question block {title!r}")

        broken_lines, broken_label_idx, broken_end_idx = _extract_labeled_code_block(body, "Broken", source, title)
        fixed_lines, fixed_label_idx, fixed_end_idx = _extract_labeled_code_block(body, "Fixed", source, title)
        if fixed_label_idx < broken_end_idx:
            raise ValueError(
                f"{source}: question {title!r} has malformed section order. Use question text, Broken, then Fixed."
            )

        prompt_lines = body[:broken_label_idx]
        prompt = "\n".join(prompt_lines).strip()
        if not prompt:
            raise ValueError(f"{source}: question {title!r} is missing the prompt text line")

        metadata_lines = body[fixed_end_idx + 1 :]
        qtype = ""
        hint = ""
        explanation = ""
        ai_note = ""
        for raw_line in metadata_lines:
            stripped = raw_line.strip()
            if not stripped:
                continue
            match = field_pattern.match(stripped)
            if not match:
                raise ValueError(
                    f"{source}: unrecognized debug metadata line {raw_line!r} in question {title!r}. "
                    "Expected Type, Hint, Explanation, AI Note."
                )
            key = match.group(1).lower()
            value = match.group(2).strip()
            if key == "type":
                qtype = value.lower()
            elif key == "hint":
                hint = value
            elif key == "explanation":
                explanation = value
            elif key.replace(" ", "") == "ainote":
                ai_note = value

        if qtype and qtype != "debug":
            raise ValueError(
                f"{source}: question {title!r} has unsupported Type {qtype!r}; debug mode expects Type: debug"
            )

        broken_code = "\n".join(broken_lines).rstrip()
        fixed_code = "\n".join(fixed_lines).rstrip()
        changed_lines = _debug_changed_line_numbers(broken_code, fixed_code)
        if not changed_lines:
            raise ValueError(
                f"{source}: question {title!r} has no detectable code differences between Broken and Fixed blocks"
            )

        questions.append(
            {
                "title": title,
                "prompt": prompt,
                "type": "debug",
                "broken_code": broken_code,
                "fixed_code": fixed_code,
                "hint": hint,
                "explanation": explanation,
                "ai_note": ai_note,
                "changed_lines": changed_lines,
            }
        )

    if not questions:
        raise ValueError(f"{source}: no valid debug questions found. Add at least one '##' question block.")

    return quiz_title, questions


def detect_quiz_mode(path: str) -> str:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if not line:
            continue
        if lowered.startswith("# essay question:"):
            return "essay"
        if lowered.startswith("# chaos:"):
            return "chaos"
        if lowered.startswith("# reverse quiz:"):
            return "reverse"
        if lowered.startswith("# millionaire quiz:"):
            return "millionaire"
        if lowered.startswith("# challenge quiz:"):
            return "challenge"
        if lowered.startswith("# debug quiz"):
            return "debug"
        if line.startswith("# "):
            if re.search(r"(?im)^type\s*:\s*debug\s*$", text):
                return "debug"
            return "mcq"
        break
    raise ValueError(
        f"{source}: expected '# ...', '# Essay Question: ...', '# Chaos: ...', '# Reverse Quiz: ...', "
        "'# Millionaire Quiz: ...', or '# Challenge Quiz: ...' header"
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
    if not first_nonempty.lower().startswith("# essay question:"):
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
        if stripped.lower().startswith("# essay question:") and not started_sections:
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
        try:
            choice = prompt_input(prompt).strip().lower()
        except RuntimeError:
            # If stdin is exhausted/non-interactive, fail closed instead of crashing.
            return False
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
        ("hello-debug.md", HELLO_DEBUG_TEMPLATE),
        ("hello-challenge.md", HELLO_CHALLENGE_TEMPLATE),
        ("hello-reverse.md", HELLO_REVERSE_TEMPLATE),
        ("hello-millionaire.md", HELLO_MILLIONAIRE_TEMPLATE),
        ("hello-chaos.md", HELLO_CHAOS_TEMPLATE),
        ("hello-essay.md", HELLO_ESSAY_TEMPLATE),
        ("QUIZ_GUIDE.md", QUIZ_GUIDE_TEMPLATE),
    ]

    existing_paths = [base / name for name, _ in files_to_create if (base / name).exists()]
    existing = [str(path) for path in existing_paths]
    if existing and not force:
        preview_limit = 6
        shown = existing_paths[:preview_limit]
        shown_lines = [f"- {path.name}" for path in shown]
        hidden_count = max(0, len(existing_paths) - len(shown))
        if hidden_count:
            shown_lines.append(f"- ... and {hidden_count} more")
        location = str(base.resolve())
        raise RuntimeError(
            "Some starter files already exist. No files were changed.\n"
            f"Location: {location}\n\n"
            "Existing files:\n"
            + "\n".join(shown_lines)
            + "\n\n"
            "Choose one:\n"
            "- Re-run with --force to overwrite existing starter files.\n"
            "- Use --dir <new-folder> to create files in a new location."
        )

    created: list[Path] = []
    for name, content in files_to_create:
        out = base / name
        out.write_text(content, encoding="utf-8")
        created.append(out)
    return created


def clear_terminal_screen() -> None:
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="")


def ensure_terminal_cursor_visible() -> None:
    if not sys.stdout.isatty():
        return
    print("\033[?25h", end="", flush=True)


def start_clean_screen(enabled: bool = True) -> None:
    if enabled:
        clear_terminal_screen()


def render_exit_message(message: str = "Exited QuizMD. See you next time.", no_color: bool = False) -> None:
    ensure_terminal_cursor_visible()
    try:
        from rich.console import Console
        from rich.panel import Panel
    except ModuleNotFoundError:
        print("")
        print(message)
        return

    theme = select_theme("auto")
    console = Console(no_color=no_color)
    console.print("")
    console.print(
        Panel(
            f"[bold {theme['primary']}]{message}[/bold {theme['primary']}]",
            border_style=theme["panel"],
        )
    )


def render_init_next_screen(created: list[Path] | None = None, target_dir: str = ".") -> None:
    """Render the experimental vNext init welcome without changing file behavior."""
    start_clean_screen()
    try:
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ModuleNotFoundError:
        print(f"QuizMD {__version__}")
        print("Write quizzes in Markdown. Run them in the terminal.")
        print(f"Folder: {Path(target_dir).expanduser().resolve()}")
        print(f"Documentation: {QUIZMD_DOCS_URL}")
        return

    theme = select_theme("auto")
    probe_console = Console()
    terminal_width = max(probe_console.size.width, 40)
    panel_width = min(terminal_width, 120)
    wide_layout = panel_width >= 96
    console = Console(width=panel_width)
    folder = Path(target_dir).expanduser().resolve()
    console.print(
        Panel(
            f"[bold {theme['primary']}]QuizMD[/bold {theme['primary']}] [dim]v{__version__}[/dim]\n"
            f"[{theme['success']}]Write quizzes in Markdown. Run them in the terminal.[/{theme['success']}]\n"
            f"[dim]Folder:[/dim] {folder}\n"
            f"[bold]Documentation:[/bold] [link={QUIZMD_DOCS_URL}][underline {theme['primary']}]{QUIZMD_DOCS_URL}[/underline {theme['primary']}][/link]",
            border_style=theme["panel"],
            box=box.ROUNDED,
            expand=True,
            width=panel_width,
        )
    )

    mode_cards = (
        "[bold]1 Classic[/bold]\n[dim]Multiple-choice quiz[/dim]\n[green]No AI key[/green]",
        "[bold]2 Imposter[/bold]\n[dim]Spot misleading answers[/dim]\n[green]No AI key[/green]",
        "[bold]3 Debug[/bold]\n[dim]Fix broken code[/dim]\n[yellow]Optional AI key[/yellow]",
        "[bold]4 Challenge[/bold]\n[dim]Category + risk stars[/dim]\n[green]No AI key[/green]",
        "[bold]5 Reverse[/bold]\n[dim]Output/behavior to code[/dim]\n[green]No AI key[/green]",
        "[bold]6 Millionaire[/bold]\n[dim]15-question ladder mode[/dim]\n[yellow]Optional AI key[/yellow]",
        "[bold]7 Chaos[/bold]\n[dim]Decision tree + recovery[/dim]\n[green]No AI key[/green]",
        "[bold]8 Essay[/bold]\n[dim]Rubric + AI feedback[/dim]\n[yellow]Needs AI key[/yellow]",
    )
    if wide_layout:
        modes = Table.grid(expand=True)
        modes.add_column(ratio=1)
        modes.add_column(ratio=1)
        modes.add_column(ratio=1)
        modes.add_column(ratio=1)
        modes.add_row(*mode_cards[:4])
        modes.add_row(*mode_cards[4:8])
    else:
        modes = "\n\n".join(mode_cards)
    console.print(
        Panel(
            modes,
            title="[bold]Recommended quiz types[/bold]",
            border_style=theme["panel"],
            expand=True,
            width=panel_width,
        )
    )

    room_cards = (
        "[bold]Compete[/bold]\n[dim]Fast live quiz race[/dim]",
        "[bold]Collaborate[/bold]\n[dim]Team consensus quiz[/dim]",
    )
    if wide_layout:
        rooms = Table.grid(expand=True)
        rooms.add_column(ratio=1)
        rooms.add_column(ratio=1)
        rooms.add_row(*room_cards)
    else:
        rooms = "\n\n".join(room_cards)
    console.print(
        Panel(
            rooms,
            title="[bold]Room modes[/bold]",
            border_style=theme["secondary"],
            expand=True,
            width=panel_width,
        )
    )

    game_cards = ("[bold]Alien Attack[/bold]\n[dim]Arcade typing mini-game[/dim]\n[green]No AI key[/green]",)
    if wide_layout:
        games = Table.grid(expand=True)
        games.add_column(ratio=1)
        games.add_row(*game_cards)
    else:
        games = "\n\n".join(game_cards)
    console.print(
        Panel(
            games,
            title="[bold]Game modes[/bold]",
            border_style=theme["accent"],
            expand=True,
            width=panel_width,
        )
    )

    if created is not None:
        labels = {
            "hello-quiz.md": "Single + multiple choice",
            "hello-imposter.md": "Imposter distractor spotting",
            "hello-debug.md": "Fix broken code with line hints",
            "hello-challenge.md": "Category mode with star scoring",
            "hello-reverse.md": "Reverse engineering MCQ mode",
            "hello-millionaire.md": "15-step points ladder (max 120s/question, optional Ask AI)",
            "hello-chaos.md": "Branching decision tree with recovery paths",
            "hello-essay.md": "Short answer with AI feedback",
            "QUIZ_GUIDE.md": "Starter commands and notes",
        }
        created_text = "\n".join(
            f"- {path.name} [dim][{labels.get(path.name, 'Created file')}][/dim]"
            for path in created
        )
        console.print(
            Panel(
                created_text,
                title=f"[bold {theme['success']}]Created starter files[/bold {theme['success']}]",
                border_style=theme["success"],
                expand=True,
                width=panel_width,
            )
        )
        console.print(
            Panel(
                "[bold]Getting started[/bold]\n"
                "[dim]Run your first quiz now:[/dim]\n"
                "quizmd hello-quiz.md",
                title=f"[bold {theme['accent']}]Try it out[/bold {theme['accent']}]",
                border_style=theme["accent"],
                expand=True,
                width=panel_width,
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


def _room_create_token_required_unsupported(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    if "token_required" not in lowered:
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
    url = f"{_room_http_base(server)}/rooms"
    try:
        return _room_post_json(url, payload)
    except RuntimeError as exc:
        if not _room_create_token_required_unsupported(str(exc)):
            raise
        if not token_required:
            raise RuntimeError(
                "This room server is too old to create open rooms without a token. "
                "Redeploy/update quizmd-server, or create a token-protected room with --require-token."
            ) from exc
        legacy_payload = dict(payload)
        legacy_payload.pop("token_required", None)
        created = _room_post_json(url, legacy_payload)
        if "token_required" not in created and created.get("room_token"):
            created["token_required"] = True
        return created


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
    points_raw = question.get("points", question.get("score", 1))
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

    try:
        points = float(points_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source}: question {index} has invalid 'points' value {points_raw!r}") from exc
    if not math.isfinite(points):
        raise ValueError(
            f"{source}: question {index} has invalid 'points' value {points}. "
            "Question points must be finite."
        )
    if points <= 0:
        raise ValueError(
            f"{source}: question {index} has invalid 'points' value {points}. "
            "Question points must be greater than zero."
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
        "points": points,
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
                "points": float(q.get("points") or 1),
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
    if mode != "mcq":
        raise RuntimeError(
            f"{mode.title()} files are not supported for room mode. "
            "Use a standard multiple-choice quiz file."
        )
    try:
        return _room_quiz_payload_from_markdown(str(quiz_path))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Invalid markdown quiz file: {exc}") from exc


def _room_prompt_quiz_file() -> str:
    if not sys.stdin.isatty():
        return ""
    default = "hello-quiz.md" if Path("hello-quiz.md").exists() else ""
    prompt = f"Enter quiz file [{default}]: " if default else "Enter quiz file [sample]: "
    value = prompt_input(prompt).strip()
    return value or default


def _room_mode_label(mode: str) -> str:
    labels = {
        "compete": "Compete",
        "collaborate": "Collaborate",
    }
    return labels.get(str(mode or "").lower(), str(mode or "Room").title())


def render_room_created_screen(
    *,
    room_name: str,
    host_name: str,
    mode: str,
    quiz_title: str,
    question_count: int,
    join_command: str,
    token_required: bool,
    room_token: str = "",
    host_role: str = "",
    theme_name: str = "auto",
    no_color: bool = False,
) -> None:
    try:
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ModuleNotFoundError:
        print("-----------------------------------")
        print("")
        print(f"Room created by: {host_name}")
        print(f"Room: {room_name}")
        if host_role:
            print(f"Role: {host_role}")
        if token_required and room_token:
            print(f"Room token: {room_token}")
        print(f"Quiz: {quiz_title}")
        print(f"Join command: {join_command}")
        return

    theme = select_theme(theme_name)
    probe_console = Console(no_color=no_color)
    terminal_width = max(probe_console.size.width, 40)
    panel_width = min(terminal_width, 120)
    console = Console(no_color=no_color, width=panel_width)
    access = "Token required" if token_required else "Open room"

    summary = Table.grid(expand=True)
    summary.add_column(ratio=1)
    summary.add_column(ratio=1)
    summary.add_row(
        f"[dim]Host[/dim]\n[bold]{host_name}[/bold]",
        f"[dim]Room[/dim]\n[bold {theme['primary']}]{room_name}[/bold {theme['primary']}]",
    )
    summary.add_row(
        f"[dim]Mode[/dim]\n[bold]{_room_mode_label(mode)}[/bold]",
        f"[dim]Access[/dim]\n[bold]{access}[/bold]",
    )
    role = str(host_role or "").strip()
    if role:
        summary.add_row(
            f"[dim]Role[/dim]\n[bold]{role}[/bold]",
            f"[dim]Questions[/dim]\n[bold]{question_count}[/bold]",
        )
    else:
        summary.add_row(
            f"[dim]Questions[/dim]\n[bold]{question_count}[/bold]",
            "",
        )

    console.print("")
    console.print(
        Panel(
            summary,
            title=f"[bold {theme['success']}]Room ready[/bold {theme['success']}]",
            subtitle=f"[dim]{quiz_title}[/dim]",
            border_style=theme["panel"],
            box=box.ROUNDED,
            expand=True,
            width=panel_width,
        )
    )

    command_body = (
        f"[bold]Quiz:[/bold] {quiz_title}\n\n"
        f"[bold]Join command:[/bold]\n"
        f"[{theme['primary']}]{join_command}[/{theme['primary']}]"
    )
    if token_required and room_token:
        command_body += f"\n\n[dim]Token is included in the command.[/dim]"
    console.print(
        Panel(
            command_body,
            border_style=theme["accent"],
            box=box.ROUNDED,
            expand=True,
            width=panel_width,
        )
    )


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


def _room_numeric_score(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_room_score(value: object) -> str:
    score = _room_numeric_score(value)
    if score.is_integer():
        return str(int(score))
    return f"{score:.2f}".rstrip("0").rstrip(".")


def _room_final_podium(players: list[dict]) -> str:
    scored_players = [
        {
            "name": str(row.get("name") or "Unknown"),
            "score": _room_numeric_score(row.get("score")),
        }
        for row in players
        if isinstance(row, dict)
    ]
    scored_players.sort(key=lambda row: (-row["score"], row["name"].lower()))
    top = scored_players[:3]
    if not top:
        return "No final scores available."

    def entry(index: int, fallback: str) -> tuple[str, str, str]:
        if index >= len(top):
            return fallback, "-", "-"
        row = top[index]
        return f"{index + 1}", row["name"], _format_room_score(row["score"])

    first_rank, first_name, first_score = entry(0, "1")
    second_rank, second_name, second_score = entry(1, "2")
    third_rank, third_name, third_score = entry(2, "3")
    winner = top[0]["name"]
    lines = [
        "Final podium",
        "",
        f"              [{first_rank}]",
        f"          {first_name}",
        f"          {first_score} pts",
        "           _____",
        "          |     |",
        "          |  1  |",
        "     _____|_____|_____",
        "    |     |     |     |",
        f"    |  {second_rank}  |     |  {third_rank}  |",
        "    |_____|     |_____|",
        "",
        f"1. {first_name} - {first_score} pts",
    ]
    if len(top) >= 2:
        lines.append(f"2. {second_name} - {second_score} pts")
    if len(top) >= 3:
        lines.append(f"3. {third_name} - {third_score} pts")
    lines.extend(
        [
            "",
            "* * * * * * * * * * * *",
            f"*   {winner} wins!   *",
            "* * * * * * * * * * * *",
        ]
    )
    return "\n".join(lines)


async def _room_final_results_countdown(seconds: int = 5, sleep_fn=asyncio.sleep) -> None:
    for remaining in range(max(0, seconds), 0, -1):
        print(f"\rFinal results in {remaining}...", end="", flush=True)
        await sleep_fn(1)
    print("\rFinal results now.        ")


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

    # Render a concrete first frame immediately so some terminals do not appear blank
    # before the first key event.
    control = FormattedTextControl(text=render())
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
    except KeyboardInterrupt:
        raise
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
    finally:
        ensure_terminal_cursor_visible()


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


def _room_runtime_question_payload(q_payload: object, question_index: int) -> dict[str, object] | None:
    if not isinstance(q_payload, dict):
        return None
    question_text = str(q_payload.get("question") or "").strip()
    options_raw = q_payload.get("options")
    if not question_text or not isinstance(options_raw, list):
        return None
    options = [str(option).strip() for option in options_raw if str(option).strip()]
    if len(options) < 2:
        return None
    q_type = "multiple" if str(q_payload.get("type") or "single").strip().lower() == "multiple" else "single"
    try:
        time_limit = int(q_payload.get("time_limit") or 30)
    except (TypeError, ValueError):
        time_limit = 30
    time_limit = max(5, min(600, time_limit))
    return {
        "title": f"Question {question_index}",
        "question": question_text,
        "options": options,
        "correct": [-1],
        "type": q_type,
        "time_limit": time_limit,
        "explanation": "",
        "imposters": [],
    }


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
    connected_players: list[dict[str, str]] = []
    known_connected: set[tuple[str, str]] = set()
    resolved_player_role = (player_role or "participant").lower()
    in_quiz = False
    stop = asyncio.Event()
    current_question_index: int | None = None
    current_total_questions = 0
    current_mode = room_mode
    current_phase = ""
    pending_question_payload: dict[str, object] | None = None
    prompted_rounds: set[tuple[int, int, int]] = set()
    current_progress_round: tuple[int, int, int] | None = None
    seen_progress: set[tuple[tuple[int, int, int], int, int, bool]] = set()
    local_chat_echoes: list[str] = []
    transcript: list[dict[str, object]] = []

    def _stdin_is_tty() -> bool:
        try:
            return bool(sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty())
        except Exception:
            return False

    def _print_lobby_prompt() -> None:
        return None

    def _clear_lobby_prompt() -> None:
        return None

    def _clear_typed_input_line() -> None:
        if _stdin_is_tty() and sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            print("\033[1A\033[2K", end="", flush=True)

    def _normalize_lobby_input(raw_text: str) -> str:
        text = raw_text.strip()
        own_prompt = f"[{display_name}]"
        if text == own_prompt:
            return ""
        if text.startswith(own_prompt):
            return text[len(own_prompt):].strip()
        return text

    def _record(event_type: str, payload: dict[str, object]) -> None:
        transcript.append(
            {
                "type": event_type,
                "ts": time.time(),
                "payload": payload,
            }
        )

    async def _send_room_event(event_type: str, payload: dict[str, object], *, silent: bool = False) -> bool:
        try:
            await ws.send(json.dumps({"type": event_type, "payload": payload}))
            return True
        except Exception:
            if not silent and not stop.is_set():
                print("Disconnected from room server.")
            stop.set()
            return False

    async def _prompt_and_submit_answer(
        *,
        q_payload: dict[str, object],
        question_index: int,
        total_questions: int,
        deadline_epoch: float | None,
        retry_count: int = 0,
    ) -> None:
        nonlocal in_quiz
        round_key = (question_index, int(deadline_epoch or 0), retry_count)
        if round_key in prompted_rounds:
            return
        prompted_rounds.add(round_key)

        q = _room_runtime_question_payload(q_payload, question_index + 1)
        if q is None:
            print("Skipping invalid room question from server (needs text and at least 2 options).")
            _record(
                "invalid_question_payload",
                {"question_index": question_index, "payload": q_payload},
            )
            return
        in_quiz = True
        print(f"Question {question_index + 1}/{max(1, total_questions)} is live.")
        try:
            _perfect, answers, _imposters, _grading = await ask_question(
                q,
                theme,
                question_index=question_index + 1,
                total_questions=max(1, total_questions),
                no_color=no_color,
                compact=False,
                full_screen=full_screen,
                show_feedback=False,
            )
        except KeyboardInterrupt:
            await _send_room_event("leave_room", {}, silent=True)
            render_exit_message("Left room. See you next time.", no_color=no_color)
            stop.set()
            return
        except Exception as exc:
            print(f"Could not open room question: {exc}")
            _record(
                "question_render_error",
                {"question_index": question_index, "error": str(exc)},
            )
            return
        finally:
            in_quiz = False

        if _grading.get("quit_requested"):
            print("Leaving room...")
            await _send_room_event("leave_room", {}, silent=True)
            render_exit_message("Left room. See you next time.", no_color=no_color)
            stop.set()
            return

        if answers:
            sent = await _send_room_event(
                "submit_answer",
                {"question_index": question_index, "answers": answers},
            )
            if not sent:
                return
            print("Answer sent. Waiting for others...")
        else:
            print("Time is up. Waiting for result...")
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
        if is_host:
            print("Type /start when you are ready. Type /next after each result.")
        print("Chat: send a message to your peers, or type /help for commands.")
        print("Commands: /start (host), /next (host), /players, /help, /quit")
        if not await _send_room_event("ready_toggle", {"ready": True}):
            return 1
        _print_lobby_prompt()

        async def recv_loop():
            nonlocal connected_players
            nonlocal known_connected
            nonlocal resolved_player_role
            nonlocal in_quiz
            nonlocal current_question_index
            nonlocal current_total_questions
            nonlocal current_mode
            nonlocal current_phase
            nonlocal pending_question_payload
            nonlocal current_progress_round
            nonlocal seen_progress
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
                    _clear_lobby_prompt()
                    sender = payload.get("from", "Unknown")
                    text = payload.get("text", "")
                    sender_role = str(payload.get("from_role") or "participant")
                    if str(sender) == display_name and str(text) in local_chat_echoes:
                        local_chat_echoes.remove(str(text))
                        _record("chat_message", {"from": str(sender), "from_role": sender_role, "text": str(text)})
                        continue
                    print(f"[{sender}] {text}")
                    _record("chat_message", {"from": str(sender), "from_role": sender_role, "text": str(text)})
                    _print_lobby_prompt()
                    continue

                if etype in {"connected", "lobby_update"}:
                    _clear_lobby_prompt()
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
                    _print_lobby_prompt()
                    continue

                if etype == "error":
                    _clear_lobby_prompt()
                    print(f"Server: {payload.get('message', 'Unknown error')}")
                    _record("error", {"message": str(payload.get("message", "Unknown error"))})
                    continue

                if etype == "game_started":
                    _clear_lobby_prompt()
                    in_quiz = False
                    print("Game started.")
                    _record("game_started", {"mode": room_mode})
                    continue

                if etype == "awaiting_next":
                    _clear_lobby_prompt()
                    in_quiz = False
                    finished_after_continue = bool(payload.get("finished_after_continue", False))
                    if is_host:
                        if finished_after_continue:
                            print("Review final results. Type /next to finish.")
                        else:
                            next_index = int(payload.get("next_question_index") or 0)
                            total_questions = int(payload.get("total_questions") or 0)
                            if total_questions:
                                print(f"Review results. Type /next for question {next_index + 1}/{total_questions}.")
                            else:
                                print("Review results. Type /next to continue.")
                    else:
                        action = "finish" if finished_after_continue else "continue"
                        print(f"Waiting for host to {action}...")
                    _record("awaiting_next", {"payload": payload})
                    _print_lobby_prompt()
                    continue

                if etype == "game_starting":
                    _clear_lobby_prompt()
                    raw_seconds = payload.get("countdown_seconds")
                    seconds = 5 if raw_seconds is None else int(raw_seconds)
                    seconds = max(0, min(30, seconds))
                    in_quiz = True
                    try:
                        if seconds:
                            for remaining in range(seconds, 0, -1):
                                print(f"\rQuiz starts in {remaining}...", end="", flush=True)
                                await asyncio.sleep(1)
                            print("\rQuiz starts now.        ")
                        else:
                            print("Quiz starts now.")
                    finally:
                        in_quiz = False
                    _record("game_starting", {"seconds": seconds})
                    continue

                if etype == "answer_progress":
                    _clear_lobby_prompt()
                    qidx = int(payload.get("question_index", current_question_index or 0))
                    submitted = int(payload.get("submitted") or 0)
                    total = int(payload.get("total") or 0)
                    all_submitted = bool(payload.get("all_submitted", False))
                    round_key = current_progress_round if current_progress_round and current_progress_round[0] == qidx else (qidx, 0, 0)
                    progress_key = (round_key, submitted, total, all_submitted)
                    if progress_key in seen_progress:
                        continue
                    seen_progress.add(progress_key)
                    if all_submitted:
                        print("All answers submitted. Showing result...")
                    elif total > 0:
                        remaining = int(payload.get("remaining") or max(0, total - submitted))
                        print(f"Submitted {submitted}/{total}. Waiting for {remaining} more...")
                    _record(
                        "answer_progress",
                        {
                            "question_index": qidx,
                            "submitted": submitted,
                            "total": total,
                            "all_submitted": all_submitted,
                        },
                    )
                    continue

                if etype == "question":
                    _clear_lobby_prompt()
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
                    retry_count = int(payload.get("retry_count") or 0)
                    current_progress_round = (current_question_index, int(float(deadline_epoch or 0)), retry_count)
                    seen_progress.clear()
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
                        retry_count=retry_count,
                    )
                    continue

                if etype == "phase_changed":
                    _clear_lobby_prompt()
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
                        retry_count = int(payload.get("retry_count") or 0)
                        current_progress_round = (qidx, int(float(payload.get("deadline_epoch") or 0)), retry_count)
                        seen_progress.clear()
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
                                retry_count=retry_count,
                            )
                        continue

                if etype == "round_result":
                    _clear_lobby_prompt()
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
                    _clear_lobby_prompt()
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
                    _clear_lobby_prompt()
                    print("")
                    print("Scoreboard:")
                    players = payload.get("players", [])
                    if isinstance(players, list):
                        for row in players:
                            print(f"  - {row.get('name', 'Unknown')}: {row.get('score', 0)}")
                    _record("scoreboard", {"payload": payload})
                    continue

                if etype == "game_finished":
                    _clear_lobby_prompt()
                    print("")
                    reason = payload.get("reason")
                    if reason:
                        print("Game finished.")
                        print(f"Reason: {reason}")
                    else:
                        players = payload.get("players", [])
                        if isinstance(players, list) and players:
                            await _room_final_results_countdown()
                            print("")
                            print(_room_final_podium(players))
                        else:
                            print("Game finished.")
                            score_payload = payload.get("final_score")
                            if isinstance(score_payload, int):
                                print(f"Final score: {score_payload}%")
                    _record("game_finished", {"payload": payload})
                    stop.set()
                    return

        recv_task = asyncio.create_task(recv_loop())
        try:
            while not stop.is_set():
                if in_quiz:
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
                    text = _normalize_lobby_input(line)

                if not text:
                    _print_lobby_prompt()
                    continue
                if text == "/quit":
                    _clear_typed_input_line()
                    await _send_room_event("leave_room", {}, silent=True)
                    stop.set()
                    break
                if text == "/players":
                    _clear_typed_input_line()
                    if connected_players:
                        labels = [_room_player_label(row["name"], row["role"]) for row in connected_players]
                        print("Connected: " + ", ".join(labels))
                    else:
                        print("No connected players shown yet.")
                    _print_lobby_prompt()
                    continue
                if text == "/help":
                    _clear_typed_input_line()
                    print("Commands: /start (host), /next (host), /players, /help, /quit")
                    _print_lobby_prompt()
                    continue
                if text == "/start":
                    _clear_typed_input_line()
                    if not is_host:
                        print("Only the room host can start.")
                        _print_lobby_prompt()
                        continue
                    if not await _send_room_event("ready_toggle", {"ready": True}):
                        break
                    await asyncio.sleep(0.15)
                    if not await _send_room_event("start_game", {}):
                        break
                    print("Start requested...")
                    continue
                if text == "/next":
                    _clear_typed_input_line()
                    if not is_host:
                        print("Only the room host can continue.")
                        _print_lobby_prompt()
                        continue
                    if not await _send_room_event("next_question", {}):
                        break
                    print("Continuing...")
                    continue
                local_chat_echoes.append(text)
                _clear_typed_input_line()
                print(f"[{display_name}] {text}")
                if not await _send_room_event("chat_message", {"text": text}):
                    break
                _print_lobby_prompt()
        except KeyboardInterrupt:
            await _send_room_event("leave_room", {}, silent=True)
            render_exit_message("Left room. See you next time.", no_color=no_color)
            stop.set()
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
    return 0


def run_room_command(args: argparse.Namespace) -> int:
    no_color = is_no_color_requested(args.no_color)
    theme_name = args.theme
    requested_role = str(getattr(args, "role", "") or "").strip().lower()
    if requested_role and requested_role not in {"teacher", "student"}:
        raise RuntimeError("Invalid room role. Use teacher or student.")
    start_clean_screen()
    print(LOGO)

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
        quiz_path = str(args.quiz or "").strip()
        if not quiz_path:
            quiz_path = _room_prompt_quiz_file()
        auto_room_name = not requested_name.strip()
        room_name = _room_validate_name(requested_name) if requested_name.strip() else _room_generate_name()
        quiz_title, questions = _room_load_quiz_payload(quiz_path)
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
        token_required = bool(created.get("token_required", token_required))
        room_token = str(created.get("room_token") or "").strip()
        role_label = str(created.get("host_role") or host_role or "").strip()
        if token_required and room_token:
            share_command = (
                f'quizmd room --join "{created.get("room_name", room_name)}" '
                f'--token "{room_token}" --name "tom"'
            )
        else:
            share_command = (
                f'quizmd room --join "{created.get("room_name", room_name)}" '
                f'--name "tom"'
            )
        render_room_created_screen(
            room_name=str(created.get("room_name") or room_name),
            host_name=str(created.get("host_display_name") or host_name),
            mode=str(created.get("mode") or mode),
            quiz_title=quiz_title,
            question_count=len(questions),
            join_command=share_command,
            token_required=token_required,
            room_token=room_token,
            host_role="",
            theme_name=theme_name,
            no_color=no_color,
        )
        if not quiz_path:
            print("Tip: use --quiz filename to load your quiz.")
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
    if detected_mode and join_role:
        # Keep compatibility with legacy callers passing a room role.
        print("Role flag ignored: rooms use participant role.")
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


def _alien_ship_sprite(mode: str) -> str:
    return _alien_ship_art(mode)[-1]



def _alien_ship_art(mode: str) -> tuple[str, ...]:
    """Return compact ship art (top-to-bottom)."""
    return {
        "single": ("|-o-|",),
        "double": ("|--o--|",),
        "triple": ("|---o---|",),
    }.get(mode, ("|-o-|",))


def _alien_sprite_pack(size: str) -> tuple[tuple[tuple[str, str, str], tuple[str, str, str]], ...]:
    if size == "small":
        return (
            (
                (" /^\\ ", "|o|", " \\v/ "),
                (" /^\\ ", "|o|", " \\^/ "),
            ),
            (
                (" /W\\ ", "|v|", " \\-/ "),
                (" /W\\ ", "|^|", " \\-/ "),
            ),
            (
                (" .^. ", "(o)", " =_= "),
                (" .^. ", "(o)", " =_= "),
            ),
            (
                (" /^\\ ", "|O|", " \\v/ "),
                (" /^\\ ", "|O|", " \\^/ "),
            ),
        )
    return (
        (
            (" /-\\ ", "|o^o|", "\\-v-/"),
            (" /-\\ ", "|o o|", "\\-^-/"),
        ),
        (
            (" /W\\ ", "|v v|", "\\-/-/"),
            (" /W\\ ", "|^^^|", "\\-\\-/"),
        ),
        (
            (" .-. ", "(o^o)", " =_= "),
            (" .-. ", "(o o)", " =_= "),
        ),
        (
            (" /-\\ ", "|O^O|", "\\-v-/"),
            (" /-\\ ", "|O O|", "\\-^-/"),
        ),
    )


def _alien_sprite_size_for_level(level: int) -> str:
    # Start with larger sprites, then tighten visual density as levels climb.
    return "small" if level >= 5 else "large"


def _alien_sprite_lines(row: int, frame: int, level: int = 1) -> tuple[str, str, str]:
    sprites = _alien_sprite_pack(_alien_sprite_size_for_level(level))
    row_sprites = sprites[row % len(sprites)]
    return row_sprites[frame % len(row_sprites)]


def _alien_sprite_dimensions(level: int = 1) -> tuple[int, int]:
    lines = _alien_sprite_lines(0, 0, level=level)
    return max(len(line) for line in lines), len(lines)


def _alien_wave_shape(level: int, board_w: int) -> tuple[int, int]:
    # Progression:
    # - Add one alien column per level.
    # - Add one extra row every 3 levels.
    desired_cols = 8 + max(0, level - 1)
    desired_rows = 4 + (max(0, level - 1) // 3)

    # Keep formations renderable on smaller terminals.
    safe_cols_max = max(6, min(18, (board_w // 6)))
    cols = max(6, min(desired_cols, safe_cols_max))
    rows = max(4, min(desired_rows, 7))
    return cols, rows


def _alien_attack_profile(mode: str, difficulty: str) -> dict:
    """Return movement/timing profile for Alien Attack mode+difficulty."""
    mode_name = (mode or "single").strip().lower()
    difficulty_name = (difficulty or "normal").strip().lower()
    mode_speed = {
        "single": 0.38,
        "double": 0.33,
        "triple": 0.29,
    }
    mode_bombs = {
        "single": 0.95,
        "double": 0.82,
        "triple": 0.72,
    }
    if difficulty_name == "inferno":
        diff_mult = 0.68
    elif difficulty_name == "hard":
        diff_mult = 0.78
    else:
        diff_mult = 1.0
    bomb_interval = mode_bombs.get(mode_name, mode_bombs["single"]) * diff_mult
    if difficulty_name == "inferno":
        # Inferno intentionally floods the board: each alien drops every second.
        bomb_interval = 1.0
    return {
        "mode": mode_name,
        "difficulty": difficulty_name,
        "ship_art": _alien_ship_art(mode_name),
        "ship_sprite": _alien_ship_sprite(mode_name),
        "alien_move_interval": mode_speed.get(mode_name, mode_speed["single"]) * diff_mult,
        "bomb_interval": bomb_interval,
        "lives": 1,
        "max_bullets": 2 if difficulty_name == "normal" else 1,
    }


def _alien_score_for_hit(flight_time: float, level: int) -> int:
    base = 100 + max(0, level - 1) * 20
    speed_bonus = max(0, int((1.4 - max(0.0, flight_time)) * 70))
    return base + speed_bonus


def _alien_clamp(value: int, minimum: int, maximum: int) -> int:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _alien_apply_player_motion(state: dict, ship_sprite: str, dt: float, now: float) -> None:
    """Apply smooth player movement based on short-lived direction intent."""
    if dt <= 0:
        return
    if state.get("phase") != "running" or state.get("too_small"):
        return
    move_dir = int(state.get("move_dir", 0))
    if move_dir == 0:
        return
    hold_until = float(state.get("move_hold_until", 0.0))
    if now > hold_until:
        state["move_dir"] = 0
        return
    speed_cps = float(state.get("move_speed_cps", 18.0))
    min_x = len(ship_sprite) // 2
    max_x = int(state.get("board_w", 80)) - 1 - min_x
    if max_x < min_x:
        return
    player_x_float = float(state.get("player_x_float", state.get("player_x", 0)))
    player_x_float += move_dir * speed_cps * dt
    player_x_float = float(max(min_x, min(max_x, player_x_float)))
    state["player_x_float"] = player_x_float
    state["player_x"] = int(round(player_x_float))


def _alien_make_shields(board_w: int, board_h: int) -> set[tuple[int, int]]:
    shields: set[tuple[int, int]] = set()
    pattern = [
        " ##### ",
        "#######",
        "##   ##",
        "#######",
    ]
    if board_w < 36 or board_h < 12:
        return shields
    ship_y = board_h - 1
    # Keep shields close to the ship (lower on screen), while still leaving
    # enough room so bullets and bombs interact with them clearly.
    gap_from_ship = 3 if board_h <= 30 else min(6, max(3, board_h // 8))
    y0 = ship_y - gap_from_ship - (len(pattern) - 1)
    y0 = max(3, y0)
    anchors = [board_w // 4, board_w // 2, (board_w * 3) // 4]
    bunker_half = len(pattern[0]) // 2
    for anchor in anchors:
        x0 = anchor - bunker_half
        for dy, row in enumerate(pattern):
            for dx, ch in enumerate(row):
                if ch == "#":
                    x = x0 + dx
                    y = y0 + dy
                    if 0 <= x < board_w and 0 <= y < board_h:
                        shields.add((x, y))
    return shields


def _alien_spawn_wave(state: dict) -> None:
    board_w = state["board_w"]
    board_h = state["board_h"]
    level = int(state.get("level", 1))
    sprite_w, sprite_h = _alien_sprite_dimensions(level=level)
    cols, rows = _alien_wave_shape(level, board_w)
    spacing = max(sprite_w + 1, min(9, (board_w - sprite_w) // max(1, cols - 1)))
    formation_width = max(1, (cols - 1) * spacing + sprite_w)
    offset_x = max(0, (board_w - formation_width) // 2)
    state["alien_rows"] = rows
    state["alien_cols"] = cols
    state["alien_spacing"] = spacing
    state["alien_row_spacing"] = sprite_h + 1
    state["alien_sprite_w"] = sprite_w
    state["alien_sprite_h"] = sprite_h
    state["alien_offset_x"] = offset_x
    state["alien_offset_y"] = 2
    state["alien_dir"] = 1
    state["alien_anim_frame"] = 0
    state["aliens_alive"] = {(r, c) for r in range(rows) for c in range(cols)}
    state["bullets"] = []
    state["bombs"] = []
    state["shields"] = _alien_make_shields(board_w, board_h)
    profile = state["profile"]
    state["alien_move_interval"] = max(
        0.08,
        profile["alien_move_interval"] * (0.93 ** max(0, state["level"] - 1)),
    )
    state["bomb_interval"] = max(
        0.14,
        profile["bomb_interval"] * (0.95 ** max(0, state["level"] - 1)),
    )
    now = time.monotonic()
    state["next_alien_move"] = now + state["alien_move_interval"]
    state["next_bomb_drop"] = now + random.uniform(0.2, state["bomb_interval"])


def _alien_ship_range(ship_x: int, ship_sprite: str) -> tuple[int, int]:
    left = ship_x - (len(ship_sprite) // 2)
    return left, left + len(ship_sprite) - 1


def _alien_ship_cells(ship_x: int, ship_art: tuple[str, ...], ship_base_y: int) -> dict[tuple[int, int], str]:
    cells: dict[tuple[int, int], str] = {}
    for offset, line in enumerate(reversed(ship_art)):
        y = ship_base_y - offset
        left = ship_x - (len(line) // 2)
        for idx, ch in enumerate(line):
            if ch == " ":
                continue
            cells[(left + idx, y)] = ch
    return cells


def _alien_positions(state: dict) -> dict[tuple[int, int], tuple[int, int]]:
    pos: dict[tuple[int, int], tuple[int, int]] = {}
    row_spacing = int(state.get("alien_row_spacing") or 4)
    anim_frame = int(state.get("alien_anim_frame") or 0)
    level = int(state.get("level", 1))
    for row, col in state["aliens_alive"]:
        x = state["alien_offset_x"] + col * state["alien_spacing"]
        y = state["alien_offset_y"] + row * row_spacing
        for dy, line in enumerate(_alien_sprite_lines(row, anim_frame, level=level)):
            for dx, ch in enumerate(line):
                if ch == " ":
                    continue
                pos[(x + dx, y + dy)] = (row, col)
    return pos


async def _run_alien_attack(mode: str, difficulty: str, no_color: bool = False) -> int:
    try:
        from prompt_toolkit import Application
        from prompt_toolkit.formatted_text import HTML as PromptHTML
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Alien Attack requires prompt_toolkit. Install dependencies from requirements.txt."
        ) from exc
    active_theme = select_theme("auto")
    palette = _prompt_ui_palette(active_theme)

    mode_options: list[tuple[str, str, str]] = [
        ("single", "Single", "|-o-|   small ship (harder to hit)."),
        ("double", "Double", "|--o--| medium ship."),
        ("triple", "Triple", "|---o---| wide ship (easier target)."),
    ]
    difficulty_options: list[tuple[str, str, str]] = [
        ("normal", "Normal", "Balanced speed and bomb pressure."),
        ("hard", "Hard", "Faster waves and denser bombs."),
        ("inferno", "Inferno", "Every alien drops bombs every second."),
    ]
    shooting_options: list[tuple[str, str, str, int]] = [
        ("unlimited", "Unlimited", "No bullet cap.", 999),
        ("two", "2 at a time", "Two active bullets max.", 2),
        ("one", "1 at a time", "Single active bullet max.", 1),
    ]
    profile = _alien_attack_profile(mode, difficulty)
    initial_mode_idx = 0
    initial_diff_idx = 0
    for idx, option in enumerate(mode_options):
        value = option[0]
        if value == profile["mode"]:
            initial_mode_idx = idx
            break
    for idx, option in enumerate(difficulty_options):
        value = option[0]
        if value == profile["difficulty"]:
            initial_diff_idx = idx
            break

    # Setup selector stays in the current terminal (no clear/full-screen yet).
    if sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
        setup_state = {
            "stage": 0,  # 0=mode, 1=difficulty, 2=shooting
            "mode_idx": initial_mode_idx,
            "diff_idx": initial_diff_idx,
            "shoot_idx": 1 if profile.get("max_bullets", 1) == 2 else 2,
        }
        if profile.get("max_bullets", 1) >= 999:
            setup_state["shoot_idx"] = 0

        def _setup_style(text: str, fg: str = "", bg: str = "") -> str:
            escaped = html.escape(text)
            if no_color:
                return escaped
            style_parts = []
            if fg:
                style_parts.append(f"fg='{fg}'")
            if bg:
                style_parts.append(f"bg='{bg}'")
            if not style_parts:
                return escaped
            return f"<style {' '.join(style_parts)}>{escaped}</style>"

        def render_setup() -> str | PromptHTML:
            stage_mode = setup_state["stage"] == 0
            stage_difficulty = setup_state["stage"] == 1
            stage_shooting = setup_state["stage"] == 2
            mode_value, mode_label, mode_desc = mode_options[setup_state["mode_idx"]]
            diff_value, diff_label, diff_desc = difficulty_options[setup_state["diff_idx"]]
            _shoot_value, shoot_label, shoot_desc, _shoot_limit = shooting_options[setup_state["shoot_idx"]]

            lines: list[str] = [
                _setup_style("ALIEN ATTACK", fg=palette["logo"]),
                "",
                _setup_style("Rules", fg=palette["title"]),
                _setup_style("- Clear waves from level 1 to level 10."),
                _setup_style("- Move with ←/→, shoot with Space, pause with P, quit with Q."),
                _setup_style("- One bomb hit ends the run. Faster hits earn more points."),
                _setup_style("- Each level adds one column; every 3 levels adds one row."),
                "",
                _setup_style(
                    f"Mode: {mode_label} ({mode_desc})",
                    fg=palette["warning"] if stage_mode else palette["body"],
                ),
                _setup_style(
                    f"Difficulty: {diff_label} ({diff_desc})",
                    fg=palette["warning"] if stage_difficulty else palette["body"],
                ),
                _setup_style(
                    f"Shooting: {shoot_label} ({shoot_desc})",
                    fg=palette["warning"] if stage_shooting else palette["body"],
                ),
                "",
                _setup_style("Mode (ship size)", fg=palette["accent"]),
            ]
            for idx, (_value, label, desc) in enumerate(mode_options):
                selected = idx == setup_state["mode_idx"]
                pointer = "*" if selected else " "
                fg = palette["selected_fg"] if (selected and stage_mode) else (palette["accent"] if selected else palette["body"])
                bg = palette["selected_bg"] if (selected and stage_mode) else ""
                lines.append(_setup_style(f"{pointer} {label:<8} {desc}", fg=fg, bg=bg))

            lines.extend(["", _setup_style("Difficulty", fg=palette["secondary"])])
            for idx, (_value, label, desc) in enumerate(difficulty_options):
                selected = idx == setup_state["diff_idx"]
                pointer = "*" if selected else " "
                fg = palette["selected_fg"] if (selected and stage_difficulty) else ("ansimagenta" if selected else palette["body"])
                bg = palette["selected_bg"] if (selected and stage_difficulty) else ""
                lines.append(_setup_style(f"{pointer} {label:<8} {desc}", fg=fg, bg=bg))

            lines.extend(["", _setup_style("Shooting", fg=palette["success"])])
            for idx, (_value, label, desc, _cap) in enumerate(shooting_options):
                selected = idx == setup_state["shoot_idx"]
                pointer = "*" if selected else " "
                fg = palette["selected_fg"] if (selected and stage_shooting) else (palette["success"] if selected else palette["body"])
                bg = palette["selected_bg"] if (selected and stage_shooting) else ""
                lines.append(_setup_style(f"{pointer} {label:<10} {desc}", fg=fg, bg=bg))

            lines.append("")
            if stage_mode:
                lines.append(_setup_style("Use ↑/↓ to choose mode. Enter to continue.", fg=palette["warning"]))
            elif stage_difficulty:
                lines.append(_setup_style("Use ↑/↓ to choose difficulty. Enter to continue.", fg=palette["warning"]))
            else:
                lines.append(_setup_style("Use ↑/↓ to choose shooting cap. Enter to start game.", fg=palette["warning"]))
            lines.append(_setup_style("Esc/Q to cancel."))

            markup = "\n".join(lines)
            if no_color:
                return re.sub(r"<[^>]+>", "", markup)
            return PromptHTML(markup)

        setup_control = FormattedTextControl(text=render_setup())
        setup_window = Window(content=setup_control, wrap_lines=True, always_hide_cursor=True)
        setup_kb = KeyBindings()

        def refresh_setup() -> None:
            setup_control.text = render_setup()

        @setup_kb.add("up")
        def _(_event):
            if setup_state["stage"] == 0:
                setup_state["mode_idx"] = (setup_state["mode_idx"] - 1) % len(mode_options)
            elif setup_state["stage"] == 1:
                setup_state["diff_idx"] = (setup_state["diff_idx"] - 1) % len(difficulty_options)
            else:
                setup_state["shoot_idx"] = (setup_state["shoot_idx"] - 1) % len(shooting_options)
            refresh_setup()

        @setup_kb.add("down")
        def _(_event):
            if setup_state["stage"] == 0:
                setup_state["mode_idx"] = (setup_state["mode_idx"] + 1) % len(mode_options)
            elif setup_state["stage"] == 1:
                setup_state["diff_idx"] = (setup_state["diff_idx"] + 1) % len(difficulty_options)
            else:
                setup_state["shoot_idx"] = (setup_state["shoot_idx"] + 1) % len(shooting_options)
            refresh_setup()

        @setup_kb.add("left")
        @setup_kb.add("right")
        @setup_kb.add("tab")
        def _(_event):
            setup_state["stage"] = (setup_state["stage"] + 1) % 3
            refresh_setup()

        @setup_kb.add("enter")
        def _(event):
            if setup_state["stage"] < 2:
                setup_state["stage"] += 1
                refresh_setup()
                return
            event.app.exit(
                result=(
                    setup_state["mode_idx"],
                    setup_state["diff_idx"],
                    setup_state["shoot_idx"],
                )
            )

        @setup_kb.add("q")
        @setup_kb.add("escape")
        def _(event):
            event.app.exit(result=None)

        @setup_kb.add("c-c")
        def _(event):
            event.app.exit(exception=KeyboardInterrupt())

        setup_app = Application(
            layout=Layout(HSplit([setup_window])),
            key_bindings=setup_kb,
            full_screen=False,
        )
        try:
            selected = await setup_app.run_async()
        finally:
            ensure_terminal_cursor_visible()
        if selected is None:
            return 0
        initial_mode_idx, initial_diff_idx, initial_shoot_idx = selected
        profile = _alien_attack_profile(
            mode_options[initial_mode_idx][0],
            difficulty_options[initial_diff_idx][0],
        )
        profile["max_bullets"] = shooting_options[initial_shoot_idx][3]
    app = None
    state = {
        "profile": profile,
        "phase": "intro",
        "board_w": 80,
        "board_h": 24,
        "score": 0,
        "lives": profile["lives"],
        "level": 1,
        "player_x": 40,
        "player_x_float": 40.0,
        "aliens_alive": set(),
        "alien_rows": 0,
        "alien_cols": 0,
        "alien_spacing": 5,
        "alien_row_spacing": 4,
        "alien_sprite_w": 5,
        "alien_sprite_h": 3,
        "alien_anim_frame": 0,
        "alien_offset_x": 0,
        "alien_offset_y": 2,
        "alien_dir": 1,
        "alien_move_interval": profile["alien_move_interval"],
        "bomb_interval": profile["bomb_interval"],
        "next_alien_move": 0.0,
        "next_bomb_drop": 0.0,
        "bullets": [],
        "bombs": [],
        "shields": set(),
        "too_small": False,
        "message": "",
        "max_level": 10,
        "confetti": [],
        "next_confetti_spawn": 0.0,
        "intro_field": 0,
        "intro_mode_idx": initial_mode_idx,
        "intro_diff_idx": initial_diff_idx,
        "shooting_cap": int(profile.get("max_bullets", 1)),
        "move_dir": 0,
        "move_hold_until": 0.0,
        "move_speed_cps": 22.0,
        "move_impulse_seconds": 0.2,
        "last_tick_time": None,
    }

    def _escape(text: str) -> str:
        return html.escape(text)

    def _style(text: str, fg: str = "", bg: str = "") -> str:
        if no_color or not text:
            return _escape(text)
        style_parts = []
        if fg:
            style_parts.append(f"fg='{fg}'")
        if bg:
            style_parts.append(f"bg='{bg}'")
        if not style_parts:
            return _escape(text)
        return f"<style {' '.join(style_parts)}>{_escape(text)}</style>"

    def sync_board_size() -> None:
        try:
            if app is None:
                raise RuntimeError("app not ready")
            size = app.output.get_size()
            columns = int(size.columns)
            rows = int(size.rows)
        except Exception:
            columns = get_terminal_columns(default=100)
            rows = 36
        board_w = max(20, columns - 2)
        board_h = max(8, rows - 6)
        state["too_small"] = board_w < 54 or board_h < 20
        if state["too_small"]:
            state["board_w"] = board_w
            state["board_h"] = board_h
            return
        if board_w == state["board_w"] and board_h == state["board_h"]:
            return
        state["board_w"] = board_w
        state["board_h"] = board_h
        ship_left, ship_right = _alien_ship_range(state["player_x"], profile["ship_sprite"])
        shift = 0
        if ship_left < 0:
            shift = -ship_left
        elif ship_right >= board_w:
            shift = board_w - 1 - ship_right
        state["player_x"] += shift
        state["player_x"] = _alien_clamp(
            state["player_x"],
            len(profile["ship_sprite"]) // 2,
            board_w - 1 - (len(profile["ship_sprite"]) // 2),
        )
        state["player_x_float"] = float(state["player_x"])
        state["bullets"] = [b for b in state["bullets"] if 0 <= b["x"] < board_w and 0 <= b["y"] < board_h]
        state["bombs"] = [b for b in state["bombs"] if 0 <= b["x"] < board_w and 0 <= b["y"] < board_h]
        state["shields"] = {(x, y) for (x, y) in state["shields"] if 0 <= x < board_w and 0 <= y < board_h}
        if state["phase"] == "running" and not state["aliens_alive"]:
            _alien_spawn_wave(state)

    def apply_intro_profile() -> None:
        nonlocal profile
        mode_value = mode_options[state["intro_mode_idx"]][0]
        difficulty_value = difficulty_options[state["intro_diff_idx"]][0]
        profile = _alien_attack_profile(mode_value, difficulty_value)
        profile["max_bullets"] = int(state.get("shooting_cap", profile.get("max_bullets", 1)))
        state["profile"] = profile
        state["lives"] = profile["lives"]

    def reset_game() -> None:
        apply_intro_profile()
        state["score"] = 0
        state["level"] = 1
        state["lives"] = profile["lives"]
        state["message"] = ""
        state["phase"] = "running"
        state["confetti"] = []
        state["next_confetti_spawn"] = 0.0
        sync_board_size()
        state["player_x"] = state["board_w"] // 2
        state["player_x_float"] = float(state["player_x"])
        state["move_dir"] = 0
        state["move_hold_until"] = 0.0
        state["last_tick_time"] = None
        _alien_spawn_wave(state)

    def new_level() -> None:
        state["level"] += 1
        state["message"] = f"Level {state['level']} — harder wave!"
        _alien_spawn_wave(state)

    def start_victory(now: float) -> None:
        state["phase"] = "victory"
        state["message"] = "Level 10 cleared! You won!"
        state["confetti"] = []
        state["next_confetti_spawn"] = now

    def draw_overlay(
        grid: list[list[str]],
        styles: list[list[str | None]],
        text: str,
        fg: str = "",
    ) -> None:
        if not text:
            return
        y = max(0, state["board_h"] // 2)
        x = max(0, (state["board_w"] - len(text)) // 2)
        for idx, ch in enumerate(text):
            cx = x + idx
            if 0 <= cx < state["board_w"]:
                grid[y][cx] = ch
                styles[y][cx] = fg

    def render() -> str | PromptHTML:
        sync_board_size()
        if state["phase"] == "intro":
            selected_mode = mode_options[state["intro_mode_idx"]][1]
            selected_difficulty = difficulty_options[state["intro_diff_idx"]][1]
            active_mode = state["intro_field"] == 0
            active_difficulty = state["intro_field"] == 1
            intro_lines = [
                _style("ALIEN ATTACK", fg=palette["logo"]),
                "",
                _style(
                    f"Mode: {selected_mode}    Difficulty: {selected_difficulty}",
                    fg=palette["body"],
                ),
                _style(
                    f"{'▶' if active_mode else ' '} Mode: {selected_mode}",
                    fg=palette["warning"] if active_mode else palette["body"],
                ),
                _style(
                    f"{'▶' if active_difficulty else ' '} Difficulty: {selected_difficulty}",
                    fg=palette["warning"] if active_difficulty else palette["body"],
                ),
                _style("Controls: ←/→ move, Space shoot, P pause, Q quit", fg=palette["body"]),
                _style("Intro: ↑/↓ choose field, ←/→ change value, Enter starts.", fg=palette["body"]),
                _style("Progression: +1 alien column per level, +1 row every 3 levels.", fg=palette["body"]),
                _style("Clear up to level 10 to win. One bomb hit ends the run.", fg=palette["body"]),
                "",
                _style("Press Enter to start.", fg=palette["warning"]),
            ]
            text_out = "\n".join(intro_lines)
            return PromptHTML(text_out) if not no_color else "\n".join(
                re.sub(r"<[^>]+>", "", line)
                for line in intro_lines
            )

        if state["too_small"]:
            msg = "Resize terminal to at least 54x20. Press Q to quit."
            out = _style(msg, fg=palette["danger"])
            return PromptHTML(out) if not no_color else msg

        board_w = state["board_w"]
        board_h = state["board_h"]
        grid = [[" " for _ in range(board_w)] for _ in range(board_h)]
        styles: list[list[str | None]] = [[None for _ in range(board_w)] for _ in range(board_h)]

        # Aliens
        for row, col in state["aliens_alive"]:
            x0 = state["alien_offset_x"] + col * state["alien_spacing"]
            y0 = state["alien_offset_y"] + row * state["alien_row_spacing"]
            for dy, line in enumerate(
                _alien_sprite_lines(row, state["alien_anim_frame"], level=int(state.get("level", 1)))
            ):
                yy = y0 + dy
                if not (0 <= yy < board_h):
                    continue
                for dx, ch in enumerate(line):
                    if ch == " ":
                        continue
                    xx = x0 + dx
                    if 0 <= xx < board_w:
                        grid[yy][xx] = ch
                        styles[yy][xx] = palette["body"]

        # Bullets
        for bullet in state["bullets"]:
            x, y = bullet["x"], bullet["y"]
            if 0 <= x < board_w and 0 <= y < board_h:
                grid[y][x] = "|"
                styles[y][x] = palette["warning"]

        # Bombs
        for bomb in state["bombs"]:
            x, y = bomb["x"], bomb["y"]
            if 0 <= x < board_w and 0 <= y < board_h:
                grid[y][x] = "!"
                styles[y][x] = palette["danger"]

        # Shields (draw after projectiles so bunkers remain visible while intact)
        for x, y in state["shields"]:
            if 0 <= x < board_w and 0 <= y < board_h:
                grid[y][x] = "#"
                styles[y][x] = palette["success"]

        # Player ship
        ship_y = board_h - 1
        for (x, y), ch in _alien_ship_cells(state["player_x"], profile["ship_art"], ship_y).items():
            if 0 <= x < board_w and 0 <= y < board_h:
                grid[y][x] = ch
                styles[y][x] = palette["success"]

        # Confetti burst on win.
        if state["phase"] == "victory":
            for particle in state.get("confetti", []):
                x = int(particle.get("x", -1))
                y = int(particle.get("y", -1))
                if 0 <= x < board_w and 0 <= y < board_h:
                    grid[y][x] = str(particle.get("ch", "*"))[:1]
                    styles[y][x] = particle.get("color", palette["accent"])

        if state["phase"] == "paused":
            draw_overlay(grid, styles, "[ PAUSED ]", fg=palette["warning"])
        elif state["phase"] == "game_over":
            draw_overlay(grid, styles, "[ GAME OVER ] Press R to restart", fg=palette["danger"])
        elif state["phase"] == "victory":
            draw_overlay(grid, styles, "[ YOU WIN ] Press R to restart", fg=palette["success"])
        elif state["message"]:
            draw_overlay(grid, styles, state["message"], fg=palette["warning"])

        shots_label = "∞" if int(profile.get("max_bullets", 1)) >= 999 else str(int(profile.get("max_bullets", 1)))
        hud = (
            f"Score: {state['score']}  Lives: {state['lives']}  "
            f"Level: {state['level']}/{state['max_level']}  Mode: {profile['mode'].title()}  "
            f"Difficulty: {profile['difficulty'].title()}  Shots: {shots_label}"
        )
        border = "+" + "-" * board_w + "+"
        footer = "Controls: ←/→ move  Space shoot  P pause  Q quit"

        lines = [_style(hud, fg=palette["body"]), _style(border, fg=palette["body"])]
        for y in range(board_h):
            rendered_cells = []
            for x in range(board_w):
                ch = grid[y][x]
                st = styles[y][x]
                rendered_cells.append(_style(ch, fg=st or palette["body"]))
            lines.append(_style("|", fg=palette["body"]) + "".join(rendered_cells) + _style("|", fg=palette["body"]))
        lines.append(_style(border, fg=palette["body"]))
        lines.append(_style(footer, fg=palette["body"]))

        text_out = "\n".join(lines)
        return PromptHTML(text_out) if not no_color else re.sub(r"<[^>]+>", "", text_out)

    def update_running(now: float, dt: float) -> None:
        if state["phase"] == "victory":
            board_w = state["board_w"]
            board_h = state["board_h"]
            particles = state.get("confetti", [])
            for p in particles:
                p["y"] = float(p.get("y", 0.0)) + float(p.get("vy", 0.7)) * dt * 18.0
                p["x"] = float(p.get("x", 0.0)) + float(p.get("vx", 0.0)) * dt * 6.0
            state["confetti"] = [
                p for p in particles if 0 <= int(p.get("x", -1)) < board_w and int(p.get("y", -1)) < board_h
            ]
            if now >= float(state.get("next_confetti_spawn", 0.0)):
                colors = [palette["accent"], palette["secondary"], palette["warning"], palette["success"]]
                for _ in range(max(6, min(18, board_w // 8))):
                    state["confetti"].append(
                        {
                            "x": random.uniform(0, max(0, board_w - 1)),
                            "y": 0.0,
                            "vx": random.uniform(-1.2, 1.2),
                            "vy": random.uniform(0.6, 1.8),
                            "ch": random.choice(["*", "+", ".", "o", "•"]),
                            "color": random.choice(colors),
                        }
                    )
                state["next_confetti_spawn"] = now + 0.12
            return

        if state["phase"] != "running" or state["too_small"]:
            return

        board_w = state["board_w"]
        board_h = state["board_h"]
        _alien_apply_player_motion(state, profile["ship_sprite"], dt, now)

        # Move bullets up.
        for bullet in state["bullets"]:
            bullet["y"] -= 1
        state["bullets"] = [b for b in state["bullets"] if b["y"] >= 0]

        # Move bombs down.
        for bomb in state["bombs"]:
            bomb["y"] += 1
        state["bombs"] = [b for b in state["bombs"] if b["y"] < board_h]

        # Move alien formation.
        if now >= state["next_alien_move"] and state["aliens_alive"]:
            columns_alive = [col for (_row, col) in state["aliens_alive"]]
            if columns_alive:
                left_col = min(columns_alive)
                right_col = max(columns_alive)
                left_x = state["alien_offset_x"] + left_col * state["alien_spacing"]
                right_x = (
                    state["alien_offset_x"]
                    + right_col * state["alien_spacing"]
                    + state["alien_sprite_w"]
                    - 1
                )
                next_left = left_x + state["alien_dir"]
                next_right = right_x + state["alien_dir"]
                if next_left < 0 or next_right >= board_w:
                    state["alien_dir"] *= -1
                    state["alien_offset_y"] += 1
                    state["alien_move_interval"] = max(0.07, state["alien_move_interval"] * 0.985)
                else:
                    state["alien_offset_x"] += state["alien_dir"]
            state["alien_anim_frame"] = 1 - int(state.get("alien_anim_frame", 0))
            state["next_alien_move"] = now + state["alien_move_interval"]

        # Bomb spawn.
        if now >= state["next_bomb_drop"] and state["aliens_alive"]:
            bottom_by_col: dict[int, int] = {}
            for row, col in state["aliens_alive"]:
                if col not in bottom_by_col or row > bottom_by_col[col]:
                    bottom_by_col[col] = row
            if state["profile"]["difficulty"] == "inferno":
                for row, col in sorted(state["aliens_alive"]):
                    x = state["alien_offset_x"] + col * state["alien_spacing"] + (state["alien_sprite_w"] // 2)
                    y = state["alien_offset_y"] + row * state["alien_row_spacing"] + state["alien_sprite_h"]
                    if 0 <= x < board_w and 0 <= y < board_h:
                        state["bombs"].append({"x": x, "y": y})
                state["next_bomb_drop"] = now + 1.0
            else:
                if bottom_by_col:
                    col = random.choice(list(bottom_by_col.keys()))
                    row = bottom_by_col[col]
                    x = state["alien_offset_x"] + col * state["alien_spacing"] + (state["alien_sprite_w"] // 2)
                    y = state["alien_offset_y"] + row * state["alien_row_spacing"] + state["alien_sprite_h"]
                    if 0 <= x < board_w and 0 <= y < board_h:
                        state["bombs"].append({"x": x, "y": y})
                state["next_bomb_drop"] = now + random.uniform(0.12, state["bomb_interval"])

        # Bullet collisions with aliens and bombs.
        alien_pos = _alien_positions(state)
        bombs_to_remove = set()
        bullets_remaining = []
        for bullet in state["bullets"]:
            bpos = (bullet["x"], bullet["y"])
            if bpos in alien_pos:
                row, col = alien_pos[bpos]
                state["aliens_alive"].discard((row, col))
                state["score"] += _alien_score_for_hit(now - bullet["born"], state["level"])
                continue
            bomb_hit = False
            for idx, bomb in enumerate(state["bombs"]):
                if bomb["x"] == bullet["x"] and bomb["y"] == bullet["y"]:
                    bombs_to_remove.add(idx)
                    state["score"] += 20
                    bomb_hit = True
                    break
            if bomb_hit:
                continue
            bullets_remaining.append(bullet)
        state["bullets"] = bullets_remaining
        if bombs_to_remove:
            state["bombs"] = [b for idx, b in enumerate(state["bombs"]) if idx not in bombs_to_remove]

        # Bombs collide with shields / ship.
        ship_y = board_h - 1
        ship_cells = set(_alien_ship_cells(state["player_x"], profile["ship_art"], ship_y).keys())
        kept_bombs = []
        for bomb in state["bombs"]:
            pos = (bomb["x"], bomb["y"])
            if pos in state["shields"]:
                state["shields"].discard(pos)
                continue
            if pos in ship_cells:
                state["lives"] = 0
                state["phase"] = "game_over"
                state["message"] = "Ship hit!"
                state["bombs"] = kept_bombs
                return
            kept_bombs.append(bomb)
        state["bombs"] = kept_bombs

        # Aliens touching shields gradually break them.
        alien_cells = set(_alien_positions(state).keys())
        shield_hits = [pos for pos in state["shields"] if pos in alien_cells]
        for pos in shield_hits:
            state["shields"].discard(pos)

        # Lose when aliens reach ship line.
        if alien_cells:
            lowest_alien = max(y for (_x, y) in alien_cells)
            if lowest_alien >= ship_y - 1:
                state["phase"] = "game_over"
                state["message"] = "Aliens reached the base!"
                return

        if state["lives"] <= 0:
            state["phase"] = "game_over"
            state["message"] = "No lives left."
            return

        if not state["aliens_alive"]:
            if state["level"] >= int(state.get("max_level", 10)):
                start_victory(now)
                return
            new_level()

    # Keep render as a callable and invalidate proactively to avoid blank first-frame
    # behavior in terminals that defer paint until the first refresh event.
    control = FormattedTextControl(text=render)
    window = Window(content=control, wrap_lines=False, always_hide_cursor=True)
    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        if state["phase"] != "intro":
            return
        state["intro_field"] = (state["intro_field"] - 1) % 2
        event.app.invalidate()

    @kb.add("down")
    def _(event):
        if state["phase"] != "intro":
            return
        state["intro_field"] = (state["intro_field"] + 1) % 2
        event.app.invalidate()

    @kb.add("left")
    def _(event):
        if state["phase"] == "intro":
            if state["intro_field"] == 0:
                state["intro_mode_idx"] = (state["intro_mode_idx"] - 1) % len(mode_options)
            else:
                state["intro_diff_idx"] = (state["intro_diff_idx"] - 1) % len(difficulty_options)
            apply_intro_profile()
            event.app.invalidate()
            return
        if state["phase"] != "running" or state["too_small"]:
            return
        state["move_dir"] = -1
        state["move_hold_until"] = time.monotonic() + float(state["move_impulse_seconds"])
        _alien_apply_player_motion(state, profile["ship_sprite"], 1 / 45, state["move_hold_until"])
        event.app.invalidate()

    @kb.add("right")
    def _(event):
        if state["phase"] == "intro":
            if state["intro_field"] == 0:
                state["intro_mode_idx"] = (state["intro_mode_idx"] + 1) % len(mode_options)
            else:
                state["intro_diff_idx"] = (state["intro_diff_idx"] + 1) % len(difficulty_options)
            apply_intro_profile()
            event.app.invalidate()
            return
        if state["phase"] != "running" or state["too_small"]:
            return
        state["move_dir"] = 1
        state["move_hold_until"] = time.monotonic() + float(state["move_impulse_seconds"])
        _alien_apply_player_motion(state, profile["ship_sprite"], 1 / 45, state["move_hold_until"])
        event.app.invalidate()

    @kb.add("space")
    def _(event):
        if state["phase"] != "running" or state["too_small"]:
            return
        if len(state["bullets"]) >= profile["max_bullets"]:
            return
        ship_y = state["board_h"] - 1
        shot_y = ship_y - len(profile["ship_art"])
        state["bullets"].append(
            {"x": state["player_x"], "y": shot_y, "born": time.monotonic()}
        )
        event.app.invalidate()

    @kb.add("p")
    def _(event):
        if state["phase"] == "running":
            state["phase"] = "paused"
            state["move_dir"] = 0
            state["move_hold_until"] = 0.0
        elif state["phase"] == "paused":
            state["phase"] = "running"
            now = time.monotonic()
            state["next_alien_move"] = now + max(0.05, state["alien_move_interval"] / 2)
            state["next_bomb_drop"] = now + max(0.08, state["bomb_interval"] / 2)
        event.app.invalidate()

    @kb.add("enter")
    def _(event):
        if state["phase"] == "intro":
            reset_game()
        elif state["phase"] in {"game_over", "victory"}:
            reset_game()
        event.app.invalidate()

    @kb.add("r")
    def _(event):
        if state["phase"] in {"game_over", "victory"}:
            reset_game()
            event.app.invalidate()

    @kb.add("q")
    @kb.add("escape")
    def _(event):
        event.app.exit(result=0)

    @kb.add("c-c")
    def _(event):
        event.app.exit(exception=KeyboardInterrupt())

    app = Application(
        layout=Layout(HSplit([window])),
        key_bindings=kb,
        full_screen=True,
        erase_when_done=True,
        refresh_interval=1 / 30,
    )

    def ensure_first_frame() -> None:
        apply_intro_profile()
        app.invalidate()

    app.pre_run_callables.append(ensure_first_frame)

    async def game_loop() -> None:
        while True:
            await asyncio.sleep(1 / 30)
            now = time.monotonic()
            last_tick = state.get("last_tick_time")
            if isinstance(last_tick, (int, float)):
                dt = max(1 / 240, min(0.1, now - float(last_tick)))
            else:
                dt = 1 / 30
            state["last_tick_time"] = now
            update_running(now, dt)
            app.invalidate()

    loop_task = asyncio.create_task(game_loop())
    try:
        reset_game()
        start_clean_screen()
        sync_board_size()
        state["player_x"] = state["board_w"] // 2
        ensure_first_frame()
        await app.run_async()
    finally:
        ensure_terminal_cursor_visible()
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
    return 0


def run_alien_attack_command(args: argparse.Namespace) -> int:
    no_color = is_no_color_requested(args.no_color)
    return run_coroutine_sync(
        _run_alien_attack(
            mode=str(args.mode or "single"),
            difficulty=str(args.difficulty or "normal"),
            no_color=no_color,
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


def save_debug_attempt(
    quiz_title: str,
    score: int,
    total_score_possible: int,
    answers: list[dict],
) -> Path:
    attempt_dir = next_attempt_dir(quiz_title)
    payload = {
        "mode": "debug",
        "quiz_title": quiz_title,
        "score": score,
        "score_total": total_score_possible,
        "total_questions": len(answers),
        "answers": answers,
    }

    (attempt_dir / "answers.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        f"Quiz: {quiz_title}",
        f"Score: {score}/{total_score_possible}",
        "",
    ]

    for item in answers:
        lines.extend(
            [
                item["question_title"],
                item["question_text"],
                f"Result: {'Perfect' if item['is_perfect'] else 'Partial/Wrong'}",
                f"Points: {item['question_points']}/{item['question_max_points']}",
                f"Hint used: {'yes' if item['used_hint'] else 'no'}",
                f"Scoring mode: {item.get('scoring_mode', 'line_exact')}",
                f"AI reviewed: {'yes' if item.get('ai_reviewed') else 'no'}",
                f"AI accepted: {'yes' if item.get('ai_accepted') else 'no'}",
                f"Changed lines expected: {', '.join(str(n) for n in item['changed_lines']) or '-'}",
                "Submitted fix:",
                item["student_code"] or "-",
                "",
            ]
        )

    (attempt_dir / "answers.txt").write_text("\n".join(lines), encoding="utf-8")
    return attempt_dir


def _challenge_star_badge(stars: int) -> str:
    if stars <= 0:
        return "🐐"
    return "⭐" * stars


def _challenge_difficulty_text(level: str) -> str:
    labels = {
        "easy": "⭐ Easy",
        "normal": "⭐⭐ Normal",
        "hard": "⭐⭐⭐ Hard",
    }
    return labels.get(level, level.title())


def save_challenge_attempt(
    quiz_title: str,
    total_stars: int,
    categories: list[dict],
    answers: list[dict],
) -> Path:
    attempt_dir = next_attempt_dir(quiz_title)
    payload = {
        "mode": "challenge",
        "quiz_title": quiz_title,
        "stars_earned": total_stars,
        "stars_total": len(categories) * 3,
        "total_categories": len(categories),
        "answers": answers,
    }
    (attempt_dir / "answers.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        f"Quiz: {quiz_title}",
        f"Stars: {total_stars}/{len(categories) * 3}",
        "",
    ]
    for item in answers:
        lines.extend(
            [
                f"Category: {item['category']}",
                f"Difficulty: {_challenge_difficulty_text(item['difficulty'])}",
                f"Stars earned: {_challenge_star_badge(item['stars_earned'])} ({item['stars_earned']})",
                f"Correct: {'yes' if item['is_correct'] else 'no'}",
                f"Selected: {item['selected_labels'] or 'No answer'}",
                f"Expected: {item['expected_labels']}",
                f"Explanation: {item['explanation'] or '-'}",
                "",
            ]
        )

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


def _reason_code_from_provider_exception(exc: Exception) -> str:
    """Best-effort provider reason code extraction, including wrapped runtime errors."""
    _retryable, reason_code = _classify_provider_error(exc)
    if reason_code != "unknown_error":
        return reason_code

    text = str(exc).strip()
    if text.startswith("[") and "]" in text:
        bracket_code = text[1:text.index("]")].strip().lower()
        if bracket_code:
            return bracket_code
    return "unknown_error"


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


def _markdown_preserve_linebreaks(text: str) -> str:
    """Preserve single newlines in markdown blocks as visible line breaks."""
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\n", "  \n")


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


def _debug_evaluator_for_provider(ai_provider: str):
    if ai_provider == "gemini":
        return evaluate_debug_with_gemini
    if ai_provider == "openai":
        return evaluate_debug_with_openai
    if ai_provider == "anthropic":
        return evaluate_debug_with_anthropic
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


def _essay_key_setup_help_text() -> str:
    return (
        "Tips:\n"
        "- Use `quizmd --validate your-essay.md` to validate essay format without any key.\n"
        "- Use MCQ modes (`hello-quiz.md`, `hello-imposter.md`, etc.) if you want to run without AI."
    )


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


def _resolve_millionaire_ai_settings(ai_provider: str, ai_model: str) -> dict:
    requested = str(ai_provider or DEFAULT_AI_PROVIDER)
    model_text = (ai_model or "").strip()

    if requested == "auto":
        providers = _available_ai_providers_by_priority()
        if not providers:
            return {"enabled": False, "provider": "", "model": "", "env_key": ""}
        provider = providers[0]
    else:
        provider = requested
        env_key = _env_key_for_provider(provider)
        if not os.environ.get(env_key, "").strip():
            return {"enabled": False, "provider": provider, "model": "", "env_key": env_key}

    env_key = _env_key_for_provider(provider)
    model = model_text or _default_model_for_provider(provider)
    return {
        "enabled": bool(os.environ.get(env_key, "").strip()),
        "provider": provider,
        "provider_name": _provider_display_name(provider),
        "model": model,
        "env_key": env_key,
    }


def _millionaire_build_ai_prompt(question: dict) -> str:
    options = question.get("options", [])
    options_lines = "\n".join(f"{idx+1}. {opt}" for idx, opt in enumerate(options))
    return (
        "You are helping a student in a quiz game.\n"
        "Give a short hint (max 2 sentences) and a likely option number.\n"
        "Do not claim certainty. Keep it concise.\n\n"
        f"Question:\n{question.get('question', '').strip()}\n\n"
        f"Options:\n{options_lines}\n\n"
        "Return plain text only."
    )


def _millionaire_ask_ai_hint(
    question: dict,
    provider: str,
    model: str,
    api_key: str,
    timeout: int,
    max_retries: int = 2,
) -> str:
    prompt = _millionaire_build_ai_prompt(question)
    last_error: Exception | None = None
    reason_code = "unknown_error"

    for attempt in range(max_retries + 1):
        try:
            if provider == "gemini":
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2},
                }
                body = json.dumps(payload).encode("utf-8")
                request = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-goog-api-key": api_key,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                    candidates = parsed.get("candidates", [])
                    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
                    if text:
                        return text[:500]
                    raise ValueError("Empty Gemini hint response")

            if provider == "openai":
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Be concise and practical."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                }
                body = json.dumps(payload).encode("utf-8")
                request = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                    choices = parsed.get("choices", [])
                    message = choices[0].get("message", {}) if choices else {}
                    text = message.get("content", "")
                    if isinstance(text, list):
                        text = "".join(
                            item.get("text", "")
                            for item in text
                            if isinstance(item, dict)
                        )
                    text = str(text).strip()
                    if text:
                        return text[:500]
                    raise ValueError("Empty OpenAI hint response")

            if provider == "anthropic":
                payload = {
                    "model": model,
                    "max_tokens": 250,
                    "temperature": 0.2,
                    "messages": [{"role": "user", "content": prompt}],
                }
                body = json.dumps(payload).encode("utf-8")
                request = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                    blocks = parsed.get("content", [])
                    text = "".join(
                        block.get("text", "")
                        for block in blocks
                        if isinstance(block, dict) and block.get("type") == "text"
                    ).strip()
                    if text:
                        return text[:500]
                    raise ValueError("Empty Anthropic hint response")

            raise RuntimeError(f"Unsupported AI provider: {provider}")
        except Exception as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            last_error = exc
            retryable, reason_code = _classify_provider_error(exc)
            if attempt >= max_retries or not retryable:
                break
            time.sleep((2 ** attempt) + random.uniform(0.1, 0.3))

    raise RuntimeError(f"[{reason_code}] AI hint failed: {last_error}")


def _select_debug_ai_candidates(ai_provider: str) -> tuple[list[str], bool]:
    """Return (provider_candidates, unsupported_requested)."""
    requested = str(ai_provider or DEFAULT_AI_PROVIDER)
    if requested == "auto":
        return (_available_ai_providers_by_priority(), False)

    resolved = _resolve_ai_provider(requested)
    if resolved == "auto":
        return ([], True)
    return ([resolved], False)


def _debug_model_for_provider(
    requested_provider: str,
    ai_model: str,
    provider: str,
    provider_index: int,
) -> str:
    model_text = (ai_model or "").strip()
    if requested_provider == "auto":
        if model_text and provider_index == 0:
            return model_text
        return _default_model_for_provider(provider)
    return model_text or _default_model_for_provider(provider)


def _debug_missing_key_hint(
    requested_provider: str,
    provider_candidates: list[str],
    providers_with_keys: list[str],
) -> tuple[str, str]:
    """Return (provider_name, env_key) when explicit provider key is missing."""
    if requested_provider == "auto" or not provider_candidates or providers_with_keys:
        return ("", "")
    provider = provider_candidates[0]
    return (provider, _env_key_for_provider(provider))


def collect_essay_answer_via_editor(
    question_title: str,
    question_text: str = "",
    hint_text: str = "",
) -> str:
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
    hint_line = hint_text.strip()
    template = (
        f"# {header_line}\n\n"
        "# When ready: Press Esc, type :wq!, then Enter to save and exit (or :q! to quit without saving).\n"
        "# Write your answer below. Keep 5-10 lines.\n"
        "# Lines starting with '#' will be ignored.\n"
    )
    if hint_line:
        template += f"# Hint: {hint_line}\n"
    template += "\n"

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


def collect_essay_answer_inline(
    question_title: str,
    question_text: str = "",
    instructions: str = "",
    hint_text: str = "",
    theme: dict | None = None,
    use_fullscreen_box: bool = False,
    show_intro: bool = True,
) -> str:
    """Collect a short essay directly in the terminal for the vNext prototype."""
    if use_fullscreen_box and sys.stdin.isatty() and sys.stdout.isatty():
        try:
            return collect_essay_answer_inline_box(
                question_title,
                question_text,
                instructions=instructions,
                hint_text=hint_text,
                theme=theme,
            )
        except ModuleNotFoundError:
            pass

    if show_intro:
        print("")
        print(LOGO)
        print(question_title)
        if question_text:
            print(question_text)
        if instructions:
            print("")
            print(instructions)
        if hint_text:
            print("")
            print(hint_text)
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


def _clean_inline_essay_answer(raw_answer: str) -> str:
    lines = []
    for line in raw_answer.splitlines():
        if line.strip().lower() == "/end":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _inline_essay_answer_height(answer_text: str, min_lines: int = 4, max_lines: int = 6) -> int:
    """Return the visible answer-box height for the inline essay prototype."""
    line_count = (answer_text or "").count("\n") + 1
    return min(max_lines, max(min_lines, line_count))


def collect_essay_answer_inline_box(
    question_title: str,
    question_text: str = "",
    instructions: str = "",
    hint_text: str = "",
    theme: dict | None = None,
) -> str:
    try:
        from prompt_toolkit import Application
        from prompt_toolkit.formatted_text import HTML as PromptHTML
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.styles import Style
        from prompt_toolkit.widgets import Frame, TextArea
    except ModuleNotFoundError:
        raise

    active_theme = theme or select_theme("auto")
    palette = _prompt_ui_palette(active_theme)

    title = html.escape(question_title.strip() or "Essay answer")
    question = html.escape((question_text or "").strip())
    instruction_text = html.escape((instructions or "").strip())
    hint = html.escape((hint_text or "").strip())
    heading_parts = [
        f"<style fg='{palette['logo']}'>{html.escape(LOGO.strip())}</style>",
        f"<style fg='{palette['accent']}'><b>{title}</b></style>",
    ]
    if question:
        heading_parts.append(f"<style fg='{palette['body']}'>{question}</style>")
    if instruction_text:
        heading_parts.append(f"<style fg='{palette['body']}'>{instruction_text}</style>")
    if hint:
        heading_parts.append(f"<style fg='{palette['warning']}'>{hint}</style>")
    heading_parts.append(
        f"<style fg='{palette['muted']}'>Type your answer below. Press Enter for a new line. "
        "Type /end on its own line to finish.</style>"
    )
    heading = "\n\n".join(heading_parts)
    heading_height = min(18, max(9, heading.count("\n") + 2))

    answer_box = TextArea(
        multiline=True,
        prompt="› ",
        height=_inline_essay_answer_height(""),
        wrap_lines=True,
    )
    app = None

    def resize_answer_box(_buffer=None):
        answer_box.window.height = _inline_essay_answer_height(answer_box.text)
        if app is not None:
            app.invalidate()

    answer_box.buffer.on_text_changed += resize_answer_box
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        current_line = answer_box.buffer.document.current_line.strip().lower()
        if current_line == "/end":
            event.app.exit(result=answer_box.text)
            return
        answer_box.buffer.insert_text("\n")
        resize_answer_box()

    @kb.add("c-c")
    def _(event):
        event.app.exit(exception=KeyboardInterrupt())

    root = HSplit(
        [
            Window(
                FormattedTextControl(PromptHTML(heading)),
                height=heading_height,
                wrap_lines=True,
            ),
            Window(height=Dimension(weight=1)),
            Frame(answer_box, title="Your answer"),
            Window(
                FormattedTextControl(
                    PromptHTML(
                        f"<style fg='{palette['muted']}'>/end finish • Ctrl+C cancel</style>"
                    )
                ),
                height=1,
            ),
        ]
    )
    style = Style.from_dict(
        {
            "frame.border": palette["border"],
            "frame.label": palette["label"],
            # Keep input readable on both light and dark terminal themes.
            "textarea": "",
            "text-area": "",
        }
    )
    app = Application(layout=Layout(root, focused_element=answer_box), key_bindings=kb, style=style, full_screen=True)
    try:
        answer = _clean_inline_essay_answer(app.run() or "")
    finally:
        ensure_terminal_cursor_visible()
    if not answer:
        raise RuntimeError("No essay answer was provided. Type your answer before /end.")
    return answer


def _evaluate_with_loading_message(
    console,
    theme: dict,
    evaluator,
    message: str,
    *args,
    **kwargs,
):
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

    result: dict = {}

    def worker():
        try:
            result["value"] = evaluator(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - bubble up after animation stops
            result["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

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


def evaluate_essay_with_loading(console, theme: dict, evaluator, *args, **kwargs):
    instructor_name = str(kwargs.pop("instructor_name", "")).strip()
    if instructor_name:
        message = f"Reviewing your answer using {instructor_name}'s rubric and guidance..."
    else:
        message = "Reviewing your answer using the rubric and guidance..."
    return _evaluate_with_loading_message(
        console,
        theme,
        evaluator,
        message,
        *args,
        **kwargs,
    )


def _play_win_confetti(console, theme: dict, no_color: bool = False, duration_seconds: float = 1.2) -> None:
    if no_color:
        return
    try:
        from rich.live import Live
        from rich.panel import Panel
    except ModuleNotFoundError:
        return

    frames = [
        "✦  ✧  ✦  ✧  ✦",
        "  ✦  ✧  ✦  ✧ ",
        "✧  ✦  ✧  ✦  ✧",
        "  ✧  ✦  ✧  ✦ ",
    ]
    delay = 0.12
    total_frames = max(1, int(duration_seconds / delay))
    with Live(console=console, transient=True, refresh_per_second=12) as live:
        for i in range(total_frames):
            frame = frames[i % len(frames)]
            live.update(
                Panel(
                    f"[bold {theme['success']}]{frame}[/bold {theme['success']}]\n"
                    f"[bold {theme['success']}]Congrats, you won![/bold {theme['success']}]\n"
                    f"[bold {theme['success']}]{frame}[/bold {theme['success']}]",
                    border_style=theme["success"],
                )
            )
            time.sleep(delay)


def _millionaire_available_options(option_count: int, hidden_options: set[int] | None) -> list[int]:
    hidden = hidden_options or set()
    return [idx for idx in range(1, option_count + 1) if idx not in hidden]


def _millionaire_points_for_question(question_index: int, total_questions: int) -> int:
    if total_questions <= 0:
        return 0
    if total_questions == MILLIONAIRE_TOTAL_QUESTIONS:
        idx = max(1, min(question_index, len(MILLIONAIRE_POINTS_LADDER)))
        return MILLIONAIRE_POINTS_LADDER[idx - 1]
    # Fallback for short custom millionaire quizzes in tests/dev.
    base = 1_000_000 / total_questions
    return max(100, int(round(base * question_index)))


def _format_points(value: int) -> str:
    return f"{max(0, int(value)):,}"


def _millionaire_5050_hidden_indexes(
    correct_indexes: list[int],
    option_count: int,
    seed: int,
) -> set[int]:
    if not correct_indexes:
        return set()
    correct = int(correct_indexes[0])
    wrong = [idx for idx in range(1, option_count + 1) if idx != correct]
    if len(wrong) <= 1:
        return set()
    rng = random.Random(seed)
    remove_count = min(2, len(wrong) - 1)
    hidden = set(rng.sample(wrong, remove_count))
    return hidden


def _millionaire_audience_percentages(
    correct_indexes: list[int],
    option_count: int,
    seed: int,
    question_index: int = 1,
    total_questions: int = MILLIONAIRE_TOTAL_QUESTIONS,
) -> tuple[int, dict[int, int]]:
    if option_count <= 0:
        return 1, {}
    correct = int(correct_indexes[0]) if correct_indexes else 1
    correct = max(1, min(option_count, correct))
    rng = random.Random(seed)

    def split_total(total: int, parts_count: int) -> list[int]:
        if parts_count <= 0:
            return []
        if total <= 0:
            return [0] * parts_count
        weights = [rng.random() for _ in range(parts_count)]
        weight_sum = sum(weights)
        if weight_sum <= 0:
            base = [0] * parts_count
            base[0] = total
            return base
        parts = [int(total * w / weight_sum) for w in weights]
        used = sum(parts)
        remainder = total - used
        for i in range(remainder):
            parts[i % parts_count] += 1
        return parts

    if option_count == 1:
        return correct, {1: 100}

    qi = max(1, int(question_index))
    tq = max(1, int(total_questions))
    if qi <= max(2, int(round(tq * 0.27))):  # Q1-Q4 on a 15-question ladder
        correct_range = (88, 98)
        winner_correct_prob = 0.97
        wrong_lead_range = (45, 62)
    elif qi <= max(5, int(round(tq * 0.47))):  # Q5-Q7
        correct_range = (68, 82)
        winner_correct_prob = 0.84
        wrong_lead_range = (42, 56)
    elif qi <= max(8, int(round(tq * 0.67))):  # Q8-Q10
        correct_range = (48, 64)
        winner_correct_prob = 0.62
        wrong_lead_range = (38, 52)
    elif qi <= max(11, int(round(tq * 0.80))):  # Q11-Q12
        correct_range = (38, 56)
        winner_correct_prob = 0.52
        wrong_lead_range = (35, 50)
    else:  # Q13+
        correct_range = (24, 50)
        winner_correct_prob = 0.36
        wrong_lead_range = (32, 48)

    correct_pct = rng.randint(*correct_range)
    winner_is_correct = rng.random() < winner_correct_prob
    wrong_options = [i for i in range(1, option_count + 1) if i != correct]
    winner = correct if winner_is_correct else rng.choice(wrong_options)

    if winner_is_correct:
        winner_pct = correct_pct
        remaining = 100 - winner_pct
        others = wrong_options
        votes = {winner: winner_pct}
        if len(others) == 1:
            votes[others[0]] = remaining
            return winner, votes
        if remaining <= 0:
            for idx in others:
                votes[idx] = 0
            return winner, votes
        parts = split_total(remaining, len(others))
        for idx, pct in zip(others, parts):
            votes[idx] = pct
        return winner, votes
    else:
        wrong_lead = rng.randint(*wrong_lead_range)
        # Keep percentages sane when ranges collide on smaller/denser cases.
        winner_pct = min(max(wrong_lead, correct_pct + 1), 99 - correct_pct)
        remaining = 100 - winner_pct - correct_pct
        if remaining < 0:
            remaining = 0
            if winner_pct + correct_pct != 100:
                winner_pct = max(1, 100 - correct_pct)
        others = [i for i in range(1, option_count + 1) if i not in {winner, correct}]
        votes = {winner: winner_pct, correct: correct_pct}
        if not others:
            return winner, votes
        if len(others) == 1:
            votes[others[0]] = max(0, remaining)
            return winner, votes
        if remaining <= 0:
            for idx in others:
                votes[idx] = 0
            return winner, votes
        parts = split_total(remaining, len(others))
        for idx, pct in zip(others, parts):
            votes[idx] = pct
        return winner, votes


def _millionaire_friend_hint(question: dict, audience_winner: int | None = None) -> str:
    hint = str(question.get("hint") or "").strip()
    if hint:
        return hint
    explanation = str(question.get("explanation") or "").strip()
    if explanation:
        return explanation
    if audience_winner is not None:
        return f"Your friend leans toward option {audience_winner}."
    return "Your friend says: focus on the most precise option."


def _millionaire_ai_loading_message(provider_name: str, tick: int, width: int = 10) -> str:
    safe_provider = (provider_name or "AI").strip() or "AI"
    bar_width = max(3, int(width))
    filled = int(tick) % (bar_width + 1)
    bar = ("█" * filled) + ("░" * (bar_width - filled))
    return f"Asking {safe_provider}... [{bar}]"


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
    millionaire_mode: bool = False,
    millionaire_lifelines_text: str = "",
    millionaire_message: str = "",
    hidden_options: set[int] | None = None,
    millionaire_points_text: str = "",
    millionaire_safety_text: str = "",
    millionaire_instruction: str = "",
) -> str:
    if imposter_marked is None:
        imposter_marked = set()

    ultra_compact = bool(terminal_width is not None and terminal_width < 70)
    ascii_compact = no_color or (compact and (_is_windows() or ultra_compact))
    separator = " | " if ascii_compact else " • "
    if imposter_mode:
        instruction = (
            "Sp/X/En/Q"
            if ultra_compact
            else "[Space] Select • [X] Imposter • [Enter] Confirm • [Q] Quit"
        )
    elif millionaire_mode:
        instruction = (
            (millionaire_instruction or "Sp/En/F/A/C/Q")
            if ultra_compact
            else (millionaire_instruction or "[Space] Select • [Enter] Confirm • [Q] Quit with points")
        )
    else:
        instruction = (
            "Sp/En/Q"
            if ultra_compact
            else ("[Space] Select | [Enter] Confirm | [Q] Quit" if ascii_compact else "[Space] Select • [Enter] Confirm • [Q] Quit")
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
        option_hidden = bool(hidden_options and idx in hidden_options)
        pointer = "&gt;" if i == selected else " "
        if option_hidden:
            marker = "-"
            hidden_label = "(removed by 50-50)"
            style = f"fg='{theme['pt_instruction']}'"
            if no_color:
                lines.append(
                    f"{'>' if i == selected else ' '} {idx}. {marker} {hidden_label}"
                )
            else:
                lines.append(f"<style {style}>{pointer} {idx}. {marker} {hidden_label}</style>")
            continue
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
                if idx in imposter_marked:
                    marker = "(x)"
                imposter_marker = ""
            else:
                imposter_marker = ("[x]" if idx in imposter_marked else "[ ]") if (no_color or ascii_compact) else ("✖" if idx in imposter_marked else "·")
        else:
            imposter_marker = ""
        selected_chip = ""

        if ui == "next" and imposter_mode and idx in imposter_marked and idx not in marked:
            style = (
                f"fg='{theme.get('pt_imposter_fg', theme['pt_marked_fg'])}' "
                f"bg='{theme.get('pt_imposter_bg', theme['pt_timer_danger'])}'"
            )
        elif idx in marked:
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

    if millionaire_mode:
        sep_width = max(30, min(74, (terminal_width or 76) - 2))
        label = " Lifelines "
        line_char = "-" if (no_color and _is_windows()) else "─"
        if sep_width <= len(label) + 2:
            separator_line = label.strip()
        else:
            side = (sep_width - len(label)) // 2
            remainder = sep_width - len(label) - side
            separator_line = (line_char * side) + label + (line_char * remainder)
        if no_color:
            lines.append(separator_line)
        else:
            lines.append(f"<style fg='{theme['pt_instruction']}'>{separator_line}</style>")
        lines.append("")

    if millionaire_mode and millionaire_lifelines_text:
        if no_color:
            lines.append(millionaire_lifelines_text)
        else:
            lines.append(f"<style fg='{theme['pt_instruction']}'>{html.escape(millionaire_lifelines_text)}</style>")
        lines.append("")

    if millionaire_mode and millionaire_points_text:
        if no_color:
            lines.append(millionaire_points_text)
        else:
            lines.append(f"<style fg='{theme['pt_title']}'>{html.escape(millionaire_points_text)}</style>")
        lines.append("")

    if millionaire_mode and millionaire_safety_text:
        if no_color:
            lines.append(millionaire_safety_text)
        else:
            lines.append(f"<style fg='{theme['pt_timer_warning']}'>{html.escape(millionaire_safety_text)}</style>")
        lines.append("")

    if millionaire_mode and millionaire_message:
        if no_color:
            lines.append(millionaire_message)
        else:
            lines.append(f"<style fg='{theme['pt_timer_warning']}'>{html.escape(millionaire_message)}</style>")
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
    show_feedback: bool = True,
    quiz_mode: str = "mcq",
    millionaire_state: dict | None = None,
    ai_provider: str = DEFAULT_AI_PROVIDER,
    ai_model: str = "",
    ai_timeout: int = 30,
    untimed: bool = False,
    status_sidebar_renderer=None,
    status_sidebar_width: int = 34,
):
    try:
        from prompt_toolkit import Application
        from prompt_toolkit.formatted_text import HTML as PromptHTML
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Interactive quiz mode requires prompt_toolkit. Install dependencies from requirements.txt."
        ) from exc

    selected = 0
    marked = set()
    imposter_marked = set()
    pulse = False
    remaining = None if untimed else q["time_limit"]
    force_compact = compact
    current_columns = get_terminal_columns()
    current_compact = force_compact or should_use_compact_layout(columns=current_columns)
    result = {"answer": None, "imposters": [], "cash_out": False, "quit_requested": False}
    submitted = False
    auto_advance_task = None
    is_multiple = q.get("type", "single") == "multiple"
    expected_imposters = sorted(q.get("imposters", []))
    imposter_mode = bool(expected_imposters)
    millionaire_mode = quiz_mode == "millionaire"
    hidden_options: set[int] = set()
    millionaire_message = ""
    ai_lifeline_in_progress = False
    used_lifelines_this_question: list[str] = []
    audience_winner: int | None = None
    friend_name = str(q.get("friend_name") or "Friend").strip() or "Friend"
    ai_settings = _resolve_millionaire_ai_settings(ai_provider, ai_model) if millionaire_mode else {"enabled": False}
    ai_lifeline_enabled = bool(ai_settings.get("enabled"))

    if millionaire_mode:
        is_multiple = False
        imposter_mode = False
        if millionaire_state is None:
            millionaire_state = {}
        millionaire_state.setdefault("fifty_fifty_used", False)
        millionaire_state.setdefault("ask_people_used", False)
        millionaire_state.setdefault("call_friend_used", False)
        millionaire_state.setdefault("usage_by_question", {})
        millionaire_state.setdefault("messages_by_question", {})
        millionaire_state.setdefault("current_points", 0)
        millionaire_state.setdefault("guaranteed_points", 0)
        millionaire_state.setdefault("current_question_points", 0)
        millionaire_state.setdefault("is_safety_net_question", False)
        millionaire_state.setdefault("ask_ai_used", False)

    def millionaire_lifelines_text() -> str:
        if not millionaire_mode or millionaire_state is None:
            return ""
        ff = "✓" if millionaire_state.get("fifty_fifty_used") else "F"
        ap = "✓" if millionaire_state.get("ask_people_used") else "A"
        cf = "✓" if millionaire_state.get("call_friend_used") else "C"
        ai = "✓" if millionaire_state.get("ask_ai_used") else "D"
        if no_color:
            base = f"Lifelines: [{ff}]50-50  [{ap}]Ask  [{cf}]Ask {friend_name}"
            if ai_lifeline_enabled:
                base += f"  [{ai}]Ask AI"
            return base
        base = f"Lifelines: [{ff}] 50-50  [{ap}] Ask the People  [{cf}] Ask {friend_name}"
        if ai_lifeline_enabled:
            provider_name = str(ai_settings.get("provider_name") or "AI")
            base += f"  [{ai}] Ask AI ({provider_name})"
        return base

    def millionaire_instruction_text() -> str:
        if not millionaire_mode:
            return ""
        if no_color or current_compact:
            return "Sp/En/Q"
        return "[Space] Select • [Enter] Confirm • [Q] Quit with points"

    def visible_options() -> list[int]:
        if not millionaire_mode:
            return list(range(1, len(q["options"]) + 1))
        return _millionaire_available_options(len(q["options"]), hidden_options)

    def ensure_selected_visible() -> None:
        nonlocal selected
        vis = visible_options()
        if not vis:
            selected = 0
            return
        if (selected + 1) in vis:
            return
        selected = vis[0] - 1

    def move_selected(step: int) -> None:
        nonlocal selected
        if step == 0:
            return
        vis = visible_options()
        if not vis:
            return
        current = selected + 1
        if current not in vis:
            selected = vis[0] - 1
            return
        pos = vis.index(current)
        pos = (pos + step) % len(vis)
        selected = vis[pos] - 1

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
            millionaire_mode=millionaire_mode,
            millionaire_lifelines_text=millionaire_lifelines_text(),
            millionaire_message=millionaire_message,
            hidden_options=hidden_options,
            millionaire_points_text=(
                f"Points: {_format_points(int(millionaire_state.get('current_points', 0)))} | "
                f"Guaranteed: {_format_points(int(millionaire_state.get('guaranteed_points', 0)))} | "
                f"This question: {_format_points(int(millionaire_state.get('current_question_points', 0)))}"
                if millionaire_mode and millionaire_state is not None
                else ""
            ),
            millionaire_safety_text=(
                "🛟 Safety Net question! Get this right to lock your guaranteed points."
                if millionaire_mode and millionaire_state is not None and bool(millionaire_state.get("is_safety_net_question"))
                else ""
            ),
            millionaire_instruction=millionaire_instruction_text(),
        )
        if full_screen and submitted:
            grading = evaluate_submission(result["answer"], result["imposters"])
            status = question_status_label(grading)
            explanation = (q.get("explanation") or "").strip()
            answer_labels = format_labels(q["options"], q["correct"]) or "None"
            is_last_question = question_index >= total_questions
            if no_color:
                markup += "\n" + status + "\n"
                markup += f"\nQuestion points: {grading['question_points']}/{grading['question_max_points']}\n"
                if show_feedback:
                    markup += f"\nAnswer: {answer_labels}\n"
                    if imposter_mode:
                        _, imposter_labels = format_imposter_feedback(
                            q["options"],
                            q["correct"],
                            expected_imposters,
                        )
                        markup += f"Imposter: {imposter_labels}\n"
                    if explanation:
                        markup += f"\nExplanation\n{explanation}\n"
                if not is_last_question:
                    markup += "\nPress Enter for the next question..."
                return markup

            status_style = question_status_style(theme, status)
            markup += f"\n<style fg='{status_style}'><b>{status}</b></style>\n"
            markup += (
                f"\n<style fg='{theme['pt_instruction']}'>"
                f"Question points: {grading['question_points']}/{grading['question_max_points']}"
                f"</style>\n"
            )
            if show_feedback:
                markup += (
                    f"\n<style fg='{theme['pt_title']}'>"
                    f"Answer: {html.escape(answer_labels)}"
                    f"</style>\n"
                )
                if imposter_mode:
                    _, imposter_labels = format_imposter_feedback(
                        q["options"],
                        q["correct"],
                        expected_imposters,
                    )
                    markup += (
                        f"<style fg='{theme['pt_title']}'>"
                        f"Imposter: {html.escape(imposter_labels)}"
                        f"</style>\n"
                    )
                if explanation:
                    explanation_lines = [render_inline_markdown_for_prompt_toolkit(line) for line in explanation.splitlines()]
                    markup += "\n<style fg='{0}'><b>Explanation</b></style>\n".format(theme["pt_title"])
                    markup += "\n".join(explanation_lines) + "\n"
            if not is_last_question:
                markup += f"\n<style fg='{theme['pt_instruction']}'>Press Enter for the next question...</style>"
        if no_color:
            return markup
        return PromptHTML(markup)

    def render_sidebar():
        if status_sidebar_renderer is None:
            return ""
        raw = str(status_sidebar_renderer() or "")
        if no_color:
            return raw
        escaped = html.escape(raw)
        return PromptHTML(f"<style fg='{theme['pt_instruction']}'>{escaped}</style>")

    control = FormattedTextControl(text=render)
    window = Window(content=control, wrap_lines=True, always_hide_cursor=True)
    sidebar_control = None
    sidebar_window = None
    if status_sidebar_renderer is not None:
        sidebar_control = FormattedTextControl(text=render_sidebar)
        sidebar_window = Window(
            content=sidebar_control,
            wrap_lines=True,
            always_hide_cursor=True,
            width=max(24, int(status_sidebar_width)),
        )
    kb = KeyBindings()

    @kb.add("up")
    def _(_):
        nonlocal pulse
        move_selected(-1)
        pulse = not pulse
        control.text = render()

    @kb.add("down")
    def _(_):
        nonlocal pulse
        move_selected(1)
        pulse = not pulse
        control.text = render()

    @kb.add("space")
    def _(_):
        nonlocal millionaire_message
        idx = selected + 1
        if millionaire_mode and idx in hidden_options:
            millionaire_message = "That option was removed by 50-50."
            control.text = render()
            return
        if idx in marked:
            marked.remove(idx)
        else:
            if not is_multiple:
                marked.clear()
            marked.add(idx)
            imposter_marked.discard(idx)
        millionaire_message = ""
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
            marked.discard(idx)
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
            marked.discard(idx)
        control.text = render()

    @kb.add("F")
    @kb.add("f")
    def _(_):
        nonlocal millionaire_message
        if not millionaire_mode or millionaire_state is None:
            return
        if millionaire_state.get("fifty_fifty_used"):
            millionaire_message = "50-50 already used."
            control.text = render()
            return
        hidden_options.clear()
        hidden_options.update(
            _millionaire_5050_hidden_indexes(
                q.get("correct", []),
                len(q.get("options", [])),
                seed=(question_index * 131) + 7,
            )
        )
        if not hidden_options:
            millionaire_message = "50-50 unavailable for this question."
            control.text = render()
            return
        millionaire_state["fifty_fifty_used"] = True
        used_lifelines_this_question.append("50-50")
        millionaire_message = "50-50 used: two wrong options removed."
        ensure_selected_visible()
        control.text = render()

    @kb.add("A")
    @kb.add("a")
    def _(_):
        nonlocal millionaire_message, audience_winner
        if not millionaire_mode or millionaire_state is None:
            return
        if millionaire_state.get("ask_people_used"):
            millionaire_message = "Ask the People already used."
            control.text = render()
            return
        winner, votes = _millionaire_audience_percentages(
            q.get("correct", []),
            len(q.get("options", [])),
            seed=(question_index * 173) + 11,
            question_index=question_index,
            total_questions=total_questions,
        )
        audience_winner = winner
        ordered = " | ".join(f"{idx}:{votes.get(idx, 0)}%" for idx in range(1, len(q.get("options", [])) + 1))
        millionaire_state["ask_people_used"] = True
        used_lifelines_this_question.append("Ask the People")
        millionaire_message = f"Audience vote -> {ordered}. Most votes: option {winner}."
        control.text = render()

    @kb.add("C")
    @kb.add("c")
    def _(_):
        nonlocal millionaire_message
        if not millionaire_mode or millionaire_state is None:
            return
        if millionaire_state.get("call_friend_used"):
            millionaire_message = "Call a Friend already used."
            control.text = render()
            return
        hint = _millionaire_friend_hint(q, audience_winner=audience_winner)
        millionaire_state["call_friend_used"] = True
        used_lifelines_this_question.append("Call a Friend")
        millionaire_message = f"{friend_name} says: {hint}"
        control.text = render()

    @kb.add("D")
    @kb.add("d")
    async def _(event):
        nonlocal millionaire_message, ai_lifeline_in_progress
        if not millionaire_mode or millionaire_state is None or not ai_lifeline_enabled:
            return
        if ai_lifeline_in_progress:
            millionaire_message = "Ask AI already in progress..."
            control.text = render()
            event.app.invalidate()
            return
        if millionaire_state.get("ask_ai_used"):
            millionaire_message = "Ask AI already used."
            control.text = render()
            return

        api_key = os.environ.get(str(ai_settings.get("env_key") or ""), "").strip()
        if not api_key:
            millionaire_message = "Ask AI unavailable (missing API key)."
            control.text = render()
            return
        provider = str(ai_settings.get("provider") or "")
        model = str(ai_settings.get("model") or "")
        provider_name = str(ai_settings.get("provider_name") or "AI")
        ai_lifeline_in_progress = True
        try:
            loop = asyncio.get_running_loop()
            task = loop.run_in_executor(
                None,
                lambda: _millionaire_ask_ai_hint(
                    q,
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    timeout=max(1, int(ai_timeout)),
                ),
            )
            tick = 0
            while not task.done():
                millionaire_message = _millionaire_ai_loading_message(provider_name, tick)
                control.text = render()
                event.app.invalidate()
                tick += 1
                await asyncio.sleep(0.1)
            hint = await task
            millionaire_state["ask_ai_used"] = True
            used_lifelines_this_question.append("Ask AI")
            millionaire_message = f"{provider_name} says: {hint}"
        except Exception as exc:
            reason = _reason_code_from_provider_exception(exc)
            millionaire_message = f"{provider_name} is unavailable now ({reason})."
        finally:
            ai_lifeline_in_progress = False
        control.text = render()
        event.app.invalidate()

    @kb.add("enter")
    def _(event):
        nonlocal submitted, millionaire_message, auto_advance_task
        if ai_lifeline_in_progress:
            millionaire_message = "Please wait, Ask AI is still fetching..."
            control.text = render()
            event.app.invalidate()
            return
        if not submitted:
            result["answer"] = sorted(marked) if marked else None
            result["imposters"] = sorted(imposter_marked)
            if millionaire_mode and millionaire_state is not None:
                millionaire_state["usage_by_question"][str(question_index)] = list(dict.fromkeys(used_lifelines_this_question))
                millionaire_state["messages_by_question"][str(question_index)] = millionaire_message
            if full_screen:
                submitted = True
                control.text = render()
                app.invalidate()
                if question_index >= total_questions:
                    async def _auto_advance_to_results():
                        await asyncio.sleep(1.1)
                        if event.app.is_running:
                            event.app.exit()
                    auto_advance_task = event.app.create_background_task(_auto_advance_to_results())
                return
        event.app.exit()

    @kb.add("q")
    @kb.add("Q")
    def _(event):
        nonlocal millionaire_message
        if not millionaire_mode:
            result["quit_requested"] = True
            result["answer"] = None
            result["imposters"] = []
            event.app.exit()
            return
        if ai_lifeline_in_progress:
            millionaire_message = "Please wait, Ask AI is still fetching..."
            control.text = render()
            event.app.invalidate()
            return
        if millionaire_state is not None:
            millionaire_state["usage_by_question"][str(question_index)] = list(dict.fromkeys(used_lifelines_this_question))
            millionaire_state["messages_by_question"][str(question_index)] = millionaire_message
        result["cash_out"] = True
        result["answer"] = None
        result["imposters"] = []
        event.app.exit()

    @kb.add("c-c")
    def _(event):
        event.app.exit(exception=KeyboardInterrupt())

    app = Application(
        layout=Layout(
            VSplit([window, sidebar_window], padding=1)
            if sidebar_window is not None
            else HSplit([window])
        ),
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
    if sidebar_control is not None:
        sidebar_control.text = render_sidebar()

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
            if millionaire_mode and millionaire_state is not None:
                millionaire_state["usage_by_question"][str(question_index)] = list(dict.fromkeys(used_lifelines_this_question))
                millionaire_state["messages_by_question"][str(question_index)] = millionaire_message
            if full_screen:
                submitted = True
                control.text = render()
                app.invalidate()
                if question_index >= total_questions:
                    async def _auto_advance_to_results():
                        await asyncio.sleep(1.1)
                        if app.is_running:
                            app.exit()
                    auto_advance_task = app.create_background_task(_auto_advance_to_results())
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
            if sidebar_control is not None:
                sidebar_control.text = render_sidebar()
            app.invalidate()

    async def watch_sidebar_clock():
        if sidebar_control is None:
            return
        while True:
            await asyncio.sleep(1)
            sidebar_control.text = render_sidebar()
            app.invalidate()

    task = asyncio.create_task(timer())
    resize_task = asyncio.create_task(watch_resize())
    sidebar_clock_task = asyncio.create_task(watch_sidebar_clock())
    try:
        await app.run_async()
    finally:
        ensure_terminal_cursor_visible()
        task.cancel()
        resize_task.cancel()
        sidebar_clock_task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        try:
            await resize_task
        except asyncio.CancelledError:
            pass
        try:
            await sidebar_clock_task
        except asyncio.CancelledError:
            pass
        if auto_advance_task is not None and not auto_advance_task.done():
            auto_advance_task.cancel()
            try:
                await auto_advance_task
            except asyncio.CancelledError:
                pass

    ans = result["answer"]
    imposters_selected = result["imposters"]
    grading = evaluate_submission(ans, imposters_selected)
    grading["quit_with_points"] = bool(result.get("cash_out"))
    grading["quit_requested"] = bool(result.get("quit_requested"))
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


def format_imposter_feedback(options: list[str], correct_indexes: list[int], imposter_indexes: list[int]) -> tuple[str, str]:
    """Return concise expected answer/imposter labels for feedback screens."""
    answer_labels = format_labels(options, correct_indexes) or "None"
    imposter_labels = format_labels(options, imposter_indexes) or "None"
    return answer_labels, imposter_labels


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


def _numbered_code_block(code: str) -> str:
    lines = _normalize_code_lines(code)
    if not lines:
        return "1 |"
    width = len(str(len(lines)))
    return "\n".join(f"{idx:>{width}} | {line}" for idx, line in enumerate(lines, start=1))


def _numbered_code_block_markup(
    code: str,
    highlight_lines: set[int] | None = None,
    default_style: str = "fg='ansigray'",
    highlight_style: str = "fg='ansiwhite' bg='#6b3a3a'",
) -> str:
    lines = _normalize_code_lines(code)
    if not lines:
        lines = [""]
    highlights = highlight_lines or set()
    width = len(str(len(lines)))
    rows: list[str] = []
    for idx, line in enumerate(lines, start=1):
        raw = f"{idx:>{width}} | {line}"
        style = highlight_style if idx in highlights else default_style
        rows.append(f"<style {style}>{html.escape(raw)}</style>")
    return "\n".join(rows)


def _default_debug_hint(question: dict) -> str:
    hint = (question.get("hint") or "").strip()
    if hint:
        return hint
    changed = question.get("changed_lines") or []
    if not changed:
        return "Check punctuation, indentation, and variable names."
    if len(changed) == 1:
        return f"The error is on line {changed[0]}."
    preview = ", ".join(str(line) for line in changed[:3])
    if len(changed) > 3:
        preview += ", ..."
    return f"Focus on lines {preview}."


def _render_debug_expected_lines(fixed_code: str, changed_lines: list[int]) -> str:
    fixed_lines = _normalize_code_lines(fixed_code)
    rows = []
    for line_no in changed_lines:
        value = fixed_lines[line_no - 1] if line_no - 1 < len(fixed_lines) else ""
        rows.append(f"- Line {line_no}: {value}")
    return "\n".join(rows) if rows else "- None"


def collect_debug_fix_inline_box(
    question: dict,
    question_index: int,
    total_questions: int,
    theme: dict | None = None,
) -> tuple[str, bool]:
    try:
        from prompt_toolkit import Application
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.formatted_text import HTML as PromptHTML
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.processors import Processor
        from prompt_toolkit.layout.processors import Transformation
        from prompt_toolkit.lexers import PygmentsLexer
        from prompt_toolkit.styles import Style
        from prompt_toolkit.styles import merge_styles
        from prompt_toolkit.styles.pygments import style_from_pygments_cls
        from prompt_toolkit.widgets import Frame, TextArea
        from pygments.lexers.python import PythonLexer
        from pygments.styles import get_style_by_name
    except ModuleNotFoundError:
        raise

    active_theme = theme or select_theme("auto")
    palette = _prompt_ui_palette(active_theme)

    prompt_text = (question.get("prompt") or "").strip()
    title = html.escape(question["title"])
    safe_prompt = html.escape(prompt_text)
    safe_logo = html.escape(LOGO.strip())
    hint_text = html.escape(_default_debug_hint(question))

    state = {
        "editing": False,
        "show_hint": False,
        "hint_requested": False,
        "action_index": 0,  # 0=proceed, 1=hint
        "changed_lines_live": set(),
        "actions_focus": True,
    }

    class ChangedLineHighlighter(Processor):
        def apply_transformation(self, transformation_input):
            line_no = transformation_input.lineno + 1
            if line_no not in state["changed_lines_live"]:
                return Transformation(transformation_input.fragments)

            highlighted = []
            for fragment in transformation_input.fragments:
                if len(fragment) == 3:
                    style_name, text, handler = fragment
                    highlighted.append((f"{style_name} class:debug-changed-line".strip(), text, handler))
                else:
                    style_name, text = fragment
                    highlighted.append((f"{style_name} class:debug-changed-line".strip(), text))
            return Transformation(highlighted)

    editor = TextArea(
        text=question["broken_code"],
        multiline=True,
        line_numbers=True,
        wrap_lines=False,
        scrollbar=True,
        read_only=Condition(lambda: not state["editing"]),
        lexer=PygmentsLexer(PythonLexer),
        input_processors=[ChangedLineHighlighter()],
    )
    app = None

    def refresh():
        if app is not None:
            app.invalidate()

    def refresh_changed_lines(_buffer=None):
        state["changed_lines_live"] = set(
            _debug_changed_line_numbers(question["broken_code"], editor.text)
        )
        refresh()

    editor.buffer.on_text_changed += refresh_changed_lines
    refresh_changed_lines()

    def render_header():
        edit_mode = "ON" if state["editing"] else "OFF"
        header = (
            f"<style fg='{palette['logo']}'>{safe_logo}</style>\n\n"
            f"<style fg='{palette['accent']}'><b>Debug {question_index}/{total_questions}</b></style> "
            f"<style fg='{palette['title']}'><b>{title}</b></style>\n"
            f"<style fg='{palette['body']}'>{safe_prompt}</style>\n\n"
            f"<style fg='{palette['muted']}'>Press </style><style fg='{palette['warning']}'><b>D</b></style>"
            f"<style fg='{palette['muted']}'> to edit • </style>"
            f"<style fg='{palette['warning']}'><b>Esc</b></style><style fg='{palette['muted']}'> to lock editor and open actions • </style>"
            f"<style fg='{palette['warning']}'><b>←/→</b></style><style fg='{palette['muted']}'> or </style>"
            f"<style fg='{palette['warning']}'><b>↑/↓</b></style><style fg='{palette['muted']}'> choose action • </style>"
            f"<style fg='{palette['warning']}'><b>Enter</b></style><style fg='{palette['muted']}'> or </style>"
            f"<style fg='{palette['warning']}'><b>Space</b></style><style fg='{palette['muted']}'> activate\n"
            f"Edit mode: {edit_mode}</style>"
        )
        if state["show_hint"]:
            header += f"\n<style fg='{palette['warning']}'>Hint: {hint_text}</style>"
        return PromptHTML(header)

    def render_actions():
        if state["editing"]:
            return PromptHTML(
                f"<style fg='{palette['muted']}'>[editing] Press Esc to open actions</style>"
            )
        if state["actions_focus"]:
            proceed_style = (
                f"fg='{palette['selected_fg']}' bg='{palette['selected_bg']}'"
                if state["action_index"] == 0
                else f"fg='{palette['body']}'"
            )
            hint_style = (
                f"fg='{palette['selected_fg']}' bg='{palette['selected_bg']}'"
                if state["action_index"] == 1
                else f"fg='{palette['body']}'"
            )
        else:
            proceed_style = f"fg='{palette['muted']}'"
            hint_style = f"fg='{palette['muted']}'"
        hint_label = "Hide hint" if state["show_hint"] else "Show hint"
        base = (
            f"<style {proceed_style}><b> Proceed </b></style>    "
            f"<style {hint_style}><b> {hint_label} </b></style>"
        )
        if state["actions_focus"]:
            return PromptHTML(base)
        return PromptHTML(
            base + f"    <style fg='{palette['muted']}'>(Esc to focus actions)</style>"
        )

    header_control = FormattedTextControl(render_header)
    action_control = FormattedTextControl(render_actions)

    def render_broken_reference():
        hint_lines = set(question.get("changed_lines", [])) if state["show_hint"] else set()
        return PromptHTML(
            _numbered_code_block_markup(
                question["broken_code"],
                highlight_lines=hint_lines,
                default_style=f"fg='{palette['body']}'",
                highlight_style=f"fg='{palette['changed_fg']}' bg='{palette['changed_bg']}'",
            )
        )

    broken_control = FormattedTextControl(render_broken_reference)

    kb = KeyBindings()
    not_editing = Condition(lambda: not state["editing"])
    is_editing = Condition(lambda: state["editing"])
    actions_focused = Condition(lambda: (not state["editing"]) and state["actions_focus"])

    @kb.add("d", filter=not_editing)
    def _(event):
        state["editing"] = True
        state["actions_focus"] = False
        event.app.layout.focus(editor)
        refresh()

    @kb.add("escape", filter=is_editing)
    def _(event):
        state["editing"] = False
        state["actions_focus"] = True
        event.app.layout.focus(editor)
        refresh()

    @kb.add("escape", filter=not_editing)
    def _(event):
        state["actions_focus"] = True
        event.app.layout.focus(editor)
        refresh()

    @kb.add("left", filter=is_editing)
    def _(event):
        document = editor.buffer.document
        row = document.cursor_position_row
        col = document.cursor_position_col
        if col > 0:
            editor.buffer.cursor_left(count=1)
            refresh()
            return
        if row <= 0:
            return
        previous_line_len = len(document.lines[row - 1])
        editor.buffer.cursor_position = document.translate_row_col_to_index(
            row - 1,
            previous_line_len,
        )
        refresh()

    @kb.add("right", filter=is_editing)
    def _(event):
        document = editor.buffer.document
        row = document.cursor_position_row
        col = document.cursor_position_col
        lines = document.lines
        current_line_len = len(lines[row])
        if col < current_line_len:
            editor.buffer.cursor_right(count=1)
            refresh()
            return
        if row >= len(lines) - 1:
            return
        editor.buffer.cursor_position = document.translate_row_col_to_index(
            row + 1,
            0,
        )
        refresh()

    @kb.add("up", filter=actions_focused)
    def _(event):
        state["action_index"] = (state["action_index"] - 1) % 2
        refresh()

    @kb.add("down", filter=actions_focused)
    def _(event):
        state["action_index"] = (state["action_index"] + 1) % 2
        refresh()

    @kb.add("left", filter=actions_focused)
    def _(event):
        state["action_index"] = (state["action_index"] - 1) % 2
        refresh()

    @kb.add("right", filter=actions_focused)
    def _(event):
        state["action_index"] = (state["action_index"] + 1) % 2
        refresh()

    @kb.add("h", filter=not_editing)
    def _(event):
        state["show_hint"] = not state["show_hint"]
        state["hint_requested"] = True
        refresh()

    def activate_selected_action(event):
        if state["action_index"] == 0:
            event.app.exit(result=editor.text)
            return
        state["show_hint"] = not state["show_hint"]
        state["hint_requested"] = True
        refresh()

    @kb.add("space", filter=actions_focused)
    def _(event):
        activate_selected_action(event)

    @kb.add("enter", filter=actions_focused)
    def _(event):
        activate_selected_action(event)

    @kb.add("c-c")
    def _(event):
        event.app.exit(exception=KeyboardInterrupt())

    editor_text_style = "bg:#f7f9fc #111111" if _is_light_theme(active_theme) else "bg:#202331 #ffffff"
    style = Style.from_dict(
        {
            "frame.border": palette["border"],
            "frame.label": palette["label"],
            "textarea": editor_text_style,
            "text-area": editor_text_style,
            "debug-changed-line": f"bg:{palette['changed_bg']} {palette['changed_fg']}",
        }
    )
    syntax_style_name = "xcode" if _is_light_theme(active_theme) else "monokai"
    syntax_style = style_from_pygments_cls(get_style_by_name(syntax_style_name))
    final_style = merge_styles([syntax_style, style])
    layout = Layout(
        HSplit(
            [
                Window(content=header_control, height=10, wrap_lines=True),
                Frame(
                    Window(
                        content=broken_control,
                        wrap_lines=False,
                    ),
                    title="Broken code (reference)",
                ),
                Frame(editor, title="Your fix (line numbers on)"),
                Frame(Window(content=action_control, height=1), title="Actions"),
                Window(
                    FormattedTextControl(
                        PromptHTML(
                            f"<style fg='{palette['muted']}'>D enters edit mode. Esc locks editor and opens actions. "
                            "Use ←/→ or ↑/↓ to select Proceed/Show hint, then Enter/Space. "
                            "Changed lines are highlighted.</style>"
                        )
                    ),
                    height=1,
                ),
            ]
        ),
        focused_element=editor,
    )
    app = Application(layout=layout, key_bindings=kb, style=final_style, full_screen=True)
    try:
        answer = app.run()
    finally:
        ensure_terminal_cursor_visible()
    return (answer or ""), bool(state["hint_requested"])


def collect_debug_fix_fallback(question: dict) -> tuple[str, bool]:
    print("")
    print(LOGO)
    print(question["title"])
    print(question["prompt"])
    print("")
    print("Broken code:")
    print(_numbered_code_block(question["broken_code"]))
    print("")
    hint_used = False
    should_prompt_hint = sys.stdin.isatty()
    if should_prompt_hint and ask_yes_no("Need a hint? [y/n]: "):
        print(f"Hint: {_default_debug_hint(question)}")
        hint_used = True
    print("Type the fixed code below. Enter '/end' on a new line when finished.")
    lines: list[str] = []
    while True:
        line = prompt_input("> ")
        if line.strip().lower() == "/end":
            break
        lines.append(line)
    if not lines:
        raise RuntimeError("No debug answer was provided.")
    return ("\n".join(lines), hint_used)


def run_debug(
    title: str,
    questions: list[dict],
    theme_name: str = "auto",
    no_color: bool = False,
    show_feedback: bool = True,
    ui: str = "classic",
    ai_provider: str = DEFAULT_AI_PROVIDER,
    ai_model: str = "",
    ai_timeout: int = 30,
):
    try:
        from rich.console import Console
        from rich.panel import Panel
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Running the quiz requires rich. Install dependencies from requirements.txt."
        ) from exc

    console = Console(no_color=no_color)
    start_clean_screen(ui == "next")
    console.print(LOGO)
    theme = select_theme(theme_name)
    theme_muted = theme.get("muted", theme.get("secondary", "white"))

    intro = (
        "[bold]Rules:[/bold]\n"
        "- Press [bold]D[/bold] to unlock the editor and fix the code\n"
        "- Line numbers are shown by default\n"
        "- Press [bold]Esc[/bold] to open actions\n"
        "- In actions, choose [bold]Proceed[/bold] or [bold]Show hint[/bold] with [bold]↑/↓[/bold] then [bold]Enter[/bold]\n"
        "- Scoring: 1 point per fixed error line\n"
        "- Press [bold]Ctrl+C[/bold] to exit at any time\n\n"
        f"[bold {theme['accent']}]Press Enter to start debugging.[/bold {theme['accent']}]"
    )
    console.print(
        Panel(
            f"[bold {theme['primary']}]{title}[/bold {theme['primary']}]\n\n{intro}",
            border_style=theme["panel"],
        )
    )
    prompt_input()

    total_points = 0
    total_possible = 0
    solved_count = 0
    debug_answers: list[dict] = []
    ai_provider_label = ""

    requested_provider = str(ai_provider or DEFAULT_AI_PROVIDER)
    provider_candidates, unsupported_debug_provider = _select_debug_ai_candidates(ai_provider)
    debug_ai_enabled = bool(provider_candidates) and bool(sys.stdin.isatty() and sys.stdout.isatty())
    if unsupported_debug_provider:
        console.print(
            f"[{theme_muted}]Debug semantic fallback is unavailable for the requested provider. "
            "Continuing with deterministic scoring.[/]"
        )
    if debug_ai_enabled:
        ai_lines = []
        for provider in provider_candidates:
            key_name = _env_key_for_provider(provider)
            if os.environ.get(key_name, "").strip():
                ai_lines.append(f"{provider} ({key_name})")
        if ai_lines:
            ai_provider_label = ", ".join(ai_lines)
        else:
            debug_ai_enabled = False
            provider_name, key_name = _debug_missing_key_hint(
                requested_provider,
                provider_candidates,
                ai_lines,
            )
            if provider_name and key_name:
                console.print(
                    f"[{theme_muted}]Debug semantic fallback for '{provider_name}' requires {key_name}. "
                    "Continuing with deterministic scoring.[/]"
                )
                console.print(f"[{theme_muted}]Set it before running, e.g.:[/]")
                console.print(f"[{theme_muted}]{_platform_setup_hint_for_env_key(key_name)}[/]")

    for i, question in enumerate(questions, start=1):
        try:
            if sys.stdin.isatty() and sys.stdout.isatty():
                student_code, used_hint = collect_debug_fix_inline_box(
                    question,
                    question_index=i,
                    total_questions=len(questions),
                    theme=theme,
                )
            else:
                student_code, used_hint = collect_debug_fix_fallback(question)
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Interactive debug mode requires prompt_toolkit. Install dependencies from requirements.txt."
            ) from exc

        grading = _score_debug_submission(
            question["broken_code"],
            question["fixed_code"],
            student_code,
        )
        if not grading["is_perfect"] and debug_ai_enabled:
            ai_applied = False
            ai_failure: tuple[str, str] | None = None
            for idx, provider in enumerate(provider_candidates):
                key_name = _env_key_for_provider(provider)
                api_key = os.environ.get(key_name, "").strip()
                if not api_key:
                    continue
                model_for_provider = _debug_model_for_provider(
                    requested_provider,
                    ai_model,
                    provider,
                    idx,
                )
                evaluator = _debug_evaluator_for_provider(provider)
                try:
                    review = _evaluate_with_loading_message(
                        console,
                        theme,
                        evaluator,
                        "Reviewing your answer...",
                        question,
                        student_code,
                        grading,
                        api_key=api_key,
                        model=model_for_provider,
                        timeout=ai_timeout,
                    )
                    grading = _apply_debug_ai_override(grading, review, provider)
                    ai_applied = True
                    break
                except Exception as exc:
                    reason_code = _reason_code_from_provider_exception(exc)
                    note = _redacted_ai_error(reason_code, True)
                    if reason_code in {"rate_limit", "server_error", "timeout", "network_error"}:
                        note += " This is usually temporary. Please try again later."
                    ai_failure = (provider, note)
                    if ai_provider != "auto":
                        break
                    continue
            if not ai_applied and ai_failure:
                failed_provider, note = ai_failure
                grading = dict(grading)
                grading["ai_reviewed"] = True
                grading["ai_accepted"] = False
                grading["ai_provider"] = failed_provider
                grading["ai_reason"] = note
                grading["ai_confidence"] = "low"
        total_points += grading["question_points"]
        total_possible += grading["question_max_points"]
        if grading["is_perfect"]:
            solved_count += 1
        question_text = (question.get("question_text") or question.get("prompt") or "").strip()
        debug_answers.append(
            {
                "question_title": question["title"],
                "question_text": question_text,
                "broken_code": question["broken_code"],
                "fixed_code": question["fixed_code"],
                "student_code": student_code,
                "changed_lines": grading["changed_lines"],
                "question_points": grading["question_points"],
                "question_max_points": grading["question_max_points"],
                "is_perfect": grading["is_perfect"],
                "exact_match": grading.get("exact_match", False),
                "semantic_match": grading.get("semantic_match", False),
                "scoring_mode": grading.get("scoring_mode", "line_exact"),
                "ai_reviewed": grading.get("ai_reviewed", False),
                "ai_accepted": grading.get("ai_accepted", False),
                "ai_provider": grading.get("ai_provider", ""),
                "ai_reason": grading.get("ai_reason", ""),
                "ai_confidence": grading.get("ai_confidence", ""),
                "used_hint": used_hint,
            }
        )

        if grading["is_perfect"]:
            status = "Correct"
            status_style = theme["success"]
        elif grading["question_points"] > 0:
            status = "Partially Correct"
            status_style = theme["accent"]
        else:
            status = "Wrong"
            status_style = theme["danger"]

        summary_lines = [
            f"[{status_style}]{status}[/{status_style}]",
            f"Question points: [bold]{grading['question_points']}/{grading['question_max_points']}[/bold]",
        ]
        if grading.get("semantic_match") and not grading.get("exact_match"):
            summary_lines.append(
                f"[{theme['secondary']}]Accepted equivalent Python fix (AST match).[/]"
            )
        if grading.get("ai_accepted"):
            provider = grading.get("ai_provider", "gemini")
            confidence = grading.get("ai_confidence", "medium")
            summary_lines.append(
                f"[{theme['secondary']}]Accepted by AI semantic check ({provider}, confidence: {confidence}).[/]"
            )
        elif grading.get("ai_reviewed") and grading.get("ai_reason"):
            summary_lines.append(
                f"[{theme_muted}]AI review note: {grading['ai_reason']}[/]"
            )
        if used_hint:
            summary_lines.append(f"[{theme['secondary']}]Hint used[/]")
        console.print(Panel("\n".join(summary_lines), border_style=theme["panel"]))

        if show_feedback:
            expected_lines = _render_debug_expected_lines(
                question["fixed_code"],
                grading["changed_lines"],
            )
            feedback_lines = [
                f"[bold {theme['secondary']}]Correct lines[/bold {theme['secondary']}]:",
                expected_lines,
            ]
            explanation = (question.get("explanation") or "").strip()
            if explanation:
                feedback_lines.append("")
                feedback_lines.append(f"[bold {theme['secondary']}]Explanation[/bold {theme['secondary']}]:")
                feedback_lines.append(explanation)
            console.print(Panel("\n".join(feedback_lines), border_style=theme["panel"]))

            if not grading["is_perfect"]:
                console.print(
                    Panel(
                        _numbered_code_block(question["fixed_code"]),
                        title="[bold]Correct answer[/bold]",
                        border_style=theme["accent"],
                    )
                )

        if i < len(questions):
            prompt_input("Press Enter for the next debug question...")

    percentage = (total_points / total_possible) * 100 if total_possible else 0.0
    completion_text = f"{len(debug_answers)}/{len(questions)} questions"
    console.print(
        Panel(
            f"[bold {theme['primary']}]Debug Summary[/bold {theme['primary']}]\n\n"
            f"Result: [bold {theme['success']}]Completed[/bold {theme['success']}]\n"
            f"Completion: [bold]{completion_text}[/bold]\n"
            f"Score: [bold]{total_points}/{total_possible}[/bold]\n"
            f"Percentage: [bold]{percentage:.1f}%[/bold]\n"
            f"Perfect fixes: [bold]{solved_count}/{len(questions)}[/bold]"
            + (
                f"\nAI fallback: deterministic first, then provider semantic review on failures"
                + (f" ({ai_provider_label})" if ai_provider_label else "")
                if debug_ai_enabled
                else ""
            ),
            border_style=theme["panel"],
        )
    )

    if ask_to_save_answers():
        try:
            attempt_dir = save_debug_attempt(
                title,
                total_points,
                total_possible,
                debug_answers,
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


def run(
    title,
    questions,
    theme_name: str = "auto",
    no_color: bool = False,
    full_screen: bool = False,
    ui: str = "classic",
    show_feedback: bool = True,
    quiz_mode: str = "mcq",
    ai_provider: str = DEFAULT_AI_PROVIDER,
    ai_model: str = "",
    ai_timeout: int = 30,
):
    try:
        from rich.console import Console
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.panel import Panel
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Running the quiz requires rich. Install dependencies from requirements.txt."
        ) from exc

    console = Console(no_color=no_color)
    start_clean_screen(ui == "next")
    console.print(LOGO)

    theme = select_theme(theme_name)
    quiz_has_imposters = any(bool(q.get("imposters")) for q in questions)
    has_multiple = any(str(q.get("type", "single")) == "multiple" for q in questions)
    has_single = any(str(q.get("type", "single")) != "multiple" for q in questions)
    saved_answers = []

    try:
        millionaire_ai_settings = _resolve_millionaire_ai_settings(ai_provider, ai_model) if quiz_mode == "millionaire" else {}
        millionaire_ai_enabled = bool(millionaire_ai_settings.get("enabled"))
        millionaire_friend_name = "Friend"
        if quiz_mode == "millionaire" and questions:
            millionaire_friend_name = str(questions[0].get("friend_name") or "Friend").strip() or "Friend"

        rule_lines = ["[bold]Rules:[/bold]"]
        if quiz_mode == "millionaire":
            rule_lines.append("- 15-question points ladder to 1,000,000")
            rule_lines.append("- Pick one best answer per question")
            rule_lines.append(
                "- Use [bold]↑/↓[/bold] to move, press [bold]Space[/bold] to select, "
                "[bold]Enter[/bold] to submit, [bold]Q[/bold] to quit with current points"
            )
            rule_lines.append(
                f"- Lifelines: [bold]F[/bold]=50-50, [bold]A[/bold]=Ask the People, "
                f"[bold]C[/bold]=Ask {millionaire_friend_name} (once each)"
            )
            if millionaire_ai_enabled:
                provider_chip = str(millionaire_ai_settings.get("provider_name") or "AI")
                rule_lines.append(
                    f"- Optional: [bold]D[/bold]=Ask AI ({provider_chip}) "
                    "(once, only when AI key is configured)"
                )
                rule_lines.append(
                    f"- AI status: [bold {theme['success']}]Connected[/bold {theme['success']}] ({provider_chip})"
                )
            rule_lines.append(
                f"- You have up to [bold]{MILLIONAIRE_MAX_TIME_LIMIT_SECONDS}s[/bold] per question"
            )
            rule_lines.append("- If Time is set in file, it is capped at 120s")
            rule_lines.append("- One wrong answer ends the game")
            rule_lines.append("- Safety nets: Q2, Q5, Q10, Q15")
        elif quiz_has_imposters:
            rule_lines.append("- Select correct answer(s) and flag misleading options (those are there to trick you)")
            rule_lines.append(
                "- Use [bold]↑/↓[/bold] to move, [bold]Space[/bold] for correct choices, "
                "[bold]X[/bold] for imposters, [bold]Enter[/bold] to submit, [bold]Q[/bold] to quit"
            )
            rule_lines.append("- Imposter scoring: +1 correct flag, -1 false flag (minimum 0 imposter points)")
        elif has_multiple and not has_single:
            rule_lines.append("- Select all options you believe are correct")
            rule_lines.append(
                "- Use [bold]↑/↓[/bold] to move, [bold]Space[/bold] to toggle choices, "
                "[bold]Enter[/bold] to submit, [bold]Q[/bold] to quit"
            )
            rule_lines.append("- You get points when your final set matches the expected correct set")
        elif has_single and not has_multiple:
            rule_lines.append("- Pick the one best answer")
            rule_lines.append(
                "- Use [bold]↑/↓[/bold] to move, press [bold]Space[/bold] to select, "
                "[bold]Enter[/bold] to submit, [bold]Q[/bold] to quit"
            )
            rule_lines.append("- Correct answer gives full question points")
        else:
            rule_lines.append("- Questions include single-choice and multiple-choice items")
            rule_lines.append(
                "- Use [bold]↑/↓[/bold] to move, [bold]Space[/bold] to select/toggle, "
                "[bold]Enter[/bold] to submit, [bold]Q[/bold] to quit"
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
        millionaire_current_points = 0
        millionaire_guaranteed_points = 0
        millionaire_lost = False
        millionaire_cashed_out = False
        millionaire_cashout_question = 0
        millionaire_lost_on_question = 0
        millionaire_lost_on_value = 0
        user_quit = False
        quit_on_question = 0
        millionaire_state = (
            {
                "fifty_fifty_used": False,
                "ask_people_used": False,
                "call_friend_used": False,
                "usage_by_question": {},
                "messages_by_question": {},
                "current_points": millionaire_current_points,
                "guaranteed_points": millionaire_guaranteed_points,
                "current_question_points": 0,
                "is_safety_net_question": False,
            }
            if quiz_mode == "millionaire"
            else None
        )

        for i, q in enumerate(questions, start=1):
            if i > 1 and not full_screen:
                console.print("\n")

            if quiz_mode == "millionaire" and millionaire_state is not None:
                q_points = _millionaire_points_for_question(i, len(questions))
                millionaire_state["current_points"] = millionaire_current_points
                millionaire_state["guaranteed_points"] = millionaire_guaranteed_points
                millionaire_state["current_question_points"] = q_points
                millionaire_state["is_safety_net_question"] = i in MILLIONAIRE_SAFETY_NET_QUESTIONS

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
                    show_feedback=show_feedback,
                    quiz_mode=quiz_mode,
                    millionaire_state=millionaire_state,
                    ai_provider=ai_provider,
                    ai_model=ai_model,
                    ai_timeout=ai_timeout,
                )
            )

            if quiz_mode == "millionaire" and grading.get("quit_with_points"):
                millionaire_cashed_out = True
                millionaire_cashout_question = i
                console.print(
                    Panel(
                        f"[bold {theme['accent']}]You cashed out.[/bold {theme['accent']}]\n"
                        f"You leave with current winnings: [bold]{_format_points(millionaire_current_points)}[/bold].\n"
                        f"Guaranteed floor remains: [bold]{_format_points(millionaire_guaranteed_points)}[/bold].",
                        border_style=theme["accent"],
                    )
                )
                break
            if grading.get("quit_requested"):
                user_quit = True
                quit_on_question = i
                console.print(
                    Panel(
                        f"[bold {theme['accent']}]You quit the quiz.[/bold {theme['accent']}]\n"
                        "Progress so far is kept in your summary.",
                        border_style=theme["accent"],
                    )
                )
                break

            selected_labels = format_labels(q["options"], ans)
            correct_labels = format_labels(q["options"], q["correct"])
            selected_imposter_labels = format_labels(q["options"], imposter_ans)
            expected_imposter_labels = format_labels(q["options"], q.get("imposters", []))
            expected_answer_labels, expected_imposter_feedback_labels = format_imposter_feedback(
                q["options"],
                q["correct"],
                q.get("imposters", []),
            )
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
                if quiz_mode == "millionaire":
                    q_points = _millionaire_points_for_question(i, len(questions))
                    if grading["answer_correct"]:
                        millionaire_current_points = q_points
                        if i in MILLIONAIRE_SAFETY_NET_QUESTIONS:
                            millionaire_guaranteed_points = millionaire_current_points
                            console.print(
                                f"[{theme['accent']}]🛟 Safety Net reached! "
                                f"Guaranteed points locked: {_format_points(millionaire_guaranteed_points)}[/]"
                            )
                    else:
                        millionaire_lost = True
                        millionaire_lost_on_question = i
                        millionaire_lost_on_value = q_points
                    console.print(
                        f"[{theme['secondary']}]Winnings:[/{theme['secondary']}] "
                        f"{_format_points(millionaire_current_points)}"
                    )
                    console.print(
                        f"[{theme['secondary']}]Guaranteed:[/{theme['secondary']}] "
                        f"{_format_points(millionaire_guaranteed_points)}"
                    )
                    console.print(
                        f"[{theme['secondary']}]Question value:[/{theme['secondary']}] "
                        f"{_format_points(q_points)}"
                    )
                else:
                    console.print(
                        f"[{theme['secondary']}]Question points:[/{theme['secondary']}] "
                        f"{grading['question_points']}/{grading['question_max_points']}"
                    )
            elif quiz_mode == "millionaire":
                q_points = _millionaire_points_for_question(i, len(questions))
                if grading["answer_correct"]:
                    millionaire_current_points = q_points
                    if i in MILLIONAIRE_SAFETY_NET_QUESTIONS:
                        millionaire_guaranteed_points = millionaire_current_points
                else:
                    millionaire_lost = True
                    millionaire_lost_on_question = i
                    millionaire_lost_on_value = q_points

            if show_feedback and not full_screen:
                console.print(
                    f"[{theme['secondary']}]Answer:[/{theme['secondary']}] "
                    f"{expected_answer_labels}"
                )
                if q.get("imposters"):
                    console.print(
                        f"[{theme['secondary']}]Imposter:[/{theme['secondary']}] "
                        f"{expected_imposter_feedback_labels}"
                    )

            if show_feedback and not full_screen and q.get("explanation"):
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
                "lifelines_used": (
                    list((millionaire_state or {}).get("usage_by_question", {}).get(str(i), []))
                    if quiz_mode == "millionaire"
                    else []
                ),
                "current_points_after_question": millionaire_current_points if quiz_mode == "millionaire" else 0,
                "guaranteed_points_after_question": millionaire_guaranteed_points if quiz_mode == "millionaire" else 0,
            })

            if quiz_mode == "millionaire" and millionaire_lost:
                console.print(
                    Panel(
                        f"[bold {theme['danger']}]You lost.[/bold {theme['danger']}]\n"
                        f"Wrong on question [bold]{millionaire_lost_on_question}[/bold] "
                        f"({_format_points(millionaire_lost_on_value)} points).\n"
                        f"You leave with guaranteed points: [bold]{_format_points(millionaire_guaranteed_points)}[/bold].",
                        border_style=theme["danger"],
                    )
                )
                break

            if not full_screen and i < len(questions):
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
        millionaire_lifeline_summary = ""
        if quiz_mode == "millionaire" and millionaire_state is not None:
            ff = "used" if millionaire_state.get("fifty_fifty_used") else "unused"
            ap = "used" if millionaire_state.get("ask_people_used") else "unused"
            cf = "used" if millionaire_state.get("call_friend_used") else "unused"
            ai_used = "used" if millionaire_state.get("ask_ai_used") else "unused"
            millionaire_lifeline_summary = (
                f"Lifelines: [bold]50-50 {ff}[/bold], "
                f"[bold]Ask {ap}[/bold], [bold]Ask {millionaire_friend_name} {cf}[/bold]"
                + (
                    f", [bold]Ask AI {ai_used}[/bold]"
                    if millionaire_ai_enabled
                    else ""
                )
                + "\n"
            )
        millionaire_score_line = ""
        if quiz_mode == "millionaire":
            if millionaire_lost:
                final_points = millionaire_guaranteed_points
            else:
                final_points = millionaire_current_points
            millionaire_score_line = (
                f"Final Winnings: [bold]{_format_points(final_points)}[/bold]\n"
                f"Guaranteed Floor: [bold]{_format_points(millionaire_guaranteed_points)}[/bold]\n"
                + (
                    f"Result: [bold {theme['danger']}]Lost on Q{millionaire_lost_on_question}[/bold {theme['danger']}]\n"
                    if millionaire_lost
                    else (
                        f"Result: [bold {theme['accent']}]Cashed out on Q{millionaire_cashout_question}[/bold {theme['accent']}]\n"
                        if millionaire_cashed_out
                        else f"Result: [bold {theme['success']}]Game complete[/bold {theme['success']}]\n"
                    )
                )
            )
        base_result_line = ""
        if quiz_mode != "millionaire":
            if user_quit:
                base_result_line = f"Result: [bold {theme['accent']}]Quit on Q{quit_on_question}[/bold {theme['accent']}]\n"
            else:
                base_result_line = "Result: [bold {theme['success']}]Completed[/bold {theme['success']}]\n"

        millionaire_won = (
            quiz_mode == "millionaire"
            and len(questions) > 0
            and correct_answers_count == len(questions)
        )
        if millionaire_won:
            _play_win_confetti(console, theme, no_color=no_color, duration_seconds=1.2)
            console.print(
                Panel(
                    f"[bold {theme['success']}]Congrats, you won![/bold {theme['success']}]",
                    border_style=theme["success"],
                )
            )

        score_line = (
            f"Score: [bold]{points_earned}/{total_points_possible}[/bold]\n"
            if total_points_possible
            else f"Score: [bold]{points_earned}/0[/bold]\n"
        )

        summary = (
            f"[bold {theme['primary']}]Quiz Summary[/bold {theme['primary']}]\n\n"
            f"{base_result_line}"
            f"{score_line}"
            f"Percentage: [bold]{percentage:.1f}%[/bold]\n"
            f"Correct Answers: [bold]{correct_answers_count}[/bold]\n"
            + millionaire_score_line
            + millionaire_lifeline_summary
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
        render_exit_message("Quiz closed. Thanks for trying QuizMD.", no_color=no_color)


def run_challenge(
    title: str,
    categories: list[dict],
    theme_name: str = "auto",
    no_color: bool = False,
    full_screen: bool = False,
    ui: str = "classic",
    show_feedback: bool = True,
):
    try:
        from rich.console import Console
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.table import Table
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Running the quiz requires rich. Install dependencies from requirements.txt."
        ) from exc

    if not categories:
        raise RuntimeError("Challenge mode requires at least one category.")

    theme = select_theme(theme_name)
    console = Console(no_color=no_color)
    start_clean_screen(ui == "next")
    console.print(LOGO)

    challenge_results: dict[int, dict] = {}
    challenge_quit = False
    challenge_quit_reason = ""
    difficulty_choices = [
        ("easy", "⭐ Easy", "Safer distractors, 1 star on correct answer."),
        ("normal", "⭐⭐ Normal", "Balanced distractors, 2 stars on correct answer."),
        ("hard", "⭐⭐⭐ Hard", "Hard distractors, 3 stars on correct answer."),
    ]
    difficulty_aliases = {
        "1": "easy",
        "easy": "easy",
        "e": "easy",
        "2": "normal",
        "normal": "normal",
        "n": "normal",
        "3": "hard",
        "hard": "hard",
        "h": "hard",
    }

    try:
        intro_lines = [
            "[bold]Rules:[/bold]",
            "- Pick one category at a time.",
            "- Choose your risk level: Easy ⭐, Normal ⭐⭐, Hard ⭐⭐⭐.",
            "- Correct answer earns stars equal to chosen difficulty.",
            "- Incorrect answer earns 0 stars.",
            "- One attempt per category (category is then locked).",
            "- In question screens: [bold]Space[/bold]=select, [bold]Enter[/bold]=confirm, [bold]Q[/bold]=quit.",
            "- In board prompts type [bold]Q[/bold] to quit and keep progress.",
            "- Press [bold]Ctrl+C[/bold] to exit at any time.",
            "",
            "Press Enter to start your challenge board.",
        ]
        console.print(
            Panel(
                f"[bold {theme['primary']}]Challenge Quiz: {title}[/bold {theme['primary']}]\n\n"
                + "\n".join(intro_lines),
                border_style=theme["panel"],
            )
        )
        prompt_input()

        while len(challenge_results) < len(categories):
            start_clean_screen(ui == "next")
            console.print(LOGO)

            total_stars_now = sum(item["stars_earned"] for item in challenge_results.values())
            board = Table(show_header=True, header_style=f"bold {theme['primary']}")
            board.add_column("#", style=theme["secondary"], justify="right", width=3)
            board.add_column("Category", style=theme["primary"])
            board.add_column("Status", style=theme["accent"])
            board.add_column("Stars", style=theme["success"], justify="center")
            selectable: dict[int, int] = {}
            for idx, category in enumerate(categories):
                category_name = category["category"]
                display_number = idx + 1
                result = challenge_results.get(idx)
                if result is None:
                    status = "Pending"
                    stars_label = "⏳ (0)"
                    display_index = str(display_number)
                    selectable[display_number] = idx
                else:
                    status = "Completed"
                    stars_label = f"{_challenge_star_badge(result['stars_earned'])} ({result['stars_earned']})"
                    display_index = str(display_number)
                board.add_row(display_index, category_name, status, stars_label)

            console.print(
                Panel(
                    board,
                    title=f"[bold {theme['primary']}]Category Board[/bold {theme['primary']}]",
                    subtitle=f"[{theme['accent']}]Current stars: {total_stars_now}/{len(categories) * 3}[/{theme['accent']}]",
                    border_style=theme["panel"],
                )
            )

            chosen_category_idx = None
            while chosen_category_idx is None:
                raw = prompt_input("Choose a pending category number: ").strip()
                if raw.lower() in {"q", "quit"}:
                    challenge_quit = True
                    challenge_quit_reason = "Exited from category board"
                    break
                if not raw:
                    console.print(
                        f"[{theme['danger']}]Please enter a category number or name.[/{theme['danger']}]"
                    )
                    continue
                pending_names = {idx: categories[idx]["category"] for idx in selectable.values()}
                lowered = raw.casefold()
                exact = [idx for idx, name in pending_names.items() if name.casefold() == lowered]
                prefix = [idx for idx, name in pending_names.items() if name.casefold().startswith(lowered)]

                # Numeric input primarily maps to the displayed pending index.
                # If that misses, still allow exact/prefix name matching (e.g. category name "101").
                if raw.isdigit():
                    chosen_category_idx = selectable.get(int(raw))
                    if chosen_category_idx is not None:
                        continue
                if len(exact) == 1:
                    chosen_category_idx = exact[0]
                elif len(prefix) == 1:
                    chosen_category_idx = prefix[0]
                elif len(prefix) > 1:
                    console.print(
                        f"[{theme['danger']}]That matches multiple categories. Type the full name or number.[/{theme['danger']}]"
                    )
                    continue
                if chosen_category_idx is None:
                    console.print(
                        f"[{theme['danger']}]That category is not available. Use a pending number or name.[/{theme['danger']}]"
                    )
            if challenge_quit:
                break

            category = categories[chosen_category_idx]
            category_name = category["category"]

            start_clean_screen(ui == "next")
            console.print(LOGO)
            difficulty_table = Table(show_header=True, header_style=f"bold {theme['primary']}")
            difficulty_table.add_column("#", style=theme["secondary"], justify="right", width=3)
            difficulty_table.add_column("Difficulty", style=theme["primary"])
            difficulty_table.add_column("Risk/Reward", style=theme["accent"])
            for idx, (_key, label, desc) in enumerate(difficulty_choices, start=1):
                difficulty_table.add_row(str(idx), label, desc)
            console.print(
                Panel(
                    difficulty_table,
                    title=f"[bold {theme['primary']}]Category: {category_name}[/bold {theme['primary']}]",
                    border_style=theme["panel"],
                )
            )

            chosen_diff_key = None
            while chosen_diff_key is None:
                raw = prompt_input("Choose difficulty (1-3): ").strip()
                if raw.lower() in {"q", "quit"}:
                    challenge_quit = True
                    challenge_quit_reason = f"Exited before answering category '{category_name}'"
                    break
                mapped = difficulty_aliases.get(raw.casefold())
                if mapped:
                    chosen_diff_key = mapped
                else:
                    console.print(
                        f"[{theme['danger']}]Please choose 1/2/3 or easy/normal/hard.[/{theme['danger']}]"
                    )
            if challenge_quit:
                break

            question = dict(category["difficulties"][chosen_diff_key])
            question["title"] = f"{category_name} ({_challenge_difficulty_text(chosen_diff_key)})"
            raw_limit = question.get("time_limit")
            try:
                parsed_limit = int(raw_limit) if raw_limit is not None else 0
            except (TypeError, ValueError):
                parsed_limit = 0
            if parsed_limit <= 0:
                question["time_limit"] = CHALLENGE_DEFAULT_TIME_LIMIT_SECONDS

            perfect, ans, _imposter_ans, grading = run_coroutine_sync(
                ask_question(
                    question,
                    theme,
                    question_index=len(challenge_results) + 1,
                    total_questions=len(categories),
                    no_color=no_color,
                    compact=False,
                    full_screen=full_screen,
                    ui=ui,
                    show_feedback=show_feedback,
                )
            )
            if grading.get("quit_requested"):
                challenge_quit = True
                challenge_quit_reason = f"Exited on question in category '{category_name}'"
                break

            stars_for_diff = CHALLENGE_STARS_BY_DIFFICULTY[chosen_diff_key]
            stars_earned = stars_for_diff if grading["answer_correct"] else 0
            expected_labels = format_labels(question["options"], question["correct"])
            selected_labels = format_labels(question["options"], ans)
            challenge_results[chosen_category_idx] = {
                "category": category_name,
                "difficulty": chosen_diff_key,
                "stars_earned": stars_earned,
                "is_correct": bool(grading["answer_correct"]),
                "selected_indexes": ans or [],
                "selected_labels": selected_labels,
                "expected_indexes": question["correct"],
                "expected_labels": expected_labels,
                "question_text": question["question"],
                "explanation": question.get("explanation", ""),
                "result_label": "Correct" if grading["answer_correct"] else "Wrong",
            }

            status = "Correct" if grading["answer_correct"] else "Wrong"
            status_style = question_status_style(theme, status)
            if not full_screen:
                console.print(f"[{status_style}]{status}[/{status_style}]")
                console.print(
                    f"[{theme['secondary']}]Question points:[/{theme['secondary']}] "
                    f"{grading['question_points']}/{grading['question_max_points']}"
                )
                if show_feedback:
                    console.print(
                        f"[{theme['secondary']}]Answer:[/{theme['secondary']}] "
                        f"{expected_labels}"
                    )
                if show_feedback and question.get("explanation"):
                    console.print(
                        Panel(
                            Markdown(f"**Explanation**\n\n{question['explanation']}"),
                            border_style=theme["panel"],
                        )
                    )

            result_color = theme["success"] if stars_earned > 0 else theme["danger"]
            console.print(
                Panel(
                    f"Category: [bold]{category_name}[/bold]\n"
                    f"Difficulty: [bold]{_challenge_difficulty_text(chosen_diff_key)}[/bold]\n"
                    f"Stars earned: [bold]{_challenge_star_badge(stars_earned)} ({stars_earned})[/bold]",
                    border_style=result_color,
                )
            )

            remaining = len(categories) - len(challenge_results)
            if remaining > 0:
                prompt_input("Press Enter to return to the category board...")

        total_stars = sum(item["stars_earned"] for item in challenge_results.values())
        correct_count = sum(1 for item in challenge_results.values() if item["is_correct"])
        solved_levels = [item["difficulty"] for item in challenge_results.values() if item["is_correct"]]
        if "hard" in solved_levels:
            highest_solved = "⭐⭐⭐ Hard"
        elif "normal" in solved_levels:
            highest_solved = "⭐⭐ Normal"
        elif "easy" in solved_levels:
            highest_solved = "⭐ Easy"
        else:
            highest_solved = "None"

        ordered_results = [challenge_results[idx] for idx in sorted(challenge_results)]
        stars_rows = "\n".join(
            f"- {item['category']}: {_challenge_star_badge(item['stars_earned'])}"
            for item in ordered_results
        )
        if not stars_rows:
            stars_rows = "- No categories completed yet."
        if challenge_quit:
            result_line = f"[bold {theme['accent']}]Quit early[/bold {theme['accent']}]"
            if challenge_quit_reason:
                result_line += f" ({challenge_quit_reason})"
        else:
            result_line = f"[bold {theme['success']}]Completed[/bold {theme['success']}]"
        completion_text = f"{len(challenge_results)}/{len(categories)} categories attempted"
        console.print(
            Panel(
                f"[bold {theme['primary']}]Challenge Summary[/bold {theme['primary']}]\n\n"
                f"Result: {result_line}\n"
                f"Completion: [bold]{completion_text}[/bold]\n"
                f"Total stars: [bold]{total_stars}/{len(categories) * 3}[/bold]\n"
                f"Correct categories: [bold]{correct_count}/{len(categories)}[/bold]\n"
                f"Highest difficulty solved: [bold]{highest_solved}[/bold]\n\n"
                f"[bold]Stars by category[/bold]\n{stars_rows}",
                border_style=theme["panel"],
            )
        )
        perfect_total_stars = len(categories) * 3
        if correct_count == len(categories) and total_stars == perfect_total_stars:
            confetti = " *ੈ✩‧₊˚༘˚⋆𐙚｡⋆𖦹.✧˚ "
            console.print(
                Panel(
                    f"[bold {theme['success']}]Perfect challenge run![/bold {theme['success']}]\n"
                    f"{confetti}\n"
                    f"[bold]{perfect_total_stars}/{perfect_total_stars} stars[/bold] — all categories solved at max difficulty!",
                    border_style=theme["success"],
                )
            )

        if ask_to_save_answers():
            attempt_dir = save_challenge_attempt(
                title,
                total_stars,
                categories,
                ordered_results,
            )
            console.print(
                Panel(
                    f"[bold {theme['success']}]Answers saved successfully.[/bold {theme['success']}]\n{attempt_dir}",
                    border_style=theme["success"],
                )
            )
    except KeyboardInterrupt:
        render_exit_message("Challenge quiz closed. Thanks for playing.", no_color=no_color)


def run_chaos(
    title: str,
    chaos: dict,
    theme_name: str = "auto",
    no_color: bool = False,
    ui: str = "classic",
):
    try:
        from rich.console import Console
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.panel import Panel
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Running the quiz requires rich. Install dependencies from requirements.txt."
        ) from exc

    theme = select_theme(theme_name)
    console = Console(no_color=no_color)
    start_clean_screen(ui == "next")
    console.print(LOGO)
    quit_early = False
    quit_reason = ""
    started_at = time.time()
    path_taken_steps: list[str] = []
    recoveries_succeeded = 0
    chaos_steps_total = 3
    selection_history: list[str] = []
    score_breakdown: list[dict] = []
    chaos_sidebar_width = 68

    def append_selection_history(step_label: str, selected_text: str, correct: bool, points_earned: int) -> None:
        mark = "✓" if correct else "✗"
        selection_history.append(
            f"{step_label} {mark} +{points_earned} ({earned}/{maximum}): {selected_text}"
        )

    def prompt_choice(
        question_block: dict,
        *,
        step_title: str,
        step_index: int,
        total_steps: int,
    ) -> str:
        def chaos_status_text() -> str:
            elapsed = max(0, int(time.time() - started_at))
            minutes, seconds = divmod(elapsed, 60)
            path_text = " \u2192 ".join(path_taken_steps) if path_taken_steps else "Start"
            history_block = ""
            if selection_history:
                history_width = max(18, chaos_sidebar_width - 8)
                lines = [f"| - {truncate_for_display(item, history_width)}" for item in selection_history[-3:]]
                history_block = "\n| Picks:\n" + "\n".join(lines)
            return (
                "Chaos Status\n\n"
                "Mode: Chaos\n"
                f"| Step: {step_index} / {total_steps}\n"
                f"| Score: {earned}/{maximum}\n"
                f"| Recoveries: {recoveries_succeeded}\n"
                f"| Path: {path_text}\n"
                f"| Time: {minutes:02d}:{seconds:02d}"
                f"{history_block}"
            )

        options = question_block["options"]
        option_texts = [item["text"] for item in options]
        option_labels = [item["label"] for item in options]
        while True:
            chaos_question = {
                "title": step_title,
                "question": question_block["question"],
                "options": option_texts,
                "correct": [option_labels.index(question_block["answer"]) + 1],
                "type": "single",
                "time_limit": 1,
                "explanation": "",
                "imposters": [],
            }
            _perfect, ans, _imposters, grading = run_coroutine_sync(
                ask_question(
                    chaos_question,
                    theme,
                    question_index=step_index,
                    total_questions=total_steps,
                    no_color=no_color,
                    compact=False,
                    full_screen=False,
                    ui=ui,
                    show_feedback=False,
                    quiz_mode="chaos",
                    untimed=True,
                    status_sidebar_renderer=chaos_status_text,
                    status_sidebar_width=chaos_sidebar_width,
                )
            )
            if grading.get("quit_requested"):
                return "__QUIT__"
            if ans:
                chosen_index = int(ans[0])
                if 1 <= chosen_index <= len(option_labels):
                    return option_labels[chosen_index - 1]
            console.print(
                f"[{theme['danger']}]Please select one option with Space, then press Enter.[/{theme['danger']}]"
            )

    def option_text_for_label(question_block: dict, label: str) -> str:
        for item in question_block["options"]:
            if item["label"] == label:
                return item["text"]
        return label

    def show_chaos_event_transition(selected_text: str) -> None:
        panel_body = "Oh no...\nA chaos event was triggered."
        console.print(
            Panel(
                panel_body,
                title=f"[bold {theme['danger']}]Chaos Alert[/bold {theme['danger']}]",
                border_style=theme["danger"],
            )
        )
        if sys.stdin.isatty() and sys.stdout.isatty():
            prompt_input("Press Enter to see what happened.")

    def show_next_stage_transition(
        *,
        title: str,
        subtitle: str,
        badge_frames: list[str],
        prompt: str,
    ) -> None:
        _ = (title, subtitle, badge_frames)
        if sys.stdin.isatty() and sys.stdout.isatty():
            prompt_input(prompt)

    def result_band(score_value: int) -> str:
        for tier in chaos["result"]["tiers"]:
            if tier["min"] <= score_value <= tier["max"]:
                return tier["text"]
        return "No result band matched this score."

    earned = 0
    maximum = int(chaos["result"]["maximum_score"])

    console.print(
        Panel(
            Markdown(
                chaos["scenario"]
                + "\n\n---\n"
                + "Rules:\n"
                + "- Use ↑/↓ to move, Space to select, Enter to confirm.\n"
                + "- Press Q to quit and keep your current score.\n"
                + "- Press Ctrl+C to force exit at any time."
            ),
            title=f"[bold {theme['primary']}]Chaos Mode: {title}[/bold {theme['primary']}]",
            border_style=theme["panel"],
        )
    )

    decision = chaos["decision1"]
    console.print("")
    choice_1 = prompt_choice(
        decision,
        step_title="Decision 1",
        step_index=1,
        total_steps=chaos_steps_total,
    )
    if choice_1 == "__QUIT__":
        quit_early = True
        quit_reason = "Quit during Decision 1"
    else:
        decision_text = option_text_for_label(decision, choice_1)
        decision_score = int(decision["score"])
        if choice_1 == decision["answer"]:
            earned += decision_score
            score_breakdown.append(
                {"step": "Decision 1", "earned": decision_score, "max": decision_score, "correct": True}
            )
            path_taken_steps.append("[Decision 1 ✓]")
            append_selection_history("Decision 1", decision_text, True, decision_score)
            decision_status_plain = "Correct decision."
        else:
            score_breakdown.append(
                {"step": "Decision 1", "earned": 0, "max": decision_score, "correct": False}
            )
            path_taken_steps.append("[Decision 1 ✗]")
            append_selection_history("Decision 1", decision_text, False, 0)
            decision_status_plain = "Risky decision."
        path_taken_steps.append(f"[Chaos {choice_1}]")

        decision_status_style = theme["success"] if choice_1 == decision["answer"] else theme["danger"]
        console.print(f"[{decision_status_style}]{decision_status_plain}[/{decision_status_style}]")
        show_chaos_event_transition(decision_text)
        console.print(
            Panel(
                Markdown(decision["chaos_events"][choice_1]),
                title=f"[bold {theme['danger']}]New Chaos Event ({choice_1})[/bold {theme['danger']}]",
                border_style=theme["danger"],
            )
        )

        path = chaos["paths"][choice_1]
        recovery = path["recovery"]
        recovery_choice = prompt_choice(
            recovery,
            step_title=f"Recovery {choice_1}",
            step_index=2,
            total_steps=chaos_steps_total,
        )
        if recovery_choice == "__QUIT__":
            quit_early = True
            quit_reason = f"Quit during Recovery {choice_1}"
        else:
            recovery_text = option_text_for_label(recovery, recovery_choice)
            recovery_score = int(recovery["score"])
            if recovery_choice == recovery["answer"]:
                earned += recovery_score
                recoveries_succeeded += 1
                score_breakdown.append(
                    {"step": "Recovery", "earned": recovery_score, "max": recovery_score, "correct": True}
                )
                path_taken_steps.append(f"[Recovery {choice_1} ✓]")
                append_selection_history("Recovery", recovery_text, True, recovery_score)
                recovery_status_plain = "Recovery successful."
            else:
                score_breakdown.append(
                    {"step": "Recovery", "earned": 0, "max": recovery_score, "correct": False}
                )
                path_taken_steps.append(f"[Recovery {choice_1} ✗]")
                append_selection_history("Recovery", recovery_text, False, 0)
                recovery_status_plain = "Recovery missed."

            recovery_status_style = theme["success"] if recovery_choice == recovery["answer"] else theme["danger"]
            console.print(f"[{recovery_status_style}]{recovery_status_plain}[/{recovery_status_style}]")
            show_next_stage_transition(
                title="Recovery phase complete.",
                subtitle="New evidence is ready for your final decision.",
                badge_frames=[
                    ">> NEW EVIDENCE UNLOCKED <<",
                    "> > NEW EVIDENCE UNLOCKED < <",
                    ">> NEW EVIDENCE UNLOCKED <<",
                ],
                prompt="Press Enter to see the final decision.",
            )
            console.print(Markdown(path["feedback"]))

            final_decision = chaos["final_decision"]
            console.print(
                Panel(
                    Markdown(final_decision["question"]),
                    title=f"[bold {theme['accent']}]New Decision Event ({choice_1})[/bold {theme['accent']}]",
                    border_style=theme["accent"],
                )
            )
            final_choice = prompt_choice(
                final_decision,
                step_title="Final Decision",
                step_index=3,
                total_steps=chaos_steps_total,
            )
            if final_choice == "__QUIT__":
                quit_early = True
                quit_reason = "Quit during Final Decision"
            else:
                final_score = int(final_decision["score"])
                if final_choice == final_decision["answer"]:
                    earned += final_score
                    score_breakdown.append(
                        {"step": "Final Decision", "earned": final_score, "max": final_score, "correct": True}
                    )
                    path_taken_steps.append("[Final Decision ✓]")
                    final_text = option_text_for_label(final_decision, final_choice)
                    append_selection_history("Final", final_text, True, final_score)
                    final_status = f"[{theme['success']}]Final decision is correct.[/{theme['success']}]"
                else:
                    score_breakdown.append(
                        {"step": "Final Decision", "earned": 0, "max": final_score, "correct": False}
                    )
                    path_taken_steps.append("[Final Decision ✗]")
                    final_text = option_text_for_label(final_decision, final_choice)
                    append_selection_history("Final", final_text, False, 0)
                    final_status = f"[{theme['danger']}]Final decision is incorrect.[/{theme['danger']}]"

                console.print("")
                console.print(
                    Panel(
                        f"{final_status}\n\n{final_decision['feedback']}",
                        title=f"[bold {theme['primary']}]Final Feedback[/bold {theme['primary']}]",
                        border_style=theme["panel"],
                    )
                )

    percent = (earned / maximum * 100.0) if maximum > 0 else 0.0
    console.print("")
    result_line = (
        f"[bold {theme['accent']}]Quit early[/bold {theme['accent']}] ({quit_reason})"
        if quit_early
        else f"[bold {theme['success']}]Completed[/bold {theme['success']}]"
    )
    completion_line = "Decision path partial" if quit_early else "Decision path complete"
    elapsed = max(0, int(time.time() - started_at))
    minutes, seconds = divmod(elapsed, 60)
    path_line = " \u2192 ".join(path_taken_steps) if path_taken_steps else "Start"
    breakdown_lines = [
        f"- {item['step']}: {item['earned']}/{item['max']}"
        for item in score_breakdown
    ]
    if not breakdown_lines:
        breakdown_lines = ["- No scored steps completed."]
    missed_steps = [item for item in score_breakdown if not item["correct"]]
    if missed_steps:
        missed_count = len(missed_steps)
        missed_points = sum(item["max"] - item["earned"] for item in missed_steps)
        retry_tip = (
            f"You missed {missed_count} step(s) and {missed_points} point(s). "
            "Review the chaos event and recovery logic, then try again."
        )
    else:
        retry_tip = "Great flow. You can replay and try a different branch for practice."
    console.print(
        Panel(
            f"[bold]Result:[/bold] {result_line}\n"
            f"[bold]Completion:[/bold] {completion_line}\n"
            f"[bold]Score:[/bold] {earned}/{maximum} ({percent:.0f}%)\n\n"
            f"[bold]Recoveries:[/bold] {recoveries_succeeded}\n"
            f"[bold]Path:[/bold] {path_line}\n"
            f"[bold]Time:[/bold] {minutes:02d}:{seconds:02d}\n\n"
            f"[bold]Score breakdown:[/bold]\n" + "\n".join(breakdown_lines) + "\n\n"
            f"[bold]Why this score:[/bold] {retry_tip}\n\n"
            f"[bold]Band:[/bold] {result_band(earned)}",
            title=f"[bold {theme['success']}]Chaos Result[/bold {theme['success']}]",
            border_style=theme["success"],
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
            f"{_platform_setup_hint_for_any_ai_key()}\n\n"
            f"{_essay_key_setup_help_text()}"
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
                f"{_platform_setup_hint_for_env_key(env_key)}\n\n"
                f"{_essay_key_setup_help_text()}"
            )

    theme = select_theme(theme_name)
    console = Console(no_color=no_color)
    start_clean_screen(ui == "next")
    title = essay["title"]
    question = essay["question"]
    instructions = essay["instructions"]
    hint_text = essay.get("hint", "").strip() or "🤔 Hint: Focus on the key points your instructor expects."
    if ui != "next":
        console.print(LOGO)
        intro_markdown = (
            f"## Question\n\n{_markdown_preserve_linebreaks(question)}\n\n"
            f"## Instructions\n\n{_markdown_preserve_linebreaks(instructions)}\n\n"
            f"## Hint\n\n{_markdown_preserve_linebreaks(hint_text)}\n\n"
            "**⏎ Press Enter to open your editor and write your answer.**"
        )

    try:
        if ui != "next":
            console.print(
                Panel(
                    Markdown(intro_markdown, code_theme="monokai"),
                    title=f"[bold {theme['primary']}]{title}[/bold {theme['primary']}]",
                    border_style=theme["panel"],
                )
            )
            prompt_input()
        if ui == "next":
            submission_markdown = (
                f"## Question\n\n{_markdown_preserve_linebreaks(question)}\n\n"
                f"## Instructions\n\n{_markdown_preserve_linebreaks(instructions)}\n\n"
                f"## Hint\n\n{_markdown_preserve_linebreaks(hint_text)}"
            )
            console.print(
                Panel(
                    Markdown(submission_markdown, code_theme="monokai"),
                    title=f"[bold {theme['primary']}]{title}[/bold {theme['primary']}]",
                    border_style=theme["panel"],
                )
            )
            student_answer = collect_essay_answer_inline(
                title,
                question,
                instructions=instructions,
                hint_text=hint_text,
                theme=theme,
                use_fullscreen_box=False,
                show_intro=False,
            )
            answer_heading = f"[bold {theme['primary']}]Your answer[/bold {theme['primary']}]"
            console.print(
                Panel(
                    student_answer,
                    title=answer_heading,
                    border_style=theme["panel"],
                )
            )
        else:
            student_answer = collect_essay_answer_via_editor(
                title,
                question,
                hint_text=hint_text,
            )

        if no_color:
            console.print("✓ Answer captured.")
        else:
            console.print(f"[bold {theme['success']}]✓ Answer captured.[/bold {theme['success']}]")

        grade = None
        fallback_message = ""
        fallback_reason = "unknown_error"
        fallback_provider = resolved_provider
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
                    fallback_provider = provider
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
                    f"{_platform_setup_hint_for_env_key(env_key)}\n\n"
                    f"{_essay_key_setup_help_text()}"
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
                fallback_provider = resolved_provider
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
            reason_code = str(grade.get("ai_reason", "unknown_error"))
            reason_label = reason_labels.get(reason_code, "unknown error")
            advice_lines: list[str] = []
            provider_for_error = fallback_provider or resolved_provider
            provider_name = _provider_display_name(provider_for_error)
            provider_env_key = _env_key_for_provider(provider_for_error)
            feedback_lines.append("")
            if reason_code == "unauthorized":
                advice_lines.append(f"{provider_name} rejected the API key (401 Unauthorized).")
                advice_lines.append(f"Update {provider_env_key} with a valid key, then run again.")
            elif reason_code == "forbidden":
                advice_lines.append(f"{provider_name} denied access (403 Forbidden).")
                advice_lines.append(
                    f"Check {provider_env_key} permissions, project access, and model availability."
                )
            else:
                advice_lines.append(
                    f"AI unavailable ({reason_label}); deterministic fallback used."
                )
            for line in advice_lines:
                feedback_lines.append(f"- Note: {line}")
            feedback_lines.append("- Scoring mode: heuristic fallback (approximate).")
            grade["suggestions"] = list(grade.get("suggestions", []))
            for line in advice_lines:
                note = f"AI note: {line}"
                if note not in grade["suggestions"]:
                    grade["suggestions"].append(note)

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
        render_exit_message("Essay closed. Your answer was not submitted.", no_color=no_color)


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
    if raw_args and raw_args[0] == "alien-attack":
        alien_parser = argparse.ArgumentParser(description="Play Alien Attack in the terminal.")
        alien_parser.add_argument(
            "--mode",
            choices=["single", "double", "triple"],
            default="single",
            help="Ship profile: single, double, or triple.",
        )
        alien_parser.add_argument(
            "--difficulty",
            choices=["normal", "hard", "inferno"],
            default="normal",
            help="Game difficulty: normal, hard, or inferno.",
        )
        alien_parser.add_argument(
            "--no-color",
            action="store_true",
            help="Disable colors/styled symbols (also enabled with NO_COLOR).",
        )
        args = alien_parser.parse_args(raw_args[1:])
        try:
            return run_alien_attack_command(args)
        except KeyboardInterrupt:
            render_exit_message("Alien Attack closed. See you next time.", no_color=is_no_color_requested(args.no_color))
            return
        except RuntimeError as exc:
            print(safe_for_stream(f"Runtime error: {exc}", sys.stderr), file=sys.stderr)
            raise SystemExit(1) from exc

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
            choices=["compete", "collaborate"],
            default="",
            help="Room mode for create. If omitted, choose interactively.",
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
        except KeyboardInterrupt:
            render_exit_message("Left room. See you next time.", no_color=is_no_color_requested(args.no_color))
            return
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
            default="next",
            help="Use an experimental UI surface for init output.",
        )
        args = init_parser.parse_args(raw_args[1:])
        try:
            created = init_starter_files(args.dir, force=args.force)
        except KeyboardInterrupt:
            render_exit_message("Init cancelled. No worries.", no_color=False)
            return
        except OSError as exc:
            print(safe_for_stream(f"File error: {exc}", sys.stderr), file=sys.stderr)
            raise SystemExit(1) from exc
        except RuntimeError as exc:
            print(safe_for_stream(f"Runtime error: {exc}", sys.stderr), file=sys.stderr)
            raise SystemExit(1) from exc

        if args.ui == "next":
            render_init_next_screen(created, target_dir=args.dir)
            return

        print("Created starter files:")
        for path in created:
            print(f"- {path}")
        print("")
        print("Next steps:")
        created_by_name = {path.name: path for path in created}
        hello_quiz = created_by_name.get("hello-quiz.md")
        hello_imposter = created_by_name.get("hello-imposter.md")
        hello_debug = created_by_name.get("hello-debug.md")
        hello_challenge = created_by_name.get("hello-challenge.md")
        hello_reverse = created_by_name.get("hello-reverse.md")
        hello_millionaire = created_by_name.get("hello-millionaire.md")
        hello_chaos = created_by_name.get("hello-chaos.md")
        hello_essay = created_by_name.get("hello-essay.md")
        if hello_quiz:
            print(f"quizmd --validate {hello_quiz}")
            print(f"quizmd {hello_quiz}")
        if hello_imposter:
            print(f"quizmd --validate {hello_imposter}")
            print(f"quizmd {hello_imposter}")
        if hello_debug:
            print(f"quizmd --validate {hello_debug}")
            print(f"quizmd {hello_debug}")
        if hello_challenge:
            print(f"quizmd --validate {hello_challenge}")
            print(f"quizmd {hello_challenge}")
        if hello_reverse:
            print(f"quizmd --validate {hello_reverse}")
            print(f"quizmd {hello_reverse}")
        if hello_millionaire:
            print(f"quizmd --validate {hello_millionaire}")
            print(f"quizmd {hello_millionaire}")
        if hello_chaos:
            print(f"quizmd --validate {hello_chaos}")
            print(f"quizmd {hello_chaos}")
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
            print("quizmd room --join <room-name> [--token <room-token>]")
            print("Room quiz requirement: Time/time_limit must be >= 5 seconds for online modes.")
            print("")
            print("Game modes:")
            print("quizmd alien-attack")
        return

    root_help_epilog = (
        "Other commands:\n"
        "  quizmd init [--ui next]\n"
        "      Create starter files (hello-quiz.md, hello-imposter.md, hello-debug.md, hello-challenge.md, hello-reverse.md, hello-millionaire.md, hello-chaos.md, hello-essay.md).\n"
        "  quizmd room --create [ROOM_NAME] [options]\n"
        "  quizmd room --join ROOM_NAME [--token ROOM_TOKEN] [options]\n"
        "      Multiplayer modes: compete, collaborate.\n"
        "  quizmd alien-attack [--mode {single,double,triple}] [--difficulty {normal,hard,inferno}]\n"
        "      Play the Alien Attack terminal game.\n"
        "\n"
        "Quick start:\n"
        "  quizmd init\n"
        "  quizmd hello-quiz.md"
    )
    parser = argparse.ArgumentParser(
        description="Run markdown quizzes in the terminal.",
        epilog=root_help_epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
        "--hide-feedback",
        "--hide",
        action="store_true",
        help="Hide expected answer/imposter and explanation after each question.",
    )
    parser.add_argument(
        "--ui",
        choices=UI_CHOICES,
        default="next",
        help="Use an experimental UI surface for quiz and essay interactions.",
    )
    parser.add_argument(
        "--ai-provider",
        default=DEFAULT_AI_PROVIDER,
        choices=["auto", "gemini", "openai", "anthropic"],
        help="'auto' priority: gemini -> openai -> anthropic.",
    )
    parser.add_argument(
        "--ai-model",
        default="",
        help="AI model name for essay/debug fallback (defaults by provider).",
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
        elif mode == "chaos":
            title, chaos = parse_chaos_markdown(args.file)
        elif mode == "reverse":
            title, questions = parse_reverse_markdown(args.file)
        elif mode == "millionaire":
            title, questions = parse_millionaire_markdown(args.file)
        elif mode == "challenge":
            title, challenge_categories = parse_challenge_markdown(args.file)
        elif mode == "debug":
            title, debug_questions = parse_debug_markdown(args.file)
        else:
            title, questions = parse_quiz_markdown(args.file)
    except KeyboardInterrupt:
        render_exit_message(no_color=no_color)
        return
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
        elif mode == "chaos":
            print(
                safe_for_stream(
                    f"Validation passed: Chaos Quiz: {title} ({len(chaos['paths'])} paths, max {chaos['result']['maximum_score']} points)",
                    sys.stdout,
                )
            )
        elif mode == "reverse":
            print(
                safe_for_stream(
                    f"Validation passed: Reverse Quiz: {title} ({len(questions)} questions)",
                    sys.stdout,
                )
            )
        elif mode == "millionaire":
            print(
                safe_for_stream(
                    f"Validation passed: Millionaire Quiz: {title} ({len(questions)} questions, max {MILLIONAIRE_MAX_TIME_LIMIT_SECONDS}s each)",
                    sys.stdout,
                )
            )
        elif mode == "challenge":
            print(
                safe_for_stream(
                    f"Validation passed: Challenge Quiz: {title} ({len(challenge_categories)} categories)",
                    sys.stdout,
                )
            )
        elif mode == "debug":
            print(safe_for_stream(f"Validation passed: {title} ({len(debug_questions)} debug questions)", sys.stdout))
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
        elif mode == "chaos":
            run_chaos(
                title,
                chaos,
                theme_name=args.theme,
                no_color=no_color,
                ui=args.ui,
            )
        elif mode == "challenge":
            run_challenge(
                title,
                challenge_categories,
                theme_name=args.theme,
                no_color=no_color,
                full_screen=args.full_screen,
                ui=args.ui,
                show_feedback=not args.hide_feedback,
            )
        elif mode == "debug":
            run_debug(
                title,
                debug_questions,
                theme_name=args.theme,
                no_color=no_color,
                show_feedback=not args.hide_feedback,
                ui=args.ui,
                ai_provider=args.ai_provider,
                ai_model=args.ai_model,
                ai_timeout=args.ai_timeout,
            )
        else:
            run(
                title,
                questions,
                theme_name=args.theme,
                no_color=no_color,
                full_screen=args.full_screen,
                ui=args.ui,
                show_feedback=not args.hide_feedback,
                quiz_mode=mode,
                ai_provider=args.ai_provider,
                ai_model=args.ai_model,
                ai_timeout=args.ai_timeout,
            )
    except KeyboardInterrupt:
        render_exit_message(no_color=no_color)
        return
    except RuntimeError as exc:
        print(safe_for_stream(f"Runtime error: {exc}", sys.stderr), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        render_exit_message()
