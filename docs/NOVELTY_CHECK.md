# Parable novelty check (2026-11-06)

**Sources checked:**
- All 4,282 ETHGlobal prize winners, 2023–2026 (full write-ups). Data is in `winners.txt`.
- Web searches for products, protocols, forums and papers.

**Limit:** the ETHGlobal showcase search can't be queried by script, so the ~20k non-winning ETHGlobal projects were **not** checked. Not finding something doesn't prove it hasn't been built.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Agent identity + spending limits/rules stored in ENS and enforced on-chain | ❌ **Done, several times, and it won** | **allowance.eth** (NY26, ENS): rules in an ENS text record, enforced by PolicyGuard.sol. **Capsule** (ETHOnline26, ENS runner-up): "AI agents as ENS names with onchain permissions, spending limits, and recall". **Steg / ENS-bound agent auth** (NY26, ENS 3rd). **MoltQore** (HackMoney26, ENS): AI trading agents with decisions in ENS records. Web: Agent Vault, HumanSign, SBO3L. |
| 2 | Expiring, non-transferable, revocable ENS "badge" per bot plus a binding kill switch | ❌ **Done** | **Batas** (ETHOnline26, **ENS 2nd**): "the agent's authority is an ENSv2 subname: expiring… revocable (grantor keeps ROLE_UNREGISTER)… soulbound (ROLE_CAN_TRANSFER_ADMIN withheld)". The registry is read during settlement, so revoking reverts every swap. Grants and revocations are logged to Hedera HCS, with ERC-8004 reputation. |
| 3 | Auto-revoke when losses pass a limit | ⚠️ **Common risk pattern; weak novelty** | Drawdown kill switches are standard trading risk tooling (vendor guides use triggers like an 8% drawdown). OniBlock: an AI "loses power if it's wrong". No winner was found doing on-chain auto-revoke on profit-and-loss via ENS, but on its own it's a feature, not a headline. |
| 4 | Public, verifiable track records and leaderboards for AI trading agents | ❌ **Done** | **nof1 Alpha Arena** (live real-money LLM trading, public leaderboard and reasoning traces, raised $15M). **Recall Network** (on-chain agent trading competitions, Recall Rank reputation, 1,000+ teams). **ViperX** (on-chain AI trading leaderboard). ETHGlobal: **KOLlateral** (0G-verified track record, finalist), honeybee, AgentRank, AgentRankr. |
| 5 | **A complete track record that counts every run and can't hide losers, tied to a unique human creator** | ✅ **Not found** | No winner and no web result combines: (a) every bot registered *before* it can trade; (b) all runs counted, including killed and failed ones; (c) the creator bound to a unique human, so they can't start fresh identities to bury failed strategies. Research confirms this is the known open problem: an append-only log stops deletion but not *selective registration*, and survivorship bias "at the join boundary" is a fundamental limit of voluntary registries. |

## What this means
- Claims 1–4 are **prior art**. Credit them in a README "Prior art" section: allowance.eth, Batas, Capsule, Steg, MoltQore, Alpha Arena, Recall.
- **The defensible novelty is #5: closing the join boundary.**
  - **Registration is mandatory, not voluntary.** The guard contract refuses any trade from a bot that wasn't registered (ENS badge plus an Arkiv record) *before* its first trade, so no bot that trades through Parable can avoid being counted.
  - **The creator is a unique human (World ID).** One person gets one creator namespace, so they can't spin up new names to hide failed strategies.
  - **Every outcome is written automatically**, including deaths, kills and auto-revokes. The report card is computed from the full list.
- **Honest limit to state in the README:** bots traded *outside* Parable aren't covered. The claim is "complete for everything that trades through Parable's guard".
- This puts **World** at the centre of the novel claim. You still only get 3 partner picks: decide among ENS / Arkiv / World / 0G.

