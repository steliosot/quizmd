# Hello Code Cards Quiz

## Question 1
What does this code print?

```python
# A
name = "QuizMD"
print(name.lower())
```

- QuizMD
- quizmd
- QUIZMD
- name

Answer: 2
Type: single
Time: 25
Explanation: `lower()` returns the text in lowercase, so it prints `quizmd`.

## Question 2
Which version avoids loading the whole file into memory?

```python
# A
with open("scores.csv", "r", encoding="utf-8") as file:
    rows = file.readlines()

for row in rows:
    print(row)
```

```python
# B
with open("scores.csv", "r", encoding="utf-8") as file:
    for row in file:
        print(row)
```

- Code A
- Code B
- Both
- Neither

Answer: 2
Type: single
Time: 35
Explanation: Code B streams one row at a time. Code A loads all lines first with `readlines()`.

## Question 3
Which snippets create the same list?

```python
# A
numbers = []
for value in range(3):
    numbers.append(value * 2)
```

```python
# B
numbers = [value * 2 for value in range(3)]
```

```python
# C
numbers = list(range(0, 6, 2))
```

- A and B only
- B and C only
- A, B, and C
- None of them

Answer: 3
Type: single
Time: 45
Explanation: All three snippets create `[0, 2, 4]`.
