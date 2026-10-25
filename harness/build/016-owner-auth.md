# GEOAI-016 — owner authentication and confirmed Telegram link

Status: READY. Base: accepted GEOAI-015 feature commit
`a0e82bc968884cd5d8a60bd522fea2bc3170f608`. Dependency 015 passed
local and GitHub push/PR checks after one recorded repair.

## Scope and security contract

Add a separate SQLite identity store under an explicit server-owned root.
Provision the single owner through a local, hidden-password CLI only; no
HTTP registration, default password, credential in Git or `.env` write.
Use Python scrypt with a unique random salt and N=2^17, r=8, p=1;
cap concurrent password checks and login attempts for the 2-vCPU VM.
Persist only a SHA-256 verifier of a 256-bit random session token.
Sessions have a 30-minute idle limit and eight-hour absolute limit,
enforced server-side. Login rotates any preexisting session; logout,
expiration and revoke-all invalidate server-side records.

Expose HTTPS-only login, session, logout, revoke and link-challenge routes
when an auth root is explicitly configured. Use a `__Host-` session cookie
with Secure, HttpOnly, SameSite=Strict and Path=/; no token in JSON, URL,
localStorage or logs. Mutating session routes require a same-origin check
and a session-bound CSRF token where authenticated. Responses containing
identity data use `Cache-Control: no-store`. A one-time, ten-minute link
challenge is confirmed only by a trusted Telegram bot update from a
configured `ADMIN_IDS` actor; the code itself does not name the Telegram
account. Bot integration is opt-in by auth-root configuration and does not
change the existing survey conversation when disabled.

Existing upload/preview/DXF routes remain as they are until GEOAI-017
adds resource ownership checks. This stage must not claim a private web
cabinet or provision real owner credentials. No production deployment,
Telegram polling, network login, bot statistics DB migration or system
packages. Candidate files: `services/auth_store.py`, `api/auth.py`,
`api/app.py`, an optional bot link adapter/handler and registration,
focused tests, and task memory.

The hash/session choices follow OWASP primary guidance:
https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
and https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html.

## Acceptance and checks

1. Owner provisioning is local and one-time. Wrong credentials have a
   generic error and bounded attempts; password/salt/session verifier
   survive restart without plaintext password or bearer token in SQLite.
2. HTTPS login issues a fresh secure cookie. Session lookup enforces both
   timeouts, logout and revoke-all; old/fixed/revoked cookies cannot work.
   CSRF/origin failures do not mutate state.
3. Link code is one-use, expires after ten minutes and binds only to the
   verified Telegram actor supplied by the trusted opt-in bot handler.
   Non-admin actors and repeated/expired codes fail without changing link.
4. Existing HTTP and Telegram regression behavior remains intact when
   auth root is absent. Run focused, isolated regression/API, negative
   security checks, `pip check` and `git diff --check`.

Budget: 90 minutes for 016, one attempt plus at most two repair cycles.
P2 deadline 2026-10-25T04:33:23Z, one writable worktree/compute worker,
zero external executor spend. Stop on missing credential/identity decision,
lost isolation, unexpected edits, failed session security, exhausted
limits or an unauthorized production operation; record exact blocker.
