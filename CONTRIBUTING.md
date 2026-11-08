# Contributing

Thanks for helping. Kisan Mitra gives crop advice to farmers, so changes are judged first
by whether they keep that advice safe.

## Ground rules

- **The guard is not negotiable.** Answers must never contain a pesticide or fertiliser
  dose or a brand name; `backend/kisan/guard.py` removes them and points to the KVK. A
  change that weakens it needs a test showing why it is still safe, and the nightly
  safety gate must stay green.
- One issue, one branch, one pull request. Keep pull requests small.
- Every change ships with tests, including failure paths. Tests never call real APIs or
  need keys: the model provider is stubbed.
- No secrets or real personal data in the repository. Keys go in a git-ignored `.env`.

## Set up and test

```bash
cd backend
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest                                          # no keys, no network
ruff check . && ruff format --check . && mypy

cd ../frontend
npm ci
npm run lint && npm run format:check && npm run check && npm test
```

`scripts/ci-local.sh` runs the same checks as CI. The README's "Test it" section covers
the browser, load and mutation tests.

## Pull requests

Say what changed, why, and paste the real test output. For UI changes, add screenshots
at 375 and 1280 px. CI (tests, lint, types, audits, gitleaks) must pass before merge.

## Reporting security issues

Please do not open a public issue. See [SECURITY.md](SECURITY.md).
