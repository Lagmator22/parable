# AI usage log

ETHGlobal requires documenting where and how AI tools were used. Each entry: date/time (IST), tool, what it produced, what I changed.

| When (IST) | Tool | What AI did | What I did |
|---|---|---|---|
| 2026-11-06 01:2x | Claude Code | Created repo skeleton: README, this log, .gitignore; copied prep notes (AGENTS.md, JUDGING.md) | Reviewed |
| 2026-11-06 12:30–13:10 | Claude Code (Opus lead + 4 Sonnet builder agents) | Phase 1 drafts: ParableVault.sol + 25 Foundry tests, World Agent Pass OIDC router + 22 tests, Arkiv raw JSON-RPC store + 13 tests, ENSv2 badge module + EnsV2BadgeOracle.sol + 17 tests, spikes, notes | Lead reviewed: vault math checked by hand; fixed World callback `iss` check (would reject real logins); pinned httpx<1 / mcp<2 (prerelease leak); flagged Arkiv store for replacement with the official SDK and fail-closed writer filter |
| 2026-11-06 13:15–13:45 | Claude Code (Opus lead + 4 Sonnet builders) | Phase 2: arkiv-bridge (official @arkiv-network/sdk), thin Arkiv client, vault.py, bot_runner.py, launcher.py, api.py, dashboard, fake_chain offline mode, ENS trim, Deploy order, oracle tests | Lead fixed 4 interface mismatches and 2 security holes (approval hijack, guessable creator wallet key), removed unused arkiv-sdk dep, ran offline end-to-end smoke test |
