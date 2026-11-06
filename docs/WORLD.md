# World ID Agent Pass & IDKit: Integration Notes and Debrief

**In one minute:** a person proves with World ID that they are a real, unique human, once per bot launch. That person gets one fixed creator ID in the vault. If they try to start fresh with a new wallet to hide their dead bots, the vault refuses (`CreatorIdentityMismatch`). No passport upload, no KYC: only "one human, one record". For demos without a phone there is a clearly marked "demo" approval.

**Status:** **Verified live on 2026-11-06** with a registered World Developer Portal client (`WORLD_MOCK=0`) over a public HTTPS tunnel, plus full offline/mock support (`WORLD_MOCK=1`) for local testing.

---

## 1. Why Parable uses World ID (The Trust Moment & Minimum Sufficient Credential)

**The problem:** An AI bot creator runs 20 bots, loses money on 17, and wants to abandon that account and open a fresh wallet to advertise a "100% win rate."
**Why a wallet signature is not enough:** Wallets are free; a dishonest creator can generate 1,000 wallets per second.
**Why KYC is too much:** Creators should not have to upload a passport to run a public trading strategy.
**Minimum sufficient credential:** **World ID Proof of Human + per-launch Agent Pass approval.**
1. **One human = one creator identity (`creatorId`):** We hash the World ID `sub` (nullifier/subject) into a 32-byte `creatorId` (`0xa4b35b7ef915b074605a2a193e3355a99b9072047a20d98b2f6a048fbd504411` in our live Sepolia runs) and derive a deterministic `creatorWallet` using a server-only HMAC secret (`PARABLE_CREATOR_SECRET`).
2. **Enforced on-chain in `ParableVault.sol`:** The Sepolia vault enforces a strict 1-to-1 bidirectional mapping (`walletOfCreator[creatorId]` and `creatorOfWallet[creatorWallet]`). If the same World ID human ever tries to register a bot under a second wallet (`POST /api/cheat/second-identity`), the vault reverts on-chain with `CreatorIdentityMismatch()`.
3. **Human checkpoint per bot launch (Agent Pass):** A bot cannot spawn more bots on its own. Every `POST /api/launch` creates a server-issued `pending_id` and secret `claim` token (`x-claim`) that requires a fresh World ID authentication (`max_age=0`) before the engine issues an ENSv2 badge or calls `ParableVault.registerBot()`.

---

## 2. Full Journey Implemented (`engine/parable/world_pass.py` & `launcher.py`)

1. **Request (`POST /api/launch` → `GET /world/start?purpose=launch_bot&ref=<pending_id>`):**
   - Server registers `pending_id` and returns a secret `claim` token to the requester's browser (`x-claim` header). Unknown `ref` values are rejected immediately with `404` (preventing approval hijacking).
   - Generates a single-use `state`, `nonce`, and S256 PKCE `code_verifier` (10-minute TTL) and redirects to `https://auth.world.org/api/v1/authorize` with `scope=openid`, `response_type=code`, `code_challenge_method=S256`, and `max_age=0`.
2. **Completion & Server-Side Validation (`GET /world/callback`):**
   - Verifies `state` (single-use; replays rejected), checks the `iss` parameter against discovery (`https://auth.world.org`), and handles `error=access_denied` / cancellation.
   - Exchanges the authorization code server-side using `client_secret` and the PKCE `code_verifier` (no secrets ever touch the browser).
   - Verifies the returned ID token with `PyJWT`: RS256 signature against World's live JWKS (`https://auth.world.org/.well-known/jwks.json`), `iss`, `aud`, `exp`, `nonce`, and `auth_time` newer than the request start.
3. **Protected Action (`POST /api/launch/{pending_id}/confirm`):**
   - Requires the matching `x-claim` header (`hmac.compare_digest`).
   - **Approved path (`200 OK`):** Mints the bot's ENSv2 badge (`bot-1-bcc2.parable.eth`), registers the bot in `ParableVault` on Sepolia (`tx 0x2bb83c9fa0a060eee5a7559b678f6661b1961ad667431d5051f4b9dbe72822f8`), writes the birth record to Arkiv, and starts the bot loop.
   - **Denied / Expired / Cancelled path (`403 Forbidden`):** If the user denies the request in World ID (`access_denied`), the token check fails, or the 10-minute window expires, `Approval.approved` is `False`, `confirm_launch` raises `ApprovalDenied`, and **zero bots are registered in the vault or Arkiv**.

Tests: **22 unit tests** in `engine/tests/test_world_pass.py` + API integration tests in `engine/tests/test_api.py` covering approve, deny, replay, expiry, forged JWT signature, wrong nonce, wrong audience, wrong issuer, stale `auth_time`, `alg=none`, and approval-hijack prevention.

---

## 3. Integration Debrief (World Judging Criteria)

- **Time to first success:**
  - **~30 minutes** to build and test the OIDC + PKCE + PyJWT verifier against World's live `.well-known/openid-configuration` and JWKS endpoints.
  - **~20 minutes** to register the client in the World Developer Portal, expose our local FastAPI callback over a Cloudflare HTTPS tunnel (`/world/callback`), and complete our first real end-to-end human approval on Sepolia (`creator_id = 0xa4b35b7e...504411`, 4 bots launched).
- **Friction encountered:**
  1. **Docs navigation & SPA sandbox guide:** The landing `/docs` page is high-level; the concrete OIDC parameters are split across `/docs/guides/oidc`, `app-registration`, `step-up`, and `testing`, while `/docs/guides/sandbox` is a client-rendered SPA that initially showed only "Loading".
  2. **`client_secret_basic` vs `client_secret_post`:** The portal defaults to `client_secret_basic`, whereas the main code snippet shows `client_secret_post`. Supporting standard Basic auth in the token exchange avoided a 401 trap.
  3. **HTTPS callback requirement during local development:** Production portal clients require an HTTPS redirect URI (`https://.../world/callback`), which meant spinning up a `cloudflared` tunnel and updating the portal's Redirect URIs whenever the tunnel URL changed.
  4. **No native payload/action binding claim in OIDC:** Because `binding_message` is not included in the signed ID token claims, we bound each approval to a specific bot launch on our server via single-use `state` + `nonce` + browser `x-claim` HMAC verification.
- **Missing docs:**
  - A single copy-paste Python (FastAPI + `PyJWT` + `httpx`) reference implementation showing PKCE + JWKS verification + required claim checks (`iss`, `aud`, `exp`, `nonce`, `auth_time`) in one file.
  - Clearer guidance on how "World ID Agent Pass" maps to OIDC step-up (`max_age=0`) vs IDKit widget flows in the portal.
- **Top improvement request:**
  - **Signed per-action intent claim (`action_hash` / `request_context`):** Allow relying parties to pass an `action_hash` (e.g. `keccak256(botRules)`) into `/authorize` that is echoed inside the signed ID token (or ZK proof public inputs), so the smart contract or verifier can cryptographically prove *"this human approved THIS specific bot configuration at timestamp T"* rather than *"this human authenticated at timestamp T"*.
