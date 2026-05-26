# VoiceDev Landing Page

Marketing site for VoiceDev — deploy to Vercel from the `landing/` directory.

## Local development

```bash
cd landing
npm install
npm run dev
```

Open http://localhost:5173

## Build

```bash
npm run build
npm run preview
```

## Deploy to Vercel

1. Push this repo to GitHub.
2. Import the project at [vercel.com/new](https://vercel.com/new).
3. Set **Root Directory** to `landing`.
4. Framework preset: **Vite** (or use repo root `vercel.json`).
5. Deploy.

The download button serves `/downloads/VoiceDev-v0.3.0.zip` from `public/downloads/`.

To use a GitHub Release instead, update `DOWNLOAD_URL` in `src/App.jsx` to your release asset URL.

## Update the zip

Replace `public/downloads/VoiceDev-v0.3.0.zip` when you ship a new version, then redeploy.
