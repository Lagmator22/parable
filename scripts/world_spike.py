"""World ID spike: run the real OIDC flow end to end against World.

Usage (from engine/):  uv run python ../scripts/world_spike.py
Needs WORLD_CLIENT_ID and WORLD_CLIENT_SECRET in the repo-root .env. Without them it
prints the portal setup steps and exits 0.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

PORT = int(os.environ.get("WORLD_SPIKE_PORT", "8000"))
REDIRECT = os.environ.get("WORLD_REDIRECT_URI", f"http://localhost:{PORT}/world/callback")

SETUP = f"""Missing: WORLD_CLIENT_ID and/or WORLD_CLIENT_SECRET (set WORLD_MOCK=1 to skip World entirely).

Manual steps (about 5 minutes):
  1. Open https://auth.world.org/portal and sign in with Google.
     (Sandbox instead: https://sandbox.auth.world.org portal, and set WORLD_ISSUER=https://sandbox.auth.world.org;
      a sandbox World ID needs the sandbox app and about 1 hour of issuance.)
  2. Register a client. Redirect URI, exact match: {REDIRECT}
     Client authentication: client_secret_basic (portal default).
  3. Copy the client ID and the secret (shown once, starts with worldidp_client_secret_).
  4. Put in the repo-root .env (never commit it):
       WORLD_CLIENT_ID=...
       WORLD_CLIENT_SECRET=...
       WORLD_MOCK=0
  5. Re-run this script, open the printed URL, authenticate with World ID.
Note: the portal may reject http:// callbacks for non-localhost hosts; use an https tunnel/deployment URL
and set WORLD_REDIRECT_URI to match if so.
"""


def main() -> int:
    if not (os.environ.get("WORLD_CLIENT_ID") and os.environ.get("WORLD_CLIENT_SECRET")):
        print(SETUP)
        return 0

    import uvicorn
    from fastapi import FastAPI

    from parable import world_pass

    os.environ["WORLD_MOCK"] = "0"
    app = FastAPI()
    app.include_router(world_pass.router)

    @app.get("/result/{pending_id}")
    def result(pending_id: str):
        ap = world_pass.get_approval(pending_id)
        return ap.model_dump() if ap else {"pending_id": pending_id, "approved": None}

    print(f"Open: http://localhost:{PORT}/world/start?purpose=launch_bot&ref=spike-1")
    print(f"Then check the validated result: http://localhost:{PORT}/result/spike-1")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
