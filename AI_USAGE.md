# AI usage log

ETHGlobal requires documenting where and how AI tools were used. Each entry: date/time (IST), tool, what it produced, what I changed.

| When (IST) | Tool | What AI did | What I did |
|---|---|---|---|
| 2026-11-06 01:2x | Claude Code | Created repo skeleton: README, this log, .gitignore; copied prep notes (AGENTS.md, JUDGING.md) | Reviewed |
| 2026-11-06 12:30–13:10 | Claude Code (Opus lead + 4 Sonnet builder agents) | Phase 1 drafts: ParableVault.sol + 25 Foundry tests, World Agent Pass OIDC router + 22 tests, Arkiv raw JSON-RPC store + 13 tests, ENSv2 badge module + EnsV2BadgeOracle.sol + 17 tests, spikes, notes | Lead reviewed: vault math checked by hand; fixed World callback `iss` check (would reject real logins); pinned httpx<1 / mcp<2 (prerelease leak); flagged Arkiv store for replacement with the official SDK and fail-closed writer filter |
