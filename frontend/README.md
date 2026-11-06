# Parable frontend

This folder contains the website. It is a static React app that the Python engine can serve after a build.

From `~/ethglobal/parable/frontend`:

```sh
npm install
npm run dev
```

Open the printed local URL. To make the production files, run `npm run build`; they appear in `frontend/dist/`.

This design pass includes the landing page, theme switch, and menu. The application views are not yet connected to the Python API. The API contract is in `../docs/FRONTEND_CONTRACT.md`.

The existing bot launch page is served by the Python engine at `/classic`. When the engine is running on port 8000, open `http://127.0.0.1:8000/classic`. The landing page links to it using the relative path `/classic`. Vite also proxies that path during development.
