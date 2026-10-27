# Security

This is a portfolio project, not a certified medical device or a production
pharmacovigilance system. It does implement the security practices below, and
documents what it deliberately does *not* handle.

## Secrets

- `ANTHROPIC_API_KEY` and `API_KEY` are read from environment variables /
  `.env` only (`src/config.py`, pydantic-settings). Neither is ever
  hardcoded, logged, or returned in an API response.
- `.env` is gitignored; `.env.example` ships with every value blank.
- `GET /config` exposes only non-secret capability metadata (model name,
  rate limit, supported languages, endpoint list) - never keys.

## Input handling

- Every user-supplied free-text field (`/ask` question, `/report`
  description) is sanitized before it reaches Claude
  (`src/api/security.py`):
  - Length-capped (422 if exceeded).
  - Control characters stripped.
  - Role-marker lines (`system:`, `assistant:`, `user:`) at the start of a
    line are stripped, so a user can't fake a conversation turn.
  - A small set of known prompt-injection patterns ("ignore all previous
    instructions", "reveal your system prompt", etc.) is rejected outright
    (422) rather than passed through.
  - This is a basic, pattern-based screen, not a guarantee against
    sophisticated prompt injection - see Known limitations below.
- Pydantic v2 schemas (`src/api/schemas.py`) enforce types and minimum
  lengths at the API boundary before any application code runs.

## Transport and response security

- `SecurityHeadersMiddleware` sets `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
  `Content-Security-Policy: default-src 'self'`, and
  `X-XSS-Protection: 0` on every response.
  - The strict CSP is enforced, not just set-and-forget: the demo page
    (`static/`) was refactored to external `.css`/`.js` files specifically
    because its own inline `<script>`/`<style>` tripped this CSP during
    manual verification - see the Phase 4 commit for the full story.
- CORS is explicit-origin (`CORS_ORIGINS` env var), not wildcard.
- The catch-all exception handler in `src/api/main.py` never leaks stack
  traces or internal error details to the client - it logs server-side and
  returns a generic 500.

## Rate limiting and auth

- `slowapi`-based rate limiting (`RATE_LIMIT_PER_MINUTE`, default 30/min),
  keyed by client IP, on `/ask`, `/report`, and `/evaluate`.
- An optional API-key dependency (`verify_api_key` in `src/api/deps.py`) is
  enforced on those same routes only when `API_KEY` is set - unset, the API
  is open (suitable for the public demo/portfolio deployment; set it for
  anything else).

## Data handling

- The regulatory corpus (`data/regulations/`) is public legal text (EUR-Lex,
  AEMPS) - no PII, no confidentiality concerns.
- `/report` descriptions and `/ask` questions submitted by a caller **are
  not necessarily de-identified**. If this were deployed for real incident
  intake, submitted text should be scrubbed of patient-identifying details
  (names, dates of birth, record numbers) before it reaches any third-party
  LLM API - this project does not implement that scrubbing, since the
  golden-dataset test cases are already synthetic/de-identified by
  construction. A production deployment handling real patient narratives
  would need a dedicated de-identification step and a signed data-processing
  agreement with the LLM provider.
- Query logs (`src/db`) store the submitted text and the system's output
  summary for operational metrics. In a real deployment this table would
  need a retention policy and the same de-identification treatment as above.

## Known limitations (explicitly not addressed)

- No authentication/authorization model beyond a single shared API key -
  no per-user accounts, roles, or audit trail of *who* submitted a report.
- The prompt-injection screen is pattern-based and will miss novel phrasings;
  it is a mitigation, not a guarantee.
- No encryption-at-rest for the SQLite file or the Chroma vector store -
  both are plain files on disk, appropriate for a local/demo deployment only.
- No automated dependency vulnerability scanning is wired into CI (a
  `pip-audit` or `safety` step would be a reasonable addition - see the
  README roadmap).
