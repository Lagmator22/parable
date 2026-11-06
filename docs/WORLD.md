# World ID launch approval

Parable uses World ID to require human approval before the engine launches a bot or swarm. A wallet signature alone would let a creator switch wallets. The engine derives a stable creator ID from the verified World subject, and the vault enforces a one-to-one mapping between that creator ID and its wallet. The engine verifies the credential through World ID OIDC and sends the resulting identity to the vault.

## Approval flow

1. **Request.** The engine creates a pending launch and gives the requesting browser a claim token. It starts World authentication with a single-use state, a nonce, PKCE and fresh authentication.
2. **Validate.** The callback exchanges the code server-side. The engine verifies the signed ID token, issuer, audience, expiry, nonce and authentication time.
3. **Confirm.** The engine checks the original claim and approved pending request before it issues an ENS badge and registers the bot. Denied, expired or replayed approvals cannot authorize registration.

On 6 November 2026, a real World approval was exercised through an HTTPS tunnel and followed by [Sepolia bot registration](https://sepolia.etherscan.io/tx/0x2bb83c9fa0a060eee5a7559b678f6661b1961ad667431d5051f4b9dbe72822f8). Denial, expiry, replay, token validation and claim handling are covered by [World ID tests](../engine/tests/test_world_pass.py) and [API tests](../engine/tests/test_api.py). The live dashboard's phone-free demo option is labeled on its records and bypasses World verification.

## Integration debrief

| Topic | Experience |
|---|---|
| Time to first success | About 30 minutes for the verifier, then 20 minutes to register the portal client, configure an HTTPS callback and complete a real approval. |
| Main friction | Token exchange examples and the portal default used different client authentication modes. Local testing also required an HTTPS callback and a matching redirect URI. |
| Missing example | One Python reference for the authorization request, PKCE exchange, JWKS verification and freshness checks. |
| Requested improvement | A signed intent hash in the ID token so a verifier can check the approved bot configuration directly. Today, Parable binds the pending action on its server using state, nonce and the claim token. |

[World integration code](../engine/parable/world_pass.py)  /  [Launch orchestration](../engine/parable/launcher.py)
