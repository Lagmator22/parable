# Parable frontend

This folder contains the website. It is a static React app that the Python engine can serve after a build.

From `~/ethglobal/parable/frontend`:

```sh
npm install
npm run dev
```

Open the printed local URL. To make the production files, run `npm run build`; they appear in `frontend/dist/`.

The React page includes the landing, theme switch, and one shared menu for Launch, Live bots, Graveyard, Compare brains, and Try to cheat. All sections use relative API routes described in `../docs/FRONTEND_CONTRACT.md`.

The main experience is served at `/` after `npm run build`. The backend's older page remains at `/classic` as a fallback, but the React menu and launch button stay on `/`.
