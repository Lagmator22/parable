# Vercel deployment plan

Parable's React site is static, but the Python engine runs bot loops, launch approvals, and background record sync. Deploy the `frontend/` directory to Vercel and keep the engine on a host with a stable public HTTPS address. Vercel is optional for ETHGlobal; the submitted link must open the working app.

## First deployment

1. In Vercel, import the GitHub repository `Lagmator22/parable`.
2. Set **Root Directory** to `frontend`, **Framework Preset** to Vite, **Build Command** to `npm run build`, and **Output Directory** to `dist`.
3. Deploy the site. It will render immediately, but API features need the backend routing below.

## Connect the Python engine

1. Give the engine a stable HTTPS URL. A named Cloudflare Tunnel or a process host works. A quick `trycloudflare.com` tunnel changes address when restarted and is unsuitable for the final link.
2. Add `frontend/vercel.json`, replacing `BACKEND.example.com` with the actual engine hostname:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://BACKEND.example.com/api/:path*" },
    { "source": "/world/:path*", "destination": "https://BACKEND.example.com/world/:path*" }
  ]
}
```

3. Set the engine's `WORLD_REDIRECT_URI` to `https://YOUR-VERCEL-DOMAIN/world/callback`, and register that exact callback with World if using its real approval flow. The mock flow works without that registration.
4. Redeploy Vercel. From a phone or private window, check `/api/info`, the World approval page, launch, live bots, graveyard, and transaction links through the Vercel domain.

The frontend uses relative `/api` and `/world` paths, so this proxy keeps the browser on one origin. Do not put private keys or backend secrets in Vercel's frontend settings. Keep `AI_USAGE.md` and the incremental Git history in the public repository for the hackathon submission.
