# World ID Agent Pass: integration notes

**DRAFT.** Written from reading the docs and local testing only. No real World ID authentication has been completed yet (no portal client registered). Update the timings and friction once the live flow has run.

## What we built
Every bot launch is a pending action with an id. The engine only proceeds when `get_approval(pending_id).approved` is true.

1. `GET /world/start?purpose=launch_bot&ref=<pending_id>` creates a single-use `state`, a `nonce` and a PKCE verifier bound to the pending id (10 minute TTL), then redirects to `https://auth.world.org/api/v1/authorize` with `scope=openid`, S256 PKCE and `max_age=0` (fresh authentication for this launch).
2. `GET /world/callback` checks `state` (unknown or replayed: rejected, nothing changes), the `iss` response parameter, handles `error=access_denied`, redeems the code server-side with the client secret, then verifies the ID token with PyJWT: RS256 only, signature against the JWKS from discovery, `iss`, `aud`, `exp`, `nonce`, and `auth_time` newer than the start of this attempt.
3. Result is stored as `Approval(pending_id, subject, approved, reason, at)`. Denied, expired, cancelled, bad token or failed exchange all give `approved=False` and the bot is never launched.
4. `WORLD_MOCK=1` serves a labelled Approve / Deny page that produces the same `Approval` objects. Proofs are mocked for the event, so this is the demo path.

Tests: 22 unit tests (mock approve / deny / replay / expiry, forged signature, wrong nonce, wrong audience, wrong issuer, expired token, stale `auth_time`, `alg=none`, unconfigured server fails closed).

## Debrief (fields World asks for)

**Time to first success:** not yet measured for a real login. Reading the docs and getting the server-side flow working against live discovery and JWKS took about 30 minutes. Portal registration plus a first real authentication: TBD.

**Friction**
- The first docs page (`/docs`) is an overview only. The real flow (endpoints, parameters, validation) is spread over `/docs/guides/oidc`, `app-registration`, `step-up`, `testing`. The guide pages are server-rendered, so they can be fetched, but `/docs/guides/sandbox` is a JavaScript app and showed only "Loading".
- Production registration needs an eligible Google account; a sandbox needs a sandbox World ID that takes about an hour to issue. For a hackathon that is a real risk, so we keep a mock path.
- The default client authentication in the portal is `client_secret_basic`, while the main guide example shows `client_secret_post`. Easy to miss.
- No action binding: the device-flow docs say `binding_message` is unsupported and the ID token does not carry the action. We bind the approval to our pending id ourselves through `state`, `nonce` and our own store.
- The docs do not say what "Agent Pass" is called in the portal or which guide it maps to; we used the human-checkpoint / step-up guides.
- A local `http://localhost` redirect URI may not be accepted for production clients (docs say use HTTPS callbacks); needs checking in the portal.

**Missing docs**
- A copy-paste minimal example of a Python backend verifying the ID token (PyJWT) and an explicit list of required checks in one place.
- The exact sandbox flow end to end for someone with no integration contact.
- What the `sub` is bound to for sector sharing, in plain words, and what to use as a "one human, one account" key across applications.

**Top improvement:** a per-action approval receipt. A signed ID token claim (or request parameter) that carries the exact operation being approved would let a relying party prove "this human approved this bot launch" instead of "this human authenticated recently".

## Open items
- Register a client (sandbox or production), run `uv run python ../spikes/world_spike.py` from `engine/`, record real timings here.
- Decide whether to request `acr` classes (Orb / Selfie Check). We currently accept the client's default accepted accounts.
