# Security policy

Kisan Mitra is maintained by one person ([@CODER7657](https://github.com/CODER7657)) in
spare time. Reports are welcome and taken seriously; please be patient with the response.

## Reporting a vulnerability

Please report privately, not in a public issue or pull request:

1. Open [the repository's Security tab](https://github.com/CODER7657/kisan_mitra/security)
   and choose **Report a vulnerability** (GitHub private vulnerability reporting). The
   report is visible only to the maintainer until an advisory is published.
2. Describe what is affected, how to reproduce it (a request, a prompt, a file), and what
   an attacker gains. Do not include real farmers' data, photos or recordings.

If the Report button is not shown, open a public issue that says only that you have a
security report and how to reach you, with no details; a private channel will be set up.

## Scope

In scope:

- **The API** (`backend/`, deployed at `kisan-mitra-api.vercel.app`): for example a crash
  or resource exhaustion from a crafted upload, a way around the upload size and pixel
  limits or the rate limit, reading another person's stored upload, or leaking the
  server's API keys.
- **The dose and brand guard** (`backend/kisan/guard.py` and the prompt in
  `backend/kisan/answer.py`): a question, in any language, that makes an answer *after the
  guard* give a pesticide or fertiliser amount or name a brand. The project promises never
  to give one, so a reproducible bypass is treated as a vulnerability. Please include the
  exact question and language.
- **The frontend** (`frontend/`, deployed at `kisan-mitra-gilt.vercel.app`): for example
  script injection through the rendered answer, or the page sending data somewhere other
  than the configured API.
- The CI workflows in `.github/workflows/` (for example a way for a pull request to reach
  a repository secret).

Out of scope:

- Agronomic quality of an answer that contains no dose or brand (please open a normal issue).
- Weaknesses already listed under Limitations in the [README](README.md), unless you show
  a concrete exploit beyond them.
- Vulnerabilities in Groq, OpenAI, Open-Meteo, Vercel or GitHub themselves (report those to
  the provider), and denial of service by sheer request volume against the free tiers.
- Reports from automated scanners without a demonstrated impact, and social engineering.

## What to expect

- An acknowledgement, usually within a week.
- An assessment and, if confirmed, a fix or mitigation as soon as practical. Guard bypasses
  are prioritised because they can harm farmers directly.
- Credit in the advisory and the changelog if you want it.

Only the latest code on `main` (and the deployment built from it) is supported; there are
no maintained older releases.
