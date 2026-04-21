# Essay Question: requirements.txt concepts

## Question

What is `requirements.txt` and what problem does it solve in Python projects?

## Instructions for Students

Write a short answer (5-10 lines).
Be clear and logical. Focus on why it is needed, not just what it is.

## Evaluation Criteria (Total: 4 points)

1. **Dependency conflict problem (1 point)**
- Different projects can require different versions of the same package
- Version mismatches can break projects

2. **Reproducibility (1 point)**
- Team members can recreate the same environment
- The project behaves consistently across machines

3. **Collaboration benefit (1 point)**
- Reduces setup friction between teammates
- Avoids "works on my machine" issues

4. **Version tracking (1 point)**
- Encourages pinning versions
- Helps debugging and long-term maintenance

## Reference Answer

`requirements.txt` lists project dependencies, often with pinned versions.
It solves dependency conflicts because each project may need different library versions.
By installing from the same file, team members and CI create the same environment.
This improves reproducibility and collaboration.
It also helps maintenance because exact versions are documented.

## AI Evaluation Rules

- Evaluate only using the rubric criteria above
- Do not use external knowledge
- Score = (points achieved / 4) x 100

## Output Format

Score: XX%

Feedback:
- What the student did well
- What is missing based on the criteria
- 1-2 suggestions for improvement
