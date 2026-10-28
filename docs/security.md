# Security

PharmaWatch AI is a portfolio project and a decision-support prototype. It is not a medical
device, has no regulatory certification, and has not been security-audited by a third party.
This page lists the controls it implements and, just as important, what it does not handle.

## Secrets

- `ANTHROPIC_API_KEY` and `API_KEY` come from environment variables or a local `.env` file
  (`src/config.py`). They are never hard-coded, logged or returned by the API.
- `.env` is git-ignored; `.env.example` ships with every secret blank.
- `GET /config` and `GET /health` expose only non-secret metadata.
- LLM errors keep the provider's status and message for diagnosis but never include keys.

## Access control and cost containment

- Cost-bearing endpoints (`/ask`, `/report`, `/report/stream`) and the incident history
  (`/reports`) need `X-API-Key` when `API_KEY` is set. With `API_KEY` empty they are
  **disabled (403)** unless `DEMO_MODE=true` is set explicitly.
- `/evaluate` always needs a configured `API_KEY`, accepts only whitelisted dataset names (never
  a path) and runs one evaluation per process (409 while busy).
- Keys are compared with `hmac.compare_digest`.
- Rate limit per client IP on the cost-bearing endpoints (`RATE_LIMIT_PER_MINUTE`, default 30).
- Request bodies over `MAX_REQUEST_BYTES` (default 64 000) are rejected with 413 before parsing.

## Input handling and prompt injection

- Pydantic schemas enforce types and lengths (questions 10–4000 characters, descriptions
  20–4000, device names ≤ 200) after stripping whitespace.
- `src/api/security.py` strips control characters, zero-width characters and role-marker lines
  (`system:`, `assistant:`, `user:`).
- A pattern screen (English and Spanish) **flags** likely prompt-injection text. It is a signal,
  not a defence: it can be bypassed and it produced false positives on legitimate questions,
  so it no longer rejects requests. Matches are logged; on `/report` they add an advisory
  escalation with an explicit reason.
- The defences that do the work are structural: user text is delimited as untrusted data in
  every prompt, model output is constrained by a JSON schema, and deadlines and recipients come
  from the rules table (`data/classification_rules.json`), never from model text.
- The evaluation includes prompt-injection cases; quoting an injected payload while refusing it
  counts as a mention, not as compliance.

## Responses and transport

- Security headers on every response, including middleware-generated 500s:
  `Content-Security-Policy: default-src 'self'` (the web interface ships no inline scripts,
  styles or `data:` assets so that it works under this policy), `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`. Only `/docs` and `/redoc`
  get a policy that allows the Swagger UI / ReDoc CDN assets.
- Uniform error envelope `{code, message, details}`; validation details never echo the
  submitted text; unhandled errors return a generic 500 and are logged server-side.
- CORS is limited to the origins in `CORS_ORIGINS` (no wildcard).
- The web interface is served from the same origin as the API, so the key is never sent to a
  third party. `/app` refuses path traversal and never serves files outside `frontend/dist`.

## Data handling

- The regulatory corpus (`data/regulations/`) is public legal and guidance text.
- **Do not submit patient-identifying data.** Descriptions are sent to a third-party model API.
  The interface says so on every screen; there is no automatic de-identification.
- By default the request log stores only the **length and SHA-256** of submitted text
  (`STORE_INPUT_TEXT=false`), not the text itself.
- Incident results are stored without the free-text narrative.
- The web interface keeps the API key in memory (optionally in `sessionStorage` until the tab
  closes), never in `localStorage`. Language, theme and motion preferences are the only
  values stored in `localStorage`.

## Limits — not handled

- **Single shared key.** No user accounts, roles, per-user audit trail or approval workflow.
  The review queue is read-only.
- **No de-identification** of submitted text, and no data-processing agreement with the model
  provider is implied.
- **No encryption at rest** for SQLite or Chroma; both are plain files meant for local use.
- **Rate limiting is in-process and per IP**: it does not hold across several workers or
  behind a proxy that hides client addresses.
- **Prompt injection is mitigated, not solved.** A determined attacker may still influence free
  text such as the reasoning or the notification draft; that is why a human reviews every
  output.
- **No dependency vulnerability scanning** is wired into CI.
- **No external security review or penetration test** has been performed.
- **CI has not been executed remotely yet** (the workflow file exists but the repository has
  not been published).

## Reporting a vulnerability

Open a private security advisory on the repository (`<REPO_URL>`) or contact the author
directly. Do not open a public issue with exploit details.
