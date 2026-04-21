# Essay Question: virtual environments

## Question

Why do we use a `.venv` virtual environment in Python projects, and what issues does it prevent?

## Instructions for Students

Write a short answer (5-10 lines).
Explain practical reasons, not only definitions.

## Instructor Name

Stelios

## Evaluation Criteria (Total: 4 points)

1. **Isolation (1 point)**
- `.venv` isolates project dependencies from system/global Python
- Prevents cross-project package interference

2. **Version compatibility (1 point)**
- Different projects can use different package versions safely
- Avoids dependency clashes

3. **Reproducible setup (1 point)**
- Makes it easier for others to recreate the same project environment
- Supports consistent behavior in class/CI

4. **Operational hygiene (1 point)**
- Keeps host system clean
- Simplifies troubleshooting and rollback

## Reference Answer

A `.venv` creates an isolated Python environment for one project.
It prevents packages installed for one project from affecting another project or system Python.
This allows each project to keep its own dependency versions without conflicts.
It improves reproducibility because classmates and CI can recreate the same setup.
It also keeps the machine cleaner and makes debugging easier.

## AI Evaluation Rules

- Evaluate only using the rubric criteria above
- Do not introduce external facts
- Score = (points achieved / 4) x 100

## Output Format

Score: XX%

Feedback:
- What the student did well
- What is missing based on the criteria
- 1-2 suggestions for improvement
