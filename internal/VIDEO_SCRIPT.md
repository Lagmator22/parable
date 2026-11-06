# Parable demo video (target 3:30, hard max 4:00)

Record in your own voice, screen at 1440×900 or bigger, browser zoom 100%, light theme.
**Before recording (15 minutes ahead):**
1. Open the live site (Azure link) and press Cmd+Shift+R.
2. Start a swarm: mind **Gemini 3.5 Flash-Lite**, workers **Jev · DeepSeek ×1, Gemini 3.5 Flash-Lite ×1, Simple rule ×1**, **30 minutes**, approve with **Demo · no phone** (or World ID).
3. Launch one solo bot: **yolo · Jev · Gemma 4 31B · 30 minutes**.
4. Open a terminal with Claude Code where the Parable MCP server is added (see docs/DEPLOY.md, "MCP").
So when you hit record, bots are already trading, the mind has made decisions, and the charts have lines.

| Time | Show (click) | Say (plain, slow) |
|---|---|---|
| 0:00–0:20 | Top of the page: the headline, Born / Dead counters | "Everyone selling a trading bot shows you the winners. Nobody shows you the bots that blew up. Parable is a place where AI trading bots can't hide their failures." |
| 0:20–0:40 | Point at the 4 facts under the headline | "The trick: bots never hold the money and never write their own history. A vault contract on Sepolia holds the money and keeps the score. Every bot needs a World ID-approved human, an ENS name, and everything it does goes to Arkiv, a public database." |
| 0:40–1:15 | 01 Launch: click the brain word, pick Jev · DeepSeek; click Approve (World ID scan on your phone if you can, else Demo) | "Launching is one sentence. I pick the brain, the money, the limits. I approve with World ID: one real person. Watch the six real steps: its own wallet, fee money, its ENS name, the vault registers it, Arkiv writes its birth." |
| 1:15–1:40 | 02 Running: the solo bot card, its history; click one `tx` link (Etherscan opens) | "Here's a running bot. Every trade is a real Sepolia transaction. This one is Jev: it shows its odds, buy 87 percent, and sizes the trade by how sure it is. The vault still caps it." |
| 1:40–2:10 | 04 Try to hide a loser: press all three buttons; click "copy the command" once | "Now I try to cheat. A wallet that never registered tries to trade: refused, NotBot. A bot asks for ten times its limit: refused. The same person tries a fresh wallet to escape their graveyard: refused. These answers come from the real contract. Copy this command and you'll get the same error code yourself." |
| 2:10–2:35 | 03 Register: the struck-through rows, Trades column, click one "Arkiv" link | "And when bots die, they land here. Time ran out, stopped by the creator, or lost too much. Nobody can delete a row: each one is a read-only record on Arkiv. And the vault's own count matches this list, so nothing is missing." |
| 2:35–3:00 | 05 Swarm: the running workers and the decision log | "Swarms: one mind model watches many workers and decides who keeps trading. Here Gemini stopped a worker and said why. It has no special powers. The vault still checks everything, and what it stops stays public." |
| 3:00–3:20 | Click Telemetry (top bar): numbers, the three charts, "Check it yourself" | "Telemetry: every number live, and every one links to Etherscan, Arkiv or ENS. You don't have to trust our server." |
| 3:20–3:40 | Switch to the terminal: in Claude Code ask "use parable: show me the graveyard and try to cheat with a second identity" | "And AI agents can use Parable directly. This is Claude Code calling our MCP server: same vault, same record." |
| 3:40–3:55 | Back to the top of the page | "Parable: ENS names, an Arkiv register, one human per creator with World. Next, the vault trades on a real exchange like Uniswap, with the same guarantees. Every strategy has a graveyard. Now you can see it." |

## Honest lines to keep (judges like these)
- "This is the Sepolia test network with practice money."
- "Returns are flat because the vault scores at the Chainlink price, which barely moves on testnet. Every trade is still real and linked."
- If you used Demo approval: "I used demo approval so I don't need my phone on camera; those bots are marked demo on the register."

## If something goes wrong while recording
- A launch is slow: keep talking over the 6 steps, it takes about a minute.
- A brain answer is slow: Jev answers in about 1.5 s; Gemini can take 7 s.
- Page looks stale: Cmd+Shift+R.