## Sources
- Batas, Capsule, Herit, Verdict.eth: ENS winners at ETHOnline 2026 (`winners.txt`); [ENS thread on ETHOnline winners](https://x.com/ensdomains/status/2100279163584409985)
- [allowance.eth](https://ethglobal.com/showcase/allowance-eth-ejosk), [Agent Vault](https://ethglobal.com/showcase/agent-vault-ngc1n), [HumanSign](https://ethglobal.com/showcase/humansign-ad6j1), [SBO3L forum post](https://discuss.ens.domains/t/sbo3l-mandate-based-policy-boundary-for-autonomous-agents/22103)
- [Recall: Messari report](https://messari.io/report/recall-onchain-ai-and-intelligence-competitions), [Recall: decentralised.co](https://www.decentralised.co/p/too-many-ais-too-little-trust), [ViperX](https://www.viperx.site/)
- [Alpha Arena explained](https://www.datawallet.com/crypto/alpha-arena-nof1-ai-explained), [Nof1 raises $15M](https://aiweekly.co/alerts/nof1-raises-15m-to-run-ai-models-in-live-trading)
- [Survivorship bias in trader rankings (NakedPnL)](https://www.nakedpnl.com/guides/survivorship-bias-trader-rankings), [arXiv 2608.27734](https://arxiv.org/pdf/2608.27734), [How to spot fake track records](https://goldenviperea.com/blog/guides/spot-fake-trading-track-records)
- [Agent spend caps and kill switch](https://www.orcarouter.ai/blog/ai-agent-spend-caps-kill-switch), [Agent wallet security 2026](https://agentbets.ai/guides/agent-wallet-security/)

## Update: second review (sister's research), checked 2026-11-06

| Project | What it does | Overlap with Parable | Status |
|---|---|---|---|
| **ENSign** (Open Agents 2026, **ENS 1st**) [repo](https://github.com/LeoFranklin015/ENSign) | Agents as sub-subnames (`trader.leo.ensign.eth`), each scoped to a contract, a daily spend limit and an expiry. Revoke by name; burning the parent kills every agent under it. | Per-bot badge, limits, expiry, revoke are **done** | Verified in winners data |
| **ActionFeed** (Open Agents 2026) [repo](https://github.com/dolepee/actionfeed) | Public signed action ledger per agent (0G Storage + ENS subnames). **V2 Authority Gate:** reads an agent's signed history and grants a bounded mandate only if the record passes; refuses over-budget actions and logs the refusals. | "Gate based on public history" is **done**. The difference: the agent appends its *own* events (self-reported), while Parable's records are written by the custody vault/guard, not the bot. | Read the README |
| **Immunity** (NY26, ENS + Chainlink + Finalist) | Agent security network; reputation stored in ENS | Security and reputation, not track records | Verified |
| **ClawGuard** (HackMoney26, ENS) | Transaction guard; manifest hash stored as an ENS record | Fingerprinting for skills, not bots | Verified |
| Namesake, ENS-AR, GhostPass | ENS subnames and identity for agents | Identity only | Not among winners |
| **8004scan** / **ERC-8004** | Agent identity, reputation and validation registries plus explorer and leaderboards | Leaderboards rank *surviving* agents, with no mandatory death log or cohort stats (per sister). The Validation Registry (code hashes, TEE) is still being revised. | Web |

**Combined verdict (my search + sister's):** every single feature exists somewhere. The defensible novelty is the **combination**, with the record written by the money-holder rather than the bot:
1. **Gate before trading:** a bot can't trade until it's registered.
2. **Leased identity that is returned at the end, with the death logged** (batch lifecycle).
3. **Cohort report card that includes failures** (per creator and per strategy).
4. **Auto-revoke on loss, measured by the vault**, not reported by the bot.
5. **Rebirths linked:** one World ID creator, plus an optional code fingerprint for lineage.

**Hard but most defensible piece (sister's point 12): trustworthy loss measurement.**
- Funds sit in a **custody vault** that the bot can only trade through.
- Equity is computed against a **high-water mark** using an independent price (Chainlink ETH/USD feed on Sepolia).
- **Anyone** can call `revoke(bot)`; the contract re-checks the maths on-chain and pays a small bounty. No trusted watcher is needed.
- **Limits to state openly:** price manipulation; realized vs unrealized loss (we use mark-to-market equity); off-chain/CEX trading is out of scope; rebirth under a new name is handled by World ID creator binding.
