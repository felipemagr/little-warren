---
paths:
  - "**"
---

# Git

- Conventional Commits: `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `refactor: ...`; imperative mood, subject < 72 chars.
- Personal repo: the remote must stay on the `github.com-personal` SSH alias (personal key). Never configure a work identity or work remote here.
- Never commit the local knowledge base (anything gitignored under `docs/`) or `data/cache/`. Never mention its contents or provenance in commit messages.
- Run `make quality` before every commit.
- NEVER `git commit` or `git push` without the owner's explicit review and approval of the exact changes. Prepare the work, show a summary of the diff (`git status` + `git diff --stat`) and the proposed commit split, then WAIT for his go.
