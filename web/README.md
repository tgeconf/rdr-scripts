# ArXiv Cluster Explorer Frontend

An interactive React + Three.js experience for exploring daily arXiv clustering results in 3D.

## Getting Started

From the `frontend` directory:

```bash
npm install
npm run dev
```

The development server exposes two API endpoints (`/api/dates` and `/api/clusters?date=YYYY-MM-DD`) that stream data directly from the repository’s `dataset/<date>/arxiv_clustering_results.json` files. Pass a custom dataset location by exporting `DATASET_ROOT` (relative or absolute path).

```bash
DATASET_ROOT=../custom-dataset npm run dev
```

## Production Build

```bash
npm run build
npm run serve
```

`npm run serve` launches an Express server that serves the static bundle from `frontend/dist` and exposes the same dataset APIs for visualization. Set `PORT` or `DATASET_ROOT` if needed.

## Key Features

- 3D galaxy of papers rendered with Three.js (`@react-three/fiber` + post-processing bloom).
- Color-coded, translucent nodes per cluster with orbit controls and cinematic black backdrop.
- Hover tooltips, anchored labels, and click-to-pin interactions for quick comparisons.
- Floating insight panels with snapshot stats, cluster breakdowns, and pinned-paper digests.
- Automatic detection of the latest dataset date plus manual switching between snapshots.
