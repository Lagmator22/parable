# Parable frontend

The dashboard is a React app built with Vite. FastAPI serves the production bundle from `frontend/dist/`.

For local development, start the engine in one terminal from the repo root:

```bash
cd engine
PARABLE_OFFLINE=1 WORLD_MOCK=1 uv run uvicorn parable.api:app --port 8000
```

In another terminal from the repo root:

```bash
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite. The development server proxies API and approval requests to the local engine. Run `npm test` and `npm run build` from `frontend/` to test and build the site.
