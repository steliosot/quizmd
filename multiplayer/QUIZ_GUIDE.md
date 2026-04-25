# QuizMD Quick Start

## Run the MCQ starter

```bash
quizmd --validate hello-quiz.md
quizmd hello-quiz.md
```

## Run the imposter starter

```bash
quizmd --validate hello-imposter.md
quizmd hello-imposter.md
```

## Run the essay starter

```bash
quizmd --validate hello-essay.md
export GEMINI_API_KEY="your_key_here"  # or OPENAI_API_KEY / ANTHROPIC_API_KEY
quizmd hello-essay.md
```
