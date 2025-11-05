import express from 'express';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const projectRoot = path.resolve(__dirname, '..', '..');
const frontendRoot = path.resolve(__dirname, '..');
const distDir = path.resolve(frontendRoot, 'dist');
const datasetRoot = process.env.DATASET_ROOT
  ? path.resolve(projectRoot, process.env.DATASET_ROOT)
  : path.resolve(projectRoot, 'dataset');

const CLUSTER_FILENAME = 'arxiv_clustering_results.json';

const isDateDirectory = (entry) => entry.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(entry.name);

const listDateDirectories = () => {
  if (!fs.existsSync(datasetRoot)) {
    return [];
  }
  return fs
    .readdirSync(datasetRoot, { withFileTypes: true })
    .filter(isDateDirectory)
    .map((dirent) => dirent.name)
    .sort((a, b) => b.localeCompare(a));
};

const loadClusteringResults = (date) => {
  const targetFile = path.join(datasetRoot, date, CLUSTER_FILENAME);
  if (!fs.existsSync(targetFile)) {
    return null;
  }
  const raw = fs.readFileSync(targetFile, 'utf-8');
  return JSON.parse(raw);
};

const app = express();

app.get('/api/dates', (_req, res) => {
  res.json({ dates: listDateDirectories() });
});

app.get('/api/clusters', (req, res) => {
  const { date } = req.query;
  if (!date || typeof date !== 'string') {
    res.status(400).json({ error: 'Missing date parameter' });
    return;
  }

  const payload = loadClusteringResults(date);
  if (!payload) {
    res.status(404).json({ error: `No clustering results for ${date}` });
    return;
  }

  res.json({ date, payload });
});

if (fs.existsSync(distDir)) {
  app.use(express.static(distDir));
  app.get('*', (_req, res) => {
    res.sendFile(path.join(distDir, 'index.html'));
  });
} else {
  app.get('*', (_req, res) => {
    res.status(404).send('Build assets not found. Run `npm run build` first.');
  });
}

const port = process.env.PORT ? Number(process.env.PORT) : 4173;

app.listen(port, () => {
  console.log(`Visualization server running on http://localhost:${port}`);
});
