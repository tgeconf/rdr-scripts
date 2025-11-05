# ArXiv Cluster Explorer Frontend

An interactive React + Three.js experience for exploring daily arXiv clustering results in 3D.

## Getting Started

From the `web` directory:

```bash
npm install
npm run export:data   # copies dataset/YYYY-MM-DD into public/data
npm run dev
```

`npm run export:data` reads `../dataset/<date>/arxiv_clustering_results.json`, copies each snapshot to `public/data/<date>/`, and rebuilds `public/data/index.json`. Re-run this script whenever the dataset changes (before `npm run dev` or `npm run build`).

## Production Build

```bash
npm run build
npm run preview
```

The production bundle is fully static; it serves JSON directly from `dist/data/…`, which makes it suitable for GitHub Pages or any static host. Configure the base path via `VITE_BASE_URL` (defaults to `/`).

## GitHub Pages Workflow

The repository contains `.github/workflows/deploy.yml`, which:

1. Checks out the repo and installs dependencies.
2. Runs `npm run export:data` to refresh `public/data`.
3. Builds the static site with an auto-detected `VITE_BASE_URL`.
4. Publishes `web/dist` to GitHub Pages.

Push changes to `web/**` or `dataset/**` on `main`/`master` to trigger a redeploy.

## Key Features

- 3D galaxy of papers rendered with Three.js (`@react-three/fiber`) plus cinematic bloom.
- Color-coded nodes per cluster with automatic orbit, hover tooltips, and click-to-select clustering.
- Floating insight panels with snapshot stats, cluster legends, cluster insights, and multi-cluster paper lists.
- Daily snapshot switching driven by static JSON (`public/data/index.json`).
