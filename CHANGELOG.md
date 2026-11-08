# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `SECURITY.md` (private reporting, scope), this changelog, `.editorconfig` and weekly
  grouped Dependabot updates for pip, npm and GitHub Actions.
- CI gates: ruff lint and format check, a coverage floor on `kisan/`, pip-audit,
  bandit (high severity), `npm audit` for production dependencies, and a gitleaks scan
  of the full history on every push and pull request.
- `scripts/ci-local.sh` runs the same checks locally when Actions minutes run out.
- `GET /ready`: 200 when a model provider is configured and the photo classifier's files
  are in place, otherwise 503 naming what is missing. `/health` stays the liveness check.
- Every response has an `X-Request-ID` header (a caller's id is kept when it is a short
  plain token), exposed to the browser through CORS.
- Structured JSON logs (structlog): one line per request with method, path, status,
  duration and request id; warnings and errors carry the request id too. No question,
  transcript, answer, file name or IP address is logged.
- Security headers for the site in `frontend/vercel.json` (CSP with `frame-ancestors
  'none'`, HSTS, Permissions-Policy, Referrer-Policy, nosniff), and a SvelteKit CSP in
  hash mode, so scripts are allowed by hash rather than `unsafe-inline`. A Playwright test
  runs the Gujarati journey under these headers and fails on any CSP violation. The API
  sends `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`.

### Changed

- Backend code formatted with ruff (listed in `.git-blame-ignore-revs`).
- Dependencies upgraded within their minor versions to clear known vulnerabilities
  (backend: anyio, certifi, dnspython, idna, orjson, Pygments, python-dotenv,
  python-multipart, requests, urllib3, ujson; frontend lockfile: svelte, SvelteKit,
  vite and their dependencies). Vulnerabilities that need a major upgrade (starlette with
  FastAPI, pillow) are listed in `backend/pip-audit-ignore.txt`.

- Configuration is read with pydantic-settings and checked at startup: a bad timeout,
  retry count or rate limit stops the app with the variable's name (never its value).
  Variable names and defaults are unchanged; keys and tokens are kept as secrets.
- The photo classifier's download has connect and read timeouts (httpx) and still checks
  the sha256; a failed download leaves no partial file. Uploads to Vercel Blob use an
  explicit 10 s timeout.
- CI builds the frontend against the production API URL, so the CSP test checks the
  origin that ships.

### Fixed

- `/health` GET and HEAD no longer share one OpenAPI operation id (FastAPI's duplicate
  operation id warning).
- The safety evaluation closes its results file before the CI step that uploads it.

## [1.0.0] - 2026-11-07

First public version: a rebuild of the 2025 prototype around measured results.

### Added

- `POST /analyze/` answers a farmer's question, spoken or typed, in Gujarati, Hindi or
  English. Speech is transcribed with Whisper on Groq and the answer is drafted on Groq
  from an evidence block in which the farmer's words are quoted as data.
- A deterministic dose and brand guard removes any sentence that pairs a quantity with a
  chemical word, or names a brand, in all three languages, and adds a Krishi Vigyan
  Kendra referral when chemicals are mentioned.
- 36 safety prompts registered before the answer pipeline was written, a safety
  evaluation script, and a safety gate workflow that runs it against the live model on
  pull requests that touch the pipeline and nightly.
- A photo check: a DINOv2 linear probe trained in a Colab notebook and tested on field
  photos, run on CPU as an int8 ONNX model committed with the function; it says when it
  is not sure.
- A 3-day Open-Meteo forecast for the farmer's location in the evidence block.
- Frontend (SvelteKit, static): record or type a question, add a photo, choose a language,
  see the weather, and hear the answer read aloud. Photos are shrunk in the browser and
  oversized uploads are refused with a clear message.
- Deployment on Vercel's free tier: the backend as a Python function in Mumbai with
  `GET /health`, the frontend as static files; a production build refuses to fall back to
  localhost.
- Per-client rate limit on `/analyze/`; 503 or 504 with a plain message when the model
  provider is rate-limited or times out; photos over 8 MB or 30 MP refused.
- Tests: backend unit tests with the provider stubbed and contract fuzzing of every route
  (schemathesis and Hypothesis); frontend unit tests and Playwright browser tests with axe
  accessibility checks at phone, tablet and desktop widths.
- A Gujarati-first restrained Bohemian design with self-hosted fonts, 48 px controls and
  text of at least 18 px.
- Docs: README with measured results, `docs/EVAL.md`, `docs/DEPLOY.md`, the rebuild plan,
  the farmer-question evaluation kit and a Gujarati farmer interview guide; MIT licence.
- `.gitattributes` storing text with LF; CI with read-only permissions and actions pinned
  by commit SHA.

[Unreleased]: https://github.com/CODER7657/kisan_mitra/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/CODER7657/kisan_mitra/releases/tag/v1.0.0
