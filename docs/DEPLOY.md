# Deploying Parable (Azure VM) and adding the MCP server

The live site runs on one Azure Ubuntu VM: **https://parable-demo.centralindia.cloudapp.azure.com**
- Caddy gives it HTTPS automatically.
- Two always-on services restart by themselves: the Arkiv helper (`parable-bridge`) and the engine (`parable-engine`).
- **Only one engine may run with the server wallet at a time.** Running bots live in its memory, and two copies would fight over transaction numbers. So when the VM is live, stop the laptop server.

Already done:
- the VM, its DNS name and its ports (80, 443, 22);
- Node, uv and Caddy installed;
- the code copied, the website built;
- the services and Caddy configured (`deploy/setup-vm.sh`, `deploy/install.sh`).

## The 4 steps left (about 5 minutes, Mac Terminal)
1. **Copy your secrets file to the VM.** It's the only copy of your keys; it never goes to GitHub.
   ```
   scp -i ~/Downloads/parable_key.pem ~/ethglobal/parable/.env parabel@104.211.91.120:~/parable/.env
   ```
2. **Start the services on the VM:**
   ```
   ssh -i ~/Downloads/parable_key.pem parabel@104.211.91.120 "sudo systemctl start parable-bridge parable-engine && sleep 8 && curl -s localhost:8000/api/info | head -c 200"
   ```
   You should see `{"offline":false,...}`. Then open https://parable-demo.centralindia.cloudapp.azure.com.
3. **Tell World ID about the new address.**
   - Open the World developer portal → your Parable app → **Manage** → redirect URLs.
   - Add `https://parable-demo.centralindia.cloudapp.azure.com/world/callback` → **Save**.
   - The VM already uses this address. "Demo · no phone" approval works without this step.
4. **Stop the laptop server**, so only the VM uses the wallet. In the Warp tab running uvicorn, press **Ctrl+C**. The tunnel tab can be closed too.

## Everyday commands
- Logs: `ssh -i ~/Downloads/parable_key.pem parabel@104.211.91.120 "journalctl -u parable-engine -n 50 --no-pager"`
- Restart: `... "sudo systemctl restart parable-engine"` (running bots simply expire; their records are repaired from the vault)
- Update after a change: copy the code again (the `rsync` in the handoff), then `bash ~/parable/deploy/install.sh parable-demo.centralindia.cloudapp.azure.com` on the VM.

## MCP: let Claude Code use Parable
In any folder on the Mac:
```
claude mcp add parable -e PARABLE_URL=https://parable-demo.centralindia.cloudapp.azure.com -- uv --directory /Users/lagmator22/ethglobal/parable/engine run python -m parable.mcp_server
```
Then open `claude` and ask in plain words, for example:
- "Use parable: show me the status and the graveyard."
- "Use parable: try to cheat with a second identity and show the vault's answer."
- "Use parable: launch a yolo bot with jev:deepseek-v4.1-flash for 10 minutes, approval demo." Then open the approve link it gives you and say "confirm the launch".

There are 14 tools: status, list_brains, launch_bot, confirm_launch, running_bots, bot_history, graveyard, compare_brains, try_to_cheat, stop_bot, start_swarm, confirm_swarm, swarm_status, telemetry. They were tested live 3 times in a row against the running server: 30 of 30 calls OK.
