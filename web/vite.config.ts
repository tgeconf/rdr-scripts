import react from '@vitejs/plugin-react';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');
const datasetRoot = process.env.DATASET_ROOT
  ? path.resolve(repoRoot, process.env.DATASET_ROOT)
  : path.resolve(repoRoot, 'dataset');

const CLUSTER_FILENAME = 'arxiv_clustering_results.json';

type DateDir = {
  name: string;
  fullPath: string;
};

const isDateDirectory = (entry: fs.Dirent) =>
  entry.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(entry.name);

const listDateDirectories = (): DateDir[] => {
  if (!fs.existsSync(datasetRoot)) {
    return [];
  }
  return fs
    .readdirSync(datasetRoot, { withFileTypes: true })
    .filter(isDateDirectory)
    .map((dirent) => ({
      name: dirent.name,
      fullPath: path.join(datasetRoot, dirent.name)
    }))
    .sort((a, b) => b.name.localeCompare(a.name));
};

const loadClusteringResults = (date: string) => {
  const targetDir = path.join(datasetRoot, date);
  const targetFile = path.join(targetDir, CLUSTER_FILENAME);

  if (!fs.existsSync(targetFile)) {
    return null;
  }

  const raw = fs.readFileSync(targetFile, 'utf-8');
  return JSON.parse(raw);
};

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'dataset-api',
      configureServer(server) {
        server.middlewares.use('/api/dates', (req, res) => {
          const dates = listDateDirectories().map((dir) => dir.name);
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ dates }));
        });

        server.middlewares.use('/api/clusters', (req, res) => {
          const parsed = new URL(req.url ?? '', 'http://localhost');
          const date = parsed.searchParams.get('date');
          if (!date) {
            res.statusCode = 400;
            res.end(JSON.stringify({ error: 'Missing date parameter' }));
            return;
          }

          const payload = loadClusteringResults(date);
          if (!payload) {
            res.statusCode = 404;
            res.end(JSON.stringify({ error: `No clustering results for ${date}` }));
            return;
          }

          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ date, payload }));
        });
      }
    }
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    port: 5173,
    host: '0.0.0.0'
  }
});
