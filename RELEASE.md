# Release Policy

This repository uses immutable semantic version tags.

## Rules

- Do not move, delete, or recreate an existing release tag.
- Do not force-push tags.
- Each release must use a new version tag (`vX.Y.Z`).
- RC releases must also use unique immutable tags (`vX.Y.ZrcN`).
- Every release tag must point to one specific release commit.
- Update `CHANGELOG.md` in the same release commit.
- Tag value must exactly match `pyproject.toml` version.
- Never reuse a published PyPI version; publish a new version instead.

## PyPI Publishing (Trusted Publisher)

1. On PyPI, open your `quizmd` project and go to `Publishing`.
2. Add a GitHub trusted publisher:
   - Owner: `steliosot`
   - Repository: `quizmd`
   - Workflow: `.github/workflows/release.yml`
   - Environment: `pypi`
3. In GitHub repo settings, create environment `pypi` (recommended protection rules optional).
4. Push a new tag (example: `v2.0.3`), and GitHub Actions publishes to PyPI.
5. Workflow guards now fail the release if:
   - tag/version mismatch
   - version already exists on PyPI
   - clean-venv starter smoke check fails (`quizmd init --force` + millionaire validate).

## Why

Students and instructors install directly from Git tags. Immutable tags ensure:

- reproducible installs
- reliable rollbacks
- consistent debugging across machines and classrooms
