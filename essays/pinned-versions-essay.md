# Essay Question: pinned versions

## Question

Why is pinning package versions (for example `package==1.2.3`) important in `requirements.txt`?

## Instructions for Students

Write a short answer (5-10 lines).
Focus on reliability, debugging, and teamwork impacts.

## Evaluation Criteria (Total: 4 points)

1. **Deterministic environments (1 point)**
- Exact versions produce predictable installs
- Reduces random breakage from upstream updates

2. **Debugging value (1 point)**
- Easier to reproduce and investigate bugs
- Clearer change tracking between working and broken states

3. **Team/CI consistency (1 point)**
- Teammates and CI run on the same dependency set
- Reduces environment-related inconsistencies

4. **Maintenance and upgrades (1 point)**
- Enables intentional upgrade strategy
- Makes dependency changes explicit and reviewable

## Reference Answer

Pinning versions makes installs deterministic, so environments stay predictable over time.
Without pins, new upstream releases can unexpectedly break previously working code.
Pinned versions help debugging because teams can reproduce the same dependency state.
They also improve consistency across developer machines and CI.
Finally, they support controlled upgrades by making dependency changes explicit.

## AI Evaluation Rules

- Evaluate only using the rubric criteria above
- Do not use outside knowledge beyond the provided rubric
- Score = (points achieved / 4) x 100

## Output Format

Score: XX%

Feedback:
- What the student did well
- What is missing based on the criteria
- 1-2 suggestions for improvement
