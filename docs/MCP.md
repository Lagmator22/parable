# Use Parable from an MCP client

The Parable MCP server exposes the same public records and launch flow as the dashboard. Read status, compare models, inspect a bot's history or request a launch. A human still approves each launch in the browser.

Codex and Claude Code use their own assistant models. The bot's model is selected separately from `list_brains`, which reports what the Parable engine offers for solo and swarm launches.

Clone this repo and install `uv`. From the repo root, start the server over standard input and output:

```bash
PARABLE_URL=https://parable-demo.centralindia.cloudapp.azure.com \
  uv --directory engine run python -m parable.mcp_server
```

From the repo root, register Parable with Codex or Claude Code:

```bash
codex mcp add parable --env PARABLE_URL=https://parable-demo.centralindia.cloudapp.azure.com \
  -- uv --directory "$PWD/engine" run python -m parable.mcp_server

claude mcp add parable -e PARABLE_URL=https://parable-demo.centralindia.cloudapp.azure.com \
  -- uv --directory "$PWD/engine" run python -m parable.mcp_server
```

Open a fresh client session after adding the server.

Try `status`, `graveyard` or `bot_history` first. To launch, call `launch_bot`, open its approval link and then call `confirm_launch` with the pending ID and claim. Keep the returned claim and owner token private. The owner token authorizes `stop_bot`. See the [14 tool definitions](../engine/parable/mcp_server.py).
