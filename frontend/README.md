# Parable frontend

This folder contains the website. It is a static React app that the Python engine can serve after a build.

From `~/ethglobal/parable/frontend`:

```sh
npm install
npm run dev
```

Open the printed local URL. To make the production files, run `npm run build`; they appear in `frontend/dist/`.

This first design pass includes the landing page, theme switch, and menu. The app sections are clearly marked placeholders and are not yet connected to the Python API. The API contract is in `../docs/FRONTEND_CONTRACT.md`.
